# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Save per-cell activity frames and contact sheets for a duration-sweep grid."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np

from .duration_sweep import (
    CROP_MARGIN_PX,
    DEFAULT_ACCUMULATIONS_MS,
    DEFAULT_DURATIONS_S,
    HIGH_PASS_PX,
    build_snapshots,
    parse_float_list,
)
from .spectral_correlation import (
    discover_recordings,
    high_pass,
    load_openevt,
    signal_window,
    write_grayscale_png,
)

VMIN, VMAX = -0.03, 0.03  # fallback gray scale when a sheet holds no contrast


def save_frames(
    output: Path,
    openevt: object,
    pattern: str,
    durations_s: Sequence[float],
    accumulations_ms: Sequence[float],
    transform: str,
) -> Path:
    """Write cropped activity + high-passed frames and a contact sheet per accumulation."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    recordings = discover_recordings(pattern)
    labels = [label for label, _ in recordings]
    cutoffs = [int(round(duration * 1_000_000)) for duration in durations_s]
    output.mkdir(parents=True, exist_ok=True)
    for acc_ms in accumulations_ms:
        per_recording = [
            build_snapshots(
                openevt, path, int(round(acc_ms * 1_000)), cutoffs, transform
            )
            for _, path in recordings
        ]
        processed: dict[tuple[float, str], np.ndarray] = {}
        for duration, cutoff in zip(durations_s, cutoffs, strict=True):
            stack = np.stack([snapshots[cutoff] for snapshots in per_recording])
            rows, columns = signal_window(stack, CROP_MARGIN_PX)
            stack = stack[:, rows, columns]
            for index, label in enumerate(labels):
                write_grayscale_png(
                    output / f"{duration:g}s_{acc_ms:g}ms_{label}_activity_cropped.png",
                    stack[index],
                )
                frame = high_pass(stack[index], HIGH_PASS_PX)
                processed[(duration, label)] = frame
                write_grayscale_png(
                    output / f"{duration:g}s_{acc_ms:g}ms_{label}_processed.png",
                    frame,
                )
        figure, axes = plt.subplots(
            len(durations_s),
            len(labels),
            figsize=(2.1 * len(labels) + 1.2, 2.1 * len(durations_s) + 0.9),
            dpi=110,
        )
        axes = np.atleast_2d(axes)
        # One scale per sheet (robust percentiles, symmetrized) so cells are
        # comparable within the sheet even though magnitudes vary by
        # accumulation interval.
        sheet_values = np.concatenate([frame.ravel() for frame in processed.values()])
        sheet_vmax = float(
            np.percentile(np.abs(sheet_values[np.nonzero(sheet_values)]), 99.5)
        )
        sheet_vmax = sheet_vmax if sheet_vmax > 0 else VMAX
        for row, duration in enumerate(durations_s):
            for column, label in enumerate(labels):
                axis = axes[row][column]
                axis.imshow(
                    processed[(duration, label)],
                    cmap="gray",
                    vmin=-sheet_vmax,
                    vmax=sheet_vmax,
                )
                axis.set_xticks([])
                axis.set_yticks([])
                if row == 0:
                    axis.set_title(label, fontsize=11)
                if column == 0:
                    axis.set_ylabel(f"{duration:g} s", fontsize=11)
        fps = round(1000 / acc_ms)
        figure.suptitle(
            f"{acc_ms:g} ms acc. ({fps} FPS) · crop + {HIGH_PASS_PX}px high-pass · "
            f"sheet scale ±{sheet_vmax:.3g}",
            fontsize=11,
        )
        figure.tight_layout(rect=(0, 0, 1, 0.96))
        figure.savefig(output / f"contact_sheet_{acc_ms:g}ms.png", dpi=110)
        plt.close(figure)
        print(f"acc={acc_ms:g} ms: frames + contact sheet written", flush=True)
    return output


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
        default=Path("results/spectral_correlation/sweep_frames"),
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
    with load_openevt(args.openevt_library) as openevt:
        output = save_frames(
            args.output.expanduser().resolve(),
            openevt,
            args.pattern,
            args.durations,
            args.accumulations,
            args.transform,
        )
    print(f"Wrote frames to {output}")


if __name__ == "__main__":
    main()
