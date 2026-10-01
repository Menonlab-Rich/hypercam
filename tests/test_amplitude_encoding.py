# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-01
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hypercam.analysis import amplitude_encoding
from hypercam.analysis.amplitude_encoding import (
    direction_statistics,
    excess_chromatic_variance,
    flux_normalize,
    log_ratio_map,
    signal_floor_mask,
    ssim_components,
)

EVENT_DTYPE = np.dtype(
    {"names": ("x", "y", "p", "t"), "formats": ("u8", "u8", "u1", "u8")}
)


def make_events(rows):
    return np.array(rows, dtype=EVENT_DTYPE)


class FakeIterator:
    def __init__(self, events, shape):
        self._events = events
        self._shape = shape
        self._window = 0

    def shape(self):
        return self._shape

    def next_delta(self, dt):
        if self._window * dt > self._events["t"].max(initial=0):
            raise StopIteration
        start = self._window * dt
        end = start + dt
        self._window += 1
        return self._events[(self._events["t"] >= start) & (self._events["t"] < end)]


class FakeRawFileReader:
    sources: dict[str, tuple[np.ndarray, tuple[int, int]]] = {}

    def __init__(self, path):
        self._events, self._shape = type(self).sources[str(path)]

    def iter(self):
        return FakeIterator(self._events, self._shape)


@pytest.fixture()
def fake_openevt():
    return SimpleNamespace(RawFileReader=FakeRawFileReader)


def test_ssim_identical_frames_are_perfect():
    pattern = np.outer(np.arange(16.0), np.arange(16.0)) + 1.0
    result = ssim_components(pattern, pattern.copy())
    assert result["ssim"] == pytest.approx(1.0)
    assert result["luminance"] == pytest.approx(1.0)
    assert result["contrast"] == pytest.approx(1.0)
    assert result["structure"] == pytest.approx(1.0)
    assert result["ssim_map"].shape == pattern.shape


def test_ssim_separates_gain_and_structure():
    # pure gain difference: structure stays perfect, contrast/luminance drop -
    # exactly the amplitude-channel information Pearson is blind to
    pattern = np.outer(np.arange(16.0), np.arange(16.0)) + 1.0
    gain = 2.0 * pattern
    result = ssim_components(pattern, gain)
    assert result["structure"] == pytest.approx(1.0)
    assert result["contrast"] < 1.0
    assert result["luminance"] < 1.0
    # opposite structure: covariance collapses; the C3 stabilization keeps the
    # statistic bounded, so "opposite" reads as well below perfect, not negative
    checker = 10.0 * (((np.arange(16)[:, None] + np.arange(16)[None, :]) % 2))
    result = ssim_components(pattern, checker)
    assert result["structure"] < 0.5
    assert result["ssim"] < 0.9


def test_flux_normalization_removes_scalar_amplitude():
    support = np.ones((8, 8), dtype=bool)
    shape = np.outer(np.arange(8.0), np.arange(8.0)) + 0.5
    first, scalar_first = flux_normalize(shape, support)
    second, scalar_second = flux_normalize(3.0 * shape, support)
    # separable null: a scalar per-band brightness must divide out exactly
    np.testing.assert_allclose(first, second)
    assert scalar_second == pytest.approx(3.0 * scalar_first)
    with pytest.raises(ValueError, match="no positive signal"):
        flux_normalize(np.zeros((8, 8)), support)


def test_signal_floor_mask_requires_every_band():
    stack = np.zeros((3, 8, 8))
    stack[0, 0, 0] = 10.0
    stack[1, 0, 0] = 10.0
    # third band has no signal at (0,0): the pixel must be excluded
    stack[2, 1, 1] = 10.0
    mask = signal_floor_mask(stack, fraction=0.05)
    assert not mask[0, 0]
    assert not mask[1, 1]


def test_log_ratio_map_is_symmetric_and_masked():
    first = np.full((4, 4), 4.0)
    second = np.full((4, 4), 1.0)
    mask = np.ones((4, 4), dtype=bool)
    mask[0, 0] = False
    ratio = log_ratio_map(first, second, mask)
    assert np.isnan(ratio[0, 0])
    np.testing.assert_allclose(ratio[1:, 1:], 2.0)


def test_direction_statistics_detect_separable_and_chromatic():
    rng = np.random.default_rng(7)
    # separable: every pixel's 3-band response is a positive multiple of one
    # common spectral vector -> all directions parallel -> resultant length 1
    weights = rng.uniform(1.0, 10.0, size=(400, 1))
    spectral = np.array([1.0, 0.6, 0.3])
    stack = (weights * spectral[None, :]).T[:, :, None]  # (bands, 400, 1)
    result = direction_statistics(stack, np.ones((400, 1), dtype=bool))
    assert result["resultant_length"] == pytest.approx(1.0)
    assert result["eigenvalues"][1] == pytest.approx(0.0, abs=1e-9)
    assert result["mean_deviation_deg"] == pytest.approx(0.0, abs=1e-6)
    # chromatic: the second and third bands' spatial patterns are independent of
    # the first (and of each other), so response directions spread widely
    chromatic = np.stack(
        [
            weights.ravel(),
            rng.uniform(1.0, 10.0, size=400),
            rng.uniform(1.0, 10.0, size=400),
        ]
    )[:, :, None]
    result = direction_statistics(chromatic, np.ones((400, 1), dtype=bool))
    assert result["resultant_length"] < 0.97
    assert result["mean_deviation_deg"] > 15.0


def test_excess_chromatic_variance_separates_null_from_chromatic():
    rng = np.random.default_rng(11)
    # separable null: bands differ only by scalars; flux normalization removes
    # them exactly, so the cross-band log variance is zero beyond noise
    shape = rng.uniform(1.0, 5.0, size=(8, 8))
    scalars = np.array([1.0, 0.7, 0.4])[:, None, None]
    stack = shape[None, :, :] * scalars
    stack = stack / stack.mean(axis=(1, 2), keepdims=True)
    mask = np.ones((8, 8), dtype=bool)
    excess_mean, excess_map = excess_chromatic_variance(stack, noise_variance=0.0, mask=mask)
    assert excess_mean == pytest.approx(0.0, abs=1e-9)
    # chromatic: an independent second pattern added per band creates excess
    chromatic = stack + rng.uniform(0.0, 2.0, size=(3, 8, 8))
    chromatic_mean, _ = excess_chromatic_variance(
        chromatic, noise_variance=0.0, mask=mask
    )
    assert chromatic_mean > 0.1
    assert excess_map.shape == (8, 8)
    assert np.isfinite(excess_map).all()


def _add_recording(path, counts_per_window, shape=(16, 16)):
    events = []
    for window, frame_counts in enumerate(counts_per_window):
        slot = 0
        for (x, y), count in frame_counts.items():
            for _ in range(count):
                events.append((x, y, 1, window * 1_000 + slot))
                slot += 1
    FakeRawFileReader.sources[str(path)] = (make_events(events), shape)
    return path


def test_analyze_smoke_writes_all_outputs(tmp_path, fake_openevt, monkeypatch):
    @contextmanager
    def fake_load_openevt(library=None):
        yield fake_openevt

    monkeypatch.setattr(amplitude_encoding, "load_openevt", fake_load_openevt)

    def pattern_counts(scale):
        return {
            (x, y): max(1, int(round(scale * ((x - 4) + (y - 4) + 6))))
            for x in range(4, 8)
            for y in range(4, 8)
        }

    windows = [pattern_counts(scale) for scale in (1.0, 1.1, 0.9, 1.0, 1.1, 0.9, 1.0, 1.0)]
    for name, windows in (
        ("circle_blue", windows),
        ("circle_green", [{p: max(1, c // 2) for p, c in w.items()} for w in windows]),
        ("circle_red", [{p: max(1, c // 3) for p, c in w.items()} for w in windows]),
    ):
        path = tmp_path / f"{name}.raw"
        path.touch()
        _add_recording(path, windows)

    output = tmp_path / "out"
    args = SimpleNamespace(
        pattern=str(tmp_path / "circle_*.raw"),
        control_pattern=None,
        output=output,
        accumulation_ms=1.0,
        duration=0.008,
        transform="raw",
        splits=2,
        crop_margin=2,
        signal_fraction=0.05,
        ssim_sigma=1.5,
        openevt_library=None,
    )
    amplitude_encoding.analyze(args)

    for name in (
        "analysis_metadata.json",
        "ssim.csv",
        "separability.json",
        "conclusions.json",
        "conclusions.md",
        "normalized_sheet_0.008s.png",
        "deviation_angle_map.png",
        "excess_variance_map.png",
        "direction_scatter.png",
    ):
        assert (output / name).exists(), name
    assert (output / "ssim_maps" / "blue_green_ssim_map.png").exists()
    assert (output / "gain_maps" / "blue_green_log2_ratio.png").exists()
    assert (output / "amplitude_frames" / "blue_normalized_0.008s.npy").exists()

    conclusions = json.loads((output / "conclusions.json").read_text())
    # near-separable synthetic response: normalized maps nearly identical
    assert conclusions["pairs"]["blue_green"]["ssim"] > 0.9
    assert conclusions["separability"]["resultant_length"] > 0.9