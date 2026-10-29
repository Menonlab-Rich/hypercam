# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-29
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""EVT3 decoding, event caching, and clip assembly at any frame density.

The model must operate across a variety of frame densities: a sample is a
clip of ``n_frames`` model frames, each accumulating ``frame_ms`` of events,
spanning ``acc_time = n_frames * frame_ms``; the system's effective fps is

    effective_fps = n_frames / acc_time = 1000 / frame_ms.

Densities reach 1000 effective fps (frame_ms = 1 ms), so the cache stores
DECODED EVENTS per recording (pixel index, timestamp, polarity — ~9 bytes
per event), not pre-rasterized frames: at sub-millisecond frame windows even
a 10 ms frame cache would miss the finest densities, while events support
EVERY density (and random clip starts) without ever re-decoding.

Accumulation floor: empirical work shows one model frame needs at least
``min_accumulations`` individual accumulation windows to carry usable
information. With the fine accumulation unit ``accumulation_us`` (default
250 us), the minimum frame_ms is 4 * 0.25 = 1 ms — exactly the 1000 fps
floor. ``frames_per_model_frame`` enforces the floor at config time.

Clip assembly: model frame j counts events with timestamps in
[t0 + j*frame_ms, t0 + (j+1)*frame_ms), rasterizes to (H, W), and applies the
count transform (log1p by default). The cache key hashes the recording
identity and the OpenEVT build, so a decoder rebuild cleanly invalidates it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import numpy as np

logger = logging.getLogger(__name__)


@contextmanager
def load_openevt(library_dir: Path | None) -> Iterator[object]:
    """Load the OpenEVT Python extension together with its device plugins.

    ``library_dir`` should contain ``libopenevt.so`` (the extension, built
    with ``cargo build --release -p openevt --features python``) and
    ``libopenevt_plugins.so`` (the raw-file device plugin, built with a
    SEPARATE ``cargo build --release -p openevt-plugins``; combining the two
    in one cargo invocation unifies the ``python`` feature into the plugin
    library and it fails to dlopen with undefined Python symbols).

    Falls back to an installed PyPI ``openevt`` when the local build is
    absent; that fallback needs ``OPENEVT_PLUGIN_PATH`` to point at a
    compatible plugin directory or opening files will fail with a clear
    runtime error.
    """
    library: Path | None = None
    if library_dir is not None:
        candidate = Path(library_dir).expanduser().resolve() / "libopenevt.so"
        library = candidate if candidate.is_file() else None
    if library is None:
        import openevt  # noqa: PLC0415 - deliberate late import for fallback

        yield openevt
        return

    plugin_directory = library.parent
    if not (plugin_directory / "libopenevt_plugins.so").is_file():
        raise FileNotFoundError(
            "the OpenEVT standard plugins were not built alongside "
            f"{library.name}; expected {plugin_directory}/libopenevt_plugins.so "
            "(build it with: cargo build --release -p openevt-plugins)"
        )

    previous_plugin_path = os.environ.get("OPENEVT_PLUGIN_PATH")
    os.environ["OPENEVT_PLUGIN_PATH"] = (
        previous_plugin_path if previous_plugin_path is not None else str(plugin_directory)
    )
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


def transform_counts(values: np.ndarray, transform: str) -> np.ndarray:
    """Transform non-negative event counts to the model-input scale."""
    floats = values.astype(np.float64)
    if transform == "raw":
        return floats
    if transform == "sqrt":
        return np.sqrt(floats)
    if transform == "log1p":
        return np.log1p(floats)
    raise ValueError(f"unknown transform: {transform}")


def decode_events(openevt: object, raw_path: Path) -> dict[str, np.ndarray | int]:
    """Decode a whole recording into flat event columns.

    Returns a dict with ``idx`` (uint32 pixel index y*width+x), ``t``
    (uint32 timestamp in microseconds, relative to stream start), ``p``
    (uint8 polarity), and the sensor geometry. Draining via ``next_batch``
    (rather than fixed accumulation windows) keeps the decode single-pass and
    density-independent.
    """
    reader = openevt.RawFileReader(str(raw_path))
    iterator = reader.iter()
    height, width = (int(value) for value in iterator.shape())
    idx_parts: list[np.ndarray] = []
    t_parts: list[np.ndarray] = []
    p_parts: list[np.ndarray] = []
    while True:
        try:
            events = iterator.next_batch()
        except OSError as error:
            # Pre-PR#5 OpenEVT builds raised EOF as OSError instead of None.
            if "end of file" in str(error).lower() or str(error).lower() == "eof":
                break
            raise
        if events is None:
            # OpenEVT >= PR #5: next_batch returns None at end of stream.
            break
        if events.size:
            idx_parts.append(events["y"].astype(np.uint32) * width + events["x"].astype(np.uint32))
            t_parts.append(events["t"].astype(np.uint32))
            p_parts.append(events["p"].astype(np.uint8))
    if not idx_parts:
        raise ValueError(f"recording contains no usable events: {raw_path}")
    return {
        "idx": np.concatenate(idx_parts),
        "t": np.concatenate(t_parts),
        "p": np.concatenate(p_parts),
        "height": height,
        "width": width,
    }


def events_cache_key(raw_path: Path, *, library_dir: Path | None = None) -> str:
    """Stable hash of recording identity and the OpenEVT build.

    The library identity matters: decoder semantics shift across builds
    (PR #5 changed end-of-file delivery), so rebuilding openevt must
    invalidate cached events.
    """
    stat = raw_path.stat()
    decoder = ""
    if library_dir is not None:
        extension = Path(library_dir) / "libopenevt.so"
        if extension.is_file():
            extension_stat = extension.stat()
            decoder = f"{extension_stat.st_size}:{extension_stat.st_mtime_ns}"
    payload = json.dumps(
        {
            "recording": raw_path.name,
            "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "decoder": decoder,
            "format": "events-v1",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def load_or_decode_events(
    raw_path: Path,
    cache_dir: Path,
    *,
    library_dir: Path | None,
) -> tuple[Path, dict]:
    """Return (cache_subdir, metadata) for one recording's event cache.

    Columns live in separate ``.npy`` files so data.py can memory-map each
    one lazily; metadata.json records geometry and stream duration.
    """
    key = events_cache_key(raw_path, library_dir=library_dir)
    recording_cache = cache_dir / key
    metadata_path = recording_cache / "metadata.json"
    if metadata_path.is_file() and (recording_cache / "t.npy").is_file():
        metadata = json.loads(metadata_path.read_text())
        metadata["cache_key"] = key
        logger.debug("event cache hit: %s", raw_path.name)
        return recording_cache, metadata

    size_mb = raw_path.stat().st_size / 1e6
    logger.info("decoding %s (%.0f MB) -> event cache (CPU; run predecode.py once to avoid this)", raw_path.name, size_mb)
    decode_start = time.perf_counter()
    with load_openevt(library_dir) as openevt:
        decoded = decode_events(openevt, raw_path)
    decode_seconds = time.perf_counter() - decode_start
    num_events = int(decoded["t"].shape[0])
    metadata = {
        "cache_key": key,
        "source": str(raw_path),
        "shape": [int(decoded["height"]), int(decoded["width"])],
        "num_events": num_events,
        "t_first_us": int(decoded["t"].min()),
        "t_last_us": int(decoded["t"].max()),
        "duration_us": int(decoded["t"].max()) - int(decoded["t"].min()) + 1,
    }
    recording_cache.mkdir(parents=True, exist_ok=True)
    for column in ("idx", "t", "p"):
        temp_path = recording_cache / f"{column}.tmp.npy"
        np.save(temp_path, decoded[column])
        temp_path.replace(recording_cache / f"{column}.npy")
    metadata_path.write_text(json.dumps(metadata, indent=2))
    logger.info("decoded %s: %d events in %.1fs", raw_path.name, num_events, decode_seconds)
    return recording_cache, metadata


def frames_per_model_frame(
    frame_ms: float, accumulation_us: int, *, min_accumulations: int = 4
) -> int:
    """Fine accumulation windows composing one model frame (floor-checked).

    Empirically a model frame needs at least ``min_accumulations``
    individual accumulations to carry usable information; a density that
    violates the floor (or does not land on the accumulation grid) is a
    configuration error, not a silent rounding.
    """
    exact = frame_ms * 1000.0 / accumulation_us
    k = round(exact)
    if abs(exact - k) > 1e-9:
        raise ValueError(
            f"frame_ms={frame_ms} is not an integer multiple of the fine "
            f"accumulation window {accumulation_us / 1000} ms"
        )
    if k < min_accumulations:
        raise ValueError(
            f"frame_ms={frame_ms} gives {k} accumulations < the floor of "
            f"{min_accumulations} (max effective fps = "
            f"{1000.0 * min_accumulations * accumulation_us / 1e6:g})"
        )
    return int(k)


def build_clip(
    idx: np.ndarray,
    t: np.ndarray,
    p: np.ndarray,
    *,
    t_start_us: int,
    n_frames: int,
    frame_us: int,
    height: int,
    width: int,
    polarity_mode: str = "both",
    transform: str = "log1p",
) -> np.ndarray:
    """Assemble (n_frames, H, W) float32 counts from cached event columns.

    Model frame j receives events with ``t`` in
    ``[t_start_us + j*frame_us, t_start_us + (j+1)*frame_us)``; counts are
    summed over the WHOLE frame window (the accumulation-floor rule is about
    how much time elapses, not about sub-window bookkeeping).
    """
    pixel_count = height * width
    clip = np.zeros((n_frames, height, width), dtype=np.float64)
    t_end = t_start_us + n_frames * frame_us
    lo = int(np.searchsorted(t, t_start_us))
    hi = int(np.searchsorted(t, t_end))
    frame_ids = (t[lo:hi].astype(np.int64) - t_start_us) // frame_us
    window_idx = idx[lo:hi]
    window_pol = p[lo:hi]
    if polarity_mode == "on":
        keep = window_pol != 0
    elif polarity_mode == "off":
        keep = window_pol == 0
    else:
        keep = np.ones(window_pol.shape, dtype=bool)
    for frame_index in range(n_frames):
        selected = keep & (frame_ids == frame_index)
        if np.any(selected):
            clip[frame_index] = np.bincount(
                window_idx[selected], minlength=pixel_count
            ).reshape(height, width)
    return transform_counts(clip, transform).astype(np.float32)


def clip_starts(num_fine: int, clip_frames: int, max_clips: int | None) -> list[int]:
    """Deterministic, evenly spaced non-overlapping clip starts."""
    count = num_fine // clip_frames
    if count <= 0:
        return []
    if max_clips is None or max_clips >= count:
        return [index * clip_frames for index in range(count)]
    picks = np.linspace(0, count - 1, max_clips).round().astype(int)
    return [int(pick) * clip_frames for pick in sorted(set(picks.tolist()))]


if __name__ == "__main__":
    # Selftest: cache events for one paired recording, then build clips at
    # several densities (including the 1000 fps floor) and verify shape,
    # monotone count accumulation, cache round-trip, and floor enforcement.
    project_root = Path(__file__).resolve().parent
    repo_root = project_root.parents[3]
    raw = repo_root / "data/raw/evt3/2026-10-19_14-43-49_2026-10-19_14:43:50.raw"
    if not raw.is_file():
        print(f"selftest skipped: {raw} not present")
        raise SystemExit(0)
    import time

    library_dir = repo_root / "openevt/target/release"
    start = time.time()
    cache_dir, meta = load_or_decode_events(
        raw, project_root / "outputs/cache", library_dir=library_dir
    )
    print(
        f"event cache: {meta['num_events']} events, duration "
        f"{meta['duration_us']/1e6:.2f}s in {time.time()-start:.1f}s"
    )
    cache_dir2, meta2 = load_or_decode_events(
        raw, project_root / "outputs/cache", library_dir=library_dir
    )
    assert cache_dir == cache_dir2 and meta == meta2, "cache round-trip mismatch"

    idx = np.load(cache_dir / "idx.npy", mmap_mode="r")
    t = np.load(cache_dir / "t.npy", mmap_mode="r")
    p = np.load(cache_dir / "p.npy", mmap_mode="r")
    height, width = meta["shape"]
    accumulation_us = 250  # 1000 fps floor with min_accumulations=4
    for n_frames, frame_ms in ((2, 1.0), (4, 1.0), (8, 4.0), (2, 100.0), (8, 250.0)):
        k = frames_per_model_frame(frame_ms, accumulation_us)
        frame_us = int(frame_ms * 1000)
        clip = build_clip(
            idx, t, p, t_start_us=int(t[0]), n_frames=n_frames, frame_us=frame_us,
            height=height, width=width,
        )
        assert clip.shape == (n_frames, height, width) and clip.dtype == np.float32
        assert (clip >= 0).all() and np.isfinite(clip).all()
        print(f"  clip n={n_frames} frame_ms={frame_ms:g} k={k} -> eff_fps={1000/frame_ms:g}")

    # A longer frame window must dominate a shorter one from the same start.
    short = build_clip(idx, t, p, t_start_us=int(t[0]), n_frames=1, frame_us=1000, height=height, width=width)
    long = build_clip(idx, t, p, t_start_us=int(t[0]), n_frames=1, frame_us=10_000, height=height, width=width)
    assert (short <= long + 1e-6).all()

    try:
        frames_per_model_frame(10.0, 10_000)  # one 10 ms accumulation < floor of 4
        raise AssertionError("floor not enforced")
    except ValueError as error:
        assert "accumulations" in str(error)
    print("EVT3 SELFTEST OK")
