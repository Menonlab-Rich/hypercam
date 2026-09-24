# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

from pathlib import Path

import numpy as np
import pytest

from hypercam.analysis.spectral_correlation import (
    box_blur,
    high_pass,
    label_from_path,
    pearson_matrix,
    signal_window,
    transform_frames,
)


def test_label_is_parsed_from_recording_name():
    assert label_from_path(Path("spectral_425.raw")) == "425"
    assert label_from_path(Path("experiment-red_632.8.raw")) == "632.8"
    assert label_from_path(Path("circle_green.raw")) == "green"
    assert label_from_path(Path("circle_red.raw")) == "red"


def test_label_without_name_or_number_is_rejected():
    with pytest.raises(ValueError, match="rename the recording"):
        label_from_path(Path("_-.raw"))


def test_pearson_matrix_has_expected_coefficients_and_unit_diagonal():
    frames = np.array([[[0, 1], [2, 3]], [[0, 2], [4, 6]], [[3, 2], [1, 0]]])
    matrix = pearson_matrix(frames)
    np.testing.assert_allclose(matrix, [[1, 1, -1], [1, 1, -1], [-1, -1, 1]])
    np.testing.assert_array_equal(np.diag(matrix), np.ones(3))


def test_pearson_matrix_excludes_pixels_idle_in_both_frames():
    frames = np.array([[[0.0, 1.0, 2.0, 3.0]], [[0.0, 1.0, 2.0, 30.0]]])
    masked = pearson_matrix(frames, frames != 0)[0, 1]
    expected = np.corrcoef(frames[0, 0, 1:], frames[1, 0, 1:])[0, 1]
    assert masked == pytest.approx(expected)
    # counting the shared background pixel would give a different, higher value
    assert pearson_matrix(frames)[0, 1] != pytest.approx(expected)


def test_constant_frame_is_rejected():
    with pytest.raises(ValueError, match="constant frame"):
        pearson_matrix(np.ones((2, 3, 3)))


def test_high_pass_removes_only_large_scale_structure():
    constant = np.full((32, 32), 3.5)
    np.testing.assert_allclose(high_pass(constant, 8), 0.0, atol=1e-12)
    np.testing.assert_allclose(box_blur(constant, 8), 3.5)


def test_signal_window_crops_to_the_bright_region():
    frame = np.zeros((64, 96))
    frame[16:48, 48:80] = 5.0
    rows, columns = signal_window(frame[None], margin=0)
    assert (rows.start, rows.stop) == (16, 48)
    assert (columns.start, columns.stop) == (48, 80)


def test_signal_window_is_the_union_across_frames():
    first = np.zeros((64, 96))
    first[16:48, 48:80] = 5.0
    second = np.zeros((64, 96))
    second[0:32, 16:48] = 4.0
    rows, columns = signal_window(np.stack([first, second]), margin=0)
    assert (rows.start, rows.stop) == (0, 48)
    assert (columns.start, columns.stop) == (16, 80)


def test_signed_log_transform_preserves_sign():
    values = np.array([[[-3, 0, 3]]])
    transformed = transform_frames(values, "log1p")
    np.testing.assert_allclose(transformed, [[[-np.log(4), 0, np.log(4)]]])
