# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Sweep recording duration and accumulation interval; plot cross-color correlation.

Decodes each recording once per accumulation interval, snapshots the averaged
activity frame at every duration cutoff, and runs the standard filtered
pipeline (crop, high-pass, support-masked Pearson) at each combination. The
plotted value is the mean Pearson r over the recording pairs whose labels
differ (all pairs here, since each color was recorded once).

``--polarity signed`` accumulates ON minus OFF events per pixel, matching the
binned event frame of Shah et al. (CVPR 2024) that approximates the change in
log intensity; ``both`` (default) folds both polarities into one count.

Each combination also reports a split-half noise ceiling: windows are dealt
into ``--splits`` interleaved replicates, every replicate is correlated with
every other within a recording (Spearman-Brown corrected to the full duration)
to estimate how reliably a single recording reproduces its own pattern, and
cross-color replicates give a standard error and Student-t significance for
each pair. ``fraction_of_ceiling`` divides the measured cross-color r by that
ceiling, so values near 1 mean the shared pattern is as reproducible as the
recordings themselves.
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .spectral_correlation import (
    discover_recordings,
    high_pass,
    load_openevt,
    pearson_matrix,
    positive_int,
    signal_window,
    transform_frames,
)

DEFAULT_DURATIONS_S = (
    0.001, 0.002, 0.004, 0.006, 0.008, 0.010, 0.012, 0.014, 0.016, 0.018,
    0.020, 0.022, 0.025, 0.035, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0,
)
DEFAULT_ACCUMULATIONS_MS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100)
CROP_MARGIN_PX = 48
HIGH_PASS_PX = 64
THRESHOLD = 0.8
HIGHLIGHT_DURATION_S = 0.016
ALPHA = 0.05


def parse_float_list(text: str) -> tuple[float, ...]:
    values = tuple(sorted(float(item) for item in text.split(",")))
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("must be comma-separated positive numbers")
    return values


def window_count(duration_s: float, accumulation_ms: float) -> int:
    """Number of accumulation windows that start before the duration cutoff."""
    return -(-int(round(duration_s * 1_000_000)) // int(round(accumulation_ms * 1_000)))


def t_critical(replicates: int) -> float:
    """Two-sided 95% Student-t threshold for df = replicates - 1."""
    return stats.t.ppf(1 - ALPHA / 2, replicates - 1)


def replicate_count(windows: int, requested: int) -> int:
    """Replicates actually used: at least 4 windows each, none below 8 windows."""
    if windows < 8:
        return 0
    return max(2, min(requested, windows // 4))


def window_terms(
    events: np.ndarray, width: int, polarity: str, transform: str
) -> tuple[np.ndarray, np.ndarray] | None:
    """Sparse per-pixel transformed values for one accumulation window."""
    if polarity == "on":
        events = events[events["p"] != 0]
    elif polarity == "off":
        events = events[events["p"] == 0]
    if not events.size:
        return None
    indices = events["y"].astype(np.int64) * width + events["x"].astype(np.int64)
    if polarity == "signed":
        on = events["p"] != 0
        unique, inverse = np.unique(indices, return_inverse=True)
        positive = np.bincount(inverse[on], minlength=unique.size).astype(np.float64)
        negative = np.bincount(inverse[~on], minlength=unique.size).astype(np.float64)
        values = transform_frames(positive - negative, transform)
    else:
        unique, counts = np.unique(indices, return_counts=True)
        values = transform_frames(counts.astype(np.float64), transform)
    return unique, values


class RecordingStream:
    """Incrementally accumulate a recording toward increasing duration cutoffs.

    The total average pools every window pulled so far; each of ``splits``
    interleaved replicates pools the windows whose index satisfies
    ``index % splits == k``, so every replicate spans the full cutoff interval
    and the replicates differ only by which windows they received.
    """

    def __init__(
        self,
        openevt: object,
        path: Path,
        accumulation_us: int,
        transform: str,
        polarity: str = "both",
        splits: int = 0,
    ) -> None:
        reader = openevt.RawFileReader(str(path))
        self._iterator = reader.iter()
        self._height, self._width = (int(value) for value in self._iterator.shape())
        self._pixel_count = self._height * self._width
        self._accumulation_us = accumulation_us
        self._transform = transform
        self._polarity = polarity
        self._splits = splits
        self._frame_sum = np.zeros(self._pixel_count, dtype=np.float64)
        self._split_sums = [
            np.zeros(self._pixel_count, dtype=np.float64) for _ in range(splits)
        ]
        self._frame_count = 0
        self._exhausted = False

    @property
    def shape(self) -> tuple[int, int]:
        return self._height, self._width

    @property
    def exhausted(self) -> bool:
        return self._exhausted

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def _pull_window(self) -> bool:
        try:
            events = self._iterator.next_delta(self._accumulation_us)
        except StopIteration:
            self._exhausted = True
            return False
        except OSError as error:
            if "end of file" in str(error).lower() or str(error).lower() == "eof":
                self._exhausted = True
                return False
            raise
        index = self._frame_count
        self._frame_count += 1
        terms = window_terms(events, self._width, self._polarity, self._transform)
        if terms is not None:
            unique, values = terms
            self._frame_sum[unique] += values
            if self._splits:
                self._split_sums[index % self._splits][unique] += values
        return True

    def advance_to(self, cutoff_us: int) -> None:
        """Pull every window that starts before ``cutoff_us``."""
        while not self._exhausted and self._frame_count * self._accumulation_us < cutoff_us:
            if not self._pull_window():
                break

    def average(self) -> np.ndarray:
        return (self._frame_sum / max(self._frame_count, 1)).reshape(self.shape)

    def split_average(self, index: int) -> np.ndarray:
        count = self._frame_count // self._splits + (index < self._frame_count % self._splits)
        return (self._split_sums[index] / max(count, 1)).reshape(self.shape)


def build_snapshots(
    openevt: object,
    path: Path,
    accumulation_us: int,
    cutoffs_us: Sequence[int],
    transform: str,
    polarity: str = "both",
) -> dict[int, np.ndarray]:
    """Decode once, returning the averaged activity frame at each duration cutoff.

    Window ``i`` covers ``[i * accumulation_us, (i + 1) * accumulation_us)``;
    a cutoff keeps every window that starts before it.
    """
    stream = RecordingStream(openevt, path, accumulation_us, transform, polarity)
    snapshots: dict[int, np.ndarray] = {}
    for cutoff in cutoffs_us:
        stream.advance_to(cutoff)
        snapshots[cutoff] = stream.average()
    return snapshots


def pair_pearson(
    first: np.ndarray, second: np.ndarray, support_first: np.ndarray, support_second: np.ndarray
) -> float:
    """Support-masked Pearson r that yields NaN instead of failing."""
    mask = support_first | support_second
    a = first[mask].astype(np.float64)
    b = second[mask].astype(np.float64)
    if a.size < 2 or a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.clip(np.corrcoef(a, b)[0, 1], -1.0, 1.0))


def replicate_statistics(values: Sequence[float]) -> tuple[float, float, float, bool]:
    """Mean, standard error, Student-t, and 95% significance across replicates."""
    array = np.asarray([value for value in values if not np.isnan(value)], dtype=np.float64)
    if array.size == 0:
        return np.nan, np.nan, np.nan, False
    mean = float(array.mean())
    if array.size < 2:
        return mean, np.nan, np.nan, False
    sem = float(stats.sem(array))
    if sem == 0.0:
        statistic = np.inf if mean != 0.0 else 0.0
        p_value = 0.0 if mean != 0.0 else 1.0
    else:
        statistic = mean / sem
        p_value = 2 * stats.t.sf(abs(statistic), array.size - 1)
    return mean, sem, float(statistic), bool(p_value < ALPHA)


def filtered_stack(frames: np.ndarray) -> np.ndarray:
    """High-pass every frame in a stack with the sweep-wide kernel."""
    return np.stack([high_pass(frame, HIGH_PASS_PX) for frame in frames])


def pair_indices_from(labels: list[str]) -> list[tuple[int, int]]:
    """Index pairs of distinct-label recordings."""
    return [
        (first, second)
        for first, second in combinations(range(len(labels)), 2)
        if labels[first] != labels[second]
    ]


def sweep(
    openevt: object,
    pattern: str,
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    transform: str,
    min_windows: int,
    support_mask: bool = True,
    polarity: str = "both",
    splits: int = 4,
    ceiling_fraction: float = 0.8,
) -> tuple[
    list[str],
    np.ndarray,
    np.ndarray,
    dict[str, np.ndarray],
]:
    """Return labels, mean cross-label correlation grid, per-pair values, and
    split-half diagnostics (replicate mean/sem/t/discernible per pair, within-
    recording reliability, Spearman-Brown ceiling, and fraction of ceiling).

    Combinations whose recording holds fewer than ``min_windows`` accumulation
    windows are left as NaN: averaging over one or two frames would measure
    raw single-frame texture, not the converged correlation. With
    ``support_mask`` the correlation excludes pixels idle in both frames;
    otherwise shared zeros count toward the coefficient.
    """
    recordings = discover_recordings(pattern)
    labels = [label for label, _ in recordings]
    pair_indices = [
        (first, second)
        for first, second in combinations(range(len(labels)), 2)
        if labels[first] != labels[second]
    ]
    if not pair_indices:
        raise ValueError("recordings must include at least two distinct labels")
    cutoffs_us = [int(round(duration * 1_000_000)) for duration in durations_s]
    shape = (len(durations_s), len(accumulations_ms))
    means = np.full(shape, np.nan)
    pairs = np.full(shape + (len(pair_indices),), np.nan)
    diagnostics = {
        "replicate_mean": np.full(shape + (len(pair_indices),), np.nan),
        "replicate_sem": np.full(shape + (len(pair_indices),), np.nan),
        "replicate_t": np.full(shape + (len(pair_indices),), np.nan),
        "discernible": np.full(shape + (len(pair_indices),), np.nan),
        "self_reliability": np.full(shape + (len(labels),), np.nan),
        "ceiling": np.full(shape, np.nan),
        "fraction_of_ceiling": np.full(shape, np.nan),
        "splits_used": np.full(shape, np.nan),
    }

    def measure_replicates(dur_index, acc_index, streams, rows, columns, used):
        """Interleaved-replicate correlations: per-pair scatter and per-recording
        Spearman-Brown ceiling."""
        replicated = np.stack(
            [[stream.split_average(index) for index in range(used)] for stream in streams]
        )[:, :, rows, columns]
        support = replicated != 0
        replicated = np.stack([filtered_stack(recording) for recording in replicated])
        for pair_slot, (first, second) in enumerate(pair_indices):
            coefficients = [
                pair_pearson(
                    replicated[first, index], replicated[second, index],
                    support[first, index], support[second, index],
                )
                for index in range(used)
            ]
            mean, sem, statistic, discernible = replicate_statistics(coefficients)
            diagnostics["replicate_mean"][dur_index, acc_index, pair_slot] = mean
            diagnostics["replicate_sem"][dur_index, acc_index, pair_slot] = sem
            diagnostics["replicate_t"][dur_index, acc_index, pair_slot] = statistic
            diagnostics["discernible"][dur_index, acc_index, pair_slot] = discernible
        for label_index in range(len(labels)):
            coefficients = [
                pair_pearson(
                    replicated[label_index, first], replicated[label_index, second],
                    support[label_index, first], support[label_index, second],
                )
                for first, second in combinations(range(used), 2)
            ]
            valid = [value for value in coefficients if not np.isnan(value)]
            if valid:
                reliability = float(np.mean(valid))
                denominator = 1 + (used - 1) * reliability
                if denominator > 0:
                    diagnostics["self_reliability"][dur_index, acc_index, label_index] = (
                        used * reliability / denominator
                    )
        ceilings = diagnostics["self_reliability"][dur_index, acc_index]
        ceilings = ceilings[~np.isnan(ceilings)]
        if ceilings.size:
            diagnostics["ceiling"][dur_index, acc_index] = float(ceilings.mean())
            if ceilings.mean() > 0:
                diagnostics["fraction_of_ceiling"][dur_index, acc_index] = (
                    means[dur_index, acc_index] / ceilings.mean()
                )

    for acc_index, acc_ms in enumerate(accumulations_ms):
        accumulation_us = int(round(acc_ms * 1_000))
        streams = [
            RecordingStream(openevt, path, accumulation_us, transform, polarity, splits)
            for _, path in recordings
        ]
        for dur_index, cutoff in enumerate(cutoffs_us):
            windows = window_count(durations_s[dur_index], acc_ms)
            if windows < min_windows:
                print(
                    f"  duration={durations_s[dur_index]:g} s: skipped, only "
                    f"{windows} accumulation window(s) (< {min_windows})",
                    flush=True,
                )
                continue
            for stream in streams:
                stream.advance_to(cutoff)
            stack = np.stack([stream.average() for stream in streams])
            rows, columns = signal_window(stack, CROP_MARGIN_PX)
            cropped = stack[:, rows, columns]
            support = cropped != 0
            try:
                matrix = pearson_matrix(filtered_stack(cropped), support if support_mask else None)
            except ValueError as error:
                print(
                    f"  duration={durations_s[dur_index]:g} s: no coefficient ({error})",
                    flush=True,
                )
                continue
            values = [float(matrix[first, second]) for first, second in pair_indices]
            pairs[dur_index, acc_index] = values
            means[dur_index, acc_index] = float(np.mean(values))

            used = replicate_count(min(stream.frame_count for stream in streams), splits)
            diagnostics["splits_used"][dur_index, acc_index] = used
            if used >= 2:
                measure_replicates(dur_index, acc_index, streams, rows, columns, used)
            detail = "  ".join(
                f"{labels[first]}-{labels[second]}={value:.3f}"
                for value, (first, second) in zip(values, pair_indices, strict=True)
            )
            print(
                f"  duration={durations_s[dur_index]:g} s: {detail}  mean={means[dur_index, acc_index]:.3f}",
                flush=True,
            )
    return labels, means, pairs, diagnostics


def results_frame(
    labels: list[str],
    pair_indices: list[tuple[int, int]],
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    means: np.ndarray,
    pairs: np.ndarray,
    diagnostics: dict[str, np.ndarray],
) -> pd.DataFrame:
    """One row per measured duration/accumulation combination, columns in CSV order."""
    records = []
    for dur_index, duration in enumerate(durations_s):
        for acc_index, acc_ms in enumerate(accumulations_ms):
            record = {
                "duration_s": f"{duration:g}",
                "accumulation_ms": f"{acc_ms:g}",
                "windows": window_count(duration, acc_ms),
                "splits": diagnostics["splits_used"][dur_index, acc_index],
                "mean_cross_correlation": means[dur_index, acc_index],
            }
            measured = not np.isnan(means[dur_index, acc_index])
            pair_names = [f"{labels[first]}_{labels[second]}" for first, second in pair_indices]
            for name, value in zip(pair_names, pairs[dur_index, acc_index]):
                record[name] = value
            for suffix, key in (("sem", "replicate_sem"), ("t", "replicate_t"), ("discernible", "discernible")):
                for name, value in zip(pair_names, diagnostics[key][dur_index, acc_index]):
                    if suffix == "discernible":
                        record[f"{name}_discernible"] = bool(value) if not np.isnan(value) else None
                    else:
                        record[f"{name}_{suffix}"] = value
            for label_index, label in enumerate(labels):
                record[f"self_reliability_{label}"] = diagnostics["self_reliability"][
                    dur_index, acc_index, label_index
                ]
            record["ceiling"] = diagnostics["ceiling"][dur_index, acc_index]
            record["fraction_of_ceiling"] = diagnostics["fraction_of_ceiling"][dur_index, acc_index]
            if not measured:
                record = {key: (value if key in ("duration_s", "accumulation_ms", "windows") else None)
                          for key, value in record.items()}
            records.append(record)
    frame = pd.DataFrame(records)
    for column in ("windows", "splits"):
        frame[column] = frame[column].astype("Int64")
    return frame


def first_reached(frame: pd.DataFrame, mask: pd.Series) -> float | None:
    """Earliest duration at which ``mask`` holds, or None."""
    reached = frame.loc[mask, "duration_s"]
    return None if reached.empty else float(reached.iloc[0])


def discernibility_summary(
    frame: pd.DataFrame,
    labels: list[str],
    pair_indices: list[tuple[int, int]],
    ceiling_fraction: float,
) -> dict[str, object]:
    """First duration at which each pair (and all pairs) become discernible
    and reach the ceiling fraction, per accumulation interval."""
    per_accumulation = []
    for acc_ms, group in frame.groupby("accumulation_ms", sort=False):
        entry: dict[str, object] = {"accumulation_ms": float(acc_ms), "pairs": {}}
        for first, second in pair_indices:
            name = f"{labels[first]}_{labels[second]}"
            entry["pairs"][name] = {
                "discernible_from_s": first_reached(group, group[f"{name}_discernible"].fillna(False).astype(bool)),
                "at_ceiling_from_s": first_reached(
                    group, group["fraction_of_ceiling"] >= ceiling_fraction
                ),
            }
        all_discernible = group[
            [f"{labels[first]}_{labels[second]}_discernible" for first, second in pair_indices]
        ].fillna(False).all(axis=1)
        entry["all_pairs_discernible_from_s"] = first_reached(group, all_discernible)
        entry["all_pairs_at_ceiling_from_s"] = first_reached(
            group, group["fraction_of_ceiling"] >= ceiling_fraction
        )
        per_accumulation.append(entry)
    return {"ceiling_fraction": ceiling_fraction, "per_accumulation": per_accumulation}


def write_outputs(
    output: Path,
    labels: list[str],
    pair_indices: list[tuple[int, int]],
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    means: np.ndarray,
    pairs: np.ndarray,
    diagnostics: dict[str, np.ndarray],
    args: argparse.Namespace,
) -> pd.DataFrame:
    frame = results_frame(labels, pair_indices, durations_s, accumulations_ms, means, pairs, diagnostics)
    frame.to_csv(
        output / "duration_accumulation_sweep.csv",
        index=False,
        na_rep="",
        float_format="%.6f",
    )

    crossings = frame.loc[frame["mean_cross_correlation"] >= THRESHOLD]
    metadata = {
        "method": "Mean Pearson r over cross-label pairs of cropped, high-passed activity-frame averages, "
        + (
            "restricted to pixels active in either frame"
            if args.support_mask
            else "over all pixels (shared zeros included)"
        ),
        "pattern": args.pattern,
        "transform": args.transform,
        "polarity": args.polarity,
        "crop_margin_px": CROP_MARGIN_PX,
        "highpass_px": HIGH_PASS_PX,
        "threshold": THRESHOLD,
        "min_windows": args.min_windows,
        "splits_requested": args.splits,
        "ceiling_fraction": args.ceiling_fraction,
        "discernibility_criterion": (
            f"two-sided Student-t test at alpha={ALPHA} across interleaved-replicate "
            "correlations; ceiling is the mean Spearman-Brown corrected within-recording reliability"
        ),
        "durations_s": list(durations_s),
        "accumulations_ms": list(accumulations_ms),
        "labels": labels,
        "skipped_combinations": [
            {"duration_s": float(row.duration_s), "accumulation_ms": float(row.accumulation_ms),
             "windows": int(row.windows)}
            for row in frame.loc[frame["mean_cross_correlation"].isna()].itertuples()
        ],
        "combinations_at_or_above_threshold": [
            {"duration_s": float(row.duration_s), "accumulation_ms": float(row.accumulation_ms),
             "mean": float(row.mean_cross_correlation)}
            for row in crossings.itertuples()
        ],
        "discernibility": discernibility_summary(frame, labels, pair_indices, args.ceiling_fraction),
    }
    (output / "duration_accumulation_sweep.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return frame


def plot_sweep(
    output: Path,
    labels: list[str],
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    means: np.ndarray,
    min_windows: int,
    support_mask: bool = True,
    polarity: str = "both",
    highlight_duration_s: float | None = None,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", context="notebook")
    duration_grid, acc_grid = np.meshgrid(
        np.array(durations_s), np.array(accumulations_ms), indexing="ij"
    )
    valid = ~np.isnan(means)
    floor = min(0.0, float(np.nanmin(means))) if valid.any() else 0.0
    figure, axis = plt.subplots(figsize=(11.5, 7.2))
    scatter = axis.scatter(
        duration_grid[valid],
        acc_grid[valid],
        c=means[valid],
        cmap="RdBu_r",
        vmin=floor,
        vmax=1.0,
        s=int(min(520, max(60, 50000 / max(valid.sum(), 1)))),
        marker="o",
        edgecolors="0.3",
        linewidths=0.6,
    )
    for x, y, value, is_valid in zip(
        duration_grid.ravel(), acc_grid.ravel(), means.ravel(), valid.ravel(), strict=True
    ):
        axis.annotate(
            f"{value:.2f}" if is_valid else "×",
            (x, y),
            ha="center",
            va="center",
            fontsize=7 if is_valid else 12,
            color="0.15" if is_valid and abs(value) > 0.25 else "0.75" if not is_valid else "0.3",
        )
    if np.nanmax(means) >= THRESHOLD:
        contour = axis.contour(
            np.log10(duration_grid),
            np.log10(acc_grid),
            means,
            levels=[THRESHOLD],
            colors="black",
            linewidths=2.2,
        )
        axis.clabel(contour, fmt={THRESHOLD: f"r = {THRESHOLD}"}, fontsize=10)
    boundary_durations = np.array([min(durations_s), max(durations_s)])
    boundary_acc = boundary_durations * 1_000 / min_windows
    axis.plot(
        boundary_durations, boundary_acc, "--", color="0.35", linewidth=1.6, zorder=1,
    )
    axis.annotate(
        f"{min_windows}+ windows required",
        (np.sqrt(boundary_durations.prod()) * 0.75, np.sqrt(boundary_acc.prod()) * 0.75),
        ha="center",
        va="bottom",
        fontsize=9,
        color="0.35",
        rotation=19,
        bbox=dict(boxstyle="round", fc="white", ec="0.8", alpha=0.9),
    )
    if highlight_duration_s is not None and min(durations_s) <= highlight_duration_s <= max(durations_s):
        axis.axvline(highlight_duration_s, color="0.1", linestyle=":", linewidth=1.8, zorder=2)
        axis.annotate(
            f"{highlight_duration_s * 1_000:g} ms",
            (highlight_duration_s, acc_grid[valid].max() if valid.any() else max(accumulations_ms)),
            ha="left",
            va="top",
            fontsize=9,
            color="0.1",
            bbox=dict(boxstyle="round", fc="white", ec="0.8", alpha=0.9),
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    ticks = [value for value in (0.001, 0.01, 0.1, 1.0, 5.0) if value in durations_s]
    axis.set_xticks(ticks)
    axis.set_xticklabels([f"{value:g}" for value in ticks])
    axis.set_yticks(list(accumulations_ms))
    axis.set_yticklabels([f"{value:g}" for value in accumulations_ms])
    axis.set_xlim(boundary_durations[0] * 0.75, boundary_durations[1] * 1.35)
    axis.set_ylim(min(accumulations_ms) * 0.75, max(accumulations_ms) * 1.35)
    axis.minorticks_off()
    axis.set_xlabel("Recording duration (s)")
    axis.set_ylabel("Accumulation interval (ms)   [effective FPS = 1000 / ms]")
    pair_note = " vs ".join(
        f"{labels[first]}-{labels[second]}" for first, second in pair_indices_from(labels)
    )
    axis.set_title(
        f"Where does cross-wavelength similarity exceed {THRESHOLD:.0%}? ({polarity} polarity)\n"
        f"Mean Pearson r over {pair_note}",
        fontsize=12,
    )
    figure.text(
        0.99,
        0.005,
        "crop + 64px high-pass, "
        + ("0=0 pixels excluded" if support_mask else "0=0 pixels included (shared zeros count)")
        + "  ·  × above the dashed line: fewer than "
        f"{min_windows} accumulation windows, not measured",
        ha="right",
        fontsize=8.5,
        color="0.4",
    )
    bar = figure.colorbar(scatter, ax=axis, shrink=0.85)
    bar.set_label("Mean cross-color Pearson r")
    figure.tight_layout(rect=(0, 0.02, 1, 1))
    figure.savefig(output / "duration_accumulation_sweep.png", dpi=200)
    figure.savefig(output / "duration_accumulation_sweep.svg")
    plt.close(figure)


def plot_discernibility(
    output: Path,
    labels: list[str],
    pair_indices: Sequence[tuple[int, int]],
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    means: np.ndarray,
    diagnostics: dict[str, np.ndarray],
    ceiling_fraction: float,
    polarity: str = "both",
    highlight_duration_s: float | None = None,
    max_panels: int = 3,
) -> None:
    """Correlation vs total averaged time with replicate confidence intervals."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    populated = [
        acc_index
        for acc_index in range(len(accumulations_ms))
        if not np.all(np.isnan(means[:, acc_index]))
    ]
    if not populated:
        return
    selected = {populated[0], populated[-1]}
    selected.add(min(populated, key=lambda index: abs(accumulations_ms[index] - 1.0)))
    sns.set_theme(style="whitegrid", context="notebook")
    figure, axes = plt.subplots(
        1, len(sorted(selected)[:max_panels]), figsize=(5.4 * len(sorted(selected)[:max_panels]), 4.6),
        sharey=True, squeeze=False,
    )
    colors = sns.color_palette("colorblind", n_colors=len(pair_indices))
    for axis, acc_index in zip(axes[0], sorted(selected)[:max_panels], strict=True):
        for slot, (first, second) in enumerate(pair_indices):
            measured = ~np.isnan(means[:, acc_index])
            xs = np.asarray(durations_s)[measured]
            sems = diagnostics["replicate_sem"][measured, acc_index, slot]
            used = diagnostics["splits_used"][measured, acc_index]
            intervals = np.where(
                np.isnan(sems), 0.0, np.abs(sems) * np.array([t_critical(int(k) if k >= 2 else 2) for k in used])
            )
            significant = diagnostics["discernible"][measured, acc_index, slot] == 1.0
            for flag in (True, False):
                points = significant == flag
                if not points.any():
                    continue
                axis.errorbar(
                    xs[points], means[measured, acc_index][points], yerr=intervals[points],
                    marker="o", markersize=5, linestyle="-" if flag else "none", linewidth=1.4,
                    markerfacecolor=colors[slot] if flag else "white", markeredgecolor=colors[slot],
                    ecolor=colors[slot], elinewidth=1.0, capsize=2,
                    label=f"{labels[first]}-{labels[second]}" if flag else "_nolegend_",
                )
        ceilings = diagnostics["ceiling"][:, acc_index]
        measured = ~np.isnan(ceilings)
        if measured.any():
            axis.plot(
                np.asarray(durations_s)[measured], ceilings[measured], "--", color="0.2",
                linewidth=1.4, label="split-half noise ceiling",
            )
        axis.axhline(0.0, color="0.6", linewidth=0.8)
        if highlight_duration_s is not None:
            axis.axvline(highlight_duration_s, color="0.1", linestyle=":", linewidth=1.4)
            axis.annotate(
                f"{highlight_duration_s * 1_000:g} ms\n(16 × 1 ms)",
                (highlight_duration_s, axis.get_ylim()[0]),
                ha="left", va="bottom", fontsize=8, color="0.1",
            )
        axis.set_xscale("log")
        axis.set_xlabel("Total averaged time (s)")
        axis.set_title(f"{accumulations_ms[acc_index]:g} ms accumulation", fontsize=11)
        axis.legend(fontsize=8, loc="best")
    axes[0][0].set_ylabel("Cross-color Pearson r")
    figure.suptitle(
        f"Discernibility vs total averaged time ({polarity} polarity): "
        "filled = significant across replicates (95% t), open = not discernible; "
        "error bars = 95% CI",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(output / "discernibility_curves.png", dpi=200)
    figure.savefig(output / "discernibility_curves.svg")
    plt.close(figure)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        default="data/raw/evt3_raw/circle_*.raw",
        help="glob for recordings (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/spectral_correlation"),
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--durations",
        type=parse_float_list,
        default=DEFAULT_DURATIONS_S,
        help="comma-separated recording durations in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--accumulations",
        type=parse_float_list,
        default=DEFAULT_ACCUMULATIONS_MS,
        help="comma-separated accumulation intervals in ms (default: %(default)s)",
    )
    parser.add_argument(
        "--polarity",
        choices=("both", "on", "off", "signed"),
        default="both",
        help="event values accumulated into each window: both (default) folds "
        "polarities, signed accumulates ON minus OFF matching the binned event "
        "frame of Shah et al. (CVPR 2024)",
    )
    parser.add_argument(
        "--splits",
        type=positive_int,
        default=4,
        help="interleaved replicates for the split-half noise ceiling; reduced "
        "automatically to keep >=4 windows per replicate and disabled below 8 "
        "windows (default: %(default)s)",
    )
    parser.add_argument(
        "--ceiling-fraction",
        type=float,
        default=0.8,
        help="a pair counts as at ceiling when its mean r reaches this fraction "
        "of the Spearman-Brown noise ceiling (default: %(default)s)",
    )
    parser.add_argument(
        "--no-support-mask",
        dest="support_mask",
        action="store_false",
        help="correlate over all pixels instead of excluding pixels idle in "
        "both frames; shared zeros then count toward similarity",
    )
    parser.add_argument(
        "--min-windows",
        type=positive_int,
        default=10,
        help="skip duration/accumulation combinations averaging fewer than "
        "this many windows (default: %(default)s)",
    )
    parser.add_argument(
        "--transform",
        choices=("raw", "sqrt", "log1p"),
        default="log1p",
        help="variance-stabilizing transform before averaging (default: %(default)s)",
    )
    parser.add_argument(
        "--openevt-library",
        type=Path,
        help="matching libopenevt.so; auto-detected from openevt/target/release",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = make_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    with load_openevt(args.openevt_library) as openevt:
        labels, means, pairs, diagnostics = sweep(
            openevt, args.pattern, args.durations, args.accumulations, args.transform,
            args.min_windows, args.support_mask, args.polarity, args.splits,
            args.ceiling_fraction,
        )
    pair_indices = pair_indices_from(labels)
    frame = write_outputs(
        output, labels, pair_indices, args.durations, args.accumulations,
        means, pairs, diagnostics, args,
    )
    plot_sweep(
        output, labels, args.durations, args.accumulations, means,
        args.min_windows, args.support_mask, args.polarity, HIGHLIGHT_DURATION_S,
    )
    plot_discernibility(
        output, labels, pair_indices, args.durations, args.accumulations,
        means, diagnostics, args.ceiling_fraction, args.polarity, HIGHLIGHT_DURATION_S,
    )
    measured = frame.dropna(subset=["mean_cross_correlation"])
    if (measured["mean_cross_correlation"] >= THRESHOLD).any():
        reached = measured.loc[measured["mean_cross_correlation"] >= THRESHOLD]
        print("Combinations at or above r={}: ".format(THRESHOLD) + ", ".join(
            f"{row.duration_s}s/{row.accumulation_ms}ms" for row in reached.itertuples()
        ))
    else:
        best = measured.loc[measured["mean_cross_correlation"].idxmax()]
        print(
            f"No combination reaches r={THRESHOLD}; maximum is "
            f"{best.mean_cross_correlation:.3f} at {best.duration_s}s/{best.accumulation_ms}ms."
        )
    summary = json.loads((output / "duration_accumulation_sweep.json").read_text())
    for entry in summary["discernibility"]["per_accumulation"]:
        print(
            f"[{entry['accumulation_ms']:g} ms] all pairs discernible from "
            f"{entry['all_pairs_discernible_from_s']} s; at ceiling from "
            f"{entry['all_pairs_at_ceiling_from_s']} s"
        )
    print(f"Wrote sweep outputs to {output}")


if __name__ == "__main__":
    main()
