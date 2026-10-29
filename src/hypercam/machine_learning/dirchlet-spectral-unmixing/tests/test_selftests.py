# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Pytest entry points around the module selftests + pure density logic."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def run_module(name: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / f"{name}.py")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"{name}.py selftest failed:\n{result.stdout}\n{result.stderr}"
    return result


def test_model_selftest() -> None:
    assert "MODEL SELFTEST OK" in run_module("model").stdout


def test_loss_selftest() -> None:
    assert "LOSS SELFTEST OK" in run_module("loss").stdout


def test_lit_selftest() -> None:
    assert "LIT SELFTEST OK" in run_module("lit").stdout


def test_targets_selftest() -> None:
    output = run_module("targets").stdout
    assert "targets selftest OK" in output or "selftest skipped" in output


def test_accumulation_floor() -> None:
    """1 ms frames on 250 us accumulations = exactly the floor; less fails."""
    import evt3

    assert evt3.frames_per_model_frame(1.0, 250, min_accumulations=4) == 4
    with pytest.raises(ValueError, match="accumulations"):
        evt3.frames_per_model_frame(0.75, 250, min_accumulations=4)
    with pytest.raises(ValueError, match="integer multiple"):
        evt3.frames_per_model_frame(0.3, 250, min_accumulations=4)


def test_clip_starts_evenly_spaced() -> None:
    import evt3

    assert evt3.clip_starts(100, 10, None) == [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    capped = evt3.clip_starts(100, 10, 3)
    assert len(capped) == 3 and capped == sorted(set(capped))
    assert evt3.clip_starts(5, 10, 3) == []


def test_density_features_encode_fps() -> None:
    """Same frame_ms => same effective fps regardless of n_frames (the
    multiple-ways-to-reach-one-fps property), and the feature reflects it."""
    import math

    from data import density_features

    for n in (2, 4, 8):
        features = density_features(n, 1.0)
        assert abs(features[0] - math.log10(1000.0)) < 1e-9
        assert abs(features[1] - math.log2(n)) < 1e-9


def test_build_clip_counts_windowed() -> None:
    """Synthetic events: each model frame must count only its own window."""
    import numpy as np

    import evt3

    height, width = 4, 4
    idx = np.array([0, 1, 5, 15, 15], dtype=np.uint32)
    t = np.array([0, 100, 900, 1000, 1900], dtype=np.uint32)
    p = np.zeros(5, dtype=np.uint8)
    clip = evt3.build_clip(
        idx, t, p, t_start_us=0, n_frames=2, frame_us=1000,
        height=height, width=width, transform="raw",
    )
    assert clip[0, 0, 0] == 1 and clip[0, 0, 1] == 1 and clip[0, 1, 1] == 1
    assert clip[0, 3, 3] == 0
    assert clip[1, 3, 3] == 2
