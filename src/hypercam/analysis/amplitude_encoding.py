# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-01
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Test the DOE's amplitude channel for wavelength-dependent redistribution.

Why this analysis exists
------------------------
The DOE is a pure phase mask: one substrate, one photoresist, no absorbing
structure. Per-band total power is therefore conserved up to terms that are
smooth in wavelength (Fresnel reflections act as a scalar), so any cross-band
amplitude differences cannot be material attenuation - they can only be
*diffraction-efficiency redistribution by interference*. For a phase profile
h(u,v) the far-field family is

    I(u,v;lambda) = |FT{ exp( i * k(lambda) * phi0(u,v) ) }|**2,

a one-parameter morph trajectory: the same phase map at different effective
depths k(lambda). Material dispersion shifts k(lambda) commonly for all
structures; geometric scaling is separate and was already excluded for the
measured texture (the magnification sweep peaks at m = 1). Consequently, any
wavelength dependence the phase mask produces must appear as a *reshaping that
is not a radial scaling* - in per-pixel amplitude ratios and non-scaling shape
residuals - which is exactly what this module measures.

The representation is the one the event-rate model dictates. Events fire at a
rate proportional to |d ln I / dt| (the modulation depth per pixel), so the
folded (ON + OFF) accumulated frame - the per-pixel swing amplitude - is the
Fisher-carrying observable for a spectral encoding, whereas the signed (ON -
OFF) shape was shown by the source-identification analysis to be
wavelength-independent to within ~10% (see
``reports/source_identification_report_2026-10-01.md``).

Procedure (existing recordings only, the LCD RGB primaries for consistency):

1. Decode each recording folded (ON + OFF) and average to the converged
   duration: non-negative amplitude maps A_lambda(u,v).
2. **Flux normalization**: divide each map by its mean over the signal area.
   This removes the per-primary scalar (display brightness / total yield) - the
   separable null model A_lambda = S(u,v) * c_lambda then predicts *identical*
   normalized maps across bands, so every deviation measured below is spatial
   chromatic structure, not brightness.
3. **SSIM with component breakdown** (dependency-free, Gaussian-window):
   luminance, contrast, and structure terms between normalized band pairs,
   globally and as local maps. The contrast term is the amplitude channel the
   earlier Pearson work could not see; the luminance term reports residual
   brightness differences; the structure term is the old shape story.
   Half-cross combinations (blue's first half vs green's second, etc.) give
   the noise floor.
4. **Gain-ratio maps**: log2( A_a / A_b ) over pixels where both normalized
   maps carry signal - the per-pixel redistribution fingerprint. Flat =>
   separable; structured => the phase depth does spectral work at those pixels.
5. **Response-vector separability**: at each signal pixel the triplet
   (A_blue, A_green, A_red) normalized to a unit direction. Parallel directions
   (resultant length ~ 1) mean every pixel responds with the same spectral
   mixture - a brightness-separable encoding. Spread directions mean a genuine
   spatial-spectral code. The deviation-angle map shows *where*.
6. **Excess chromatic variance**: per signal pixel, the variance across bands
   of log normalized amplitude, minus the noise variance estimated from
   within-band half-to-half differences. ~0 => separable; structured positive
   => chromatic. The map shows where.
7. Dark control (optional): a dark recording's folded map is noise-driven
   (Lambda_0); its normalized map should not overlap the color maps.

Outputs (self-contained directory): ``analysis_metadata.json``;
``amplitude_frames/<label>_{activity,normalized}_{D}s.{npy,png}``;
``normalized_sheet_{D}s.png`` (the headline visual: three flux-normalized maps
side by side); ``ssim.csv`` + ``ssim_maps/<pair>.{png,npy}``;
``gain_maps/<pair>.{png,npy}``; ``separability.json`` +
``direction_scatter.png`` + ``deviation_angle_map.png`` +
``excess_variance_map.png``; ``conclusions.json`` and ``conclusions.md``.
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

from .duration_sweep import pair_pearson  # noqa: F401  (re-exported for symmetry)
from .source_identification import (
    WindowArchive,
    block_bounds,
    decode_windows,
    positive_float,
)
from .spectral_correlation import (
    discover_recordings,
    high_pass,
    load_openevt,
    positive_int,
    signal_window,
    write_grayscale_png,
)

# A pixel enters the ratio/direction analyses only when both (all) normalized
# maps carry at least this fraction of the frame's peak normalized amplitude;
# below that the per-pixel amplitude is quantization noise and ratios explode.
DEFAULT_SIGNAL_FRACTION = 0.05

# SSIM stabilization constants follow Wang et al. (2004): C1 = (K1 L)^2,
# C2 = (K2 L)^2 with K1 = 0.01, K2 = 0.03 and L the dynamic range.
SSIM_K1 = 0.01
SSIM_K2 = 0.03


def ssim_components(
    first: np.ndarray,
    second: np.ndarray,
    mask: np.ndarray | None = None,
    sigma: float = 1.5,
    data_range: float | None = None,
) -> dict[str, float | np.ndarray]:
    """SSIM of two non-negative frames with the luminance/contrast/structure
    breakdown (Wang et al. 2004), computed with a Gaussian window.

    Returns a dict with the full SSIM map, its masked mean, and the masked
    means of the three component maps. The breakdown matters here: for the
    DOE question, *contrast* carries the per-pixel amplitude redistribution
    Pearson is blind to, *luminance* reports residual brightness differences,
    and *structure* reproduces the shape-only story.

    ``data_range`` defaults to the joint maximum of the two frames (both are
    non-negative in this analysis), which sets the stabilization constants
    C1 = (K1 L)^2 and C2 = (K2 L)^2.
    """
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    if data_range is None:
        data_range = float(max(first.max(), second.max()))
    if data_range <= 0:
        data_range = 1.0
    c1 = (SSIM_K1 * data_range) ** 2
    c2 = (SSIM_K2 * data_range) ** 2
    mu_first = ndimage.gaussian_filter(first, sigma)
    mu_second = ndimage.gaussian_filter(second, sigma)
    mu_first_sq = mu_first * mu_first
    mu_second_sq = mu_second * mu_second
    mu_cross = mu_first * mu_second
    var_first = ndimage.gaussian_filter(first * first, sigma) - mu_first_sq
    var_second = ndimage.gaussian_filter(second * second, sigma) - mu_second_sq
    covariance = ndimage.gaussian_filter(first * second, sigma) - mu_cross
    std_first = np.sqrt(np.clip(var_first, 0.0, None))
    std_second = np.sqrt(np.clip(var_second, 0.0, None))
    c3 = c2 / 2.0
    luminance = (2.0 * mu_cross + c1) / (mu_first_sq + mu_second_sq + c1)
    contrast = (2.0 * std_first * std_second + c2) / (
        var_first + var_second + c2
    )
    structure = (covariance + c3) / (std_first * std_second + c3)
    ssim_map = luminance * contrast * structure
    if mask is None:
        mask = np.ones(first.shape, dtype=bool)
    mask = np.asarray(mask, dtype=bool)

    def masked_mean(values: np.ndarray) -> float:
        if not mask.any():
            return np.nan
        return float(np.mean(values[mask]))

    return {
        "ssim_map": ssim_map,
        "ssim": masked_mean(ssim_map),
        "luminance": masked_mean(luminance),
        "contrast": masked_mean(contrast),
        "structure": masked_mean(structure),
    }


def flux_normalize(
    frame: np.ndarray, support: np.ndarray
) -> tuple[np.ndarray, float]:
    """Divide by the mean amplitude over the signal area (the separable null).

    Under the separable model A_lambda = S(u,v) * c_lambda, this scalar removes
    the per-primary brightness exactly, so flux-normalized maps of a separable
    encoding are identical across bands and every subsequent deviation is
    spatial chromatic structure.
    """
    scalar = float(np.mean(frame[support]))
    if scalar <= 0:
        raise ValueError("flux normalization failed: no positive signal in support")
    return frame / scalar, scalar


def signal_floor_mask(
    normalized_stack: np.ndarray, fraction: float
) -> np.ndarray:
    """Pixels where every band's normalized amplitude clears a common floor.

    The floor is a fraction of the stack's peak normalized amplitude; below it
    the per-pixel amplitude is quantization noise and ratios/directions become
    meaningless.
    """
    peak = float(np.max(normalized_stack))
    if peak <= 0:
        return np.zeros(normalized_stack.shape[1:], dtype=bool)
    return np.all(normalized_stack >= fraction * peak, axis=0)


def log_ratio_map(
    first: np.ndarray, second: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    """log2 of the flux-normalized amplitude ratio, NaN outside ``mask``.

    log2 keeps the map symmetric: +1 means the first band redistributes twice
    the amplitude to this pixel relative to the second, 0 means equality.
    """
    ratio = np.full(first.shape, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        values = np.log2(first[mask] / second[mask])
    ratio[mask] = values
    return ratio


def direction_statistics(
    stack: np.ndarray, mask: np.ndarray
) -> dict[str, float | np.ndarray]:
    """Separability statistics of per-pixel normalized response directions.

    At every masked pixel the band amplitudes form a vector, normalized to unit
    length. A brightness-separable encoding (A_lambda = S * c_lambda) sends
    every direction to the same point on the sphere: the signal-weighted
    resultant length is 1 and the response-vector cloud is rank-1. Spread
    directions are a genuine spatial-spectral code. The principal axis is the
    common spectral-response direction; deviations from it are mapped by the
    caller.
    """
    vectors = stack[:, mask].T  # (N pixels, n bands)
    totals = vectors.sum(axis=1)
    weights = totals.copy()
    # normalize to UNIT directions (L2): the resultant-length statistic assumes
    # unit vectors; a sum-based normalization leaves |d| != 1 even when every
    # direction is identical. Zero vectors are dropped by the totals > 0 filter.
    norms = np.linalg.norm(vectors, axis=1)
    norms_safe = np.where(norms == 0, 1.0, norms)
    directions = vectors / norms_safe[:, None]
    finite = np.all(np.isfinite(directions), axis=1) & (totals > 0)
    directions = directions[finite]
    weights = weights[finite]
    if directions.shape[0] < 2:
        return {
            "pixels": int(directions.shape[0]),
            "resultant_length": np.nan,
            "resultant_length_unweighted": np.nan,
            "eigenvalues": np.full(3, np.nan),
            "principal_axis": np.full(3, np.nan),
            "mean_deviation_deg": np.nan,
            "median_deviation_deg": np.nan,
            "_deviations": np.empty(0),
            "_directions": np.empty((0, 3)),
        }
    total_weight = float(np.sum(weights))
    weighted_mean = directions.T @ weights / total_weight
    resultant_length = float(np.linalg.norm(weighted_mean))
    moment = (directions * weights[:, None]).T @ directions / total_weight
    eigenvalues, eigenvectors = np.linalg.eigh(moment)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    principal = eigenvectors[:, order[0]]
    if principal[np.argmax(np.abs(principal))] < 0:
        principal = -principal
    deviations = np.degrees(
        np.arccos(np.clip(directions @ principal, -1.0, 1.0))
    )
    return {
        "pixels": int(directions.shape[0]),
        "resultant_length": resultant_length,
        "resultant_length_unweighted": float(
            np.linalg.norm(directions.mean(axis=0))
        ),
        "eigenvalues": [float(value) for value in eigenvalues],
        "principal_axis": [float(value) for value in principal],
        "mean_deviation_deg": float(np.mean(deviations)),
        "median_deviation_deg": float(np.median(deviations)),
        "_deviations": deviations,
        "_directions": directions,
    }


def excess_chromatic_variance(
    stack: np.ndarray,
    noise_variance: float,
    mask: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Cross-band variance of log normalized amplitude, minus the noise floor.

    For each signal pixel the log-amplitudes of the (flux-normalized) bands
    scatter by Var_lambda; the within-band half-to-half log differences give
    the pure noise contribution (their variance is twice the single-estimate
    variance). Excess ~ 0 => the encoding is separable (bands differ only by a
    scalar); structured positive excess => chromatic redistribution. Returns
    (mean positive excess over signal pixels, per-pixel excess map with NaN
    outside the mask).
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.log(np.where(stack > 0, stack, np.nan))
    per_pixel_variance = np.nanvar(logs, axis=0, ddof=1)
    excess = per_pixel_variance - noise_variance
    excess_map = np.full(stack.shape[1:], np.nan)
    excess_map[mask] = excess[mask]
    finite = np.isfinite(excess_map)
    positive_mean = float(np.mean(np.clip(excess_map[finite], 0.0, None)))
    return positive_mean, excess_map


def half_noise_variance(
    archives: dict[str, WindowArchive],
    rows: slice,
    columns: slice,
    blocks: int,
    mask: np.ndarray | None = None,
) -> float:
    """Noise variance of log amplitude from within-band disjoint halves.

    For each band the two halves are flux-normalized independently and their
    log difference is formed over the evaluated pixels; the variance of that
    difference equals twice the single-estimate noise variance. The mean over
    bands is returned as the noise floor for the excess-chromatic-variance
    statistic. ``mask`` restricts the estimate to the same signal pixels the
    excess statistic evaluates: background pixels are quantization-noise
    dominated and would inflate the floor until it swamps any chromatic signal.
    """
    per_band: list[float] = []
    for archive in archives.values():
        bounds = [
            bounds
            for bounds in block_bounds(archive.frame_count, blocks)
            if bounds[1] > bounds[0]
        ]
        if len(bounds) < 2:
            continue
        halves = []
        for start, stop in bounds:
            frame = archive.frame(start, stop)[rows, columns]
            support = frame != 0
            normalized, _ = flux_normalize(frame, support)
            halves.append(normalized)
        with np.errstate(divide="ignore", invalid="ignore"):
            difference = np.log(halves[0]) - np.log(halves[1])
        finite = np.isfinite(difference)
        if mask is not None:
            finite = finite & mask
        if finite.sum() > 2:
            # var(log h1 - log h2) = 2 * var(single estimate) for independent
            # halves with equal noise
            per_band.append(float(np.var(difference[finite]) / 2.0))
    if not per_band:
        return np.nan
    return float(np.mean(per_band))


def _map_png(
    path: Path,
    data: np.ndarray,
    title: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
) -> None:
    """Single-panel heat map with a labeled colorbar."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7.5, 5.2))
    image = axis.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    axis.set_title(title, fontsize=11)
    axis.axis("off")
    colorbar = figure.colorbar(image, ax=axis, shrink=0.85)
    colorbar.set_label(colorbar_label, fontsize=9)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _amplitude_sheet_png(
    path: Path,
    title: str,
    panels: list[tuple[str, np.ndarray]],
    scale_percentile: float = 99.7,
) -> tuple[float, float]:
    """Non-negative amplitude panels on one shared sequential scale."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stacked = np.concatenate([panel.ravel() for _, panel in panels])
    vmax = float(np.nanpercentile(stacked, scale_percentile))
    vmin = 0.0
    if vmax <= vmin:
        vmax = 1.0
    columns = len(panels)
    figure, axes = plt.subplots(
        1, columns, figsize=(4.0 * columns, 3.8), squeeze=False
    )
    for index, (label, panel) in enumerate(panels):
        image = axes[0][index].imshow(
            panel, cmap="magma", vmin=vmin, vmax=vmax, interpolation="nearest"
        )
        axes[0][index].set_title(label, fontsize=10)
        axes[0][index].axis("off")
    colorbar = figure.colorbar(image, ax=axes.ravel().tolist(), shrink=0.85)
    colorbar.set_label("folded amplitude (log1p ON+OFF, shared scale)")
    figure.suptitle(title, fontsize=12)
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return vmin, vmax


def _direction_scatter_png(
    path: Path,
    directions: np.ndarray,
    principal: np.ndarray,
    title: str,
) -> None:
    """Response directions projected onto the plane normal to the principal axis.

    A separable encoding collapses every direction to the origin of this plot;
    spread is the spatial-spectral code. Contour density replaces a raw
    scatter of hundreds of thousands of points.
    """
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    helper = np.zeros(3)
    helper[np.argmin(np.abs(principal))] = 1.0
    e1 = np.cross(principal, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(principal, e1)
    x = directions @ e1
    y = directions @ e2
    figure, axis = plt.subplots(figsize=(6.4, 5.6))
    axis.hexbin(x, y, gridsize=60, cmap="viridis", mincnt=1)
    axis.axhline(0.0, color="0.6", linewidth=0.8)
    axis.axvline(0.0, color="0.6", linewidth=0.8)
    axis.set_xlabel("response direction, e1 component")
    axis.set_ylabel("response direction, e2 component")
    axis.set_title(title, fontsize=11)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _write_conclusions(
    output: Path,
    labels: list[str],
    pair_names: list[str],
    ssim_table: dict[str, dict[str, float]],
    separability: dict[str, object],
    flux_scalars: dict[str, float],
    control_summary: dict[str, object] | None,
) -> None:
    """Write the amplitude-channel conclusions (JSON + markdown)."""
    conclusions = {
        "question": (
            "does the pure-phase DOE redistribute amplitude across the three "
            "primaries (a spatial-spectral code), or are the bands separable "
            "(brightness coding only)?"
        ),
        "physical_constraint": (
            "lossless phase mask: cross-band amplitude differences can only be "
            "diffraction-efficiency redistribution (the k(lambda) morph "
            "trajectory), never material attenuation"
        ),
        "null_model": (
            "separable response A_lambda = S(u,v) * c_lambda: after flux "
            "normalization all bands are identical; SSIM = 1 with contrast and "
            "luminance deficits = 0; response directions parallel; excess "
            "chromatic variance = 0"
        ),
        "flux_scalars": flux_scalars,
        "pairs": ssim_table,
        "separability": {
            key: value
            for key, value in separability.items()
            if not key.startswith("_")
        },
        "control": control_summary,
    }
    (output / "conclusions.json").write_text(
        json.dumps(conclusions, indent=2, default=float) + "\n", encoding="utf-8"
    )

    lines = [
        "# Amplitude-encoding analysis - conclusions",
        "",
        "## Question and null model",
        "",
        "- The DOE is a lossless phase mask: cross-band amplitude differences",
        "  can only be diffraction-efficiency redistribution (the k(lambda)",
        "  morph trajectory), never material attenuation.",
        "- Null model (separable response): flux-normalized amplitude maps are",
        "  identical across bands; SSIM = 1; response directions parallel;",
        "  excess chromatic variance = 0.",
        "",
        "## Per-primary event yield (flux scalars, before normalization)",
        "",
        "| band | relative folded yield |",
        "|---|---|",
    ]
    reference = flux_scalars[labels[0]]
    for label in labels:
        lines.append(
            f"| {label} | {flux_scalars[label]:.4f} "
            f"({flux_scalars[label] / reference:.2f}x {labels[0]}) |"
        )
    lines += [
        "",
        "## SSIM between flux-normalized amplitude maps (full duration)",
        "",
        "| pair | SSIM | luminance | contrast | structure | high-passed SSIM | half-cross floor |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in pair_names:
        entry = ssim_table[name]
        lines.append(
            f"| {name} | {entry['ssim']:.4f} | {entry['luminance']:.4f} | "
            f"{entry['contrast']:.4f} | {entry['structure']:.4f} | "
            f"{entry['ssim_highpass']:.4f} | {entry['half_cross_ssim']:.4f} |"
        )
    lines += ["", "## Separability of the response directions", ""]
    lines.append(
        f"- Signal-weighted resultant length {separability['resultant_length']:.4f} "
        f"(1 = all pixel response vectors parallel = brightness-separable); "
        f"unweighted {separability['resultant_length_unweighted']:.4f}."
    )
    eigenvalues = separability["eigenvalues"]
    lines.append(
        f"- Response-cloud eigenvalues {eigenvalues[0]:.4f} / {eigenvalues[1]:.4f} / "
        f"{eigenvalues[2]:.4f} - a rank-1 cloud (separable) has e2, e3 ~ 0."
    )
    lines.append(
        f"- Mean deviation of pixel response directions from the principal axis: "
        f"{separability['mean_deviation_deg']:.2f} degrees "
        f"(median {separability['median_deviation_deg']:.2f}). Baselines at three "
        f"all-positive bands: 0 degrees = perfectly parallel (separable); "
        f"~20 degrees = random directions (no common spectral response). Values "
        f"well below ~20 degrees indicate a common spectral component with "
        f"limited chromatic spread."
    )
    lines.append(
        f"- Excess chromatic variance beyond the half-to-half noise floor: "
        f"{separability['excess_chromatic_variance']:.5f} "
        f"(noise floor {separability['noise_variance']:.5f})."
    )
    if control_summary:
        lines += ["", "## Dark control (Lambda_0 / noise amplitude map)", ""]
        for control_label, entry in control_summary.items():
            lines.append(
                f"- **{control_label}**: normalized-amplitude SSIM vs colors "
                + ", ".join(
                    f"{label} {entry['ssim_vs_colors'][label]:.3f}"
                    for label in labels
                )
                + " - near-zero overlap means the color amplitude maps are "
                "scene-driven, not the dark noise rate map."
            )
    lines += [
        "",
        "## Reading the numbers",
        "",
        "- SSIM structure ~ 1 with a contrast deficit: same shapes, different",
        "  per-pixel amplitudes - the amplitude channel carries the encoding.",
        "- SSIM ~ 1 everywhere: the three primaries produce proportional",
        "  amplitude maps - the encoding is brightness-separable at these",
        "  wavelengths, and the phase depth k(lambda) does no measurable work.",
        "- Excess chromatic variance ~ 0: same as the previous line, in",
        "  per-pixel variance terms. Structured excess (see the map) marks",
        "  where the redistribution lives.",
        "",
    ]
    (output / "conclusions.md").write_text("\n".join(lines), encoding="utf-8")


def analyze(args: argparse.Namespace) -> Path:
    """Run the amplitude-encoding analysis and write the results directory."""
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
    frames_dir = output / "amplitude_frames"
    maps_dir = output / "ssim_maps"
    gain_dir = output / "gain_maps"
    for directory in (frames_dir, maps_dir, gain_dir):
        directory.mkdir(parents=True, exist_ok=True)

    accumulation_us = int(round(args.accumulation_ms * 1_000))
    duration_full = float(args.duration)
    window_budget = int(round(duration_full * 1_000_000)) // accumulation_us

    with load_openevt(args.openevt_library) as openevt:
        archives: dict[str, WindowArchive] = {}
        for index, (label, path) in enumerate(recordings, start=1):
            print(f"[{index}/{len(recordings)}] Decoding {path.name} (folded)...", flush=True)
            archives[label] = decode_windows(
                openevt, label, path, "both", accumulation_us, args.transform
            )
        control_archives: dict[str, WindowArchive] = {}
        for index, (label, path) in enumerate(controls, start=1):
            print(f"[{index}/{len(controls)}] Decoding control {path.name}...", flush=True)
            control_archives[label] = decode_windows(
                openevt, label, path, "both", accumulation_us, args.transform
            )

    truncated = {
        label: min(window_budget, archive.frame_count)
        for label, archive in archives.items()
    }
    activity = {
        label: archives[label].frame(0, truncated[label]) for label in labels
    }
    stack = np.stack([activity[label] for label in labels])
    rows, columns = signal_window(stack, args.crop_margin)
    cropped = {label: activity[label][rows, columns] for label in labels}
    supports = {label: cropped[label] != 0 for label in labels}

    normalized: dict[str, np.ndarray] = {}
    flux_scalars: dict[str, float] = {}
    for label in labels:
        normalized[label], flux_scalars[label] = flux_normalize(
            cropped[label], supports[label]
        )
        np.save(frames_dir / f"{label}_activity_{duration_full:g}s.npy", cropped[label])
        np.save(frames_dir / f"{label}_normalized_{duration_full:g}s.npy", normalized[label])
        write_grayscale_png(
            frames_dir / f"{label}_activity_{duration_full:g}s.png", cropped[label]
        )
    normalized_stack = np.stack([normalized[label] for label in labels])
    signal_mask = signal_floor_mask(normalized_stack, args.signal_fraction)
    print(
        f"  signal floor: {int(np.count_nonzero(signal_mask))} pixels at "
        f"{args.signal_fraction:.0%} of peak normalized amplitude",
        flush=True,
    )

    normalized_panels = [
        (f"{label} (flux-normalized)", normalized[label]) for label in labels
    ]
    amplitude_low, amplitude_high = _amplitude_sheet_png(
        output / f"normalized_sheet_{duration_full:g}s.png",
        f"Flux-normalized folded amplitude maps ({duration_full:g} s, "
        f"{args.accumulation_ms:g} ms windows) - the separable null predicts "
        "identical maps",
        normalized_panels,
    )
    for label in labels:
        write_grayscale_png(
            frames_dir / f"{label}_normalized_{duration_full:g}s.png",
            normalized[label],
            amplitude_low,
            amplitude_high,
        )

    # ---- Noise floor from within-band disjoint halves ----
    # Restricted to the same signal pixels the excess statistic evaluates:
    # background pixels are quantization-noise dominated and would inflate the
    # floor until it swamps any chromatic signal.
    noise_variance = half_noise_variance(
        archives, rows, columns, args.splits, mask=signal_mask
    )

    # ---- SSIM per pair (normalized maps; raw maps for reference) ----
    ssim_table: dict[str, dict[str, float]] = {}
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        mask = supports[labels[first]] & supports[labels[second]]
        full = ssim_components(
            normalized[labels[first]], normalized[labels[second]], mask
        )
        highpassed = ssim_components(
            high_pass(normalized[labels[first]], 64),
            high_pass(normalized[labels[second]], 64),
            mask,
        )
        half_values = []
        bounds = [
            bounds
            for bounds in block_bounds(truncated[labels[first]], args.splits)
            if bounds[1] > bounds[0]
        ]
        bounds_second = [
            bounds
            for bounds in block_bounds(truncated[labels[second]], args.splits)
            if bounds[1] > bounds[0]
        ]
        for (start_first, stop_first), (start_second, stop_second) in zip(
            bounds, bounds_second, strict=False
        ):
            half_first = archives[labels[first]].frame(start_first, stop_first)[rows, columns]
            half_second = archives[labels[second]].frame(start_second, stop_second)[rows, columns]
            half_first, _ = flux_normalize(half_first, half_first != 0)
            half_second, _ = flux_normalize(half_second, half_second != 0)
            half_values.append(
                ssim_components(half_first, half_second, mask)["ssim"]
            )
        valid_halves = [value for value in half_values if np.isfinite(value)]
        half_floor = float(np.mean(valid_halves)) if valid_halves else np.nan
        ssim_table[name] = {
            "ssim": full["ssim"],
            "luminance": full["luminance"],
            "contrast": full["contrast"],
            "structure": full["structure"],
            "ssim_highpass": highpassed["ssim"],
            "half_cross_ssim": half_floor,
        }
        np.save(maps_dir / f"{name}_ssim_map.npy", full["ssim_map"])
        _map_png(
            maps_dir / f"{name}_ssim_map.png",
            full["ssim_map"],
            f"{name}: local SSIM of flux-normalized amplitude maps",
            "viridis",
            0.0,
            1.0,
            "local SSIM",
        )
        print(
            f"  SSIM {name}: {full['ssim']:.4f} "
            f"(luminance {full['luminance']:.4f}, contrast {full['contrast']:.4f}, "
            f"structure {full['structure']:.4f}); half-cross floor {half_floor:.4f}",
            flush=True,
        )
    with (output / "ssim.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["pair", "ssim", "luminance", "contrast", "structure", "ssim_highpass", "half_cross_ssim"]
        )
        for name in pair_names:
            entry = ssim_table[name]
            writer.writerow([name] + [entry[key] for key in (
                "ssim", "luminance", "contrast", "structure", "ssim_highpass", "half_cross_ssim"
            )])

    # ---- Gain-ratio maps: the per-pixel redistribution fingerprint ----
    for name, (first, second) in zip(pair_names, pair_indices, strict=True):
        ratio = log_ratio_map(
            normalized[labels[first]], normalized[labels[second]], signal_mask
        )
        np.save(gain_dir / f"{name}_log2_ratio.npy", ratio)
        finite = np.isfinite(ratio)
        robust_limit = float(np.nanpercentile(np.abs(ratio[finite]), 99.0)) if finite.any() else 1.0
        _map_png(
            gain_dir / f"{name}_log2_ratio.png",
            ratio,
            f"{name}: log2 amplitude ratio (flux-normalized, signal floor)",
            "RdBu_r",
            -robust_limit,
            robust_limit,
            "log2( A_a / A_b )",
        )
        stats_text = ""
        if finite.any():
            stats_text = (
                f"median {np.nanmedian(ratio[finite]):+.3f}, "
                f"robust |range| {robust_limit:.3f} log2 units"
            )
        print(f"  gain map {name}: {stats_text}", flush=True)

    # ---- Separability of the response directions ----
    statistics = direction_statistics(normalized_stack, signal_mask)
    finite_signal = signal_mask & np.all(np.isfinite(normalized_stack), axis=0) & (
        normalized_stack.sum(axis=0) > 0
    )
    excess_mean, excess_map = excess_chromatic_variance(
        normalized_stack, noise_variance, finite_signal
    )
    directions = statistics.pop("_directions")
    deviations = statistics.pop("_deviations")
    principal = statistics["principal_axis"]
    separability = {
        **statistics,
        "noise_variance": noise_variance,
        "excess_chromatic_variance": excess_mean,
        "signal_fraction": args.signal_fraction,
    }
    deviation_map = np.full(cropped[labels[0]].shape, np.nan)
    deviation_map[signal_mask] = np.nan
    # Re-project the deviations onto their pixels for the spatial map.
    vectors = normalized_stack[:, finite_signal].T
    totals = vectors.sum(axis=1)
    totals_safe = np.where(totals == 0, 1.0, totals)
    unit = vectors / totals_safe[:, None]
    angle = np.degrees(np.arccos(np.clip(unit @ principal, -1.0, 1.0)))
    deviation_map[finite_signal] = angle
    _map_png(
        output / "deviation_angle_map.png",
        deviation_map,
        "Deviation of per-pixel response direction from the principal axis",
        "viridis",
        0.0,
        max(float(np.nanmax(angle)), 1e-6),
        "degrees from principal spectral-response direction",
    )
    _map_png(
        output / "excess_variance_map.png",
        excess_map,
        "Excess chromatic variance of log normalized amplitude (beyond noise floor)",
        "viridis",
        0.0,
        max(float(np.nanmax(excess_map)), 1e-6),
        "variance excess (log units)",
    )
    if directions.shape[0] > 0:
        _direction_scatter_png(
            output / "direction_scatter.png",
            directions,
            principal,
            "Per-pixel response directions (plane normal to the principal axis)",
        )
    print(
        f"  separability: resultant={statistics['resultant_length']:.4f} "
        f"mean deviation {statistics['mean_deviation_deg']:.2f} deg "
        f"excess chromatic variance {excess_mean:.5f} (noise {noise_variance:.5f})",
        flush=True,
    )
    (output / "separability.json").write_text(
        json.dumps(separability, indent=2, default=float) + "\n", encoding="utf-8"
    )

    # ---- Dark control: the Lambda_0 amplitude map should not overlap ----
    control_summary: dict[str, object] | None = None
    if control_archives:
        control_summary = {}
        for control_label, control_archive in control_archives.items():
            control_count = min(window_budget, control_archive.frame_count)
            control_frame = control_archive.frame(0, control_count)[rows, columns]
            control_support = control_frame != 0
            control_normalized, control_scalar = flux_normalize(
                control_frame, control_support
            )
            np.save(
                frames_dir / f"{control_label}_normalized_{duration_full:g}s.npy",
                control_normalized,
            )
            per_color = {
                label: ssim_components(
                    control_normalized, normalized[label], supports[label]
                )["ssim"]
                for label in labels
            }
            control_summary[control_label] = {
                "flux_scalar": control_scalar,
                "ssim_vs_colors": per_color,
            }
            print(
                f"  control {control_label}: normalized-amplitude SSIM vs colors "
                + ", ".join(f"{label} {per_color[label]:.3f}" for label in labels),
                flush=True,
            )

    _write_conclusions(
        output, labels, pair_names, ssim_table, separability, flux_scalars, control_summary
    )

    metadata = {
        "method": (
            "Amplitude-channel encoding test: folded (ON+OFF) amplitude maps, "
            "flux normalization (separable null), SSIM with "
            "luminance/contrast/structure breakdown, log2 gain-ratio maps, "
            "response-direction separability statistics, and excess chromatic "
            "variance beyond the within-band half-to-half noise floor"
        ),
        "pattern": args.pattern,
        "control_pattern": args.control_pattern,
        "polarity": "both",
        "transform": args.transform,
        "accumulation_ms": args.accumulation_ms,
        "duration_s": duration_full,
        "crop_margin_px": args.crop_margin,
        "signal_fraction": args.signal_fraction,
        "ssim_sigma": args.ssim_sigma,
        "splits": args.splits,
        "labels": labels,
        "controls": list(control_archives),
        "recordings": [
            archives[label].metadata(accumulation_us) for label in labels
        ],
        "control_recordings": [
            control_archives[label].metadata(accumulation_us)
            for label in control_archives
        ],
    }
    (output / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2, default=float) + "\n", encoding="utf-8"
    )
    print(f"Wrote amplitude-encoding analysis to {output}")
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
        help="optional glob for dark/blank control recordings "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/amplitude_encoding"),
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--accumulation-ms",
        type=positive_float,
        default=1.0,
        help="accumulation interval in milliseconds (default: %(default)s)",
    )
    parser.add_argument(
        "--duration",
        type=positive_float,
        default=5.0,
        help="converged averaging duration in seconds (default: %(default)s)",
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
        help="contiguous disjoint blocks for the noise floor and SSIM floors "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--crop-margin",
        type=positive_int,
        default=48,
        help="padding in pixels around the detected signal window (default: %(default)s)",
    )
    parser.add_argument(
        "--signal-fraction",
        type=positive_float,
        default=DEFAULT_SIGNAL_FRACTION,
        help="pixels enter ratio/direction analyses when every band's "
        "normalized amplitude clears this fraction of the peak "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--ssim-sigma",
        type=positive_float,
        default=1.5,
        help="Gaussian window sigma for SSIM local statistics (default: %(default)s)",
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