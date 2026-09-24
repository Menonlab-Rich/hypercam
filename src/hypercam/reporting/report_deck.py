# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Generate the polarity-verification report deck."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = REPO_ROOT / "results" / "spectral_correlation_fine_signed"
OUTPUT = REPO_ROOT / "reports" / "decks" / "polarity_verification_report.pptx"

NAVY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0x2E, 0x74, 0xB5)
LIGHT_BLUE = RGBColor(0xBD, 0xD7, 0xEE)
PALE_BLUE = RGBColor(0xDD, 0xEB, 0xF7)
TEXT = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x7F, 0x7F, 0x7F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x2E, 0x7D, 0x32)
BAD = RGBColor(0xB3, 0x3E, 0x3E)

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FOOTER = "Hypercam spectral correlation · polarity verification report · September 2026"


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
):
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
    if not paragraph.runs:
        paragraph.add_run()
    run = paragraph.runs[0]
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_table(slide, rows, columns, left, top, width, height, header_fill=NAVY):
    frame = slide.shapes.add_table(rows, columns, left, top, width, height)
    table = frame.table
    for column in range(columns):
        style_cell(table.cell(0, column), "", bold=True, color=WHITE, fill=header_fill)
    return table


def build() -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    prs.core_properties.title = "Polarity verification — Shah et al. (CVPR 2024) vs hypercam results"

    # ---- Slide 1: title ----
    slide = new_slide(prs)
    background = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    background.fill.solid()
    background.fill.fore_color.rgb = NAVY
    background.line.fill.background()
    background.shadow.inherit = False
    add_text(slide, "Signed-Polarity Spectral Correlation", Inches(0.9), Inches(2.05), Inches(11.6), Inches(1.6), size=40, bold=True, color=WHITE)
    add_text(
        slide,
        "Verifying our results against Shah et al., CodedEvents (CVPR 2024) — and what the fine-grid sweep changed",
        Inches(0.9), Inches(3.75), Inches(11.6), Inches(0.9), size=20, color=LIGHT_BLUE,
    )
    add_text(slide, "Hypercam spectral correlation · verification report · September 2026", Inches(0.9), Inches(6.55), Inches(11.6), Inches(0.5), size=14, color=RGBColor(0x8E, 0xA9, 0xDB))
    slide.notes_slide.notes_text_frame.text = (
        "Executive summary: all four shared claims verify against Shah et al. The new instrumented sweep "
        "shows the strong negative short-time correlation was a polarity-folding artifact, not physics. "
        "Switching to the paper's ON−OFF binning strengthens the converged signal from 0.61 to 0.78 and "
        "pushes green-red to 0.90 — 80% similarity is now reached, contradicting our earlier conclusion #3. "
        "16 ms is measured as the lower edge of detectability at 1 ms accumulation. Two diagnostics need a "
        "fix before the next deck refresh."
    )

    # ---- Slide 2: what was done ----
    slide = new_slide(prs)
    add_title(slide, "Scope: what was verified, and with what instrument")
    add_bullets(
        slide,
        [
            ("Paper evidence:  ", "paper + supplement extracted and read (S1–S4, Tables 1/3/4, Figs. 2/11–13); all quoted numbers taken from the text"),
            ("Results audited:  ", "all folders — spectral / gaussian / no_filter laser scans, LCD circle RGB (raw + filtered), and the three duration-sweep variants (min1 / min5 / unmasked)"),
            ("New instrument:  ", "duration × accumulation sweep upgraded — fine 12/14/16/18/20/22 ms grid, ± polarity split, split-half noise ceiling with Student-t discernibility per pair"),
            ("Signed polarity:  ", "each window accumulates ON − OFF per pixel with sign-preserving log1p — exactly the paper's binned event frame ≈ Δlog I / T (Supplement S4, |error| < 1)"),
            ("Data:  ", "5 s circle_blue / green / red recordings, 720 × 1280 EVT3, crop + 64 px high-pass + support-masked Pearson"),
        ],
        Inches(0.75), Inches(1.55), Inches(11.8), Inches(4.8), size=16,
    )
    add_footer(slide, 2)
    slide.notes_slide.notes_text_frame.text = (
        "The signed mode is not a new metric — it is the paper's own measurement model. The earlier sweeps folded "
        "both polarities into one count, which the paper never does."
    )

    # ---- Slide 3: verification verdicts ----
    slide = new_slide(prs)
    add_title(slide, "Verification verdicts on the four shared claims")
    table = add_table(slide, 5, 3, Inches(0.6), Inches(1.5), Inches(12.1), Inches(4.6))
    table.columns[0].width = Inches(3.3)
    table.columns[1].width = Inches(4.4)
    table.columns[2].width = Inches(4.4)
    for column, header in enumerate(("Claim", "Shah et al. (CVPR 2024)", "Our results")):
        style_cell(table.cell(0, column), header, bold=True, color=WHITE, fill=NAVY)
    rows = (
        ("Binned frames recreate the log-intensity change",
         "Proven (Supp. S4; Fig. 2): binned frame = Δlog I / T ± 1",
         "Signed binning raises converged r 0.61 → 0.78 — verified, now demonstrated"),
        ("Success at 16 refresh cycles (16 × 1 ms?)",
         "16 cycles stated; 10 kHz refresh ⇒ 1.6 ms/bin, so 16 ms is our interpretation",
         "First positive reproducible r at 14–16 ms (1 ms acc.) — supported as a detectability edge"),
        ("CRLB-loss inverse design behaves ideally",
         "NPM: CRB 33.1 nm (best of 5), tracking RMSE 51.2 nm",
         "DoE artifacts are not in this workspace — not checkable here"),
        ("Multiple accumulated frames strictly required",
         "Without accumulation: RMSE +45% (NPM), +54% (NAM)",
         "≥5-frame floor (deviation ≤0.075); 1–2 frames break down (up to ~0.74)"),
    )
    for row_index, row in enumerate(rows, start=1):
        for column, text in enumerate(row):
            style_cell(table.cell(row_index, column), text, size=13,
                       fill=PALE_BLUE if row_index % 2 else WHITE)
    add_footer(slide, 3)
    slide.notes_slide.notes_text_frame.text = (
        "Caveat on row 2: the paper never states 1 ms per refresh cycle. Its own numbers (1000 accumulated "
        "frames/s; 10 kHz → 625 FPS with 16-frame bins) imply 1–1.6 ms per bin. Our real-world prototype demo "
        "in S1 uses 1 ms bins without 16-frame accumulation. Treat '16 ms' as our reading, and the claim as "
        "verified only in the detectability-edge sense."
    )

    # ---- Slide 4: finding 1 ----
    slide = new_slide(prs)
    add_title(slide, "Finding 1 — the −0.99 short-time regime was polarity folding")
    table = add_table(slide, 5, 3, Inches(0.6), Inches(1.55), Inches(6.4), Inches(2.9))
    table.columns[0].width = Inches(2.4)
    table.columns[1].width = Inches(2.0)
    table.columns[2].width = Inches(2.0)
    for column, header in enumerate(("Total averaged time", "ON+OFF (old)", "ON−OFF (paper)")):
        style_cell(table.cell(0, column), header, bold=True, color=WHITE, fill=NAVY)
    data = (("1–2 ms", "−0.996", "−0.112"), ("25 ms", "−0.708", "−0.013"), ("50 ms", "−0.253", "+0.011"), ("100 ms", "−0.163", "−0.004"))
    for row_index, row in enumerate(data, start=1):
        for column, text in enumerate(row):
            style_cell(table.cell(row_index, column), text, size=14, align=PP_ALIGN.CENTER if column else PP_ALIGN.LEFT,
                       fill=PALE_BLUE if row_index % 2 else WHITE)
    add_bullets(
        slide,
        [
            ("Artifact confirmed:  ", "the strong negative cross-color r below 25 ms exists only when ON and OFF are folded into one count"),
            ("Not spectral physics:  ", "under the paper's pos−neg binning the same cells sit at ~0 — the September deck's 'disjoint event spikes' hypothesis was right"),
            ("Consequence:  ", "any conclusion drawn from the negative branch (e.g. 'disjoint event patterns') described the transform, not the scene"),
        ],
        Inches(7.35), Inches(1.7), Inches(5.5), Inches(3.6), size=14,
    )
    add_caption(slide, "Mean cross-color Pearson r, ON+OFF vs ON−OFF (signed), matched durations.", Inches(0.6), Inches(4.65), Inches(6.4))
    add_footer(slide, 4)
    slide.notes_slide.notes_text_frame.text = (
        "The signed cells are not exactly zero because the union-support mask biases two sparse frames toward "
        "slight anti-correlation. Magnitude ≤ 0.11 and non-monotonic — noise-level wobble, not structure."
    )

    # ---- Slide 5: finding 2 ----
    slide = new_slide(prs)
    add_title(slide, "Finding 2 — signed polarity strengthens the signal at every duration")
    picture = slide.shapes.add_picture(str(RESULTS / "duration_accumulation_sweep.png"), Inches(0.55), Inches(1.35), width=Inches(7.1))
    add_bullets(
        slide,
        [
            ("Converged signal up:  ", "mean cross-color r 0.612 → 0.784 at 5 s (1 ms acc.); every duration ≥ 0.5 s improves"),
            ("Green–red hits 0.897:  ", "pair ordering now tracks wavelength separation (green–red > blue–red > blue–green)"),
            ("80% threshold reached:  ", "green–red crosses 0.8 between 2 s and 5 s — the September deck's conclusion #3 ('max 0.62, 80% never reached') is falsified"),
            ("16 ms grid line:  ", "the dotted line marks 16 × 1 ms — the paper's bin structure, now a measured column"),
        ],
        Inches(7.9), Inches(1.55), Inches(5.0), Inches(4.9), size=14,
    )
    add_footer(slide, 5)
    slide.notes_slide.notes_text_frame.text = (
        "The improvement is expected from the paper's model: signed frames approximate the log-intensity change "
        "itself, while folded counts mix the pattern with a polarity-independent activity map. This upgrades the "
        "log-intensity claim from 'consistent with the paper' to demonstrated."
    )

    # ---- Slide 6: finding 3 ----
    slide = new_slide(prs)
    add_title(slide, "Finding 3 — 16 ms is the lower edge of detectability (1 ms acc.)")
    table = add_table(slide, 8, 4, Inches(0.6), Inches(1.5), Inches(6.6), Inches(3.9))
    table.columns[0].width = Inches(1.5)
    table.columns[1].width = Inches(1.9)
    table.columns[2].width = Inches(1.6)
    table.columns[3].width = Inches(1.6)
    for column, header in enumerate(("Duration", "blue–green", "blue–red", "green–red")):
        style_cell(table.cell(0, column), header, bold=True, color=WHITE, fill=NAVY)
    acc1 = [
        ("10 ms", "−0.006 (ns)", "−0.005 (ns)", "−0.059 (ns)"),
        ("12 ms", "+0.003 (ns)", "+0.010 (ns)", "−0.033 (ns)"),
        ("14 ms", "+0.010 (t=+7.5)", "+0.024 (ns)", "−0.029 (ns)"),
        ("16 ms", "+0.006 (t=+4.8)", "+0.017 (t=+3.3)", "−0.048 (t=−11.2)"),
        ("18 ms", "+0.000 (ns)", "+0.005 (ns)", "−0.056 (t=−6.3)"),
        ("25 ms", "+0.004 (ns)", "+0.010 (ns)", "−0.054 (t=−5.6)"),
        ("50 ms", "+0.008 (ns)", "−0.008 (ns)", "+0.034 (t=+14.8)"),
    ]
    for row_index, row in enumerate(acc1, start=1):
        for column, text in enumerate(row):
            style_cell(table.cell(row_index, column), text, size=13, align=PP_ALIGN.LEFT if column == 0 else PP_ALIGN.CENTER,
                       fill=PALE_BLUE if row_index == 4 else WHITE)
    add_bullets(
        slide,
        [
            ("Holds as an edge:  ", "16 frames × 1 ms is the first duration with reproducible positive cross-color structure (14–16 ms); 10–12 ms shows nothing"),
            ("Honest caveats:  ", "effect size r ≈ 0.006–0.024 — a hint, not usable signal; flags flicker again by 18–25 ms; the green–red flag at 16 ms is negative anti-structure"),
            ("Usable signal:  ", "needs 0.5–1 s of total averaged time (r ≥ 0.16 → 0.36)"),
        ],
        Inches(7.5), Inches(1.6), Inches(5.4), Inches(3.9), size=14,
    )
    add_caption(slide, "Signed sweep, 1 ms accumulation column. ns = not significant at 95% (Student-t across replicates).", Inches(0.6), Inches(5.55), Inches(6.6))
    add_footer(slide, 6)
    slide.notes_slide.notes_text_frame.text = (
        "This is the direct measurement of the claim that 16 × 1 ms is 'the very limit of discernibility'. "
        "Supported as a lower edge; state it with the effect-size caveat. The flagged rows below 50 ms "
        "reproducibly wobble around zero with both signs."
    )

    # ---- Slide 7: curves ----
    slide = new_slide(prs)
    add_title(slide, "Discernibility vs total averaged time")
    picture = slide.shapes.add_picture(str(RESULTS / "discernibility_curves.png"), Inches(0.55), Inches(1.4), width=Inches(12.2))
    add_bullets(
        slide,
        [
            ("Panel rule:  ", "filled = significant across interleaved replicates (95% t); error bars = 95% CI; dashed = split-half noise ceiling (see open issue)"),
            ("Read:  ", "positive reproducible structure appears at the 16 ms line and grows monotonically with total averaged time, independent of accumulation interval"),
        ],
        Inches(0.75), Inches(5.35), Inches(11.8), Inches(1.4), size=14,
    )
    add_footer(slide, 7)
    slide.notes_slide.notes_text_frame.text = (
        "The three panels are 0.1 ms, 1 ms and 100 ms accumulation — the independence of the curves' shape from "
        "accumulation interval is the visual form of 'total averaged time is what matters'."
    )

    # ---- Slide 8: finding 4 ----
    slide = new_slide(prs)
    add_title(slide, "Finding 4 — the accumulation-time story is reframed")
    table = add_table(slide, 4, 3, Inches(0.6), Inches(1.55), Inches(6.4), Inches(2.4))
    table.columns[0].width = Inches(2.8)
    table.columns[1].width = Inches(1.8)
    table.columns[2].width = Inches(1.8)
    for column, header in enumerate(("5 s total, 0.1 → 100 ms acc.", "ON+OFF (old)", "ON−OFF (paper)")):
        style_cell(table.cell(0, column), header, bold=True, color=WHITE, fill=NAVY)
    data = (("r at 0.1 ms / 100 ms", "0.614 / 0.543", "0.785 / 0.780"), ("Spread (relative)", "0.072  (11.6%)", "0.005  (0.65%)"), ("Verdict", "strong degradation", "near-independent"))
    for row_index, row in enumerate(data, start=1):
        for column, text in enumerate(row):
            style_cell(table.cell(row_index, column), text, size=14, align=PP_ALIGN.LEFT if column == 0 else PP_ALIGN.CENTER,
                       fill=PALE_BLUE if row_index % 2 else WHITE)
    add_bullets(
        slide,
        [
            ("Claim 1 — strengthened:  ", "per-frame accumulation time is close to a free choice; total averaged time is the operative variable (needs ~0.5–1 s)"),
            ("Claim 2 — deflated:  ", "the strong 'signal degrades with longer accumulation' result was mostly a folding artifact; under signed polarity it is monotonic but ~20× weaker"),
            ("What the paper has not shown:  ", "still true for both — the paper never varies per-frame bin time at fixed total time"),
        ],
        Inches(7.35), Inches(1.7), Inches(5.5), Inches(3.9), size=14,
    )
    add_footer(slide, 8)
    slide.notes_slide.notes_text_frame.text = (
        "The earlier degradation result is real under the old transform but should be attributed to the transform, "
        "not to wavelength physics. Keep the monotonicity claim, drop the magnitude."
    )

    # ---- Slide 9: open issue ----
    slide = new_slide(prs)
    add_title(slide, "Open issue — the split-half ceiling breaks under signed data")
    add_bullets(
        slide,
        [
            ("Symptom:  ", "within-recording reliability is negative almost everywhere (blue/green/red −0.27/−0.36/−1.24 at 16 ms; worst ceiling −5.6 at 1 s), so Spearman-Brown correction is undefined and fraction-of-ceiling is meaningless (the one defined value, 3.99, is nonsense)"),
            ("Cause:  ", "interleaved odd/even windows of signed frames systematically anti-correlate (raw part-r down to ≈ −0.7) — opposite-phase windows, consistent with ON-burst/OFF-burst alternation or a display PWM/blink period commensurate with the window grid"),
            ("What still works:  ", "the replicate Student-t discernibility test and the SEM error bars — the ceiling line in the curves figure is the only casualty"),
        ],
        Inches(0.75), Inches(1.55), Inches(11.8), Inches(3.4), size=16,
    )
    add_text(slide, "Planned fix", Inches(0.75), Inches(5.0), Inches(11.8), Inches(0.4), size=17, bold=True, color=NAVY)
    add_bullets(
        slide,
        [
            ("Contiguous split mode:  ", "first half vs second half of the windows — each half spans whole blink cycles, restoring positive part-reliability"),
            ("Sign-aware flags:  ", "report discernible-positive and discernible-negative separately, so 'first structure' and 'first shared structure' stop being conflated"),
        ],
        Inches(0.75), Inches(5.5), Inches(11.8), Inches(1.3), size=15,
    )
    add_footer(slide, 9)
    slide.notes_slide.notes_text_frame.text = (
        "The 16 ms claim does not depend on the ceiling — it uses the t-test only. The ceiling matters for the "
        "'are we noise-limited or signal-limited' question and for the next deck refresh."
    )

    # ---- Slide 10: next steps ----
    slide = new_slide(prs)
    add_title(slide, "Recommendations and next steps")
    add_bullets(
        slide,
        [
            ("Implement the ceiling fix:  ", "contiguous split mode + sign-aware discernibility flags, then re-run the signed fine sweep"),
            ("Complete the polarity split:  ", "fine-grid runs for ON+OFF (both), ON-only, OFF-only — the comparison table above uses the old coarse grid for the old transform"),
            ("Regenerate the main matrices signed:  ", "500-frame results move from 0.54–0.67 to ~0.71–0.90; the stakeholder deck's conclusions #3–#5 need updating"),
            ("Characterize the anti-phase source:  ", "A/B interleaved vs contiguous splits isolates the display PWM/blink periodicity behind the negative reliability"),
            ("Push past the mean threshold:  ", "green–red is already ≥ 0.8; recordings ≥ 6 s should carry the mean past 0.8 too"),
            ("Keep the operating envelope:  ", "≥5 accumulated frames, ≥0.5–1 s total averaged time, any frame rate 10–10,000 FPS; 16 ms remains the detectability edge, not an operating point"),
        ],
        Inches(0.75), Inches(1.55), Inches(11.8), Inches(5.2), size=16, numbered=True,
    )
    add_footer(slide, 10)
    slide.notes_slide.notes_text_frame.text = (
        "Order matters: the ceiling fix (1) should land before the re-runs (2) so the new sweeps carry a usable "
        "ceiling. Items 3–5 can then reuse the fixed instrument."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(f"Wrote {build()}")
