# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================
"""Build the customer report deck for the delivered SAGE IV DRISM DOE.

The deck documents the pillar-relief meta-filter (data/nasa/profile_v2.mat,
266 x 266 cells at 10.35 um pitch) operated at its validated collimated
Fourier-plane prescription, and demonstrates what the actual optic should
produce on the 3296 x 2472 @ 5.5 um reference detector: the per-wavelength
Fraunhofer codes, the design validation against the HySpec operating table,
and the expected raw camera frames rendered from real hyperspectral video.

Run:  uv run python -m hypercam.reporting.drism_doe_deck
"""

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from hypercam.reporting.report_deck import (
    ACCENT,
    GOOD,
    MUTED,
    NAVY,
    SLIDE_H,
    SLIDE_W,
    TEXT,
    WHITE,
    add_bullets,
    add_table,
    add_text,
    new_slide,
    style_cell,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIGURES = REPO_ROOT / "reports" / "figures" / "drism_doe"
RESULTS = REPO_ROOT / "results" / "doe_synthetic_v2"
OUTPUT = REPO_ROOT / "reports" / "decks" / "sage_iv_drism_doe_report.pptx"

FOOTER = ("SAGE IV DRISM meta-filter · design validation report · "
          "October 2026   ·   ")


def title_slide(prs) -> None:
    slide = new_slide(prs)
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(2.1))
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    band.line.fill.background()
    band.shadow.inherit = False
    add_text(slide, "SAGE IV DRISM Meta-Filter", Inches(0.7), Inches(0.45),
             Inches(12), Inches(0.7), size=34, bold=True, color=WHITE)
    add_text(slide, "Diffractive optic: delivered design, validation, and expected camera output",
             Inches(0.7), Inches(1.2), Inches(12), Inches(0.6), size=18, color=WHITE)
    add_text(slide, "Inversely designed pillar relief · 266 × 266 cells · ma-P 1275 photoresist\n"
                    "Validated against the proposed-work operating table (HySpec2: 200 µrad / 9.4 nm)",
             Inches(0.7), Inches(2.6), Inches(11.5), Inches(1.2), size=16, color=TEXT)
    add_text(slide, "Richard G. Baird  ·  Hypercam project  ·  27 October 2026",
             Inches(0.7), Inches(6.6), Inches(11), Inches(0.4), size=13, color=MUTED)


def slide_title(slide, text, number) -> None:
    add_text(slide, text, Inches(0.55), Inches(0.3), Inches(12.3), Inches(0.7),
             size=27, bold=True, color=NAVY)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.0), Inches(2.3), Pt(3.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False
    add_text(slide, FOOTER + str(number), Inches(0.55), Inches(7.1),
             Inches(12), Inches(0.3), size=10, color=MUTED)


def add_image(slide, path, left, top, width) -> None:
    slide.shapes.add_picture(str(path), left, top, width=width)


def add_caption(slide, text, left, top, width) -> None:
    add_text(slide, text, left, top, width, Inches(0.35), size=11, color=MUTED)


def executive_summary(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Executive Summary", 2)
    add_bullets(slide, [
        ("Delivered optic: ", "an aperiodic array of 70,756 polymer pillars (266 × 266 cells, "
         "10.35 µm pitch, 2.75 mm square), heights 0.4 – 49.5 µm, etched in ma-P 1275 "
         "photoresist. Each pillar height is an independent design parameter; the array "
         "is neither periodic nor blazed."),
        ("Optical prescription: ", "the DOE sits in the collimated beam; a Fourier lens "
         "(f = 55 mm, F/20, NA 0.025) turns every scene point into a wavelength-specific "
         "diffraction code on the 3296 × 2472 @ 5.5 µm reference detector."),
        ("Validated performance: ", "angular resolution 116 µrad and spectral resolution "
         "5.7 nm (decorrelation half-widths) — both inside the HySpec2 requirement of "
         "200 µrad / 9.4 nm."),
        ("Spectral channels: ", "all four design channels (386, 525, 600, 1020 nm at "
         "15 nm FWHM) produce mutually uncorrelated codes (pairwise overlap ≤ 0.04), "
         "so each exposure carries independent spectral information."),
        ("Demonstrated end-to-end: ", "we synthesized the expected video from a real "
         "hyperspectral cube (400–700 nm, 151 bands) with the full physical model: "
         "measured material dispersion, Fraunhofer propagation, noiseless detector."),
    ], Inches(0.7), Inches(1.35), Inches(12), Inches(5.4), size=15)


def prescription_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Instrument and Optical Prescription", 3)
    add_image(slide, FIGURES / "optical_schematic.png", Inches(0.5), Inches(1.25), Inches(8.3))
    add_caption(slide, "Collimated Fourier-plane layout: scene angle → plane-wave tilt at the DOE → "
                       "lateral code shift f·θ on the FPA.", Inches(0.6), Inches(6.35), Inches(8))
    rows, cols = 9, 2
    table = add_table(slide, rows, cols, Inches(9.1), Inches(1.3), Inches(3.7), Inches(5.2))
    table.columns[0].width = Inches(2.0)
    table.columns[1].width = Inches(1.7)
    data = [
        ("Parameter", "Value"),
        ("Detector", "3296 × 2472"),
        ("Pixel pitch", "5.5 µm"),
        ("Field of view", "1° circular"),
        ("Fourier lens f", "55 mm"),
        ("Coherent width D", "2.75 mm (F/20)"),
        ("Angular scale", "100 µrad / px"),
        ("Speckle grain", "11 µm = 2 px"),
        ("Scene footprint", "175 px"),
    ]
    for r, (key, value) in enumerate(data):
        style_cell(table.cell(r, 0), key, size=12,
                   bold=(r == 0), color=WHITE if r == 0 else TEXT,
                   fill=NAVY if r == 0 else None)
        style_cell(table.cell(r, 1), value, size=12,
                   bold=(r == 0), color=WHITE if r == 0 else TEXT,
                   fill=NAVY if r == 0 else None)


def doe_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "The Delivered Diffractive Optic", 4)
    add_image(slide, FIGURES / "doe_profile.png", Inches(0.5), Inches(1.3), Inches(9.2))
    add_bullets(slide, [
        "266² pillars, 10.35 µm pitch",
        "heights 0.4–49.5 µm (≈ 60 waves at 400 nm)",
        "aperiodic: one free height per cell",
        "ma-P 1275 relief in air; substrate transmission 1",
    ], Inches(9.9), Inches(1.5), Inches(3.1), Inches(4.5), size=13)
    add_caption(slide, "Fabrication note: peak aspect ratio ≈ 4.8. Confirm processability "
                       "(HAR resist or etch transfer) before mask release.",
                Inches(0.6), Inches(6.6), Inches(11))


def phase_mask_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "The Optic as a Phase Mask", 5)
    add_image(slide, RESULTS / "running-frog" / "running-frog_phase_mask.png",
              Inches(0.55), Inches(1.25), Inches(12.2))
    add_caption(slide, "Top: wrapped transmission phase at 400–700 nm — the fabrication-relevant view. "
                       "Bottom: phase in waves. The relief reaches 80 waves at 400 nm and 40 at 700 nm; "
                       "this 1/λ scaling, plus material dispersion, encodes the spectrum.",
                Inches(0.6), Inches(6.75), Inches(12))


def codes_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "What Every Scene Point Becomes on the Sensor", 6)
    add_image(slide, FIGURES / "fraunhofer_codes.png",
              Inches(0.55), Inches(1.3), Inches(12.2))
    add_caption(slide, "Top: the point-spread code across the detector (square-root intensity — the "
                       "code grows with wavelength because diffraction angles scale with λ). "
                       "Bottom: 275 µm detail showing the 11 µm speckle grain. Each scene point "
                       "becomes this pattern, shifted by f·θ; the layout changes completely between "
                       "bands — the meta-filter's joint angular/spectral encoding.",
                Inches(0.6), Inches(6.65), Inches(12.2))


def validation_method_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Validation Method — What a Reconstruction Can Distinguish", 7)
    add_bullets(slide, [
        ("Operational criteria, not photon-limited bounds: ", "two points are resolvable "
         "when their codes decorrelate; the same test applies to two wavelengths. These "
         "thresholds hold for any exposure and any decoder."),
        ("Angular resolution: ", "half-width at half-maximum of the code autocorrelation, "
         "converted through f·θ."),
        ("Spectral resolution: ", "code overlap versus Δλ at 400 / 550 / 700 nm."),
        ("Pearson (mean-subtracted) overlap. ", "Independent speckle patterns share raw "
         "intensity overlap 0.5 exactly, because speckle intensity follows negative-exponential "
         "statistics. Subtracting each mean makes identical codes score 1 and independent "
         "codes score 0, so the 0.5 threshold means what it should."),
        ("Envelope normalization. ", "Every code carries the same smooth aperture envelope, "
         "which is deterministic and carries no information. We measure overlap on the "
         "speckle that remains after subtracting each code's blurred envelope."),
        ("Channel check: ", "band-integrated codes for the four design channels "
         "(Gaussian FWHM 15 nm) must all decorrelate."),
    ], Inches(0.7), Inches(1.35), Inches(12), Inches(5.4), size=15)


def validation_results_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Validation Results — HySpec2 Requirement Met", 8)
    add_image(slide, RESULTS / "validation" / "validation.png",
              Inches(0.55), Inches(1.25), Inches(12.2))
    rows, cols = 4, 4
    table = add_table(slide, rows, cols, Inches(0.7), Inches(4.85), Inches(11.9), Inches(1.9))
    data = [
        ("Metric", "Measured", "HySpec2 spec", "Verdict"),
        ("Angular resolution (HWHM)", "116 µrad", "≤ 200 µrad", "PASS"),
        ("Spectral resolution (half-width)", "5.7 nm", "≤ 9.4 nm", "PASS"),
        ("Closest channel pair (525/600 nm)", "0.037", "< 0.5", "PASS"),
    ]
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            color = WHITE if r == 0 else (GOOD if c == 3 and r > 0 else TEXT)
            style_cell(table.cell(r, c), value, size=13,
                       bold=(r == 0 or c == 3), color=color,
                       fill=NAVY if r == 0 else None)


def scorecard_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Scorecard Against the Proposed Operating Table", 9)
    add_image(slide, FIGURES / "hyspec_scorecard.png", Inches(0.7), Inches(1.3), Inches(8.6))
    add_bullets(slide, [
        ("HySpec2 (200 µrad / 9.4 nm): MET ", "on both axes."),
        ("HySpec3 (300 µrad / 4.2 nm): ", "angular met with 2.6× margin; spectral 5.7 vs 4.2 nm — "
         "reachable with a ~70 µm height budget."),
        ("HySpec1 (100 µrad / 38 nm): ", "spectral met with margin; angular needs a 5.5 mm "
         "coherent window (larger optic)."),
        ("HySpec4 (9400 µrad / 2.3 nm): ", "spectral-limited; requires the taller relief as well."),
    ], Inches(9.5), Inches(1.5), Inches(3.4), Inches(5.2), size=12)


def expected_output_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Expected Raw Camera Output", 10)
    add_image(slide, FIGURES / "raw_frame_reference.png", Inches(0.7), Inches(1.3), Inches(9.0))
    add_bullets(slide, [
        "Single exposure: scene ⊛ code, all bands summed",
        "Speckle contrast ~11% — multiplexed, not lost",
        "Video: 11 frames, 151 bands, 4 fps",
        "Decoder recovers (x, y, λ) per pixel",
    ], Inches(9.9), Inches(1.6), Inches(3.1), Inches(4.6), size=13)
    add_caption(slide, "Left: the source hyperspectral scene (pseudo-RGB). Right: one synthetic FPA "
                       "exposure through the delivered optic — the expected single-frame appearance; "
                       "spectral and angular information is recoverable by reconstruction.",
                Inches(0.8), Inches(6.6), Inches(11))


def deliverables_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Deliverables and Reproduction", 11)
    add_bullets(slide, [
        ("Optic definition: ", "data/nasa/profile_v2.mat — 266² heights (m), cell pitch, "
         "2.753 mm aperture, f = 55 mm, F/20 metadata."),
        ("Validation report: ", "results/doe_synthetic_v2/validation/ (validation.png, "
         "validation.json) — reproduce with: synthesize_doe_video.py --validate "
         "--profile data/nasa/profile_v2.mat"),
        ("Expected video: ", "results/doe_synthetic_v2/running-frog/running-frog_doe.mp4 "
         "(151 bands, 400–700 nm, 11 frames) — reproduce with: synthesize_doe_video.py "
         "--clip running-frog --profile data/nasa/profile_v2.mat"),
        ("Forward model & renderer: ", "src/scripts/synthesize_doe_video.py — Fraunhofer "
         "code stack, band-integrated exposure, design tables built in."),
        ("Design pipeline: ", "src/notebooks/coded_mask_drism.py — pillar parameterization, "
         "CRLB + channel-overlap objective (TOML-configurable for CHPC batches)."),
        ("Material data: ", "data/nasa/mat_maP1275.xlsx — measured n(λ), k(λ); k < 0.002 "
         "across 400–700 nm justifies the lossless-substrate assumption."),
    ], Inches(0.7), Inches(1.35), Inches(12), Inches(5.4), size=14)


def closing_slide(prs) -> None:
    slide = new_slide(prs)
    slide_title(slide, "Summary and Next Steps", 12)
    add_bullets(slide, [
        ("Delivered and validated: ", "the pillar-relief DRISM meta-filter meets the "
         "HySpec2 operating point (116 µrad / 5.7 nm measured vs 200 µrad / 9.4 nm "
         "required) with all four spectral channels decorrelated (≤ 0.04)."),
        ("Fabrication: ", "confirm the 4.8 aspect-ratio pillar array in ma-P 1275 "
         "(or transfer to a harder resist / fused-silica etch) before mask release."),
        ("Reconstruction: ", "a decoder demultiplexes the coded exposures; the validated "
         "overlap metrics bound the achievable (x, y, λ) precision and set the decoder's "
         "design target."),
        ("Upgrade path: ", "a ~70 µm height budget (same optics, retrain) reaches the "
         "HySpec3 column (300 µrad / 4.2 nm); a 5.5 mm coherent window reaches HySpec1."),
    ], Inches(0.7), Inches(1.45), Inches(12), Inches(4.6), size=16)


def build() -> Path:
    presentation = Presentation()
    presentation.slide_width = SLIDE_W
    presentation.slide_height = SLIDE_H
    executive_summary_after_title = [
        prescription_slide, doe_slide, phase_mask_slide, codes_slide,
        validation_method_slide, validation_results_slide, scorecard_slide,
        expected_output_slide, deliverables_slide, closing_slide,
    ]
    title_slide(presentation)
    for builder in executive_summary_after_title:
        builder(presentation)
    # Insert the executive summary right after the title slide.
    executive_summary(presentation)
    xml_slides = presentation.slides._sldIdLst
    slides = list(xml_slides)
    xml_slides.remove(slides[-1])
    xml_slides.insert(1, slides[-1])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KiB)")
