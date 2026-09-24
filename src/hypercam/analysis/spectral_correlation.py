# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Build activity frames from EVT3 recordings and compare them with Pearson r.

Each recording is averaged into an activity frame, cropped to the common
signal window, high-passed to drop large-scale background, and correlated
pairwise over the pixels that are active in either frame. Recordings are
labeled from their filenames (number if present, else trailing word).
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import struct
import sys
import zlib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np


def label_from_path(path: Path) -> str:
    """Return a human-readable recording label from the filename.

    The last number wins when present (``spectral_425`` -> ``"425"``);
    otherwise the trailing word is used (``circle_green`` -> ``"green"``).
    """
    numbers = re.findall(r"(?:^|[_-])(\d+(?:\.\d+)?)", path.stem)
    if numbers:
        return f"{float(numbers[-1]):g}"
    words = re.findall(r"[A-Za-z]+", path.stem)
    if not words:
        raise ValueError(
            f"{path.name} carries neither a number nor a name to label it "
            "with; rename the recording"
        )
    return words[-1]


def label_sort_key(label: str) -> tuple[int, float, str]:
    """Order numeric labels first (numerically), then names alphabetically."""
    try:
        return (0, float(label), "")
    except ValueError:
        return (1, 0.0, label)


def discover_recordings(pattern: str) -> list[tuple[str, Path]]:
    """Expand a user-aware glob and return recordings ordered by label."""
    import glob

    paths = [Path(item).resolve() for item in glob.glob(os.path.expanduser(pattern))]
    if not paths:
        raise FileNotFoundError(f"no recordings match {pattern!r}")
    recordings = sorted(
        ((label_from_path(path), path) for path in paths),
        key=lambda item: label_sort_key(item[0]),
    )
    labels = [label for label, _ in recordings]
    if len(labels) != len(set(labels)):
        raise ValueError("recording filenames contain duplicate labels")
    return recordings


@contextmanager
def load_openevt(library: Path | None = None) -> Iterator[object]:
    """Load matching Python and device-plugin instances from a local OpenEVT build.

    The Python extension (``libopenevt.so``) and the standard device plugins
    (``libopenevt_plugins.so``, which carries the EVT3 raw-file reader) are
    separate shared libraries built side by side, so the extension is imported
    from the build directory while that same directory is put on
    ``OPENEVT_PLUGIN_PATH`` for the plugin search.
    """
    if library is None:
        project_root = Path(__file__).resolve().parents[2]
        candidate = project_root / "openevt" / "target" / "release" / "libopenevt.so"
        library = candidate if candidate.exists() else None

    if library is None:
        import openevt

        yield openevt
        return

    library = library.expanduser().resolve()
    if not library.is_file():
        raise FileNotFoundError(f"OpenEVT library does not exist: {library}")

    plugin_directory = library.parent
    if not (plugin_directory / "libopenevt_plugins.so").is_file():
        raise FileNotFoundError(
            "the OpenEVT standard plugins were not built alongside "
            f"{library.name}; expected {plugin_directory}/libopenevt_plugins.so. "
            "Build them with: cargo build --release --features python"
        )

    previous_plugin_path = os.environ.get("OPENEVT_PLUGIN_PATH")
    os.environ["OPENEVT_PLUGIN_PATH"] = str(plugin_directory)
    previous_module = sys.modules.pop("openevt", None)
    try:
        spec = importlib.util.spec_from_file_location("openevt", library)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load OpenEVT extension: {library}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["openevt"] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop("openevt", None)
        if previous_module is not None:
            sys.modules["openevt"] = previous_module
        if previous_plugin_path is None:
            os.environ.pop("OPENEVT_PLUGIN_PATH", None)
        else:
            os.environ["OPENEVT_PLUGIN_PATH"] = previous_plugin_path


def build_activity_frame(
    openevt: object,
    path: Path,
    polarity: str = "both",
    accumulation_us: int = 10_000,
    transform: str = "log1p",
) -> tuple[np.ndarray, dict[str, int | list[int] | None]]:
    """Stream and average transformed fixed-duration EVT3 activity frames."""
    reader = openevt.RawFileReader(str(path))
    iterator = reader.iter()
    height, width = (int(value) for value in iterator.shape())
    pixel_count = height * width
    signed = polarity == "signed"
    frame_sum = np.zeros(pixel_count, dtype=np.float64)
    total_events = 0
    used_events = 0
    frame_count = 0
    t_first: int | None = None
    t_last: int | None = None

    while True:
        try:
            events = iterator.next_delta(accumulation_us)
        except StopIteration:
            break
        except OSError as error:
            # OpenEVT 1.0.4 exposes a clean RAW EOF as OSError rather than
            # translating it to Python's StopIteration for some recordings.
            if "end of file" in str(error).lower() or str(error).lower() == "eof":
                break
            raise
        frame_count += 1
        total_events += int(events.size)
        if events.size:
            batch_first = int(events["t"][0])
            batch_last = int(events["t"][-1])
            t_first = batch_first if t_first is None else min(t_first, batch_first)
            t_last = batch_last if t_last is None else max(t_last, batch_last)

        if polarity == "on":
            events = events[events["p"] != 0]
        elif polarity == "off":
            events = events[events["p"] == 0]
        if events.size:
            indices = events["y"] * width + events["x"]
            if np.any(indices >= pixel_count):
                raise ValueError(
                    f"{path.name} contains events outside {width}x{height}"
                )
            if signed:
                weights = events["p"].astype(np.int8) * 2 - 1
                window = np.bincount(indices, weights=weights, minlength=pixel_count)
            else:
                window = np.bincount(indices, minlength=pixel_count)
            used_events += int(events.size)
        else:
            window = np.zeros(pixel_count, dtype=np.float64)
        frame_sum += transform_frames(window, transform)

    if total_events == 0 or frame_count == 0:
        raise ValueError(f"recording contains no CD events: {path}")

    metadata: dict[str, int | list[int] | None] = {
        "shape": [height, width],
        "events_total": total_events,
        "events_used": used_events,
        "accumulation_us": accumulation_us,
        "frames_averaged": frame_count,
        "t_first_us": t_first,
        "t_last_us": t_last,
        "duration_us": None if t_first is None or t_last is None else t_last - t_first,
    }
    return (frame_sum / frame_count).reshape(height, width), metadata


def transform_frames(frames: np.ndarray, transform: str) -> np.ndarray:
    """Transform event counts before spatial correlation."""
    values = frames.astype(np.float64)
    if transform == "raw":
        return values
    if transform == "sqrt":
        return np.sign(values) * np.sqrt(np.abs(values))
    if transform == "log1p":
        return np.sign(values) * np.log1p(np.abs(values))
    raise ValueError(f"unknown transform: {transform}")


def block_mean(frame: np.ndarray, size: int) -> np.ndarray:
    """Mean over non-overlapping ``size``×``size`` blocks, edge-padded."""
    height, width = frame.shape
    padded = np.pad(frame, ((0, (-height) % size), (0, (-width) % size)), mode="edge")
    blocks_y, blocks_x = padded.shape[0] // size, padded.shape[1] // size
    return padded.reshape(blocks_y, size, blocks_x, size).mean(axis=(1, 3))


def box_blur(frame: np.ndarray, size: int) -> np.ndarray:
    """Edge-padded separable moving average with window ``size``."""
    blurred = np.asarray(frame, dtype=np.float64)
    if size <= 1:
        return blurred.copy()
    for axis in (0, 1):
        before = size // 2
        widths: list[tuple[int, int]] = [(0, 0), (0, 0)]
        widths[axis] = (before, size - 1 - before)
        padded = np.pad(blurred, widths, mode="edge")
        cumulative = np.cumsum(padded, axis=axis)
        zeros_shape = list(cumulative.shape)
        zeros_shape[axis] = 1
        cumulative = np.concatenate([np.zeros(zeros_shape), cumulative], axis=axis)
        length = blurred.shape[axis]
        upper = np.take(cumulative, np.arange(size, size + length), axis=axis)
        lower = np.take(cumulative, np.arange(length), axis=axis)
        blurred = (upper - lower) / size
    return blurred


def high_pass(frame: np.ndarray, size: int) -> np.ndarray:
    """Remove spatial structure larger than ``size`` pixels from a frame."""
    if size <= 1:
        return np.asarray(frame, dtype=np.float64).copy()
    return np.asarray(frame, dtype=np.float64) - box_blur(frame, size)


def signal_window(
    frames: np.ndarray, margin: int, smooth_px: int = 16, percentile: float = 97.0
) -> tuple[slice, slice]:
    """Smallest common window covering the bright signal in every frame.

    Each frame is block-averaged, thresholded at a percentile of its own
    values (the signal dominates the top few percent of pixels even when
    background levels differ between recordings), and the union of the
    resulting bounding boxes - padded by ``margin`` - is returned.
    """
    rows_lo: list[int] = []
    rows_hi: list[int] = []
    cols_lo: list[int] = []
    cols_hi: list[int] = []
    for frame in frames:
        low = block_mean(frame, smooth_px)
        mask = low >= np.percentile(low, percentile)
        if mask.any():
            ys, xs = np.nonzero(mask)
            rows_lo.append(int(ys.min()))
            rows_hi.append(int(ys.max()) + 1)
            cols_lo.append(int(xs.min()))
            cols_hi.append(int(xs.max()) + 1)
        else:
            rows_lo.append(0)
            rows_hi.append(low.shape[0])
            cols_lo.append(0)
            cols_hi.append(low.shape[1])
    height, width = frames.shape[1:]
    row = slice(
        max(min(rows_lo) * smooth_px - margin, 0),
        min(max(rows_hi) * smooth_px + margin, height),
    )
    column = slice(
        max(min(cols_lo) * smooth_px - margin, 0),
        min(max(cols_hi) * smooth_px + margin, width),
    )
    return row, column


def pearson_matrix(
    frames: np.ndarray, support: np.ndarray | None = None
) -> np.ndarray:
    """Pairwise Pearson coefficients between flattened frames.

    ``support`` marks pixels that carry signal (nonzero before filtering).
    Each pair is correlated only over pixels active in either frame, so a
    shared empty background cannot inflate the coefficient; without
    ``support`` every pixel participates.
    """
    count = frames.shape[0]
    flat = np.asarray(frames, dtype=np.float64).reshape(count, -1)
    support_flat = (
        None if support is None else np.asarray(support, bool).reshape(count, -1)
    )
    matrix = np.eye(count, dtype=np.float64)
    for first in range(count):
        for second in range(first + 1, count):
            if support_flat is None:
                mask = np.ones(flat.shape[1], dtype=bool)
            else:
                mask = support_flat[first] | support_flat[second]
            a, b = flat[first, mask], flat[second, mask]
            if a.size < 2 or a.std() == 0 or b.std() == 0:
                raise ValueError(
                    f"cannot correlate constant frame(s) at index "
                    f"{[index for index in (first, second)]}"
                )
            coefficient = float(np.corrcoef(a, b)[0, 1])
            matrix[first, second] = matrix[second, first] = np.clip(
                coefficient, -1.0, 1.0
            )
    return matrix


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_grayscale_png(path: Path, frame: np.ndarray) -> None:
    """Write a dependency-free 8-bit preview with robust intensity scaling."""
    values = np.asarray(frame, dtype=np.float64)
    low, high = np.percentile(values, [0.1, 99.9])
    if high <= low:
        high = low + 1.0
    image = np.clip((values - low) / (high - low), 0.0, 1.0)
    image = np.rint(image * 255).astype(np.uint8)
    height, width = image.shape
    scanlines = b"".join(b"\x00" + row.tobytes() for row in image)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _heat_color(value: float) -> str:
    """Blue-white-red diverging color for a coefficient in [-1, 1]."""
    value = float(np.clip(value, -1.0, 1.0))
    if value < 0:
        fraction = value + 1.0
        rgb = (round(45 + 210 * fraction), round(95 + 160 * fraction), 255)
    else:
        fraction = value
        rgb = (255, round(255 - 205 * fraction), round(255 - 205 * fraction))
    return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"


def write_heatmap_svg(path: Path, matrix: np.ndarray, labels: Sequence[str]) -> None:
    """Write a labeled, fixed-scale Pearson correlation heat map as SVG."""
    import matplotlib

    matplotlib.use("Agg")
    import seaborn as sns
    from matplotlib import pyplot as plt

    side = 1.6 + 0.9 * len(labels)
    figure, axis = plt.subplots(figsize=(side, side))
    sns.heatmap(
        np.asarray(matrix, dtype=np.float64),
        xticklabels=labels,
        yticklabels=labels,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        center=0.0,
        square=True,
        linewidths=0.5,
        linecolor="white",
        cbar_kws={
            "label": "Pearson correlation coefficient (r)",
            "ticks": [-1.0, 0.0, 1.0],
        },
        ax=axis,
    )
    axis.set_title("EVT3 scene Pearson correlation")
    axis.set_xlabel("Recording")
    axis.set_ylabel("Recording")
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def write_matrix_csv(path: Path, matrix: np.ndarray, labels: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["recording", *labels])
        for label, row in zip(labels, matrix, strict=True):
            writer.writerow([label, *(f"{value:.10f}" for value in row)])


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def analyze(args: argparse.Namespace) -> Path:
    recordings = discover_recordings(args.pattern)
    labels = [label for label, _ in recordings]
    output = args.output.expanduser().resolve()
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []
    records_metadata: list[dict[str, object]] = []

    with load_openevt(args.openevt_library) as openevt:
        expected_shape: tuple[int, int] | None = None
        for index, (label, path) in enumerate(recordings, start=1):
            print(
                f"[{index}/{len(recordings)}] Decoding {path.name} ({label})...",
                flush=True,
            )
            frame, metadata = build_activity_frame(
                openevt,
                path,
                args.polarity,
                args.accumulation_ms * 1_000,
                args.transform,
            )
            if expected_shape is None:
                expected_shape = frame.shape
            elif frame.shape != expected_shape:
                raise ValueError(
                    f"sensor shape mismatch: {path.name} is {frame.shape}, expected {expected_shape}"
                )
            frames.append(frame)
            np.save(frames_dir / f"{label}_activity.npy", frame)
            write_grayscale_png(frames_dir / f"{label}_activity.png", frame)
            records_metadata.append({"label": label, "path": str(path), **metadata})

    stack = np.stack(frames)
    crop_window: tuple[slice, slice] | None = None
    if args.crop:
        crop_window = signal_window(stack, args.crop_margin)
        stack = stack[:, crop_window[0], crop_window[1]]
        print(
            f"Cropped to rows {crop_window[0].start}:{crop_window[0].stop}, "
            f"columns {crop_window[1].start}:{crop_window[1].stop}"
        )
    support = stack != 0
    if args.highpass_px > 1 or crop_window is not None:
        if args.highpass_px > 1:
            stack = np.stack([high_pass(frame, args.highpass_px) for frame in stack])
        for label, frame in zip(labels, stack, strict=True):
            np.save(frames_dir / f"{label}_processed.npy", frame)
            write_grayscale_png(frames_dir / f"{label}_processed.png", frame)

    correlation = pearson_matrix(stack, support)
    np.save(output / "pearson_correlation.npy", correlation)
    write_matrix_csv(output / "pearson_correlation.csv", correlation, labels)
    write_heatmap_svg(output / "pearson_correlation_heatmap.svg", correlation, labels)
    metadata = {
        "method": "Pearson correlation of cropped, high-passed, temporally averaged EVT3 activity frames, restricted to pixels active in either frame of each pair",
        "polarity": args.polarity,
        "transform": args.transform,
        "accumulation_ms": args.accumulation_ms,
        "crop": None
        if crop_window is None
        else {
            "rows": [crop_window[0].start, crop_window[0].stop],
            "columns": [crop_window[1].start, crop_window[1].stop],
        },
        "highpass_px": args.highpass_px,
        "heatmap_scale": [-1.0, 1.0],
        "recordings": records_metadata,
    }
    (output / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote correlation analysis to {output}")
    return output


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        default="data/raw/evt3_raw/spectral_*.raw",
        help="glob for recordings; the last underscore/hyphen number is the wavelength",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/spectral_correlation"),
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--accumulation-ms",
        type=positive_int,
        default=10,
        help="activity-frame accumulation interval in milliseconds (default: %(default)s)",
    )
    parser.add_argument(
        "--polarity",
        choices=("both", "on", "off", "signed"),
        default="both",
        help="event values accumulated into each activity frame (default: %(default)s)",
    )
    parser.add_argument(
        "--transform",
        choices=("raw", "sqrt", "log1p"),
        default="log1p",
        help="variance-stabilizing transform before correlation (default: %(default)s)",
    )
    parser.add_argument(
        "--no-crop",
        dest="crop",
        action="store_false",
        help="correlate full frames instead of cropping to the signal window",
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
        help="remove spatial structure larger than this many pixels before "
        "correlating; 0 disables (default: %(default)s)",
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
