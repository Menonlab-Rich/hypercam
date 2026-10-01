# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-01
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

import csv
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hypercam.analysis import source_identification
from hypercam.analysis.source_identification import (
    WindowArchive,
    analyze,
    block_bounds,
    disattenuated,
    gradient_congruence,
    safe_pearson,
    spearman_brown,
    window_congruence_map,
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


def test_block_bounds_are_contiguous_disjoint_and_complete():
    assert block_bounds(10, 2) == [(0, 5), (5, 10)]
    assert block_bounds(7, 2) == [(0, 3), (3, 7)]
    assert block_bounds(8, 4) == [(0, 2), (2, 4), (4, 6), (6, 8)]
    # fewer windows than blocks: some blocks are empty, none overlap
    bounds = block_bounds(3, 4)
    assert bounds == [(0, 0), (0, 1), (1, 2), (2, 3)]
    for index in range(len(bounds) - 1):
        assert bounds[index][1] == bounds[index + 1][0]
    assert bounds[0][0] == 0 and bounds[-1][1] == 3


def test_spearman_brown_predicts_full_length_reliability():
    assert spearman_brown(0.6, 2) == pytest.approx(0.75)
    assert spearman_brown(1.0, 2) == pytest.approx(1.0)
    assert spearman_brown(0.25, 4) == pytest.approx(4 * 0.25 / 1.75)
    # a negative mean split correlation extrapolates to an absurd (but defined)
    # negative reliability with two blocks...
    assert spearman_brown(-0.6, 2) == pytest.approx(-3.0)
    # ...and becomes undefined once the denominator turns non-positive: the
    # regime the interleaved dealing produced under signed polarity
    assert np.isnan(spearman_brown(-0.6, 3))
    assert np.isnan(spearman_brown(0.5, 1))
    assert np.isnan(spearman_brown(np.nan, 2))


def test_disattenuated_recovers_true_correlation():
    # r_obs = r_true * sqrt(rel_a * rel_b): 0.5 * sqrt(0.25) = 0.25 observed
    assert disattenuated(0.25, 0.5, 0.5) == pytest.approx(0.5)
    assert disattenuated(0.5, 0.5, 0.5) == pytest.approx(1.0)
    assert disattenuated(0.3, 0.6, 0.6) == pytest.approx(0.5)
    # zero reliability: the observed r carries no information
    assert np.isnan(disattenuated(0.5, 0.0, 0.5))
    # noisy reliabilities can push the estimate above 1; it must clip
    assert disattenuated(1.0, 0.9, 0.9) == pytest.approx(1.0)


def test_window_archive_frames_and_disjoint_halves(fake_openevt):
    from hypercam.analysis.source_identification import decode_windows

    counts = (1, 3, 5, 7, 9, 11, 13, 15)
    events = []
    for window, count in enumerate(counts):
        events.extend([(0, 0, 1, window * 1_000)] * count)
    path = Path("fake_archive.raw")
    FakeRawFileReader.sources[str(path)] = (make_events(events), (4, 4))
    archive = decode_windows(
        fake_openevt, "blue", path, polarity="signed",
        accumulation_us=1_000, transform="raw",
    )
    assert archive.frame_count == 8
    assert archive.frame()[0, 0] == pytest.approx(np.mean(counts))
    first, second = block_bounds(8, 2)
    assert archive.frame(*first)[0, 0] == pytest.approx(np.mean(counts[:4]))
    assert archive.frame(*second)[0, 0] == pytest.approx(np.mean(counts[4:]))
    # stop beyond the recording clamps, matching sweep cutoff semantics
    assert archive.frame(0, 100)[0, 0] == pytest.approx(np.mean(counts))
    with pytest.raises(ValueError, match="empty"):
        archive.frame(9, 12)


def test_gradient_congruence_is_invariant_to_gain_and_offset():
    rows = np.arange(32.0)
    pattern = np.outer(rows + 1.0, rows + 1.0)
    affine = 3.0 * pattern + 5.0
    support = np.ones((32, 32), dtype=bool)
    # Pearson is invariant to affine transformations, so a pure gain/offset
    # difference between bands correlates at exactly 1: r = 1 does NOT mean
    # "no variance between color bands"
    assert gradient_congruence(pattern, affine, support, support) == pytest.approx(1.0)
    assert gradient_congruence(pattern, pattern, support, support) == pytest.approx(1.0)


def test_gradient_congruence_drops_with_band_specific_structure():
    rows = np.arange(32.0)
    smooth = 0.05 * np.outer(rows + 1.0, rows + 1.0)
    # period-4 sinusoid: Sobel's +/-1-pixel kernel cannot see a period-2
    # checkerboard (Nyquist), so the band-specific structure must be resolvable
    detail = 8.0 * np.sin(np.arange(32.0)[:, None] * np.pi / 2.0)
    first = smooth + detail
    second = smooth - detail
    support = np.ones((32, 32), dtype=bool)
    congruence = gradient_congruence(first, second, support, support)
    # the shared smooth component and the band-specific structure have
    # opposing gradient contributions, so the congruence must be negative
    assert congruence < -0.5
    assert gradient_congruence(first, first, support, support) == pytest.approx(1.0)


def test_window_congruence_map_flags_degenerate_windows():
    axis = np.sin(np.linspace(0.0, np.pi, 32))
    pattern = np.outer(axis, axis) + 0.1
    first = pattern.copy()
    first[0:16, 0:16] = 0.0
    second = pattern.copy()
    congruence = window_congruence_map(
        first, second, first != 0, second != 0, window=16
    )
    assert congruence.shape == (2, 2)
    # the zeroed window has no measured pixels in `first` (intersection support
    # is empty): undefined
    assert np.isnan(congruence[0, 0])
    # identical structure elsewhere: high local congruence. The window adjacent
    # to the zeroed block degrades visibly (0.57 here): the support edge bleeds
    # through the +/-1-pixel Sobel stencil and dominates weak structure - a
    # reminder to read congruence maps with support edges in mind.
    assert congruence[1, 1] > 0.9
    assert congruence[0, 1] > 0.5


def test_safe_pearson_handles_degenerate_inputs():
    assert safe_pearson(np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 6.0])) == pytest.approx(1.0)
    assert np.isnan(safe_pearson(np.ones(3), np.ones(3)))
    assert np.isnan(safe_pearson(np.empty(0), np.empty(0)))


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

    monkeypatch.setattr(source_identification, "load_openevt", fake_load_openevt)

    def counts(base):
        return {
            (x, y): base + (x - 4) + (y - 4)
            for x in range(4, 8)
            for y in range(4, 8)
        }

    blue_windows = [counts(base + window) for window, base in enumerate((2, 2, 2, 2, 2, 2, 2, 2))]
    green_windows = [
        {pixel: max(1, count // 2) for pixel, count in window.items()}
        for window in blue_windows
    ]
    control_windows = [
        {(2, 2): 1 + (window % 2), (9, 9): 3 + ((window + 1) % 2)} for window in range(8)
    ]
    for name, windows in (
        ("circle_blue", blue_windows),
        ("circle_green", green_windows),
        ("blank", control_windows),
    ):
        path = tmp_path / f"{name}.raw"
        path.touch()
        _add_recording(path, windows)

    output = tmp_path / "out"
    args = SimpleNamespace(
        pattern=str(tmp_path / "circle_*.raw"),
        control_pattern=str(tmp_path / "blank.raw"),
        output=output,
        accumulation_ms=1.0,
        durations=[0.004, 0.008],
        polarity="signed",
        transform="raw",
        splits=2,
        crop_margin=2,
        highpass_px=0,
        congruence_window=16,
        segment_s=0.002,
        max_shift_px=2,
        sweep_tile=16,
        sweep_min=0.8,
        sweep_max=1.2,
        sweep_step=0.2,
        openevt_library=None,
    )
    analyze(args)

    for name in (
        "analysis_metadata.json",
        "correlation_full.csv",
        "correlation_full.npy",
        "reliability.csv",
        "gradient_congruence.csv",
        "segments.csv",
        "magnification_sweep.csv",
        "conclusions.json",
        "conclusions.md",
    ):
        assert (output / name).exists(), name
    assert (output / "gradient_congruence_maps" / "blue_green_congruence_map.png").exists()
    assert (output / "magnification_sweep_blue_green.png").exists()
    assert (output / "reliability_ladder.png").exists()
    assert (output / "frames" / "activity_sheet_0.008s.png").exists()
    assert (output / "frames" / "processed_sheet_0.008s.png").exists()
    assert (output / "frames" / "segments_sheet_0.008s.png").exists()
    assert (output / "frames" / "blue_processed_0.008s.npy").exists()
    assert (output / "frames" / "blue_segment_early_0.008s.npy").exists()
    assert (output / "frames" / "blank_processed_0.008s.png").exists()

    metadata = json.loads((output / "analysis_metadata.json").read_text())
    assert metadata["polarity"] == "signed"
    assert metadata["split_scheme"] == "contiguous disjoint time blocks"
    assert metadata["controls"] == ["blank"]

    rows = list(csv.DictReader((output / "reliability.csv").open()))
    assert [row["duration_s"] for row in rows] == ["0.004", "0.008"]
    # identical spatial patterns: high observed r, high ceiling, high r_true
    assert float(rows[-1]["r_observed_blue_green"]) > 0.9
    assert float(rows[-1]["self_reliability_blue"]) > 0.9
    assert float(rows[-1]["r_true_blue_green"]) > 0.9

    conclusions = json.loads((output / "conclusions.json").read_text())
    assert conclusions["pairs"]["blue_green"]["r_true"] > 0.9
    assert "present-in-direct-display-image" in conclusions["pending_branches"][0]
    assert conclusions["control"]["blank"]["control_reliability"] == pytest.approx(1.0)
    assert conclusions["segments"]["segment_windows"] == 2
    assert "argmax_gradient_m" in conclusions["magnification"]["blue_green"]