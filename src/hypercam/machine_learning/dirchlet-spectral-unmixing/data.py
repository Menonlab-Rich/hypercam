# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-29
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Density-aware Dataset: event clips + constant spectral simplex targets.

One sample is a clip of ``n_frames`` model frames (each accumulating
``frame_ms``) drawn from a paired recording's cached events. Every recording
contributes samples at EVERY configured density — including several
densities with the SAME effective fps but different frame counts — and all
samples of a recording share its constant spectral target.

Clip placement:
- train: each (recording, density, slot) gets a fresh RANDOM start time per
  epoch (seeded by epoch+index so runs are reproducible), exposing the model
  to every part of the recording instead of a fixed prefix;
- val/test: deterministic evenly spaced starts so scores are comparable
  across epochs and checkpoints.

Batches are grouped by density (``DensityGroupedBatchSampler``) so a batch
never mixes frame counts, and densities interleave round-robin through the
epoch (not "the first 100 samples at 20 fps, then 40 fps, ...").
"""

from __future__ import annotations

import csv
import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, Sampler

import evt3

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent


def density_features(n_frames: int, frame_ms: float) -> list[float]:
    """Conditioning vector telling the model its own frame density.

    [log10(effective_fps), log2(n_frames), log10(acc_time_s)] — evidence
    strength S should grow with more/denser frames, and the model needs to
    know which operating point it is at to be calibrated across densities.
    """
    effective_fps = 1000.0 / frame_ms
    acc_time_s = n_frames * frame_ms / 1000.0
    return [
        float(np.log10(effective_fps)),
        float(math.log2(n_frames)),
        float(np.log10(acc_time_s)),
    ]


@dataclass
class ClipSlot:
    """One (recording, density, slot) sample; start resolved per epoch."""

    stem: str
    band_label: int
    cache_dir: Path
    height: int
    width: int
    n_frames: int
    frame_us: int
    max_start_us: int
    fixed_start_us: int | None  # set for val/test; None = random (train)
    density_index: int
    frame_ms: float
    target_path: Path


def center_crop(clip: np.ndarray, crop_size: int | None) -> np.ndarray:
    """Centered square crop over the trailing (H, W) axes; None = no-op."""
    if crop_size is None:
        return clip
    height, width = clip.shape[-2:]
    if crop_size >= min(height, width):
        return clip
    top = (height - crop_size) // 2
    left = (width - crop_size) // 2
    return clip[..., top : top + crop_size, left : left + crop_size]


def box_blur(frame: np.ndarray, size: int) -> np.ndarray:
    """Edge-padded separable moving average (vendored from the repo)."""
    blurred = np.asarray(frame, dtype=np.float64)
    if size <= 1:
        return blurred.copy()
    for axis in (0, 1):
        before = size // 2
        pad_widths: list[tuple[int, int]] = [(0, 0), (0, 0)]
        pad_widths[axis] = (before, size - 1 - before)
        padded = np.pad(blurred, pad_widths, mode="edge")
        cumulative = np.cumsum(padded, axis=axis)
        zeros_shape = list(cumulative.shape)
        zeros_shape[axis] = 1
        cumulative = np.concatenate([np.zeros(zeros_shape), cumulative], axis=axis)
        length = blurred.shape[axis]
        upper = np.take(cumulative, np.arange(size, size + length), axis=axis)
        lower = np.take(cumulative, np.arange(length), axis=axis)
        blurred = (upper - lower) / size
    return blurred


def high_pass(clip: np.ndarray, size: int) -> np.ndarray:
    """Per-frame common-mode high-pass (removes structure > size pixels)."""
    if size <= 1:
        return clip
    return np.stack([np.asarray(f, dtype=np.float64) - box_blur(f, size) for f in clip])


def normalize_p999(clip: np.ndarray) -> np.ndarray:
    """Scale each frame by its 99.9th percentile (withdoe convention)."""
    scales = np.percentile(clip, 99.9, axis=(-2, -1), keepdims=True)
    return clip / np.clip(scales, 1e-9, None)


class SplitMissingError(ValueError):
    """Raised when a manifest split has no rows (a legitimate skip signal)."""


def split_row_count(manifest_path: Path, split: str) -> int:
    """How many manifest rows belong to a split (before building a dataset)."""
    with manifest_path.open(newline="") as handle:
        return sum(1 for row in csv.DictReader(handle) if row["split"] == split)


class ManifestDataset(Dataset):
    """All density clips for one manifest split."""

    def __init__(
        self,
        manifest_path: Path,
        split: str,
        *,
        library_dir: Path | None,
        cache_dir: Path,
        densities: list[dict],
        polarity_mode: str = "both",
        accumulation_us: int = 250,
        min_accumulations_per_frame: int = 4,
        transform: str = "log1p",
        clips_per_density: int | None = 4,
        max_recordings: int | None = None,
        crop: int | None = None,
        highpass_px: int = 0,
        normalize: str = "none",
    ):
        self.manifest_path = Path(manifest_path)
        self.split = split
        self.cache_dir = Path(cache_dir)
        self.library_dir = Path(library_dir) if library_dir is not None else None
        self.polarity_mode, self.accumulation_us = polarity_mode, int(accumulation_us)
        self.transform, self.crop = transform, crop
        self.highpass_px, self.normalize = int(highpass_px), normalize
        self.min_accumulations = int(min_accumulations_per_frame)
        self.densities = [
            {"n_frames": int(d["n_frames"]), "frame_ms": float(d["frame_ms"])}
            for d in densities
        ]
        if not self.densities:
            raise ValueError("data.densities must list at least one density")
        self.epoch = 0

        rows = self._read_manifest_rows()
        if max_recordings is not None:
            rows = rows[:max_recordings]
        logger.info("dataset[%s]: building %d recordings x %d densities", split, len(rows), len(self.densities))
        build_start = time.perf_counter()
        self.samples: list[ClipSlot] = []
        for row_number, row in enumerate(rows, start=1):
            recording_cache, meta = evt3.load_or_decode_events(
                Path(row["recording"]), self.cache_dir, library_dir=self.library_dir
            )
            if row_number % 20 == 0 or row_number == len(rows):
                logger.info(
                    "dataset[%s]: %d/%d recordings ready (%d clips, %.1fs)",
                    split, row_number, len(rows), len(self.samples),
                    time.perf_counter() - build_start,
                )
            duration_us = int(meta["duration_us"])
            t_first_us = int(meta["t_first_us"])
            height, width = (int(value) for value in meta["shape"])
            for density_index, density in enumerate(self.densities):
                frame_us = int(round(density["frame_ms"] * 1000))
                evt3.frames_per_model_frame(
                    density["frame_ms"],
                    self.accumulation_us,
                    min_accumulations=self.min_accumulations,
                )
                clip_us = density["n_frames"] * frame_us
                if clip_us > duration_us:
                    continue  # recording shorter than this density's span
                count = max(1, int(clips_per_density or 1))
                fixed_starts = np.linspace(0, duration_us - clip_us, count).round().astype(int)
                for slot in range(count):
                    self.samples.append(
                        ClipSlot(
                            stem=row["stem"],
                            band_label=int(row["band_label"]),
                            cache_dir=recording_cache,
                            height=height,
                            width=width,
                            n_frames=density["n_frames"],
                            frame_us=frame_us,
                            max_start_us=duration_us - clip_us,
                            fixed_start_us=(
                                int(fixed_starts[slot]) + t_first_us
                                if split != "train"
                                else None
                            ),
                            density_index=density_index,
                            frame_ms=density["frame_ms"],
                            target_path=Path(row["target"]),
                        )
                    )
        if not self.samples:
            raise ValueError(
                f"split {self.split!r} produced no clips — recordings shorter "
                "than the coarsest density's acc_time?"
            )
        self.density_indices = np.array([s.density_index for s in self.samples])
        logger.info(
            "dataset[%s]: %d clips over %d densities in %.1fs",
            split, len(self.samples), len(self.densities), time.perf_counter() - build_start,
        )
        self.wavelength_grid = np.load(self.manifest_path.parent / "wavelength_grid.npy")
        self.num_spectral_bins = int(self.wavelength_grid.shape[0])
        self.targets_by_stem: dict[str, np.ndarray] = {}
        self.event_columns: dict[Path, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    def set_epoch(self, epoch: int) -> None:
        """Re-seed the random clip starts for train (val/test stay fixed)."""
        self.epoch = int(epoch)

    def _read_manifest_rows(self) -> list[dict[str, str]]:
        with self.manifest_path.open(newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["split"] == self.split]
        if not rows:
            raise SplitMissingError(
                f"manifest {self.manifest_path} has no rows for split {self.split!r}"
            )
        return rows

    def __len__(self) -> int:
        return len(self.samples)

    def _columns(self, cache_dir: Path):
        # Memory-map each recording's event columns once per worker; slices of
        # an mmap are cheap and keep RSS proportional to touched pages only.
        if cache_dir not in self.event_columns:
            self.event_columns = dict(list(self.event_columns.items())[-4:])
            self.event_columns[cache_dir] = (
                np.load(cache_dir / "idx.npy", mmap_mode="r"),
                np.load(cache_dir / "t.npy", mmap_mode="r"),
                np.load(cache_dir / "p.npy", mmap_mode="r"),
            )
        return self.event_columns[cache_dir]

    def _target_for(self, ref: ClipSlot) -> np.ndarray:
        if ref.stem not in self.targets_by_stem:
            self.targets_by_stem[ref.stem] = np.load(ref.target_path).astype(np.float32)
        return self.targets_by_stem[ref.stem]

    def _start_us(self, ref: ClipSlot, index: int) -> int:
        if ref.fixed_start_us is not None:
            return ref.fixed_start_us
        rng = np.random.default_rng([self.epoch, index, ref.density_index])
        return int(rng.integers(0, ref.max_start_us + 1))

    def __getitem__(self, index: int):
        ref = self.samples[index]
        idx, t, p = self._columns(ref.cache_dir)
        start_us = self._start_us(ref, index)
        clip = evt3.build_clip(
            idx,
            t,
            p,
            t_start_us=start_us,
            n_frames=ref.n_frames,
            frame_us=ref.frame_us,
            height=ref.height,
            width=ref.width,
            polarity_mode=self.polarity_mode,
            transform=self.transform,
        )
        clip = center_crop(clip, self.crop)
        if self.highpass_px > 1:
            clip = high_pass(clip, self.highpass_px)
        if self.normalize == "p999":
            clip = normalize_p999(clip)
        target = self._target_for(ref)
        meta = {
            "stem": ref.stem,
            "band_label": ref.band_label,
            "density_index": ref.density_index,
            "n_frames": ref.n_frames,
            "frame_ms": ref.frame_ms,
            "effective_fps": 1000.0 / ref.frame_ms,
            "start_us": start_us,
        }
        return (
            torch.from_numpy(np.ascontiguousarray(clip, dtype=np.float32)),
            torch.from_numpy(target),
            meta,
        )


def collate(batch):
    frames = torch.stack([item[0] for item in batch])
    targets = torch.stack([item[1] for item in batch])
    metas = [item[2] for item in batch]
    # Batches are density-grouped, so the first sample describes the batch.
    features = torch.tensor(
        density_features(metas[0]["n_frames"], metas[0]["frame_ms"]),
        dtype=torch.float32,
    ).expand(frames.shape[0], -1)
    return frames, targets, metas, features


class DensityGroupedBatchSampler(Sampler[list[int]]):
    """Yield same-density batches; shuffled within groups when training.

    Iteration rotates densities batch by batch (round-robin over groups) so
    a step never mixes frame counts and every density is seen evenly
    throughout the epoch. set_epoch forwards to the dataset so train clip
    starts refresh each epoch.
    """

    def __init__(self, dataset: ManifestDataset, batch_size: int, shuffle: bool, seed: int = 0):
        self.dataset = dataset
        self.batch_size = int(batch_size)
        self.shuffle = shuffle
        self.seed = int(seed)
        self._epoch = 0
        self.groups: dict[int, list[int]] = {}
        for position, density in enumerate(dataset.density_indices):
            self.groups.setdefault(int(density), []).append(position)

    def set_epoch(self, epoch: int) -> None:
        self._epoch = int(epoch)
        self.dataset.set_epoch(epoch)

    def __iter__(self):
        rng = np.random.default_rng(self.seed + self._epoch if self.shuffle else 0)
        queues: dict[int, list[int]] = {}
        for density, indices in sorted(self.groups.items()):
            order = list(indices)
            if self.shuffle:
                rng.shuffle(order)
            queues[density] = order
        batches: list[list[int]] = []
        while any(queues.values()):
            for density in sorted(queues):
                queue = queues[density]
                if queue:
                    batches.append(queue[: self.batch_size])
                    del queue[: self.batch_size]
        if self.shuffle:
            rng.shuffle(batches)
        yield from batches

    def __len__(self) -> int:
        return sum(
            math.ceil(len(indices) / self.batch_size)
            for indices in self.groups.values()
        )


def build_dataloaders(cfg, batch_size: int, num_workers: int) -> dict[str, DataLoader]:
    """Construct train/val/test loaders from one config tree (train.py/eval)."""
    library_dir = Path(cfg.evt3.library_dir)
    if not library_dir.is_absolute():
        library_dir = PROJECT_ROOT / library_dir
    common = dict(
        library_dir=library_dir,
        cache_dir=PROJECT_ROOT / cfg.data.cache_dir,
        densities=[dict(d) for d in cfg.data.densities],
        polarity_mode=cfg.evt3.polarity_mode,
        accumulation_us=int(cfg.evt3.accumulation_us),
        min_accumulations_per_frame=int(cfg.data.min_accumulations_per_frame),
        transform=cfg.data.transform,
        clips_per_density=cfg.data.clips_per_density,
        max_recordings=cfg.data.get("max_recordings"),
        crop=cfg.data.crop,
        highpass_px=int(cfg.data.highpass_px),
        normalize=cfg.data.normalize,
    )
    manifest_path = PROJECT_ROOT / cfg.data.manifest
    loaders = {}
    for split, shuffle in (("train", True), ("val", False), ("test", False)):
        try:
            dataset = ManifestDataset(manifest_path, split, **common)
        except SplitMissingError:
            continue  # legitimately absent split (e.g. tiny manifests) - skip
        sampler = DensityGroupedBatchSampler(
            dataset, batch_size=batch_size, shuffle=shuffle, seed=int(cfg.training.seed)
        )
        loaders[split] = DataLoader(
            dataset,
            batch_sampler=sampler,
            num_workers=num_workers,
            collate_fn=collate,
            persistent_workers=num_workers > 0,
        )
    return loaders


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Selftest: two recordings at three densities (including the 1000 fps
    # floor); verify clip shapes track the density, train starts move across
    # epochs while val starts do not, batches are density-homogeneous, and
    # the accumulation floor rejects impossible configs.
    manifest = PROJECT_ROOT / "outputs/manifests/manifest.csv"
    if not manifest.is_file():
        print("selftest skipped: run build_manifest.py first")
        raise SystemExit(0)
    densities = [
        {"n_frames": 2, "frame_ms": 1.0},    # 1000 effective fps (floor)
        {"n_frames": 4, "frame_ms": 50.0},   # 20 effective fps
        {"n_frames": 8, "frame_ms": 250.0},  # 4 effective fps
    ]
    common = dict(
        library_dir=PROJECT_ROOT.parents[3] / "openevt/target/release",
        cache_dir=PROJECT_ROOT / "outputs/cache",
        densities=densities,
        clips_per_density=2,
        max_recordings=2,
    )
    train_set = ManifestDataset(manifest, "train", **common)
    val_set = ManifestDataset(manifest, "val", **common)
    assert len(train_set) > 0 and len(val_set) > 0

    frame, target, meta = train_set[0]
    assert frame.ndim == 3 and frame.shape[0] == meta["n_frames"]
    assert target.shape[0] == train_set.num_spectral_bins
    assert abs(float(target.sum()) - 1.0) < 1e-4

    # Train starts must change across epochs; val starts must not.
    starts_epoch0 = [train_set._start_us(s, i) for i, s in enumerate(train_set.samples)]
    train_set.set_epoch(7)
    starts_epoch7 = [train_set._start_us(s, i) for i, s in enumerate(train_set.samples)]
    assert starts_epoch0 != starts_epoch7, "train clip starts are not randomized"
    assert all(s.fixed_start_us is not None for s in val_set.samples)

    by_density: dict[int, list[int]] = {}
    for index in range(len(train_set)):
        sample_frame, _, sample_meta = train_set[index]
        by_density.setdefault(sample_meta["density_index"], []).append(index)
        assert sample_frame.shape[0] == densities[sample_meta["density_index"]]["n_frames"]
        assert np.isfinite(sample_frame.numpy()).all()
    assert len(by_density) == len(densities), "a density produced no clips"

    sampler = DensityGroupedBatchSampler(train_set, batch_size=2, shuffle=True, seed=1)
    seen = 0
    for batch_indices in sampler:
        densities_in_batch = {train_set[i][2]["density_index"] for i in batch_indices}
        assert len(densities_in_batch) == 1, "batch mixed densities"
        seen += 1
    assert seen == len(sampler)
    assert abs(density_features(4, 50.0)[0] - np.log10(20.0)) < 1e-9

    # Floor enforcement: 10 ms frames on a 10 ms accumulation unit (k=1 < 4).
    try:
        ManifestDataset(
            manifest, "train",
            **{**common, "accumulation_us": 10_000,
               "densities": [{"n_frames": 2, "frame_ms": 10.0}]},
        )
        raise AssertionError("accumulation floor not enforced")
    except ValueError as error:
        assert "accumulations" in str(error)
    print(
        f"DATA SELFTEST OK ({len(train_set)} train clips, {len(val_set)} val, "
        f"{len(densities)} densities, K={train_set.num_spectral_bins})"
    )
