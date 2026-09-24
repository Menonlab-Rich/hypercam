# Weekly Status Report — Spectral Correlation with Event Cameras

**Name:** Rich Baird
**Week of:** September 14–18, 2026
**Audience:** rmenon (PI)
**Re:** Follow-ups to this week's Slack thread (FPS independence, single-frame limits, effective frame rate definition, and the rotating-wheel experiment)

---

## 🎯 Summary

This week I instrumented the correlation analysis to answer the questions raised in the Slack thread directly: a fine duration × frame-rate sweep with the paper's ON−OFF binning, a split-half noise ceiling, and a per-pair significance test. The headline measurements: **cross-color correlation is flat in effective frame rate (10 → 10,000 FPS) and grows only with total averaging time** — confirming the TLDR ("it's not the FPS, it's the total duration") — and the earlier apparent FPS dependence was an artifact of how events were binned, which is now fixed.

---

## 📐 Definitions (to align on terms first)

| Symbol | Name | Definition |
|--------|------|------------|
| t | accumulation interval | wall-clock time integrated into one binned frame |
| 1/t | effective frame rate (FPS) | frames produced per second |
| N | frame count | number of binned frames averaged |
| T | total averaging time | T = N·t |
| r | cross-color Pearson r | correlation between the averaged frames of two wavelength recordings |
| noise ceiling | within-recording reliability | how well a recording reproduces its own pattern (split-half, Spearman-Brown) |

One note on the proposed definition "effective frame rate = number of frames / accumulation time per frame": with N frames each accumulated over t, that expression is N/t, which mixes units. The natural pair is **effective FPS = 1/t** and **N = T/t** — the two free knobs are (T, FPS), and N follows. All results below are reported in those terms. This matters because the whole finding is that **T is the operative variable and FPS is nearly free**.

---

## 💬 Responses to the open questions

### Q1 — "Are you saying single events (very short durations) cannot be detected? That's what DVS is for (lightning, Ca spikes — the BU paper)."

No — and this is the key distinction I failed to make in the thread. **Detection and estimation are different problems.** Every threshold crossing is detected and timestamped at microsecond resolution; nothing in our pipeline prevents single-event detection, which is exactly why DVS works for lightning and Ca transients.

Our task, however, is *estimation*: reconstructing the spatial diffraction pattern that encodes the spectrum from binned events. A single event, or a single binned frame, is one Poisson-distributed, threshold-quantized sample of that pattern. I measured how far 1–2-frame reconstructions land from the converged answer: **deviations up to ~0.74 in correlation units**, while **≥5 averaged frames converge (≤0.075 deviation)**. The BU paper (Shah et al., CVPR 2024) makes the same move from the tracking side: they bin 16 refresh cycles into every frame, and their ablation without accumulation degrades tracking RMSE by +45–54%.

So: single events are detectable; a single frame is not a reliable estimator of the pattern.

### Q2 — "Maybe you mean the spectral reconstruction error increases with effective frame rate (this is what I expect) and you have the data to show this."

Measured this week — the data shows **neither**. At fixed total averaging time, reconstruction quality (cross-color r) is essentially **flat in effective frame rate**. See Figure 1 (`reports/figures/cross_correlation_vs_effective_frame_rate.png`), left panel, and the table below.

| Total averaging T | 10 FPS | 1,000 FPS | 10,000 FPS | FPS spread |
|---|---|---|---|---|
| 5 s | 0.7796 | 0.7844 | 0.7847 | 0.005 |
| 2 s | 0.5675 | 0.5840 | 0.5847 | 0.017 |
| 1 s | 0.3410 | 0.3605 | 0.3614 | 0.020 |
| 0.5 s | — | 0.1582 | 0.1588 | 0.001 |

What *does* increase error is **less total averaging time** (0.5 s: 0.16 → 5 s: 0.78). There *was* an apparent FPS dependence in the earlier data — up to 11.6% spread, in the direction you found counter-intuitive — but it was an artifact of folding ON and OFF events into one count before a nonlinearity. Binning events with the paper's signed scheme (ON − OFF, which the BU paper proves approximates the log-intensity change) collapses the spread to 0.5–2%, and it also *raises* the converged signal itself: 5 s correlation 0.61 → 0.78, with green–red reaching 0.90. So the 80% cross-color separation target is now reached where the earlier report said it was never reached.

### Q3 — "This is spectroscopy, there is no FoV; cross-correlation across the colors should be as low as possible. If it decreases with effective frame rate, does that mean colors differentiate better as you go faster? Counter-intuitive."

Two clarifications:

1. **On "no FoV":** agreed the deliverable is the spectrum/RGB value. The sensor's pixel array is still the substrate that encodes it — the diffraction pattern is spatial, and the binned frame is the intermediate representation from which the spectrum is decoded. "Across the full aperture" in my earlier message meant: the estimator needs the event record covering the whole encoding pattern, not a spatial subset. The output remains a spectrum, not an image.

2. **On "lower cross-correlation = better differentiation as FPS rises":** this was the trap in the earlier plot, and your instinct that it was counter-intuitive was correct. Cross-color r falling toward zero is only *better differentiation* if each recording is independently reliable. Below ~0.25 s of total averaging, the recordings are not yet self-reproducible — the low r there is uncorrelated noise, not signal (as I noted in the thread: "the lowest numbers are only just purely uncorrelated noise — not signal"). The correct statement is: **differentiation = low cross-color r relative to a high within-recording noise ceiling**, and the noise ceiling itself is built by total averaging time. Under the corrected estimator the FPS curve is flat, so no — FPS does not buy differentiation; total signal does.

### Q4 — "Can you plot the cross-correlation as a function of the effective frame rate?"

Yes — Figure 1, attached as `reports/figures/cross_correlation_vs_effective_frame_rate.png` (also SVG). Left panel: the corrected ON−OFF estimator (current). Right panel: the earlier ON+OFF estimator for contrast — this is where the apparent FPS trend lived, and the panel makes visible that it was an artifact. Both panels share the y-axis; each curve is a fixed total averaging time (0.5 / 1 / 2 / 5 s), x-axis is effective FPS from 10 to 10,000.

### Q5 — "Oh so you mean the display is not bright enough?"

No — brightness is not the limiter. The display is a **60 Hz screen**: content updates every 16.7 ms, and the backlight/refresh modulates the sensor even for static content. Consequences measured this week:

- The first accumulation interval that contains reproducible structure is **~16 ms — one display period** — which we now treat as a display-period artifact, not a fundamental limit (the BU paper's "16 frames at 1 ms" coincidence is worth re-examining on hardware that isn't refresh-locked).
- Split-half reliability diagnostics go negative in a pattern consistent with windows sampling fixed phases of a ~60 Hz-periodic modulation.
- Practical upshot: the *scene's* temporal dynamics are capped by the display, so the "how fast can the scene change" axis of the experiment cannot be probed on this source — hence the rotating-wheel experiment below.

### Q6 — "With a faster source you can probe the limit I'm looking for, right? Rotating filter wheel with a lamp or bright source, color filters for different spectra?"

Agreed — that is the right next experiment, and it directly tests the claim from the thread that smaller accumulation intervals require more dynamic signal. One design upgrade to consider: rather than a continuously rotating *filter* wheel, the CAD'd 18-LED chopper wheel (63 mm, 20° station spacing, already modeled in `models/`) puts the timing under precise control — mounting two wavelength LEDs in the wheel gives known, stable modulation frequency **and** the spectral pair in the same instrument, with the same correlation pipeline as output.

Predicted scaling to verify: a pixel fires when the log-intensity change accumulates past the contrast threshold C, so a window of length t captures ≈ t·|d log I/dt|/C events. Enough events per window requires t ≳ a few·C/|d log I/dt| — i.e., **the minimum usable accumulation interval scales inversely with modulation frequency** (t_min ∝ 1/f). Equivalently: the governing quantity is **events per window**, not FPS. Protocol:

1. Frequency ladder incommensurate with 60 Hz (e.g., 97, 211, 503 Hz) + one deliberate 60 Hz-commensurate run as a positive control for aliasing.
2. Chopper-off baseline capture: characterizes the display's intrinsic modulation and provides the event-starved ("static scene") end point, where t_min should blow up.
3. For each frequency: 10 s recording, full sweep at ON−OFF binning; extract events-per-window, minimum t with significant r, and the FPS-invariance check.

If the t_min ∝ 1/f scaling holds — equivalently, if results collapse onto a single curve in events-per-window — that confirms "smaller t requires faster dynamics" quantitatively and gives you the t vs frequency design map for the spectroscopy experiments.

### Q7 — "If you need more frames, we can define the effective frame rate accordingly: number of frames / accumulation time per frame."

Agreed on needing precise definitions — proposal in the Definitions table above: **effective FPS = 1/t**, **T = N·t**, N = T·FPS. Then your TLDR example becomes exactly measurable, and it verifies: 1,000 frames at 10,000 FPS (T = 100 ms) vs 100 frames at 1,000 FPS (T = 100 ms) give r = −0.0043 vs −0.0045 — indistinguishable (both are at the noise floor, since 100 ms is far below the ~0.5 s minimum), and at T = 5 s, 0.7847 vs 0.7844. Same total time, same answer — at any FPS.

---

## ✅ Accomplishments

- Completed the fine duration × frame-rate sweep instrument: 12–25 ms resolution grid, ON−OFF / ON / OFF / folded polarity modes, split-half noise ceiling, per-pair Student-t significance
- Switched the estimator to the BU paper's ON−OFF binning (proven ≈ log-intensity change, their Supplement S4); converged cross-color correlation 0.61 → 0.78, green–red 0.90; the 80% separation target is now reached
- Diagnosed the earlier FPS-dependent trend as a polarity-folding artifact; FPS dependence collapsed from 11.6% to 0.5–2% spread
- Verified all four shared claims against Shah et al. (CVPR 2024), including their 16-refresh-cycle binning and their no-accumulation ablation (+45–54% RMSE) matching our multi-frame requirement
- Produced Figure 1 answering the requested cross-correlation vs effective-frame-rate plot; verification report deck delivered

## 🚧 In Progress

| Task | Status | Expected completion |
|------|--------|---------------------|
| Chopper LED wheel mounting + frequency ladder captures | hardware ready, awaiting bench time | next week |
| Partition-invariance test (ON−OFF with linear scaling; needs no new capture) | queued | early next week |
| Sub-10-frame floor re-measurement under the corrected estimator | queued | next week |

## 🚫 Blockers

- **60 Hz display ceiling** — the current source cannot probe scene dynamics above one refresh period, and it injects its own periodic modulation (this is the likely cause of a negative-reliability diagnostic in the split-half analysis). Impact: the t_min vs frequency scaling cannot be measured on the LCD. Resolution: the chopper/LED wheel captures above — hardware exists, needs mounting.

## 📅 Next Week's Priorities

1. Chopper bench setup; frequency ladder captures (incommensurate with 60 Hz + one commensurate control + chopper-off baseline)
2. Partition-invariance test on existing recordings (validates the estimator before new captures are analyzed)
3. t_min ∝ 1/f scaling analysis from the frequency ladder; updated FPS plot with chopper data
4. Revised spectra-deck conclusions (80% target reached; 16 ms finding re-scoped as display-period artifact pending chopper data)

## 💬 Notes / FYI

- Standing operating envelope from this week's measurements: **≥5 averaged frames; ≥0.5–1 s total averaging for reliable discrimination; effective FPS free from 10 to 10,000** (signed estimator). The paper's 16 ms bin sits at the lower edge of detectability on display-driven content; treat it as an edge, not an operating point, until the chopper data re-baselines it.
- Figure 1 data: LCD circle recordings, 720×1280 EVT3, 5 s per color; crop + spatial high-pass + support-masked Pearson; ON−OFF binning per Shah et al. Supplement S4. All scripts and result tables are in the repository (`src/hypercam/duration_sweep.py`, `src/hypercam/results/`).

---

**Figure 1.** `reports/figures/cross_correlation_vs_effective_frame_rate.png` — Mean cross-color Pearson r vs effective frame rate at fixed total averaging times. Left: ON−OFF binned frames (current estimator). Right: earlier ON+OFF estimator, showing the artifact responsible for the apparent FPS trend.
