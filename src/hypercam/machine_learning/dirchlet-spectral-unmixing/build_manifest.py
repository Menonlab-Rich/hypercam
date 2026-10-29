# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Build the paired spectra/recordings manifest with gates and split labels.

Pairing rule (verified on all 265 pairs in Phase 0): the event recording
``<stem>_<capture>.raw`` (capture time uses colons) joins the spectrum
``<stem>.csv`` or ``<stem>.parquet`` on ``<stem> = %Y-%m-%d_%H-%M-%S``.
Band labels come from the spectrum content (weighted-mean lambda of the raw
counts over the full axis, binned by ``--band-bin``); filenames carry no
band information.

Outputs (under ``outputs/manifests/``):
- ``manifest.csv``     one row per paired recording with gate + split;
- ``gates.json``       machine-readable pass/fail summary (train.py refuses
                       to start on failed gates unless ``force=true``);
- ``targets/<stem>.npy`` the simplex target per pair (float32);
- ``wavelength_grid.npy`` the shared windowed lambda axis (defines K).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import targets as targets_mod

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parents[3]
DEFAULT_SPECTRA = REPO_ROOT / "data/raw/spectra"
DEFAULT_EVENTS = REPO_ROOT / "data/raw/evt3"
DEFAULT_OUT = PROJECT_ROOT / "outputs/manifests"

STEM_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
EVENT_STEM = re.compile(
    r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})$"
)


def discover_pairs(spectra_dir: Path, events_dir: Path) -> dict[str, dict[str, Path]]:
    """Join spectra and recordings on the shared timestamp stem."""
    pairs: dict[str, dict[str, Path]] = {}
    for path in sorted(spectra_dir.iterdir()):
        if path.name == "reference.parquet" or path.suffix not in (".csv", ".parquet"):
            continue
        match = STEM_PATTERN.match(path.stem)
        if not match:
            continue
        pairs.setdefault(match.group(1), {})["spectrum"] = path
    for path in sorted(events_dir.glob("*.raw")):
        match = EVENT_STEM.match(path.stem)
        if not match:
            continue
        stem = match.group(1)
        entry = pairs.setdefault(stem, {})
        entry["recording"] = path
        triggers = path.with_name(path.name[: -len(".raw")] + "_triggers.csv")
        if triggers.is_file():
            entry["triggers"] = triggers
    return pairs


def assign_band_splits(
    band_of_stem: dict[str, int], rng: np.random.Generator
) -> dict[str, str]:
    """Hold out whole stimulus bands: smallest band -> val, next -> test.

    With fewer than three populated bands, band-level holdout is impossible
    and the caller must fall back to stratified splitting.
    """
    counts = Counter(band_of_stem.values())
    ordered = sorted(counts, key=lambda band: (counts[band], band))
    val_band, test_band = ordered[0], ordered[1]
    return {
        stem: ("val" if band == val_band else "test" if band == test_band else "train")
        for stem, band in band_of_stem.items()
    }


def assign_stratified_splits(
    band_of_stem: dict[str, int],
    rng: np.random.Generator,
    val_fraction: float,
    test_fraction: float,
) -> dict[str, str]:
    """Random split within each band so every band appears in every split."""
    split: dict[str, str] = {}
    by_band: dict[int, list[str]] = defaultdict(list)
    for stem, band in band_of_stem.items():
        by_band[band].append(stem)
    for stems in by_band.values():
        order = rng.permutation(len(stems))
        n_val = max(1, round(len(stems) * val_fraction))
        n_test = max(1, round(len(stems) * test_fraction))
        for position, index in enumerate(order):
            if position < n_val:
                split[stems[index]] = "val"
            elif position < n_val + n_test:
                split[stems[index]] = "test"
            else:
                split[stems[index]] = "train"
    return split


def build(
    spectra_dir: Path,
    events_dir: Path,
    out_dir: Path,
    *,
    mode: str,
    window_min_nm: float,
    window_max_nm: float,
    min_snr: float,
    min_positive_minus_negative: float,
    band_bin_nm: int,
    split_mode: str,
    val_fraction: float,
    test_fraction: float,
    seed: int,
) -> dict:
    """Run the full manifest build; returns the gates summary."""
    pairs = discover_pairs(spectra_dir, events_dir)
    reference = targets_mod.load_reference(spectra_dir / "reference.parquet")
    rng = np.random.default_rng(seed)

    rows: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    wavelength_grid: np.ndarray | None = None
    targets_dir = out_dir / "targets"
    targets_dir.mkdir(parents=True, exist_ok=True)

    for stem, paths in sorted(pairs.items()):
        if "spectrum" not in paths or "recording" not in paths:
            excluded.append({"stem": stem, "reason": "ORPHAN: missing partner file"})
            continue
        try:
            spectrum = targets_mod.load_spectrum(paths["spectrum"])
        except ValueError as error:
            excluded.append({"stem": stem, "reason": f"SCHEMA: {error}"})
            continue

        # Band label from the raw counts over the full axis: era-independent
        # and stable (the transmittance target's argpeak scatters, see
        # FINDINGS.md §4).
        full = np.clip(spectrum.counts, 0.0, None)
        weighted_mean = float((spectrum.wavelength_nm * full).sum() / max(full.sum(), 1e-9))
        band = int(weighted_mean // band_bin_nm) * band_bin_nm

        try:
            wl, target = targets_mod.build_target(
                spectrum,
                reference,
                mode=mode,
                window_min_nm=window_min_nm,
                window_max_nm=window_max_nm,
            )
        except ValueError as error:
            excluded.append({"stem": stem, "reason": f"TARGET: {error}"})
            continue

        reason = targets_mod.gate_reason(
            spectrum,
            target,
            min_snr=min_snr,
            min_positive_minus_negative=min_positive_minus_negative,
        )
        if reason is not None:
            excluded.append({"stem": stem, "reason": reason})
            continue

        if wavelength_grid is None:
            wavelength_grid = wl
        elif len(wl) != len(wavelength_grid) or not np.allclose(wl, wavelength_grid):
            excluded.append({"stem": stem, "reason": "GRID: wavelength axis differs"})
            continue

        np.save(targets_dir / f"{stem}.npy", target.astype(np.float32))
        metrics = targets_mod.shape_metrics(target)
        noise = targets_mod.noise_metrics(spectrum.counts)
        rows.append(
            {
                "stem": stem,
                "spectrum": str(paths["spectrum"]),
                "recording": str(paths["recording"]),
                "triggers": str(paths.get("triggers", "")),
                "target": str(targets_dir / f"{stem}.npy"),
                "band_label": band,
                "weighted_mean_nm": round(weighted_mean, 2),
                "peak_to_mean": round(metrics["peak_to_mean"], 4),
                "normalized_entropy": round(metrics["normalized_entropy"], 5),
                "snr_mean_over_std": round(noise["snr_mean_over_std"], 4),
                "positive_minus_negative": round(noise["positive_minus_negative"], 2),
                "median_counts": round(spectrum.median_counts, 2),
                "era_amplitude_corrected": spectrum.amplitude_corrected,
                "exposure_ms": spectrum.exposure_ms,
                "hw_average": spectrum.hw_average,
                "acquired_utc_ms": spectrum.acquired_utc_ms,
            }
        )

    populated_bands = {row["stem"]: row["band_label"] for row in rows}
    if split_mode == "band":
        if len(set(populated_bands.values())) < 3:
            raise SystemExit(
                "band-holdout splits need >= 3 populated bands; only "
                f"{sorted(set(populated_bands.values()))} found. Use "
                "--split-mode stratified or relax the gates."
            )
        split = assign_band_splits(populated_bands, rng)
    else:
        split = assign_stratified_splits(populated_bands, rng, val_fraction, test_fraction)
    for row in rows:
        row["split"] = split[row["stem"]]

    out_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with (out_dir / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if wavelength_grid is not None:
        np.save(out_dir / "wavelength_grid.npy", wavelength_grid)

    band_counts = Counter((row["split"], row["band_label"]) for row in rows)
    gates = {
        "passed": len(rows) > 0,
        "num_pairs": len(rows),
        "num_excluded": len(excluded),
        "excluded": excluded,
        "spectral_bins": int(len(wavelength_grid)) if wavelength_grid is not None else 0,
        "wavelength_range_nm": (
            [float(wavelength_grid[0]), float(wavelength_grid[-1])]
            if wavelength_grid is not None
            else None
        ),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "split_by_band": {f"{s}/{b}": c for (s, b), c in sorted(band_counts.items())},
        "settings": {
            "mode": mode,
            "window_min_nm": window_min_nm,
            "window_max_nm": window_max_nm,
            "min_snr": min_snr,
            "min_positive_minus_negative": min_positive_minus_negative,
            "band_bin_nm": band_bin_nm,
            "split_mode": split_mode,
            "seed": seed,
        },
    }
    (out_dir / "gates.json").write_text(json.dumps(gates, indent=2))
    return gates


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectra-dir", type=Path, default=DEFAULT_SPECTRA)
    parser.add_argument("--events-dir", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--target-mode", choices=targets_mod.TARGET_MODES,
                        default="reference_transmittance")
    parser.add_argument("--window-min-nm", type=float, default=420.0)
    parser.add_argument("--window-max-nm", type=float, default=680.0)
    parser.add_argument("--min-snr", type=float, default=0.4,
                        help="raw-count mean/std below this is noise (real files >=0.74)")
    parser.add_argument("--min-positive-minus-negative", type=float, default=5.0,
                        help="pos-mean minus neg-mean below this (with low SNR) is noise")
    parser.add_argument("--band-bin", type=int, default=25)
    parser.add_argument("--split-mode", choices=("band", "stratified"), default="band")
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    gates = build(
        args.spectra_dir,
        args.events_dir,
        args.out_dir,
        mode=args.target_mode,
        window_min_nm=args.window_min_nm,
        window_max_nm=args.window_max_nm,
        min_snr=args.min_snr,
        min_positive_minus_negative=args.min_positive_minus_negative,
        band_bin_nm=args.band_bin,
        split_mode=args.split_mode,
        val_fraction=args.val_fraction,
        test_fraction=args.test_fraction,
        seed=args.seed,
    )
    summary = {k: gates[k] for k in
               ("passed", "num_pairs", "num_excluded", "spectral_bins",
                "wavelength_range_nm", "split_counts", "split_by_band")}
    print(json.dumps(summary, indent=2))
    for item in gates["excluded"]:
        print(f"excluded {item['stem']}: {item['reason']}")
    return 0 if gates["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
