# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Spectrometer ground-truth targets for Dirichlet spectral unmixing.

The user decision of 2026-10-27 (see outputs/investigation/FINDINGS.md §4)
replaces the plan's "amplitude_corrected only" rule: every paired spectrum is
normalized against ``reference.parquet`` following the documented workflow in
``src/hypercam/notebooks/spectra/analysis.py``:

1. join the signal and the reference on the (identical) wavelength axis;
2. restrict to the analysis window (420-680 nm by default);
3. ``transmittance = clipped signal counts / reference counts``;
4. rolling median (width 3) then Savitzky-Golay (window 40, poly 2);
5. clip negatives and renormalize.

The result is converted to a probability simplex (the Dirichlet target) by
dividing by the sum. Two alternative target modes are wired for comparison:
``amplitude_corrected_counts`` (raw counts of corrected-era files only) and
``raw_counts`` (all raw counts); each is clipped and simplex-normalized.

Degenerate targets are rejected, not silently trained on, using the raw
count noise metrics above (per the dataset author: SNR mean/std and the
positive-vs-negative mean asymmetry — noise is symmetric about zero):
- NOISE: near-zero SNR AND no positive/negative asymmetry (a dark frame).
Real curves — even gentle transmittance dips — all pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy.signal import savgol_filter

TARGET_MODES = ("reference_transmittance", "amplitude_corrected_counts", "raw_counts")


@dataclass
class SpectrumRecord:
    """One spectrum file reduced to the facts the pipeline needs."""

    path: Path
    wavelength_nm: np.ndarray
    counts: np.ndarray
    amplitude_corrected: bool
    acquired_utc_ms: int
    exposure_ms: float
    hw_average: int
    median_counts: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.median_counts = float(np.median(self.counts))


def load_spectrum(path: Path) -> SpectrumRecord:
    """Read one spectrum file; the extension lies (both are parquet bytes).

    The 2026-10-19 era files end in ``.csv`` but contain Parquet (magic
    ``PAR1``), so the loader always uses the parquet reader.
    """
    table = pq.read_table(path)
    columns = set(table.column_names)
    required = {
        "wavelength_nm",
        "intensity_counts",
        "amplitude_corrected",
        "acquired_utc_ms",
        "exposure_ms",
        "hw_average",
        "spectrum_index",
    }
    missing = required - columns
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    data = table.to_pydict()
    unique_indices = set(data["spectrum_index"])
    if len(unique_indices) != 1:
        raise ValueError(
            f"{path.name} holds {len(unique_indices)} spectra; the pipeline assumes one"
        )
    return SpectrumRecord(
        path=path,
        wavelength_nm=np.asarray(data["wavelength_nm"], dtype=np.float64),
        counts=np.asarray(data["intensity_counts"], dtype=np.float64),
        amplitude_corrected=bool(np.all(np.asarray(data["amplitude_corrected"], dtype=bool))),
        acquired_utc_ms=int(data["acquired_utc_ms"][0]),
        exposure_ms=float(data["exposure_ms"][0]),
        hw_average=int(data["hw_average"][0]),
    )


def load_reference(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return the reference spectrum's (wavelength_nm, counts) arrays."""
    record = load_spectrum(path)
    return record.wavelength_nm, np.clip(record.counts, 0.0, None)


def smooth_transmittance(transmittance: np.ndarray) -> np.ndarray:
    """Rolling median (3) then Savitzky-Golay (40, poly 2), as documented."""
    median_filtered = np.asarray(
        [
            np.median(transmittance[max(0, index - 1) : index + 2])
            for index in range(len(transmittance))
        ]
    )
    return savgol_filter(median_filtered, window_length=40, polyorder=2)


def build_target(
    spectrum: SpectrumRecord,
    reference: tuple[np.ndarray, np.ndarray],
    *,
    mode: str,
    window_min_nm: float,
    window_max_nm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelength_nm, simplex_target) for one spectrum.

    Raises ``ValueError`` for modes that the file cannot serve (e.g. asking
    for corrected counts from an uncorrected-era file).
    """
    if mode not in TARGET_MODES:
        raise ValueError(f"unknown target mode {mode!r}; expected one of {TARGET_MODES}")
    if mode == "amplitude_corrected_counts" and not spectrum.amplitude_corrected:
        raise ValueError(f"{spectrum.path.name} is not amplitude corrected")

    wavelength = spectrum.wavelength_nm
    counts = np.clip(spectrum.counts, 0.0, None)
    window = (wavelength >= window_min_nm) & (wavelength <= window_max_nm)
    wl_w, counts_w = wavelength[window], counts[window]

    if mode == "reference_transmittance":
        reference_wl, reference_counts = reference
        ref_w = np.interp(wl_w, reference_wl, reference_counts)
        transmittance = counts_w / np.clip(ref_w, 1e-9, None)
        values = np.clip(smooth_transmittance(transmittance), 0.0, None)
    elif mode == "raw_counts":
        values = counts_w
    else:  # amplitude_corrected_counts
        values = counts_w

    total = float(values.sum())
    if total <= 0:
        raise ValueError(f"{spectrum.path.name}: target sums to zero")
    return wl_w, values / total


def shape_metrics(target: np.ndarray) -> dict[str, float]:
    """Degeneracy metrics used by the manifest gates."""
    peak_to_mean = float(target.max() * len(target))
    positive = target[target > 0]
    entropy = float(-(positive * np.log(positive)).sum())
    return {
        "peak_to_mean": peak_to_mean,
        "normalized_entropy": entropy / np.log(len(target)),
    }


def noise_metrics(counts: np.ndarray) -> dict[str, float]:
    """Signal-vs-noise metrics on the RAW (uncorrected) counts.

    A pure-noise spectrum (dark frame, no light) is symmetric about zero:
    the mean of its positive counts equals the mean of its negative counts,
    so ``positive_minus_negative`` is ~0, and its overall ``mean/std``
    (SNR) is tiny. A real spectrum has a strong positive DC level and almost
    no negative excursions, so both metrics are large. The SNR (mean/std) is
    the more robust of the two (per the dataset author).
    """
    positive = counts[counts > 0]
    negative = counts[counts < 0]
    pos_mean = float(positive.mean()) if positive.size else 0.0
    neg_mean = float(abs(negative.mean())) if negative.size else 0.0
    std = float(counts.std())
    return {
        "snr_mean_over_std": (float(counts.mean()) / std) if std > 0 else 0.0,
        "positive_minus_negative": pos_mean - neg_mean,
        "positive_mean": pos_mean,
        "negative_mean": neg_mean,
    }


def gate_reason(
    spectrum: SpectrumRecord,
    target: np.ndarray,
    *,
    min_snr: float = 0.4,
    min_positive_minus_negative: float = 5.0,
) -> str | None:
    """Return why this pair is noise (not usable ground truth), or None.

    Rejects a spectrum only when BOTH raw-count noise metrics say "no
    signal": near-zero SNR and no positive/negative asymmetry. Real spectral
    curves — even gentle transmittance dips — pass, so the gate no longer
    discards valid data the way a peak/mean threshold did.
    """
    metrics = noise_metrics(spectrum.counts)
    if (
        metrics["snr_mean_over_std"] < min_snr
        and metrics["positive_minus_negative"] < min_positive_minus_negative
    ):
        return (
            f"NOISE: snr={metrics['snr_mean_over_std']:.3f}<{min_snr} and "
            f"pos-neg={metrics['positive_minus_negative']:.1f}<{min_positive_minus_negative}"
        )
    return None


if __name__ == "__main__":
    # Selftest: build targets for one file of each era plus the known dark
    # file, assert simplex invariants and that the gates flag them correctly.
    project_root = Path(__file__).resolve().parent
    repo_root = project_root.parents[3]
    spectra_dir = repo_root / "data/raw/spectra"
    reference_path = spectra_dir / "reference.parquet"
    if not reference_path.is_file():
        print("selftest skipped: data/raw/spectra/reference.parquet not present")
        raise SystemExit(0)
    reference = load_reference(reference_path)

    cases = {
        "2026-10-19_14-43-49.csv": ("csv-era corrected", False),
        "2026-10-21_11-38-30.parquet": ("parquet-era uncorrected", False),
        "2026-10-20_14-46-50.parquet": ("known dark/noise file", True),
    }
    for name, (label, expect_gate) in cases.items():
        path = spectra_dir / name
        if not path.is_file():
            print(f"  missing {name}, skipping")
            continue
        spectrum = load_spectrum(path)
        wl, target = build_target(
            spectrum, reference, mode="reference_transmittance",
            window_min_nm=420.0, window_max_nm=680.0,
        )
        assert np.isclose(target.sum(), 1.0), f"{name}: not a simplex"
        assert (target >= 0).all(), f"{name}: negative target mass"
        assert len(wl) == len(target) and np.all(np.diff(wl) > 0)
        reason = gate_reason(spectrum, target)
        flagged = reason is not None
        metrics = noise_metrics(spectrum.counts)
        print(
            f"  {label}: snr={metrics['snr_mean_over_std']:.2f} "
            f"pos-neg={metrics['positive_minus_negative']:.1f} gate={reason or 'pass'}"
        )
        assert flagged is expect_gate, f"{name} gate verdict wrong: {reason}"
    print("targets selftest OK")
