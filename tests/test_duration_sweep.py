# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

import csv
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hypercam.analysis.duration_sweep import (
    build_snapshots,
    pair_pearson,
    replicate_count,
    replicate_statistics,
    sweep,
    window_terms,
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
        self._cursor = 0
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


def test_window_terms_applies_polarity_and_signed_transform():
    events = make_events([
        (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 2), (1, 1, 0, 3),
    ])
    signed = window_terms(events, width=4, polarity="signed", transform="log1p")
    np.testing.assert_allclose(
        signed[1], [np.log1p(2 - 1), -np.log1p(1)]
    )
    np.testing.assert_array_equal(signed[0], [0, 5])
    both = window_terms(events, width=4, polarity="both", transform="log1p")
    np.testing.assert_allclose(both[1], [np.log1p(3), np.log1p(1)])
    on = window_terms(events, width=4, polarity="on", transform="log1p")
    np.testing.assert_allclose(on[1], [np.log1p(2)])
    off = window_terms(events, width=4, polarity="off", transform="log1p")
    np.testing.assert_allclose(off[1], [np.log1p(1), np.log1p(1)])


def test_build_snapshots_is_backward_compatible(fake_openevt):
    path = Path("fake_recording.raw")
    FakeRawFileReader.sources[str(path)] = (
        make_events([(0, 0, 1, 0), (0, 0, 1, 1000), (2, 2, 0, 3000)]),
        (4, 4),
    )
    snapshots = build_snapshots(
        fake_openevt, path, accumulation_us=1_000,
        cutoffs_us=[1_000, 4_000], transform="log1p",
    )
    assert snapshots[1_000][0, 0] == pytest.approx(np.log1p(1))
    assert snapshots[4_000][0, 0] == pytest.approx(2 * np.log1p(1) / 4)
    assert snapshots[4_000][2, 2] == pytest.approx(np.log1p(1) / 4)


def test_recording_stream_splits_windows_by_index(fake_openevt):
    from hypercam.analysis.duration_sweep import RecordingStream

    events = []
    for window, count in enumerate((1, 3, 5, 7)):
        events.extend([(0, 0, 1, window * 1_000)] * count)
    path = Path("fake_splits.raw")
    FakeRawFileReader.sources[str(path)] = (make_events(events), (4, 4))
    stream = RecordingStream(
        fake_openevt, path, accumulation_us=1_000, transform="raw",
        polarity="both", splits=2,
    )
    stream.advance_to(4_000)
    assert stream.frame_count == 4
    assert stream.split_average(0)[0, 0] == pytest.approx(3.0)
    assert stream.split_average(1)[0, 0] == pytest.approx(5.0)
    assert stream.average()[0, 0] == pytest.approx(4.0)
    stream.advance_to(5_000)
    assert stream.exhausted


def test_replicate_count_policy():
    assert replicate_count(4, 4) == 0
    assert replicate_count(7, 4) == 0
    assert replicate_count(8, 4) == 2
    assert replicate_count(10, 4) == 2
    assert replicate_count(16, 4) == 4
    assert replicate_count(100, 4) == 4
    assert replicate_count(16, 8) == 4


def test_t_critical_values_are_two_sided_95_percent():
    from hypercam.analysis.duration_sweep import t_critical

    assert t_critical(2) == pytest.approx(12.706, abs=1e-3)
    assert t_critical(4) == pytest.approx(3.182, abs=1e-3)
    assert t_critical(5) == pytest.approx(2.776, abs=1e-3)
    assert t_critical(12) == pytest.approx(2.201, abs=1e-3)
    assert t_critical(100) == pytest.approx(1.984, abs=5e-3)


def test_replicate_statistics_flags_significance():
    mean, sem, statistic, discernible = replicate_statistics([0.9, 0.92, 0.88, 0.91])
    assert discernible
    assert mean == pytest.approx(0.9025)
    assert abs(statistic) > 2
    mean, sem, statistic, discernible = replicate_statistics([0.5, -0.5, 0.5, -0.5])
    assert not discernible
    assert mean == pytest.approx(0.0)
    mean, sem, _, discernible = replicate_statistics([np.nan])
    assert np.isnan(mean) and not discernible


def test_pair_pearson_handles_degenerate_frames():
    frame = np.array([[1.0, 2.0, 3.0]])
    support = np.array([[True, True, False]])
    assert pair_pearson(frame, frame, support, support) == pytest.approx(1.0)
    constant = np.ones((1, 3))
    assert np.isnan(pair_pearson(constant, constant, support, support))


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


def test_sweep_reports_split_half_diagnostics(tmp_path, fake_openevt):
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
    recordings = []
    for name, windows in (("blue", blue_windows), ("green", green_windows)):
        path = tmp_path / f"circle_{name}.raw"
        path.touch()
        _add_recording(path, windows)
        recordings.append(path)

    durations = (0.002, 0.008)
    labels, means, pairs, diagnostics = sweep(
        fake_openevt, str(tmp_path / "circle_*.raw"), durations, (1,),
        "log1p", min_windows=4, polarity="both", splits=4,
    )
    assert labels == ["blue", "green"]
    assert means.shape == (2, 1)
    assert np.isnan(means[0, 0]), "2-window combination must be skipped"
    assert means[1, 0] > 0.9, "identical spatial patterns must correlate strongly"
    assert diagnostics["splits_used"][1, 0] == 2
    assert diagnostics["ceiling"][1, 0] > 0.9
    assert diagnostics["fraction_of_ceiling"][1, 0] > 0.9
    assert diagnostics["discernible"][1, 0, 0] == 1.0

    output = tmp_path / "out"
    output.mkdir()
    args = Namespace(
        pattern="x", transform="log1p", polarity="both", support_mask=True,
        min_windows=4, splits=4, ceiling_fraction=0.8,
    )
    from hypercam.analysis.duration_sweep import write_outputs

    write_outputs(
        output, labels, [(0, 1)], durations, (1.0,), means, pairs,
        diagnostics, args,
    )
    rows = list(csv.DictReader((output / "duration_accumulation_sweep.csv").open()))
    assert rows[0]["mean_cross_correlation"] == ""
    assert rows[0]["windows"] == "2"
    assert rows[1]["blue_green_t"]
    assert rows[1]["blue_green_discernible"] == "True"
    assert float(rows[1]["ceiling"]) > 0.9
    metadata = json.loads((output / "duration_accumulation_sweep.json").read_text())
    assert metadata["polarity"] == "both"
    entry = metadata["discernibility"]["per_accumulation"][0]
    assert entry["all_pairs_discernible_from_s"] == 0.008
    assert entry["all_pairs_at_ceiling_from_s"] == 0.008
    assert metadata["skipped_combinations"] == [
        {"duration_s": 0.002, "accumulation_ms": 1.0, "windows": 2}
    ]
