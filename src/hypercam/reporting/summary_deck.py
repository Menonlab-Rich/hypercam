# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Generate the stakeholder-facing spectral-correlation slide deck."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = REPO_ROOT / "results" / "spectral_correlation"
RESULTS_MIN5 = REPO_ROOT / "results" / "spectral_correlation_min5"
RESULTS_MIN1 = REPO_ROOT / "results" / "spectral_correlation_min1"
OUTPUT = REPO_ROOT / "reports" / "decks" / "spectral_correlation_summary.pptx"

NAVY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0x2E, 0x74, 0xB5)
LIGHT_BLUE = RGBColor(0xBD, 0xD7, 0xEE)
PALE_BLUE = RGBColor(0xDD, 0xEB, 0xF7)
TEXT = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x7F, 0x7F, 0x7F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FOOTER = "Hypercam spectral correlation · September 2026"


def new_slide(prs) -> object:
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_text(
    slide,
    text,
    left,
    top,
    width,
    height,
    size=16,
    bold=False,
    color=TEXT,
    align=PP_ALIGN.LEFT,
) -> object:
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_bullets(slide, items, left, top, width, height, size=16, numbered=False):
    """Bulleted list; tuple items render a bold lead-in followed by regular text."""
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(8)
        prefix = f"{index + 1}.  " if numbered else "•  "
        parts = ((prefix + item[0], True), (item[1], False)) if isinstance(item, tuple) else ((prefix + item, False),)
        for text, bold in parts:
            run = paragraph.add_run()
            run.text = text
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = TEXT
    return box


def add_title(slide, title) -> None:
    add_text(slide, title, Inches(0.55), Inches(0.3), Inches(12.3), Inches(0.7), size=27, bold=True, color=NAVY)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.0), Inches(2.3), Pt(3.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False


def add_footer(slide, number) -> None:
    add_text(slide, f"{FOOTER}   ·   {number}", Inches(0.55), Inches(7.1), Inches(12), Inches(0.3), size=10, color=MUTED)


def add_caption(slide, text, left, top, width, align=PP_ALIGN.LEFT) -> None:
    add_text(slide, text, left, top, width, Inches(0.3), size=11, color=MUTED, align=align)


def style_cell(cell, text, size=15, bold=False, color=TEXT, fill=None, align=PP_ALIGN.LEFT) -> None:
    cell.text = text
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = Inches(0.12)
    cell.margin_right = Inches(0.12)
    if fill is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
    paragraph = cell.text_frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.runs[0]
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def build() -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    prs.core_properties.title = "Hypercam spectral correlation — results and next steps"

    # ---- Slide 1: title ----
    slide = new_slide(prs)
    background = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    background.fill.solid()
    background.fill.fore_color.rgb = NAVY
    background.line.fill.background()
    background.shadow.inherit = False
    add_text(slide, "Wavelength Pattern Correlation in EVT3 Event Streams", Inches(0.9), Inches(2.25), Inches(11.6), Inches(1.7), size=40, bold=True, color=WHITE)
    add_text(slide, "Separating measurement artifact from spectral signal on the LCD calibration scene", Inches(0.9), Inches(3.95), Inches(11.6), Inches(0.8), size=20, color=LIGHT_BLUE)
    add_text(slide, "Hypercam spectral correlation · summary for stakeholders · September 2026", Inches(0.9), Inches(6.55), Inches(11.6), Inches(0.5), size=14, color=RGBColor(0x8E, 0xA9, 0xDB))
    slide.notes_slide.notes_text_frame.text = (
        "Executive summary: the initial 87% green-red similarity was an artifact of shared "
        "scene geometry on the LCD target. After spatial filtering the correlation drops to 0.67. "
        "A sweep across frame rates (10 to 10,000 FPS) and recording lengths reveals that "
        "frame rate does not buy differentiation — scene time does (requiring ~1 to 2 seconds). "
        "The measurement floor is established at >=5 accumulated frames."
    )

    # ---- Slide 2: experimental setup ----
    slide = new_slide(prs)
    add_title(slide, "Experimental setup and data")
    add_bullets(
        slide,
        [
            ("Sensor:  ", "Prophesee EVT3 neuromorphic event sensor (720 × 1280 resolution)"),
            ("Calibration target:  ", "Blinking circle displayed on an LCD monitor, captured one color at a time (green, red, blue)"),
            ("Data volume:  ", "5 seconds per color; 5.3 to 7.6 million events per recording"),
            ("Activity frames:  ", "10 ms accumulation windows, log-transformed, averaged across 500 frames per color"),
            ("Metric:  ", "Pairwise Pearson correlation coefficient (r) between spatial activity patterns"),
            ("Objective:  ", "Determine whether differing display wavelengths produce measurably distinct spatial patterns"),
        ],
        Inches(0.75), Inches(1.55), Inches(11.8), Inches(4.8), size=17,
    )
    add_footer(slide, 2)
    slide.notes_slide.notes_text_frame.text = (
        "The target is an LCD monitor displaying a blinking circle in pure primary colors. "
        "Event cameras respond to temporal contrast (the blink transitions). "
        "Recordings capture 5 seconds of active blinking per color."
    )

    # ---- Slide 3: diagnosis ----
    slide = new_slide(prs)
    add_title(slide, "Diagnosis: the 87% similarity was scene geometry")
    picture = slide.shapes.add_picture(str(RESULTS / "frames" / "green_activity.png"), Inches(0.6), Inches(1.3), width=Inches(5.5))
    slide.shapes.add_picture(str(RESULTS / "frames" / "red_activity.png"), Inches(6.5), Inches(1.3), width=Inches(5.5))
    add_caption(slide, "green — raw averaged activity frame", Inches(0.6), picture.top + picture.height + Inches(0.05), Inches(5.5), PP_ALIGN.CENTER)
    add_caption(slide, "red — raw averaged activity frame", Inches(6.5), picture.top + picture.height + Inches(0.05), Inches(5.5), PP_ALIGN.CENTER)
    add_bullets(
        slide,
        [
            ("Shared geometry:  ", "Bright circle in the same pixel location + diffuse sensor background → coarse pattern r ≈ 0.99 for all pairs"),
            ("Unshared fine detail:  ", "Interior texture correlates near r ≈ 0.0 across all color pairs"),
            ("Why blue scored lower (0.60):  ", "Silicon sensitivity is lower at blue wavelengths (~3.7× dimmer disc), softening its coarse agreement"),
            ("Takeaway:  ", "The raw 0.87 measured 'same circle in the same spot,' not optical or spectral similarity"),
        ],
        Inches(0.75), Inches(4.85), Inches(12), Inches(2.1), size=14,
    )
    add_footer(slide, 3)
    slide.notes_slide.notes_text_frame.text = (
        "Because Pearson correlation is variance-weighted, the large shared circle dominates "
        "the raw calculation. Breaking the images into spatial-frequency bands proves that the "
        "coarse envelope correlates at 0.99 while the fine interior texture correlates at zero."
    )

    # ---- Slide 4: filtered methodology ----
    slide = new_slide(prs)
    add_title(slide, "Refined analysis methodology")
    add_bullets(
        slide,
        [
            ("Signal cropping:  ", "Isolates the 288 × 288 px active region, removing ~91% of inactive sensor background"),
            ("Spatial high-pass filter:  ", "Removes broad illumination envelope (>64 px), retaining mid-band spatial texture"),
            ("Support-masked correlation:  ", "Evaluates only pixels active in either recording, preventing shared empty pixels from inflating agreement"),
            ("Meaningful labeling:  ", "Recordings tracked by color name (green / red / blue) rather than arbitrary numeric identifiers"),
        ],
        Inches(0.75), Inches(1.65), Inches(7.9), Inches(4.8), size=17, numbered=True,
    )
    picture = slide.shapes.add_picture(str(RESULTS / "frames" / "green_processed.png"), Inches(9.3), Inches(1.75), width=Inches(3.3))
    add_caption(slide, "green after crop + high-pass filter", Inches(9.3), picture.top + picture.height + Inches(0.08), Inches(3.3), PP_ALIGN.CENTER)
    add_footer(slide, 4)
    slide.notes_slide.notes_text_frame.text = (
        "The refined methodology strips away the shared background and coarse circle envelope, "
        "leaving only the mid-band and fine texture where optical or display-specific patterns "
        "can be evaluated honestly."
    )

    # ---- Slide 5: results comparison ----
    slide = new_slide(prs)
    add_title(slide, "Results: before and after spatial filtering")
    table_frame = slide.shapes.add_table(4, 3, Inches(0.6), Inches(1.85), Inches(5.8), Inches(2.1))
    table = table_frame.table
    table.columns[0].width = Inches(2.6)
    table.columns[1].width = Inches(1.6)
    table.columns[2].width = Inches(1.6)
    table.rows[0].height = Inches(0.5)
    for row in range(1, 4):
        table.rows[row].height = Inches(0.52)
    for column, header in enumerate(("Color pair", "Raw", "Filtered")):
        style_cell(table.cell(0, column), header, bold=True, color=WHITE, fill=NAVY)
    rows = (("green ↔ red", "0.869", "0.669"), ("blue ↔ green", "0.596", "0.539"), ("blue ↔ red", "0.620", "0.576"))
    for index, (pair, before, after) in enumerate(rows, start=1):
        highlight = index == 1
        style_cell(table.cell(index, 0), pair, bold=highlight, fill=PALE_BLUE if highlight else WHITE)
        style_cell(table.cell(index, 1), before, bold=highlight, align=PP_ALIGN.CENTER, fill=PALE_BLUE if highlight else WHITE)
        style_cell(table.cell(index, 2), after, bold=highlight, align=PP_ALIGN.CENTER, fill=PALE_BLUE if highlight else WHITE)
    add_caption(slide, "Raw: full-frame.  Filtered: cropped, 64 px high-pass, support-masked.", Inches(0.6), Inches(4.2), Inches(6.0))
    add_bullets(
        slide,
        [
            ("Geometry inflation eliminated:  ", "The spurious 0.87 correlation drops to 0.67"),
            ("Blue pairs stabilize:  ", "Blue pairs show modest change (0.60 → 0.54, 0.62 → 0.58) because the high-pass removes the photometric brightness gap"),
            ("Narrower spread:  ", "All pairs now fall within 0.54 to 0.67, representing shared mid-band structure rather than scene geometry"),
        ],
        Inches(0.6), Inches(4.8), Inches(6.6), Inches(2.1), size=14,
    )
    slide.shapes.add_picture(str(RESULTS / "heatmap_for_slides.png"), Inches(7.7), Inches(1.45), width=Inches(4.7))
    add_footer(slide, 5)
    slide.notes_slide.notes_text_frame.text = (
        "Filtering flattens the correlation matrix substantially. Green-red remains the most similar "
        "pair at 0.67, which prompts the investigation into what shared structure remains."
    )

    # ---- Slide 6: interpretation (LCD target) ----
    slide = new_slide(prs)
    add_title(slide, "Interpreting the remaining 0.67 correlation")
    add_bullets(
        slide,
        [
            ("LCD subpixel grid:  ", "Monitors use fixed vertical subpixel stripes (R-G-B) at fixed screen coordinates. Camera blur couples this grid into a shared spatial pattern regardless of active color"),
            ("Common backlight modulation:  ", "LCD backlights use global pulse-width modulation (PWM), imposing identical temporal modulation across all displayed colors"),
            ("Broadband primary spectra:  ", "LCD color filters have broad, overlapping spectral profiles (~50–80 nm FWHM), unlike narrowband lasers or LEDs"),
            ("Setup alignment:  ", "Small centroid offsets (20–60 px) between captures reflect physical camera/monitor positioning, not wavelength dispersion"),
            ("Validated reference:  ", "Narrowband laser scans on this sensor demonstrate genuine spectral separation (e.g., 525 vs 625 nm correlates at 0.41)"),
        ],
        Inches(0.75), Inches(1.55), Inches(12), Inches(5.2), size=16,
    )
    add_footer(slide, 6)
    slide.notes_slide.notes_text_frame.text = (
        "Knowing the target is an LCD monitor clarifies the residual correlation: the physical "
        "subpixel geometry and shared backlight impose spatial and temporal structure common to all "
        "recordings. The LCD target is a functional test scene, not a narrowband calibration source."
    )

    # ---- Slide 7: duration x accumulation sweep ----
    slide = new_slide(prs)
    add_title(slide, "Frame rate vs recording length: what drives differentiation?")
    picture = slide.shapes.add_picture(
        str(RESULTS / "duration_accumulation_sweep.png"),
        Inches(0.55), Inches(1.25), width=Inches(7.2)
    )
    add_bullets(
        slide,
        [
            ("80% threshold is never reached:  ", "Across 120 tested combinations (10 to 10,000 FPS, 1 ms to 5 s duration), maximum correlation is 0.62"),
            ("Frame rate does not buy differentiation:  ", "At any given duration, columns from 10 FPS (100 ms) to 10,000 FPS (0.1 ms) yield nearly identical correlation values"),
            ("Scene time is what matters:  ", "Cross-color correlation requires ~1 to 2 seconds of exposure to stabilize and differentiate pairs"),
            ("Ultra-short durations (<25 ms):  ", "Frames are sparse, uncorrelated event spikes — Pearson correlation reads negative (~ −0.99) due to disjoint event patterns, not physical anticorrelation"),
        ],
        Inches(8.0), Inches(1.55), Inches(4.8), Inches(5.1), size=14,
    )
    add_footer(slide, 7)
    slide.notes_slide.notes_text_frame.text = (
        "Key takeaway for system design: increasing effective frame rate does not improve "
        "spectral differentiation. The event statistics require ~1 to 2 seconds of scene time "
        "to accumulate sufficient signal. High frame rates are viable without penalty, but "
        "exposure duration cannot be compressed below ~1 second for this metric."
    )

    # ---- Slide 8: frame minimum floor comparison (10 vs 5 vs 1) ----
    slide = new_slide(prs)
    add_title(slide, "Measurement floor: how few frames can we average?")
    # Three plots side by side
    col_w = Inches(3.95)
    gap = Inches(0.18)
    top_pos = Inches(1.25)
    lefts = [Inches(0.55), Inches(0.55) + col_w + gap, Inches(0.55) + (col_w + gap) * 2]

    slide.shapes.add_picture(str(RESULTS / "duration_accumulation_sweep.png"), lefts[0], top_pos, width=col_w)
    slide.shapes.add_picture(str(RESULTS_MIN5 / "duration_accumulation_sweep.png"), lefts[1], top_pos, width=col_w)
    slide.shapes.add_picture(str(RESULTS_MIN1 / "duration_accumulation_sweep.png"), lefts[2], top_pos, width=col_w)

    add_caption(slide, "10-frame cutoff (conservative)", lefts[0], Inches(4.55), col_w, PP_ALIGN.CENTER)
    add_caption(slide, "5-frame cutoff (operational floor)", lefts[1], Inches(4.55), col_w, PP_ALIGN.CENTER)
    add_caption(slide, "1-frame cutoff (breakdown regime)", lefts[2], Inches(4.55), col_w, PP_ALIGN.CENTER)

    add_bullets(
        slide,
        [
            ("5 frames is the true empirical floor:  ", "Every 5-frame cell reproduces the converged multi-frame value within 0.08 — no loss of measurement fidelity"),
            ("1 to 2 frames breakdown:  ", "Values deviate by up to ±0.35 from converged readings; single-frame rows become flat (correlation is set solely by accumulation interval, duration axis is meaningless)"),
            ("Operating rule:  ", "Require ≥5 accumulated frames for any measurement. Higher counts (10+) add safety margin but do not change the result"),
        ],
        Inches(0.65), Inches(4.95), Inches(12.0), Inches(2.0), size=14,
    )
    add_footer(slide, 8)
    slide.notes_slide.notes_text_frame.text = (
        "Quantifying the frame cutoff: 10 frames was our initial conservative setting. "
        "Testing down to 5 frames shows identical trend reproduction (within 0.08 across all cells). "
        "Testing down to 1 frame reveals severe breakdown: deviations up to 0.35 and flat rows "
        "where the duration axis loses physical meaning. 5 frames is the solid operational floor."
    )

    # ---- Slide 9: executive conclusions ----
    slide = new_slide(prs)
    add_title(slide, "Executive Conclusions")
    add_bullets(
        slide,
        [
            ("1. The 87% similarity was an artifact:  ", "Full-frame correlation was dominated by scene geometry (shared circle + sensor fog), not wavelength-dependent optics"),
            ("2. Filtered correlation is 0.67, driven by LCD hardware:  ", "Spatial filtering removes geometry; residual 0.67 is explained by the display's physical subpixel grid and shared backlight PWM"),
            ("3. 80% cross-color similarity is never reached:  ", "Across 120 tested parameter combinations, correlation tops out at 0.62 — '80% similarity' does not occur in this optical configuration"),
            ("4. Frame rate does not buy differentiation:  ", "10 FPS to 10,000 FPS yield nearly identical correlation values; spectral differentiation requires ~1 to 2 seconds of scene exposure"),
            ("5. Clear operational envelope:  ", "Valid measurements require ≥5 accumulated frames and ≥1–2 s scene time. Effective frame rate (10 to 1,000+ FPS) is an unconstrained engineering choice"),
        ],
        Inches(0.75), Inches(1.55), Inches(11.8), Inches(5.1), size=16,
    )
    add_footer(slide, 9)
    slide.notes_slide.notes_text_frame.text = (
        "Five definitive conclusions for project leadership: 1) Artifact diagnosed and resolved. "
        "2) Residual correlation understood through LCD physics. 3) 80% threshold does not bind. "
        "4) System trade-off identified: scene time matters, frame rate is flexible. "
        "5) Concrete operational parameters established."
    )

    # ---- Slide 10: recommendations / next steps ----
    slide = new_slide(prs)
    add_title(slide, "Recommendations and next steps")
    add_bullets(
        slide,
        [
            ("Split-half reliability control:  ", "Correlate the first and second halves of each recording against itself to establish the experimental noise ceiling"),
            ("Exploit temporal dynamics:  ", "Use LCD pixel transition profiles (rise/fall response curves differ by color primary) rather than purely spatial pattern correlation"),
            ("Characterize subpixel contribution:  ", "Shift target position on screen to decouple display subpixel grid from sensor pixel grid"),
            ("Transition to narrowband targets:  ", "Use calibrated spectral sources (lasers / filtered LEDs) where optical dispersion is the primary physical mechanism"),
            ("Adopt operating envelope:  ", "Standardize capture duration at ≥2 seconds; select frame rate based on downstream processing needs (10 to 1,000+ FPS)"),
        ],
        Inches(0.75), Inches(1.55), Inches(12), Inches(5.1), size=17, numbered=True,
    )
    add_footer(slide, 10)
    slide.notes_slide.notes_text_frame.text = (
        "Recommendations: 1) Measure the noise ceiling directly with split-half validation. "
        "2) The temporal domain (transition dynamics) offers stronger color discrimination than "
        "static spatial correlation for LCD targets. 3) Narrowband sources remain the path to "
        "true spectral calibration."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(f"Wrote {build()}")
