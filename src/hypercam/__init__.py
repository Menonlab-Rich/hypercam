# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Event-camera tools for comparing wavelength-dependent scenes."""


def main() -> None:
    """Run the spectral correlation command-line interface."""
    from .analysis.spectral_correlation import main as correlation_main

    correlation_main()
