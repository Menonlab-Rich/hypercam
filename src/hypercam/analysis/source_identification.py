# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-01
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Identify what the repeatable component of the converged correlation is.

Motivation
----------
The duration sweeps show the cross-color Pearson r of the signed (ON - OFF)
activity frames rising monotonically with total averaging time T toward
r ~= 0.7-0.9 at 5 s. Measurement noise attenuates an observed correlation
toward zero, so that rise establishes only that *some* spatially structured
component of the event stream is repeatable across independent recordings -
it does not establish *what* the component is. The candidates are:

1. the DOE's spectral encoding fine structure (color-dependent; the wanted
   signal),
2. a color-independent sensor-fixed map (per-pixel ON/OFF threshold mismatch,
   latency/refractory asymmetry) - identical in every recording regardless of
   displayed content, pixel-scale, and therefore *not* removed by the 64 px
   high-pass,
3. scene-coupled structure shared across bands (the displayed circle occupies
   the same pixels for every color, so brightness-map edges are shared),
4. display-refresh phase-locking artifacts (60 Hz LCD).

This module measures each candidate's signature using existing recordings
only:

* **Corrected split-half reliability.** Each recording is split into
  *disjoint, contiguous time blocks*, and the blocks are correlated through
  the standard pipeline (crop, high-pass, support mask). This corrects the
  ``duration_sweep`` diagnostic: there, windows are dealt *interleaved*
  (``index % splits``), handing every replicate a fixed phase offset of the
  display-periodic modulation, so under signed polarity the replicate
  differences are systematic and the split-half reliability collapses to
  negative values (visible in
  ``results/spectral_correlation_fine_signed/duration_accumulation_sweep.csv``).
  Contiguous blocks each span many complete display periods, so their phase
  sampling is unbiased. A Spearman-Brown correction lifts the block-pair
  correlation to the reliability of the full-length estimate, and the
  per-pair *disattenuated* correlation ``r_true = r_obs / sqrt(rel_a*rel_b)``
  (Spearman 1904) estimates the correlation of the repeatable components
  themselves - the number that distinguishes "the spectra encode similar
  shapes" from "a shared non-spectral map dominates".
* **Gradient congruence without the high-pass.** Signed Sobel components
  (Sx, Sy) of the cropped, *unfiltered* frames, correlated across bands
  globally and in local windows. Pearson r is invariant to gain and offset,
  so even r_true = 1 does not preclude color-distinguishing information
  living in the amplitude channel; the gradient field inherits that
  blindness, which is why the control tests below matter alongside it. A
  color-independent artifact map is congruous across bands by definition, so
  repeatable *incongruous* structure cannot be artifact - but it could still
  be band-dependent scene coupling (display brightness differs per color),
  which only the direct-image branch can separate.
* **Control recordings** (e.g. a dark or blank-display capture). Any
  structure that repeats in a control is sensor-fixed by construction,
  directly bounding component 2.

Not resolvable with existing data: the "present in the direct display image"
branch of the decision tree. No linear-camera capture of the display through
the optics exists in the repository (``results/rgb_raw`` holds *event* frames
of these same recordings - folded polarity, no high-pass - and is not an
independent sensor), so that branch is reported as pending.

Outputs (a self-contained directory, per the ``results/README.md`` contract):
``analysis_metadata.json``; ``correlation_full.csv/.npy`` + heat map (standard
pipeline, full duration); ``reliability.csv`` (per-duration disjoint-block
reliabilities, observed correlations, attenuation ceilings, disattenuated
r_true, fraction of ceiling); ``gradient_congruence.csv`` + per-pair local
congruence maps; ``segments.csv`` (early-vs-late stationarity diagnostics);
``magnification_sweep.csv`` + plots (cross-band congruence vs radial
magnification - the lambda-scaling test); ``conclusions.json`` and
``conclusions.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import ndimage

from .duration_sweep import (
    pair_pearson,
    parse_float_list,
    window_count,
    window_terms,
)
from .spectral_correlation import (
    block_mean,
    discover_recordings,
    high_pass,
    load_openevt,
    pearson_matrix,
    positive_int,
    signal_window,
    write_grayscale_png,
    write_heatmap_svg,
    write_matrix_csv,
)

# A congruence-map window must hold at least this many supported pixels before
# its local Pearson is computed; below this the coefficient is dominated by
# quantization texture rather than structure.
MIN_WINDOW_PIXELS = 64

# Heuristic interpretation thresholds for the disattenuated correlation. They
# are descriptive aids for the written conclusions, not decision boundaries of
# the pipeline.
SHAPE_IDENTICAL_THRESHOLD = 0.95
SHAPE_SHARED_THRESHOLD = 0.70


def positive_float(value: str) -> float:
    """argparse type: strictly positive float (accumulation intervals)."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


class WindowArchive:
    """Sparse per-window event terms from one decoded recording.

    Each accumulation window is stored once as sparse (flat pixel index,
    transformed value) terms. Every downstream frame - the full-duration
    average, contiguous time blocks, or a truncated-duration average - is then
    a summation over a window range instead of a fresh decode. Memory stays
    modest because a window touches only the pixels that fired in it.
    """

    def __init__(self, label: str, path: Path, shape: tuple[int, int]) -> None:
        self.label = label
        self.path = path
        self.shape = shape
        self.indices: list[np.ndarray] = []
        self.values: list[np.ndarray] = []
        self.frame_count = 0
        self.events_total = 0
        self.events_used = 0
        self.t_first: int | None = None
        self.t_last: int | None = None

    @property
    def pixel_count(self) -> int:
        return self.shape[0] * self.shape[1]

    def add_window(self, terms: tuple[np.ndarray, np.ndarray] | None) -> None:
        """Append one window's sparse terms (or empty terms for an idle window)."""
        if terms is None:
            self.indices.append(np.empty(0, dtype=np.int64))
            self.values.append(np.empty(0, dtype=np.float64))
        else:
            unique, values = terms
            if unique.size and int(unique.max()) >= self.pixel_count:
                raise ValueError(
                    f"{self.path.name} contains events outside "
                    f"{self.shape[1]}x{self.shape[0]}"
                )
            self.indices.append(np.asarray(unique, dtype=np.int64))
            self.values.append(np.asarray(values, dtype=np.float64))
        self.frame_count += 1

    def frame(self, start: int = 0, stop: int | None = None) -> np.ndarray:
        """Dense mean over windows [start, stop); default: every window.

        The mean (not the sum) keeps truncated durations comparable with the
        full-duration frames, exactly like the sweep's advancing averages.
        ``stop`` beyond the recording clamps to the last window, matching the
        sweep's behaviour of pulling every window that starts before a cutoff.
        """
        stop = self.frame_count if stop is None else min(stop, self.frame_count)
        count = stop - start
        if count <= 0:
            raise ValueError(
                f"{self.label}: window slice [{start}:{stop}] is empty "
                f"({self.frame_count} windows available)"
            )
        indices = np.concatenate(self.indices[start:stop])
        values = np.concatenate(self.values[start:stop])
        dense = np.bincount(indices, weights=values, minlength=self.pixel_count)
        return (dense / count).reshape(self.shape)

    def metadata(self, accumulation_us: int) -> dict[str, object]:
        """Recording provenance block for analysis_metadata.json."""
        return {
            "label": self.label,
            "path": str(self.path),
            "shape": [self.shape[0], self.shape[1]],
            "events_total": self.events_total,
            "events_used": self.events_used,
            "accumulation_us": accumulation_us,
            "frames_averaged": self.frame_count,
            "t_first_us": self.t_first,
            "t_last_us": self.t_last,
            "duration_us": None
            if self.t_first is None or self.t_last is None
            else self.t_last - self.t_first,
        }


def used_event_count(events: np.ndarray, polarity: str) -> int:
    """Events a polarity mode actually accumulates (signed/both use all)."""
    if polarity in ("signed", "both"):
        return int(events.size)
    if polarity == "on":
        return int(np.count_nonzero(events["p"] != 0))
    return int(np.count_nonzero(events["p"] == 0))


def decode_windows(
    openevt: object,
    label: str,
    path: Path,
    polarity: str,
    accumulation_us: int,
    transform: str,
) -> WindowArchive:
    """Decode one recording into sparse per-window terms (one pass).

    Mirrors ``spectral_correlation.build_activity_frame``: window ``i`` covers
    event times ``[i*accumulation_us, (i+1)*accumulation_us)``, and a clean
    OpenEVT 1.0.4 end-of-file surfaces as ``OSError`` rather than
    ``StopIteration`` for some recordings.
    """
    reader = openevt.RawFileReader(str(path))
    iterator = reader.iter()
    height, width = (int(value) for value in iterator.shape())
    archive = WindowArchive(label, path, (height, width))
    while True:
        try:
            events = iterator.next_delta(accumulation_us)
        except StopIteration:
            break
        except OSError as error:
            if "end of file" in str(error).lower() or str(error).lower() == "eof":
                break
            raise
        archive.events_total += int(events.size)
        if events.size:
            batch_first = int(events["t"][0])
            batch_last = int(events["t"][-1])
            archive.t_first = (
                batch_first
                if archive.t_first is None
                else min(archive.t_first, batch_first)
            )
            archive.t_last = (
                batch_last
                if archive.t_last is None
                else max(archive.t_last, batch_last)
            )
            archive.events_used += used_event_count(events, polarity)
        archive.add_window(window_terms(events, width, polarity, transform))
    if archive.events_total == 0 or archive.frame_count == 0:
        raise ValueError(f"recording contains no CD events: {path}")
    return archive


def block_bounds(count: int, blocks: int) -> list[tuple[int, int]]:
    """Contiguous, disjoint [start, stop) window ranges covering ``count``.

    Block sizes differ by at most one window. Contiguity in time is the whole
    point: each block spans many complete periods of any periodic modulation
    slower than the block itself, so block-to-block differences reflect
    genuine recording noise rather than a fixed phase offset of the display
    refresh - the failure mode of interleaved (``index % blocks``) dealing.
    Blocks may be empty when ``count < blocks``; callers must skip them.
    """
    return [
        (count * block // blocks, count * (block + 1) // blocks)
        for block in range(blocks)
    ]


def spearman_brown(mean_split_r: float, blocks: int) -> float:
    """Reliability of the full-length estimate from disjoint block pairs.

    Given the mean correlation between disjoint blocks of one recording, the
    Spearman-Brown prediction formula gives the reliability of the average
    over all blocks: ``blocks * r / (1 + (blocks - 1) * r)``. Undefined (NaN)
    where the denominator is non-positive (``r <= -1/(blocks - 1)``) - exactly
    the regime the interleaved dealing produced under signed polarity.
    """
    if blocks < 2 or not np.isfinite(mean_split_r):
        return np.nan
    denominator = 1 + (blocks - 1) * mean_split_r
    if denominator <= 0:
        return np.nan
    return float(blocks * mean_split_r / denominator)


def disattenuated(
    r_observed: float, reliability_first: float, reliability_second: float
) -> float:
    """Correlation of the repeatable components (Spearman 1904 attenuation).

    Independent noise in either estimate biases the observed correlation
    toward zero by approximately the product of the reliabilities, so
    ``r_true ~= r_observed / sqrt(rel_first * rel_second)``. Values above 1
    (possible when the reliability estimates themselves are noisy) are clipped
    to 1 and should be read with that caveat. Zero reliability => NaN: with
    no reliable signal the attenuation factor is undefined, and the observed
    correlation carries no information about the true one.
    """
    factor = np.sqrt(max(reliability_first, 0.0) * max(reliability_second, 0.0))
    if factor == 0.0 or not np.isfinite(r_observed):
        return np.nan
    return float(np.clip(r_observed / factor, -1.0, 1.0))


def sobel_gradients(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Signed Sobel gradient components (row-direction, column-direction).

    Signed components, not magnitude: magnitude maps are non-negative with a
    positive floor, and correlating them inflates agreement wherever both
    frames have any structure at all (shared-support bias). The derivative
    also removes any DC offset by construction, which is why the congruence
    test needs no high-pass even though the standard correlation does.
    """
    rows = ndimage.sobel(frame, axis=0)
    columns = ndimage.sobel(frame, axis=1)
    return rows, columns


def gradient_vector(frame: np.ndarray, support: np.ndarray) -> np.ndarray:
    """Both Sobel components of one frame as a single support-masked vector."""
    rows, columns = sobel_gradients(frame)
    stacked = np.concatenate([rows.ravel(), columns.ravel()])
    mask = np.concatenate([support.ravel(), support.ravel()])
    return stacked[mask]


def safe_pearson(first: np.ndarray, second: np.ndarray) -> float:
    """Pearson r that yields NaN for empty or degenerate inputs."""
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    if first.size < 2 or first.std() == 0 or second.std() == 0:
        return np.nan
    return float(np.clip(np.corrcoef(first, second)[0, 1], -1.0, 1.0))


def gradient_congruence(
    first: np.ndarray,
    second: np.ndarray,
    support_first: np.ndarray,
    support_second: np.ndarray,
) -> float:
    """Global congruence of signed gradient fields between two frames.

    Restricted to the *intersection* of the two intensity supports: the
    gradient of a pixel a recording never measured is undefined rather than
    zero, so including union-support pixels would correlate measured structure
    against support-boundary artifacts and deflate the statistic. (The main
    intensity correlation keeps the repository's union-support convention for
    continuity; the gradient statistic is new and chooses the honest mask.)
    """
    mask = support_first & support_second
    return safe_pearson(gradient_vector(first, mask), gradient_vector(second, mask))


def window_congruence_map(
    first: np.ndarray,
    second: np.ndarray,
    support_first: np.ndarray,
    support_second: np.ndarray,
    window: int,
) -> np.ndarray:
    """Local congruence map: per-window Pearson of signed gradient fields.

    Non-overlapping ``window`` x ``window`` tiles (edge-padded to fit, like
    ``block_mean``). Windows holding fewer than ``MIN_WINDOW_PIXELS``
    intersection-support pixels, or with a degenerate gradient field, are NaN.
    The intersection mask matters here for the same reason as in
    ``gradient_congruence``: without it, the support edge of a band that went
    idle inside a window shows up as a ring of spurious gradient. The map
    answers *where* the bands agree: sensor-fixed artifacts sit at scattered
    pixel positions across the whole frame, scene-coupled structure tracks the
    displayed edges, and diffraction structure organizes into rings and lobes.
    """
    height, width = first.shape
    padded_rows = (window - height % window) % window
    padded_columns = (window - width % window) % window
    first_p = np.pad(first, ((0, padded_rows), (0, padded_columns)), mode="edge")
    second_p = np.pad(second, ((0, padded_rows), (0, padded_columns)), mode="edge")
    support_first_p = np.pad(
        support_first, ((0, padded_rows), (0, padded_columns)), mode="edge"
    )
    support_second_p = np.pad(
        support_second, ((0, padded_rows), (0, padded_columns)), mode="edge"
    )
    grid_rows = first_p.shape[0] // window
    grid_columns = first_p.shape[1] // window
    first_rows, first_columns = sobel_gradients(first_p)
    second_rows, second_columns = sobel_gradients(second_p)
    congruence = np.full((grid_rows, grid_columns), np.nan)
    for block_row in range(grid_rows):
        for block_column in range(grid_columns):
            rows = slice(block_row * window, (block_row + 1) * window)
            columns = slice(block_column * window, (block_column + 1) * window)
            mask = (
                support_first_p[rows, columns] & support_second_p[rows, columns]
            ).ravel()
            if np.count_nonzero(mask) < MIN_WINDOW_PIXELS:
                continue
            first_field = np.concatenate(
                [
                    first_rows[rows, columns].ravel()[mask],
                    first_columns[rows, columns].ravel()[mask],
                ]
            )
            second_field = np.concatenate(
                [
                    second_rows[rows, columns].ravel()[mask],
                    second_columns[rows, columns].ravel()[mask],
                ]
            )
            congruence[block_row, block_column] = safe_pearson(first_field, second_field)
    return congruence


def disk_centroid(
    frame: np.ndarray, block: int = 16, percentile: float = 90.0
) -> tuple[float, float]:
    """Centroid of the brightest region (the displayed disk / encoding core).

    Radial magnification must be taken about the pattern's own center, not the
    frame center: the disk sits off-center in these recordings. The centroid of
    the block-averaged frame's top-percentile pixels lands inside the disk for
    all three colors, since the disk dominates the bright tail in each.
    """
    low = block_mean(frame, block)
    threshold = np.percentile(low, percentile)
    ys, xs = np.nonzero(low >= threshold)
    if ys.size == 0:
        height, width = frame.shape
        return height / 2.0, width / 2.0
    return float(ys.mean()), float(xs.mean())


def rescaled_tile(
    frame: np.ndarray,
    center_row: float,
    center_column: float,
    size: int,
    magnification: float,
) -> np.ndarray:
    """The frame's structure around ``center`` as it would look magnified.

    Extracts the (size/magnification)-square region centered on the centroid,
    clipped to the frame, and zooms it back to (size, size). Under the
    diffractive-scaling hypothesis a DOE's far-field pattern grows linearly
    with wavelength, so rescaling band b by m = lambda_a / lambda_b before
    comparing against band a should maximize the congruence if the shared fine
    structure is diffractive; a direct optical image (the displayed circle
    itself) does not scale with wavelength and peaks at m = 1. When the source
    region would leave the frame (m far below 1 near an edge) it is clipped and
    the effective magnification deviates from the nominal one; the sweep grid
    is chosen so this does not occur for these recordings.
    """
    height, width = frame.shape
    half = size / (2.0 * magnification)
    row_start = max(int(round(center_row - half)), 0)
    row_stop = min(int(round(center_row + half)), height)
    column_start = max(int(round(center_column - half)), 0)
    column_stop = min(int(round(center_column + half)), width)
    if row_stop - row_start < 2 or column_stop - column_start < 2:
        row_start, row_stop, column_start, column_stop = 0, height, 0, width
    region = frame[row_start:row_stop, column_start:column_stop]
    zoom_factors = (size / region.shape[0], size / region.shape[1])
    return ndimage.zoom(region, zoom_factors, order=1)


def magnification_sweep(
    frame_first: np.ndarray,
    frame_second: np.ndarray,
    center_row: float,
    center_column: float,
    size: int,
    magnifications: np.ndarray,
    highpass_px: int,
) -> list[tuple[float, float, float]]:
    """Cross-band congruence as a function of radial magnification of band 2.

    For each magnification, band 2's tile is rescaled about the disk centroid
    and compared against band 1's fixed tile twice: through the signed
    gradient field (no high-pass) and through the high-passed intensity frame.
    Returns (magnification, gradient_congruence, intensity_r) triples.
    """
    tile_first = rescaled_tile(frame_first, center_row, center_column, size, 1.0)
    support_first = tile_first != 0
    hp_first = high_pass(tile_first, highpass_px)
    results = []
    for magnification in magnifications:
        tile_second = rescaled_tile(
            frame_second, center_row, center_column, size, float(magnification)
        )
        support_second = tile_second != 0
        gradient = gradient_congruence(
            tile_first, tile_second, support_first, support_second
        )
        mask = support_first & support_second
        intensity = safe_pearson(
            hp_first[mask], high_pass(tile_second, highpass_px)[mask]
        )
        results.append((float(magnification), gradient, intensity))
    return results


def sweep_plot(
    path: Path,
    name: str,
    sweep: list[tuple[float, float, float]],
) -> None:
    """Plot congruence vs magnification with the gradient-field argmax marked."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    magnifications = np.array([row[0] for row in sweep])
    gradients = np.array([row[1] for row in sweep])
    intensities = np.array([row[2] for row in sweep])
    figure, axis = plt.subplots(figsize=(7.5, 4.6))
    axis.plot(magnifications, gradients, "-o", markersize=3, label="gradient congruence")
    axis.plot(magnifications, intensities, "-s", markersize=3, label="high-passed intensity r")
    axis.axvline(1.0, color="0.5", linestyle=":", linewidth=1.2, label="m = 1 (no scaling)")
    peak = magnifications[int(np.nanargmax(gradients))]
    axis.axvline(peak, color="0.15", linestyle="--", linewidth=1.2,
                 label=f"gradient peak m = {peak:.2f}")
    axis.set_xlabel("radial magnification applied to the second band")
    axis.set_ylabel("cross-band correlation")
    axis.set_title(f"{name}: congruence vs magnification about the disk centroid")
    axis.legend(fontsize=8, loc="best")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def shift_frame(frame: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Integer translation with zero fill (positive dy shifts down)."""
    out = np.zeros_like(frame)
    height, width = frame.shape
    source_rows = slice(max(0, -dy), height - max(0, dy))
    source_columns = slice(max(0, -dx), width - max(0, dx))
    target_rows = slice(max(0, dy), height - max(0, -dy))
    target_columns = slice(max(0, dx), width - max(0, -dx))
    out[target_rows, target_columns] = frame[source_rows, source_columns]
    return out


def best_shift_r(
    first: np.ndarray,
    second: np.ndarray,
    support_first: np.ndarray,
    support_second: np.ndarray,
    max_shift: int,
) -> dict[str, float]:
    """Support-masked r between two frames, maximized over integer shifts.

    A translation search separates mechanical drift (correlation restored at a
    nonzero shift) from in-place decorrelation (best at zero shift, as found
    for these recordings - the slowly varying shared component moves noisily in
    place, e.g. per-pixel sensor-state drift, rather than sliding).
    """
    best = {"r": np.nan, "dy": 0.0, "dx": 0.0, "r_at_zero": np.nan}
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            shifted = shift_frame(second, dy, dx)
            shifted_support = shifted != 0
            value = pair_pearson(first, shifted, support_first, shifted_support)
            if dy == 0 and dx == 0:
                best["r_at_zero"] = value
            if np.isfinite(value) and (
                not np.isfinite(best["r"]) or value > best["r"]
            ):
                best.update({"r": value, "dy": float(dy), "dx": float(dx)})
    return best


def sheet_png(
    path: Path,
    title: str,
    panels: list[tuple[str, np.ndarray]],
    columns: int,
    scale_percentile: float = 99.7,
) -> tuple[float, float]:
    """Panel grid on one shared, symmetric robust scale; returns that scale.

    Signed event data is plotted on a diverging colormap with limits
    ``+/- percentile(|values|, scale_percentile)`` computed over *all* panels
    together, so cross-frame intensity comparisons are honest (per-frame
    scaling would make an empty frame and a full frame look alike).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stacked = np.concatenate([panel.ravel() for _, panel in panels])
    limit = float(np.nanpercentile(np.abs(stacked), scale_percentile))
    if not np.isfinite(limit) or limit == 0:
        limit = 1.0
    rows = -(-len(panels) // columns)
    figure, axes = plt.subplots(
        rows, columns, figsize=(4.0 * columns, 3.6 * rows), squeeze=False
    )
    for index, (label, panel) in enumerate(panels):
        axis = axes[index // columns][index % columns]
        image = axis.imshow(
            panel, cmap="RdBu_r", vmin=-limit, vmax=limit, interpolation="nearest"
        )
        axis.set_title(label, fontsize=10)
        axis.axis("off")
    for index in range(len(panels), rows * columns):
        axes[index // columns][index % columns].axis("off")
    colorbar = figure.colorbar(image, ax=axes.ravel().tolist(), shrink=0.85)
    colorbar.set_label("signed log1p(ON - OFF) activity (shared scale)")
    figure.suptitle(title, fontsize=12)
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return -limit, limit


def ladder_plot(
    path_png: Path,
    path_svg: Path,
    ladder: list[dict[str, object]],
    pair_names: list[str],
) -> None:
    """Corrected reliability ladder: observed r per pair, mean r, ceiling, r_true.

    The plot makes the central finding legible: the cross-band correlations
    track the disjoint-block split-half ceiling as total averaging time grows,
    and the disattenuated r_true sits at or near 1 wherever it is defined.
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    durations = np.array([entry["duration_s"] for entry in ladder])
    mean = np.array([entry["mean_cross_correlation"] for entry in ladder])
    ceiling = np.array([entry["ceiling"] for entry in ladder])
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    axis.plot(durations, mean, "-o", color="0.1", linewidth=1.6, label="mean cross-band r")
    axis.plot(
        durations, ceiling, "--s", color="0.35", linewidth=1.4,
        label="split-half ceiling (disjoint blocks)",
    )
    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for slot, name in enumerate(pair_names):
        color = palette[slot % len(palette)]
        r_observed = np.array([entry["r_observed"][name] for entry in ladder])
        r_true = np.array([entry["r_true_disattenuated"][name] for entry in ladder])
        axis.plot(durations, r_observed, "-o", markersize=3, color=color, alpha=0.85,
                  label=f"{name} r_observed")
        axis.plot(durations, r_true, ":^", markersize=3, color=color, alpha=0.6,
                  label=f"{name} r_true (disattenuated)")
    axis.axhline(0.0, color="0.6", linewidth=0.8)
    axis.axhline(1.0, color="0.6", linewidth=0.8, linestyle=":")
    axis.set_xscale("log")
    axis.set_xlabel("total averaging time T (s)")
    axis.set_ylabel("Pearson r")
    axis.set_ylim(-0.15, 1.05)
    axis.legend(fontsize=7.5, loc="lower right")
    axis.set_title("Corrected reliability ladder: r(T) tracks the ceiling; r_true ~ 1")
    figure.tight_layout()
    figure.savefig(path_png, dpi=160)
    figure.savefig(path_svg)
    plt.close(figure)


def congruence_map_png(path: Path, congruence: np.ndarray, title: str) -> None:
    """Diverging heat map of a local congruence map on the fixed [-1, 1] scale."""
    import matplotlib

    matplotlib.use("Agg")
    import seaborn as sns
    from matplotlib import pyplot as plt

    figure, axis = plt.subplots(figsize=(7.5, 5.2))
    sns.heatmap(
        np.asarray(congruence, dtype=np.float64),
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0.0,
        square=True,
        linewidths=0.3,
        linecolor="white",
        cbar_kws={"label": "local gradient-field Pearson r"},
        ax=axis,
    )
    axis.set_title(title)
    axis.set_xlabel("window column")
    axis.set_ylabel("window row")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _decode_all(
    openevt: object,
    recordings: Sequence[tuple[str, Path]],
    polarity: str,
    accumulation_us: int,
    transform: str,
) -> dict[str, WindowArchive]:
    """Decode every recording once, in label order, with progress output."""
    archives: dict[str, WindowArchive] = {}
    for index, (label, path) in enumerate(recordings, start=1):
        print(
            f"[{index}/{len(recordings)}] Decoding {path.name} ({label})...",
            flush=True,
        )
        archives[label] = decode_windows(
            openevt, label, path, polarity, accumulation_us, transform
        )
    return archives


def _block_reliability(
    archive: WindowArchive,
    blocks: int,
    rows: slice,
    columns: slice,
    highpass_px: int,
    windows: int | None = None,
) -> tuple[float, int]:
    """Disjoint-block split-half reliability of one recording.

    Forms the contiguous block averages of the first ``windows`` windows (all
    of them when ``windows`` is None), runs them through the identical
    pipeline as the main correlation (crop, high-pass, per-frame support
    mask), correlates every block pair within the recording, and
    Spearman-Brown corrects the mean to the full-length estimate. Returns
    (reliability, number of non-empty blocks); NaN when fewer than two blocks
    yield a usable coefficient.

    ``windows`` must carry the truncated count at the duration being scored:
    the reliability of a T-second average is measured from halves OF that
    T-second span, not halves of the whole recording.
    """
    stop = archive.frame_count if windows is None else min(windows, archive.frame_count)
    bounds = [bounds for bounds in block_bounds(stop, blocks) if bounds[1] > bounds[0]]
    if len(bounds) < 2:
        return np.nan, len(bounds)
    block_frames = [
        high_pass(archive.frame(start, stop)[rows, columns], highpass_px)
        for start, stop in bounds
    ]
    supports = [frame != 0 for frame in block_frames]
    coefficients = [
        pair_pearson(
            block_frames[first], block_frames[second], supports[first], supports[second]
        )
        for first, second in combinations(range(len(block_frames)), 2)
    ]
    valid = [value for value in coefficients if not np.isnan(value)]
    if not valid:
        return np.nan, len(bounds)
    # Spearman-Brown takes the number of blocks (not the number of block
    # pairs): two blocks give one pair but a two-block prediction.
    return spearman_brown(float(np.mean(valid)), len(bounds)), len(bounds)


def _reliability_ladder_csv(
    path: Path,
    ladder: list[dict[str, object]],
    labels: list[str],
    pair_names: list[str],
) -> None:
    """Write the per-duration reliability/correlation ladder as CSV.

    Reliabilities are per recording; observed and disattenuated correlations
    are per cross-label pair, keyed exactly like the conclusions.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        header = ["duration_s", "mean_cross_correlation", "ceiling", "fraction_of_ceiling"]
        header += [f"self_reliability_{label}" for label in labels]
        header += [f"r_observed_{name}" for name in pair_names]
        header += [f"r_true_{name}" for name in pair_names]
        writer.writerow(header)
        for entry in ladder:
            row: list[object] = [
                entry["duration_s"],
                entry["mean_cross_correlation"],
                entry["ceiling"],
                entry["fraction_of_ceiling"],
            ]
            row += [entry["self_reliability"][label] for label in labels]
            row += [entry["r_observed"][name] for name in pair_names]
            row += [entry["r_true_disattenuated"][name] for name in pair_names]
            writer.writerow(row)


def _segments_csv(path: Path, labels: list[str], pair_names: list[str], segments: dict[str, object]) -> None:
    """Write the early-vs-late segment diagnostics as CSV."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["comparison", "r"])
        writer.writerow(["segment_windows", segments["segment_windows"]])
        writer.writerow(["segment_s", segments["segment_s"]])
        for label in labels:
            writer.writerow([f"{label}_early_vs_late", segments[f"{label}_early_vs_late"]])
            writer.writerow([f"{label}_best_shift_r", segments[f"{label}_best_shift_r"]])
            writer.writerow([f"{label}_best_shift_dy", segments[f"{label}_best_shift_dy"]])
            writer.writerow([f"{label}_best_shift_dx", segments[f"{label}_best_shift_dx"]])
        for name in pair_names:
            for suffix in ("early_early", "late_late", "early_late"):
                writer.writerow([f"{name}_{suffix}", segments[f"{name}_{suffix}"]])


def _congruence_csv(path: Path, pair_names: list[str], congruence: dict[str, dict[str, float]]) -> None:
    """Write the per-pair gradient-congruence statistics as CSV."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pair",
                "global_congruence",
                "half_cross_mean",
                "half_cross_sd",
                "window_median",
                "fraction_windows_above_0.7",
            ]
        )
        for name in pair_names:
            entry = congruence[name]
            writer.writerow(
                [
                    name,
                    entry["global_congruence"],
                    entry["half_cross_mean"],
                    entry["half_cross_sd"],
                    entry["window_median"],
                    entry["fraction_windows_above_0.7"],
                ]
            )


def _magnification_csv(
    path: Path,
    pair_names: list[str],
    sweep_rows: list[tuple[str, float, float, float]],
) -> None:
    """Write the per-pair magnification sweep curves as CSV."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair", "magnification", "gradient_congruence", "intensity_r"])
        for pair, magnification, gradient, intensity in sweep_rows:
            writer.writerow([pair, magnification, gradient, intensity])


def _write_conclusions(
    output: Path,
    labels: list[str],
    pair_names: list[str],
    pair_full: dict[str, dict[str, float]],
    control_summary: dict[str, object] | None,
    ladder: list[dict[str, object]],
    segments: dict[str, object] | None,
    sweep_summary: dict[str, object] | None,
) -> None:
    """Write the decision-tree conclusions (JSON for machines, MD for humans)."""
    conclusions = {
        "question": (
            "what is the repeatable component that the cross-band correlation "
            "converges to as total averaging time grows?"
        ),
        "established": (
            "a spatially structured component repeats across independent "
            "recordings and emerges from noise with averaging (attenuation "
            "arithmetic); per-sample measurement model is Shah et al. S4 "
            "(binned signed frame = dlogI/T +- 1)"
        ),
        "pairs": pair_full,
        "control": control_summary,
        "ladder": ladder,
        "segments": segments,
        "magnification": sweep_summary,
        "pending_branches": [
            "present-in-direct-display-image: no linear-camera capture of the "
            "display through the optics exists in the repository, so "
            "band-dependent scene coupling cannot be separated from DOE "
            "encoding with current data",
        ],
    }
    (output / "conclusions.json").write_text(
        json.dumps(conclusions, indent=2, default=float) + "\n", encoding="utf-8"
    )

    lines = [
        "# Source identification - conclusions",
        "",
        "## What is established",
        "",
        "- A spatially structured component of the signed event frames repeats",
        "  across independent recordings and emerges from noise as total",
        "  averaging time grows (the monotone r(T) rise is attenuation",
        "  arithmetic, not the spectra converging).",
        "- Per sample, each accumulation window is a threshold-quantized signed",
        "  measurement of the log-intensity change (Shah et al. S4).",
        "",
        "## Reliability ladder (corrected disjoint-block diagnostic)",
        "",
        "| duration (s) | mean cross r | ceiling | fraction of ceiling |",
        "|---|---|---|---|",
    ]
    for entry in ladder:
        lines.append(
            f"| {entry['duration_s']:g} | {entry['mean_cross_correlation']:.3f} | "
            f"{entry['ceiling']:.3f} | {entry['fraction_of_ceiling']:.3f} |"
        )
    lines += [
        "",
        "## Pair-level findings (full duration)",
        "",
        "| pair | r_obs | rel_a | rel_b | attenuation ceiling | r_true | gradient congruence |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in pair_names:
        entry = pair_full[name]
        lines.append(
            f"| {name} | {entry['r_observed']:.3f} | {entry['reliability_first']:.3f} | "
            f"{entry['reliability_second']:.3f} | {entry['attenuation_ceiling']:.3f} | "
            f"{entry['r_true']:.3f} | {entry['gradient_congruence_mean']:.3f} |"
        )
    lines += ["", "## Reading the numbers", ""]
    for name in pair_names:
        entry = pair_full[name]
        r_true = entry["r_true"]
        if not np.isfinite(r_true):
            lines.append(
                f"- **{name}**: reliability too low to disattenuate; the observed "
                "correlation carries no information about the true one."
            )
        elif r_true >= SHAPE_IDENTICAL_THRESHOLD:
            lines.append(
                f"- **{name}**: r_true = {r_true:.3f} - the repeatable components are "
                "shape-identical across bands. This is compatible with (a) a "
                "color-independent map (sensor artifact or shared geometry) and/or "
                "(b) color differences confined to the amplitude channel, which "
                "Pearson r is blind to by construction. Check the gradient "
                "congruence and the control overlap before calling this spectral."
            )
        elif r_true >= SHAPE_SHARED_THRESHOLD:
            lines.append(
                f"- **{name}**: r_true = {r_true:.3f} - substantial shared shape "
                "structure with a genuine color-specific component of order "
                f"{1 - r_true:.2f} of the shape variance. Consistent with spectral "
                "encoding, band-dependent scene coupling, or a mixture."
            )
        else:
            lines.append(
                f"- **{name}**: r_true = {r_true:.3f} - genuine cross-band shape "
                "differences dominate the repeatable component."
            )
    if control_summary:
        lines += ["", "## Control recordings (sensor-fixed component)", ""]
        for control_label, entry in control_summary.items():
            lines.append(
                f"- **{control_label}**: control self-reliability "
                f"{entry['control_reliability']:.3f}"
            )
            for color_label, color_entry in entry["colors"].items():
                lines.append(
                    f"  - vs {color_label}: map r {color_entry['map_r_vs_control']:.3f}, "
                    f"gradient congruence {color_entry['gradient_r_vs_control']:.3f}. "
                    "A high map correlation means the color recordings' repeatable "
                    "component overlaps the sensor-fixed map measured with little "
                    "scene signal; a low one argues it is scene- or encoding-driven."
                )
    if segments is not None:
        lines += [
            "",
            "## Early vs late segments (stationarity of the repeatable pattern)",
            "",
            f"- Segment length: {segments['segment_windows']} windows "
            f"({segments['segment_s']:.2f} s) at each end of every recording.",
            "- Per color, early-vs-late r "
            + ", ".join(
                f"{label} {segments[f'{label}_early_vs_late']:.3f}" for label in labels
            )
            + "; best over a +/- shift search: "
            + ", ".join(
                f"{label} {segments[f'{label}_best_shift_r']:.3f} at "
                f"(dy={segments[f'{label}_best_shift_dy']:+.0f}, dx={segments[f'{label}_best_shift_dx']:+.0f})"
                for label in labels
            )
            + ". A low value that the shift search cannot restore means the",
            "  recording's pattern decorrelates in place over its span (slow",
            "  sensor-state/display settling), rather than sliding mechanically,",
            "  so short averages measure different patterns rather than noisy",
            "  versions of one pattern.",
            "- Cross-band, early-early vs late-late r: "
            + ", ".join(
                f"{name} {segments[f'{name}_early_early']:.3f}/{segments[f'{name}_late_late']:.3f}"
                for name in pair_names
            )
            + ". If early-early sits well below late-late, the early segment",
            "  carries extra band-specific structure and the monotone r(T) rise",
            "  reflects progressive dilution of that early segment - not noise",
            "  attenuation of a fixed shared pattern.",
        ]
    if sweep_summary is not None:
        lines += [
            "",
            "## Magnification sweep (lambda-scaling test)",
            "",
            "- A DOE far-field pattern scales radially with wavelength, so a",
            "  congruence peak at m = lambda_a/lambda_b (e.g. ~0.75 for a 460 nm",
            "  primary against a 610 nm primary) identifies diffractive spectral",
            "  structure. A peak at m = 1 says the shared fine structure is",
            "  wavelength-independent: direct-image geometry, display content,",
            "  or non-diffractive sensor structure.",
        ]
        for name in pair_names:
            entry = sweep_summary[name]
            lines.append(
                f"- **{name}**: gradient peak m = {entry['argmax_gradient_m']:.2f} "
                f"(r {entry['peak_gradient']:.3f}; r at m=1: "
                f"{entry['gradient_at_m1']:.3f}), intensity peak m = "
                f"{entry['argmax_intensity_m']:.2f} (r {entry['peak_intensity']:.3f})."
            )
    lines += [
        "",
        "## Pending branches",
        "",
        "- Present-in-direct-display-image: requires a linear-camera capture of",
        "  the display through the optics, which does not exist in the",
        "  repository; band-dependent scene coupling therefore cannot yet be",
        "  separated from DOE encoding.",
        "",
        "## What would settle the remainder",
        "",
        "- Blank/uniform-display control recordings (bounds the sensor-fixed map).",
        "- Same-color repeat recordings (within-band reproducibility ceiling).",
        "- A drive incommensurate with 60 Hz (display-refresh phase-locking test).",
        "- A linear-camera capture through the same optics (direct-image branch).",
        "",
    ]
    (output / "conclusions.md").write_text("\n".join(lines), encoding="utf-8")


def analyze(args: argparse.Namespace) -> Path:
    """Run the source-identification analysis and write the results directory."""
    recordings = discover_recordings(args.pattern)
    labels = [label for label, _ in recordings]
    if len(labels) < 2:
        raise ValueError("at least two recordings are required for cross-band comparison")
    pair_indices = [
        (first, second)
        for first, second in combinations(range(len(labels)), 2)
        if labels[first] != labels[second]
    ]
    pair_names = [f"{labels[first]}_{labels[second]}" for first, second in pair_indices]
    controls = discover_recordings(args.control_pattern) if args.control_pattern else []

    output = args.output.expanduser().resolve()
    frames_dir = output / "frames"
    maps_dir = output / "gradient_congruence_maps"
    frames_dir.mkdir(parents=True, exist_ok=True)
    maps_dir.mkdir(parents=True, exist_ok=True)

    accumulation_us = int(round(args.accumulation_ms * 1_000))
    durations_s = sorted(set(args.durations))
    duration_full = durations_s[-1]

    with load_openevt(args.openevt_library) as openevt:
        archives = _decode_all(
            openevt, recordings, args.polarity, accumulation_us, args.transform
        )
        control_archives = (
            _decode_all(openevt, controls, args.polarity, accumulation_us, args.transform)
            if controls
            else {}
        )

    ladder: list[dict[str, object]] = []
    crop_window: tuple[slice, slice] | None = None
    full_frames: dict[str, np.ndarray] = {}
    cropped_full: dict[str, np.ndarray] = {}
    cropped_full_support: dict[str, np.ndarray] = {}
    half_frames: dict[str, list[np.ndarray]] = {}

    for duration in durations_s:
        truncated = {
            label: min(window_count(duration, args.accumulation_ms), archive.frame_count)
            for label, archive in archives.items()
        }
        frames = {
            label: archives[label].frame(0, truncated[label]) for label in labels
        }
        stack = np.stack([frames[label] for label in labels])
        rows, columns = signal_window(stack, args.crop_margin)
        crop_window = (rows, columns)
        cropped = stack[:, rows, columns]
        support = cropped != 0
        filtered = np.stack([high_pass(frame, args.highpass_px) for frame in cropped])
        try:
            correlation = pearson_matrix(filtered, support)
        except ValueError as error:
            print(f"  duration={duration:g} s: no coefficient ({error})", flush=True)
            continue

        r_observed = {
            name: float(correlation[first, second])
            for name, (first, second) in zip(pair_names, pair_indices, strict=True)
        }
        mean_cross = float(
            np.mean([r_observed[name] for name in pair_names])
        )
        reliabilities: dict[str, float] = {}
        for label in labels:
            reliability, _ = _block_reliability(
                archives[label], args.splits, rows, columns, args.highpass_px,
                windows=truncated[label],
            )
            reliabilities[label] = reliability
        valid_reliabilities = [
            value for value in reliabilities.values() if np.isfinite(value)
        ]
        ceiling = float(np.mean(valid_reliabilities)) if valid_reliabilities else np.nan
        fraction = (
            mean_cross / ceiling if np.isfinite(ceiling) and ceiling > 0 else np.nan
        )

        for label in labels:
            np.save(frames_dir / f"{label}_activity_{duration:g}s.npy", frames[label])
            np.save(frames_dir / f"{label}_processed_{duration:g}s.npy", filtered[labels.index(label)])
        if duration == duration_full:
            for label in labels:
                write_grayscale_png(
                    frames_dir / f"{label}_activity_{duration:g}s.png", frames[label]
                )
                write_grayscale_png(
                    frames_dir / f"{label}_processed_{duration:g}s.png",
                    filtered[labels.index(label)],
                )
            np.save(output / "correlation_full.npy", correlation)
            write_matrix_csv(output / "correlation_full.csv", correlation, labels)
            write_heatmap_svg(
                output / "correlation_full_heatmap.svg", correlation, labels
            )

        r_true = {
            name: disattenuated(
                r_observed[name],
                reliabilities[labels[first]],
                reliabilities[labels[second]],
            )
            for name, (first, second) in zip(pair_names, pair_indices, strict=True)
        }
        ladder.append(
            {
                "duration_s": duration,
                "windows_per_recording": truncated,
                "crop_rows": [rows.start, rows.stop],
                "crop_columns": [columns.start, columns.stop],
                "mean_cross_correlation": mean_cross,
                "r_observed": r_observed,
                "self_reliability": reliabilities,
                "ceiling": ceiling,
                "fraction_of_ceiling": fraction,
                "r_true_disattenuated": r_true,
            }
        )
        ceiling_text = f"{ceiling:.3f}" if np.isfinite(ceiling) else "NaN"
        detail = "  ".join(f"{name}={r_observed[name]:.3f}" for name in pair_names)
        print(
            f"  duration={duration:g} s: {detail}  mean={mean_cross:.3f}  "
            f"ceiling={ceiling_text}",
            flush=True,
        )
        if duration == duration_full:
            full_frames = frames
            cropped_full = {
                label: frames[label][rows, columns] for label in labels
            }
            cropped_full_support = {
                label: cropped_full[label] != 0 for label in labels
            }
            half_frames = {
                label: [
                    archives[label].frame(start, stop)
                    for start, stop in block_bounds(truncated[label], args.splits)
                    if stop > start
                ]
                for label in labels
            }

    if not ladder or crop_window is None:
        raise ValueError("no duration produced a measurable correlation")
    rows, columns = crop_window

    # ---- Gradient congruence at the full duration (no high-pass, by design) ----
    congruence: dict[str, dict[str, float]] = {}
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        frame_first = cropped_full[labels[first]]
        frame_second = cropped_full[labels[second]]
        global_value = gradient_congruence(
            frame_first,
            frame_second,
            cropped_full_support[labels[first]],
            cropped_full_support[labels[second]],
        )
        half_values = [
            gradient_congruence(
                half_frames[labels[first]][index_first][rows, columns],
                half_frames[labels[second]][index_second][rows, columns],
                half_frames[labels[first]][index_first][rows, columns] != 0,
                half_frames[labels[second]][index_second][rows, columns] != 0,
            )
            for index_first in range(len(half_frames[labels[first]]))
            for index_second in range(len(half_frames[labels[second]]))
        ]
        valid_halves = [value for value in half_values if np.isfinite(value)]
        half_mean = float(np.mean(valid_halves)) if valid_halves else np.nan
        half_sd = float(np.std(valid_halves)) if len(valid_halves) > 1 else np.nan
        # The half-cross combinations use independent time spans, so their mean
        # is the unbiased congruence estimate and their spread its noise scale;
        # the full-frame value shares both halves' noise and sits slightly high.
        congruence_map = window_congruence_map(
            frame_first,
            frame_second,
            cropped_full_support[labels[first]],
            cropped_full_support[labels[second]],
            args.congruence_window,
        )
        np.save(maps_dir / f"{name}_congruence_map.npy", congruence_map)
        congruence_map_png(
            maps_dir / f"{name}_congruence_map.png",
            congruence_map,
            f"{name}: local gradient-field congruence (no high-pass)",
        )
        finite_map = np.isfinite(congruence_map)
        congruence[name] = {
            "global_congruence": global_value,
            "half_cross_mean": half_mean,
            "half_cross_sd": half_sd,
            "window_median": float(np.nanmedian(congruence_map))
            if finite_map.any()
            else np.nan,
            "fraction_windows_above_0.7": float(np.mean(congruence_map[finite_map] > 0.7))
            if finite_map.any()
            else np.nan,
        }
        print(
            f"  gradient congruence {name}: global={global_value:.3f} "
            f"half-cross={half_mean:.3f}+-{half_sd:.3f}",
            flush=True,
        )
    _congruence_csv(output / "gradient_congruence.csv", pair_names, congruence)

    # ---- Early vs late segments: is the emerging structure stationary? ----
    segment = min(
        window_count(args.segment_s, args.accumulation_ms),
        min(archive.frame_count for archive in archives.values()) // 4,
    )
    early = {
        label: high_pass(
            archives[label].frame(0, segment)[rows, columns], args.highpass_px
        )
        for label in labels
    }
    late = {
        label: high_pass(
            archives[label].frame(
                archives[label].frame_count - segment, archives[label].frame_count
            )[rows, columns],
            args.highpass_px,
        )
        for label in labels
    }
    segments: dict[str, object] = {
        "segment_windows": segment,
        "segment_s": segment * accumulation_us / 1_000_000.0,
    }
    for label in labels:
        search = best_shift_r(
            early[label],
            late[label],
            early[label] != 0,
            late[label] != 0,
            args.max_shift_px,
        )
        segments[f"{label}_early_vs_late"] = search["r_at_zero"]
        segments[f"{label}_best_shift_r"] = search["r"]
        segments[f"{label}_best_shift_dy"] = search["dy"]
        segments[f"{label}_best_shift_dx"] = search["dx"]
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        segments[f"{name}_early_early"] = pair_pearson(
            early[labels[first]], early[labels[second]],
            early[labels[first]] != 0, early[labels[second]] != 0,
        )
        segments[f"{name}_late_late"] = pair_pearson(
            late[labels[first]], late[labels[second]],
            late[labels[first]] != 0, late[labels[second]] != 0,
        )
        segments[f"{name}_early_late"] = pair_pearson(
            early[labels[first]], late[labels[second]],
            early[labels[first]] != 0, late[labels[second]] != 0,
        )
    # Save the segment frames on one shared scale: the honest comparison is
    # early-vs-late on identical axes, which per-frame normalization hides.
    segment_panels = [
        (f"{label} early ({segment} windows)", early[label]) for label in labels
    ] + [(f"{label} late", late[label]) for label in labels]
    segment_low, segment_high = sheet_png(
        output / f"frames/segments_sheet_{duration_full:g}s.png",
        f"Early vs late segments ({segment} windows = "
        f"{segments['segment_s']:.2f} s each, 64 px high-pass, shared scale)",
        segment_panels,
        columns=len(labels),
    )
    for label in labels:
        np.save(frames_dir / f"{label}_segment_early_{duration_full:g}s.npy", early[label])
        np.save(frames_dir / f"{label}_segment_late_{duration_full:g}s.npy", late[label])
        write_grayscale_png(
            frames_dir / f"{label}_segment_early_{duration_full:g}s.png",
            early[label], segment_low, segment_high,
        )
        write_grayscale_png(
            frames_dir / f"{label}_segment_late_{duration_full:g}s.png",
            late[label], segment_low, segment_high,
        )
    _segments_csv(output / "segments.csv", labels, pair_names, segments)
    stationarity = ", ".join(
        f"{label} {segments[f'{label}_early_vs_late']:.3f}" for label in labels
    )
    print(f"  segments ({segment} windows each end): early-vs-late r: {stationarity}", flush=True)

    # ---- Magnification sweep: does the shared fine structure scale with lambda? ----
    grid = np.arange(args.sweep_min, args.sweep_max + args.sweep_step / 2, args.sweep_step)
    sweep_summary: dict[str, object] = {}
    sweep_rows: list[tuple[str, float, float, float]] = []
    sweep_tile = min(
        args.sweep_tile, min(min(archives[label].shape) for label in labels)
    )
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        combined = full_frames[labels[first]] + full_frames[labels[second]]
        center_row, center_column = disk_centroid(combined)
        sweep = magnification_sweep(
            full_frames[labels[first]],
            full_frames[labels[second]],
            center_row,
            center_column,
            sweep_tile,
            grid,
            args.highpass_px,
        )
        sweep_plot(output / f"magnification_sweep_{name}.png", name, sweep)
        sweep_rows.extend(
            (name, magnification, gradient, intensity)
            for magnification, gradient, intensity in sweep
        )
        gradients = np.array([row[1] for row in sweep])
        intensities = np.array([row[2] for row in sweep])
        finite_gradients = np.isfinite(gradients)
        finite_intensities = np.isfinite(intensities)
        one_row = int(np.argmin(np.abs(grid - 1.0)))
        sweep_summary[name] = {
            "centroid_row": center_row,
            "centroid_column": center_column,
            "tile": sweep_tile,
            "argmax_gradient_m": float(grid[finite_gradients][np.nanargmax(gradients[finite_gradients])])
            if finite_gradients.any()
            else np.nan,
            "peak_gradient": float(np.nanmax(gradients)) if finite_gradients.any() else np.nan,
            "gradient_at_m1": gradients[one_row],
            "argmax_intensity_m": float(grid[finite_intensities][np.nanargmax(intensities[finite_intensities])])
            if finite_intensities.any()
            else np.nan,
            "peak_intensity": float(np.nanmax(intensities)) if finite_intensities.any() else np.nan,
        }
        print(
            f"  magnification {name}: gradient peak m={sweep_summary[name]['argmax_gradient_m']:.2f} "
            f"(at m=1: {sweep_summary[name]['gradient_at_m1']:.3f}), "
            f"intensity peak m={sweep_summary[name]['argmax_intensity_m']:.2f}",
            flush=True,
        )
    _magnification_csv(output / "magnification_sweep.csv", pair_names, sweep_rows)

    # ---- Control recordings: bound the sensor-fixed component ----
    control_summary: dict[str, object] | None = None
    control_processed_frames: dict[str, np.ndarray] = {}
    if control_archives:
        control_summary = {}
        for control_label, control_archive in control_archives.items():
            control_count = min(
                window_count(duration_full, args.accumulation_ms),
                control_archive.frame_count,
            )
            control_frame_raw = control_archive.frame(0, control_count)[rows, columns]
            control_frame_processed = high_pass(control_frame_raw, args.highpass_px)
            control_support = control_frame_raw != 0
            np.save(
                frames_dir / f"{control_label}_activity_{duration_full:g}s.npy",
                control_archive.frame(0, control_count),
            )
            np.save(
                frames_dir / f"{control_label}_processed_{duration_full:g}s.npy",
                control_frame_processed,
            )
            write_grayscale_png(
                frames_dir / f"{control_label}_activity_{duration_full:g}s.png",
                control_archive.frame(0, control_count),
            )
            write_grayscale_png(
                frames_dir / f"{control_label}_processed_{duration_full:g}s.png",
                control_frame_processed,
            )
            control_processed_frames[control_label] = control_frame_processed
            control_reliability, _ = _block_reliability(
                control_archive, args.splits, rows, columns, args.highpass_px,
                windows=control_count,
            )
            per_color: dict[str, object] = {}
            for label in labels:
                color_support = cropped_full_support[label]
                map_mask = color_support | control_support
                # Map correlation runs through the standard high-passed pipeline:
                # the high-pass keeps the pixel-scale artifact and only removes
                # smooth geometry, so this r is the artifact-overlap estimate.
                map_r = safe_pearson(
                    control_frame_processed[map_mask], cropped_full[label][map_mask]
                )
                gradient_r = gradient_congruence(
                    control_frame_raw, cropped_full[label], control_support, color_support
                )
                per_color[label] = {
                    "map_r_vs_control": map_r,
                    "gradient_r_vs_control": gradient_r,
                }
            control_summary[control_label] = {
                "control_reliability": control_reliability,
                "colors": per_color,
            }
            overlap_text = ", ".join(
                f"{label}: map {per_color[label]['map_r_vs_control']:.3f}, "
                f"gradient {per_color[label]['gradient_r_vs_control']:.3f}"
                for label in labels
            )
            print(
                f"  control {control_label}: reliability={control_reliability:.3f}  {overlap_text}",
                flush=True,
            )

    # ---- Shared-scale frame sheets and the reliability-ladder figure ----
    activity_panels = [
        (f"{label} (signed log1p)", full_frames[label]) for label in labels
    ] + [
        (
            f"{control_label} (control)",
            control_archives[control_label].frame(
                0,
                min(
                    window_count(duration_full, args.accumulation_ms),
                    control_archives[control_label].frame_count,
                ),
            ),
        )
        for control_label in control_archives
    ]
    sheet_png(
        output / f"frames/activity_sheet_{duration_full:g}s.png",
        f"Full-duration activity frames on a shared scale ({duration_full:g} s)",
        activity_panels,
        columns=len(labels),
    )
    processed_panels = [
        (f"{label} (64 px high-pass)", cropped_full[label]) for label in labels
    ] + [
        (f"{control_label} (control)", control_processed_frames[control_label])
        for control_label in control_processed_frames
    ]
    sheet_png(
        output / f"frames/processed_sheet_{duration_full:g}s.png",
        f"High-passed frames on a shared scale ({duration_full:g} s)",
        processed_panels,
        columns=len(labels),
    )
    ladder_plot(output / "reliability_ladder.png", output / "reliability_ladder.svg", ladder, pair_names)

    last = ladder[-1]
    pair_full: dict[str, dict[str, float]] = {}
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        reliability_first = last["self_reliability"][labels[first]]
        reliability_second = last["self_reliability"][labels[second]]
        pair_full[name] = {
            "r_observed": last["r_observed"][name],
            "reliability_first": reliability_first,
            "reliability_second": reliability_second,
            "attenuation_ceiling": float(
                np.sqrt(max(reliability_first, 0.0) * max(reliability_second, 0.0))
            ),
            "r_true": last["r_true_disattenuated"][name],
            "gradient_congruence_global": congruence[name]["global_congruence"],
            "gradient_congruence_mean": congruence[name]["half_cross_mean"],
            "gradient_congruence_sd": congruence[name]["half_cross_sd"],
            "window_median": congruence[name]["window_median"],
            "fraction_windows_above_0.7": congruence[name]["fraction_windows_above_0.7"],
        }

    _reliability_ladder_csv(output / "reliability.csv", ladder, labels, pair_names)
    _write_conclusions(
        output, labels, pair_names, pair_full, control_summary, ladder,
        segments, sweep_summary,
    )

    metadata = {
        "method": (
            "Source identification for the repeatable component of the converged "
            "signed cross-band correlation: disjoint-time-block split-half "
            "reliability (Spearman-Brown), disattenuated cross-band correlation "
            "(Spearman 1904), signed-Sobel gradient congruence on unfiltered "
            "frames (global + windowed), and optional control-recording overlap"
        ),
        "pattern": args.pattern,
        "control_pattern": args.control_pattern,
        "polarity": args.polarity,
        "transform": args.transform,
        "accumulation_ms": args.accumulation_ms,
        "splits": args.splits,
        "split_scheme": "contiguous disjoint time blocks",
        "crop_margin_px": args.crop_margin,
        "highpass_px": args.highpass_px,
        "congruence_window_px": args.congruence_window,
        "durations_s": list(durations_s),
        "labels": labels,
        "controls": list(control_archives),
        "recordings": [archives[label].metadata(accumulation_us) for label in labels],
        "control_recordings": [
            control_archives[label].metadata(accumulation_us)
            for label in control_archives
        ],
        "ladder": ladder,
    }
    (output / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2, default=float) + "\n", encoding="utf-8"
    )
    print(f"Wrote source-identification analysis to {output}")
    return output


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        default="data/raw/evt3_raw/circle_*.raw",
        help="glob for the recordings under investigation (default: %(default)s)",
    )
    parser.add_argument(
        "--control-pattern",
        default=None,
        help="optional glob for blank/dark control recordings (e.g. "
        "data/raw/evt3_raw/baseline.raw); structure that repeats in a control "
        "is sensor-fixed by construction",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/source_identification"),
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--accumulation-ms",
        type=positive_float,
        default=1.0,
        help="accumulation interval in milliseconds (default: %(default)s)",
    )
    parser.add_argument(
        "--durations",
        type=parse_float_list,
        default="0.5,1,2.5,5",
        help="comma-separated durations in seconds; the longest one is the "
        "converged state the congruence test runs on (default: %(default)s)",
    )
    parser.add_argument(
        "--polarity",
        choices=("both", "on", "off", "signed"),
        default="signed",
        help="event values accumulated into each window; signed (ON - OFF) is "
        "the Shah et al. binned event frame (default: %(default)s)",
    )
    parser.add_argument(
        "--transform",
        choices=("raw", "sqrt", "log1p"),
        default="log1p",
        help="variance-stabilizing transform before averaging (default: %(default)s)",
    )
    parser.add_argument(
        "--splits",
        type=positive_int,
        default=2,
        help="number of contiguous disjoint time blocks for the split-half "
        "reliability; 2 = time halves (default: %(default)s)",
    )
    parser.add_argument(
        "--crop-margin",
        type=positive_int,
        default=48,
        help="padding in pixels around the detected signal window (default: %(default)s)",
    )
    parser.add_argument(
        "--highpass-px",
        type=int,
        default=64,
        help="high-pass kernel for the main correlation and the reliability "
        "blocks; the gradient congruence test never high-passes (default: %(default)s)",
    )
    parser.add_argument(
        "--congruence-window",
        type=positive_int,
        default=64,
        help="window size in pixels for the local congruence maps (default: %(default)s)",
    )
    parser.add_argument(
        "--segment-s",
        type=positive_float,
        default=0.5,
        help="length in seconds of the early and late segments used for the "
        "stationarity diagnostic (default: %(default)s)",
    )
    parser.add_argument(
        "--max-shift-px",
        type=positive_int,
        default=12,
        help="half-width of the integer shift search in the stationarity "
        "diagnostic (default: %(default)s)",
    )
    parser.add_argument(
        "--sweep-tile",
        type=positive_int,
        default=400,
        help="side length in pixels of the square tile compared across "
        "magnifications (default: %(default)s)",
    )
    parser.add_argument(
        "--sweep-min",
        type=float,
        default=0.6,
        help="lowest radial magnification in the lambda-scaling sweep "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--sweep-max",
        type=float,
        default=1.4,
        help="highest radial magnification in the lambda-scaling sweep "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--sweep-step",
        type=float,
        default=0.02,
        help="magnification step of the lambda-scaling sweep (default: %(default)s)",
    )
    parser.add_argument(
        "--openevt-library",
        type=Path,
        help="matching libopenevt.so; auto-detected from openevt/target/release",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    analyze(make_parser().parse_args(argv))


if __name__ == "__main__":
    main()