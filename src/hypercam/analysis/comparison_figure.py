# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Create a poster-scale comparison of multiple correlation matrices."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Sequence

import numpy as np

from .spectral_correlation import _heat_color


def load_result(directory: Path) -> tuple[np.ndarray, list[str]]:
    matrix = np.load(directory / "pearson_correlation.npy")
    metadata = json.loads((directory / "analysis_metadata.json").read_text())
    labels = [
        str(item.get("label", item.get("wavelength_nm", "unknown")))
        for item in metadata["recordings"]
    ]
    if matrix.shape != (len(labels), len(labels)):
        raise ValueError(f"matrix and recording labels disagree in {directory}")
    return matrix, labels


def write_comparison_figure(
    path: Path,
    panels: Sequence[tuple[str, np.ndarray, Sequence[float]]],
) -> None:
    """Write three square heat maps with one shared Pearson colorbar."""
    if len(panels) != 3:
        raise ValueError("the poster layout requires exactly three panels")

    canvas_width, canvas_height = 5400, 1900
    panel_size = 1320
    panel_lefts = (150, 1740, 3330)
    matrix_top = 250
    colorbar_x, colorbar_width = 4970, 72
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="54in" height="19in" viewBox="0 0 {canvas_width} {canvas_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#111}",
        ".figure-title{font-size:54px;font-weight:700}",
        ".panel-title{font-size:46px;font-weight:700}",
        ".tick{font-size:30px}",
        ".axis{font-size:34px;font-weight:600}",
        ".value{font-size:25px;font-weight:500}",
        ".note{font-size:27px}",
        "</style>",
        f'<text class="figure-title" x="{canvas_width / 2:g}" y="66" text-anchor="middle">Wavelength Pattern Correlation by Optical Configuration</text>',
    ]

    for panel_index, (title, matrix, labels) in enumerate(panels):
        n = len(labels)
        if matrix.shape != (n, n):
            raise ValueError(f"panel {title!r} has mismatched data and labels")
        left = panel_lefts[panel_index]
        cell = panel_size / n
        center_x = left + panel_size / 2
        parts.append(
            f'<text class="panel-title" x="{center_x:g}" y="155" text-anchor="middle">{escape(title)}</text>'
        )
        for index, label in enumerate(labels):
            center = left + (index + 0.5) * cell
            parts.append(
                f'<text class="tick" x="{center:g}" y="225" text-anchor="middle">{escape(label)}</text>'
            )
            center_y = matrix_top + (index + 0.5) * cell + 10
            parts.append(
                f'<text class="tick" x="{left - 22}" y="{center_y:g}" text-anchor="end">{escape(label)}</text>'
            )

        for row in range(n):
            for column in range(n):
                value = float(matrix[row, column])
                x = left + column * cell
                y = matrix_top + row * cell
                text_color = "white" if abs(value) > 0.72 else "#111"
                parts.append(
                    f'<rect x="{x:g}" y="{y:g}" width="{cell:g}" height="{cell:g}" '
                    f'fill="{_heat_color(value)}" stroke="white" stroke-width="2"/>'
                )
                parts.append(
                    f'<text class="value" x="{x + cell / 2:g}" y="{y + cell / 2 + 9:g}" '
                    f'text-anchor="middle" style="fill:{text_color}">{value:.2f}</text>'
                )

        parts.extend(
            [
                f'<rect x="{left}" y="{matrix_top}" width="{panel_size}" height="{panel_size}" fill="none" stroke="#222" stroke-width="3"/>',
                f'<text class="axis" x="{center_x:g}" y="1645" text-anchor="middle">Recording</text>',
                f'<text class="axis" transform="translate({left - 112} {matrix_top + panel_size / 2:g}) rotate(-90)" text-anchor="middle">Recording</text>',
            ]
        )

    steps = 220
    for index in range(steps):
        value = 1.0 - 2.0 * index / (steps - 1)
        y = matrix_top + index * panel_size / steps
        parts.append(
            f'<rect x="{colorbar_x}" y="{y:g}" width="{colorbar_width}" '
            f'height="{panel_size / steps + 1:g}" fill="{_heat_color(value)}"/>'
        )
    parts.extend(
        [
            f'<rect x="{colorbar_x}" y="{matrix_top}" width="{colorbar_width}" height="{panel_size}" fill="none" stroke="#222" stroke-width="3"/>',
            f'<text class="tick" x="{colorbar_x + colorbar_width + 22}" y="{matrix_top + 10}" dominant-baseline="middle">1.0</text>',
            f'<text class="tick" x="{colorbar_x + colorbar_width + 22}" y="{matrix_top + panel_size / 2 + 10:g}" dominant-baseline="middle">0.0</text>',
            f'<text class="tick" x="{colorbar_x + colorbar_width + 22}" y="{matrix_top + panel_size}" dominant-baseline="middle">−1.0</text>',
            f'<text class="axis" transform="translate({colorbar_x + 190} {matrix_top + panel_size / 2:g}) rotate(-90)" text-anchor="middle">Pearson correlation coefficient (r)</text>',
            f'<text class="note" x="{canvas_width / 2:g}" y="1815" text-anchor="middle">10 ms EVT3 activity frames · log1p normalized per frame · 500 frames averaged per wavelength</text>',
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    results = repo_root / "results"
    reports_figures = repo_root / "reports" / "figures"
    specifications = [
        ("No Filter", results / "no_filter_correlation"),
        ("Gaussian", results / "gaussian_correlation"),
        ("Spectral", results / "spectral_correlation"),
    ]
    panels = []
    for title, directory in specifications:
        matrix, wavelengths = load_result(directory)
        panels.append((title, matrix, wavelengths))
    write_comparison_figure(
        reports_figures / "correlation_comparison_poster.svg", panels
    )


if __name__ == "__main__":
    main()
