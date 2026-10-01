==============================================================================
Author:        Richard G. Baird
Date Modified: 2026-09-26
Notice:        This file was authored or modified with the assistance of
               Kilo CLI (GLM, z-ai/glm-5.3-flash).
==============================================================================

# Where We Are: Demonstrating Hyperspectral Event Sensing — Practice and Theory

**Date:** September 26, 2026
**Purpose:** A single synthesis of (a) the weekly status report
(`weekly_report_2026-09-18.md`), (b) the theory manuscript
(`proposed_CRLB_Derivation.pdf`, "Derivation of 4D Fisher Information Matrix
for Event-Based Sensors"), and (c) the technical response
(`Proposed_CRLB_response.pdf`, "Hyperspectral coded events: a diffractive
surface model for spectrum recovery, with corrected information bounds").
Cross-checked against the actual analysis outputs in `results/` so the
numbers below are the measured ones, not paraphrases.

---

## 1. The goal, stated once

Demonstrate **hyperspectral event sensing**: use a wavelength-engineered
diffraction pattern (a diffractive optical element / phase mask in front of a
Prophesee EVT3 event camera) so that the *spatial event pattern* encodes the
spectrum of the scene, then recover the spectrum from the asynchronous event
stream. The combined system — engineered PSF + event sensor + decoder — has
not been established by any cited prior work; Majumder et al. (Optica 2025)
supply the diffractive spectral encoding, Shah et al. (CVPR 2024,
"CodedEvents") supply event-based PSF engineering for 3D tracking, and our
contribution is their synthesis plus information-driven design. Both tracks
below are in service of that demonstration.

---

## 2. Track A — In practice (the lab measurements)

### 2.1 What works end to end

The sensing chain is functional and has survived one optical redesign. The first
superk illumination attempt was mis-focused — the beam was not brought to a correct
focus and the frame filled with light instead of forming a tight coded image — which
made the original 425–675 nm narrowband sweep unusable as a spectral measurement and
motivated a temporary switch to a color display target (at the cost of the display's
60 Hz ceiling). The current setup returns to the laser with corrected illumination: a
**collimated superk beam projected onto a translucent screen**, producing a perfectly
divergent source the lens cannot focus to a point, with the **Coded Events-derived
diffractive optical element in the beam path** and the 12-window chopper wheel as the
temporal probe. Decoding (OpenEVT), activity frames, crop / high-pass /
support-masked Pearson correlation, and the reproducibility machinery
(`results/README.md`, GHCR data images) are all unchanged and working.

### 2.2 Established empirical results (week of Sep 14–18, 2026)

These are the settled findings, verified against
`results/spectral_correlation_fine_signed/` (display reference target: red/green/blue
circles). They demonstrate the **estimator**, not yet the coded optics on laser
lines:

| Finding | Measured value | Status |
|---|---|---|
| Cross-color correlation vs effective frame rate | flat: 0.5–2 % spread at fixed T | **Settled** (was 11.6 % artifact) |
| Converged cross-color r (signed ON−OFF estimator, T = 5 s) | **0.78** mean (blue–green 0.71, blue–red 0.74, green–red **0.89**) | **Settled** — 80 % separation target reached |
| First superk sweep (ON+OFF legacy, mis-focused beam) | 0.59 mean (green–red 0.67) | Superseded — illumination flaw, kept as control |
| Minimum reliable integration | ≥ 5 averaged frames (≤ 0.075 r deviation); 1–2 frames deviate up to ~0.74 | **Settled** |
| Operating envelope | T ≥ 0.5–1 s; FPS free from 10 to 10 000 | **Settled** |
| Detection vs estimation | single events *detectable*; a single binned frame is *not a reliable estimator* | **Settled** (answers PI's Q1/Q2 directly) |

The estimator switch matters as much as the numbers: binning events with the
paper's signed ON−OFF scheme (proven ≈ log-intensity change, Shah et al.
Supplement S4) both raised the converged signal (0.61 → 0.78) and collapsed
the spurious FPS dependence. The earlier "FPS changes discrimination" story
was a polarity-folding artifact of folding ON and OFF into one count before a
nonlinearity.

### 2.3 Known physical blocker: the 60 Hz display ceiling

The display target was a deliberate detour after the mis-focused first superk
attempt: simple to drive, clean to analyze, but the 60 Hz refresh caps scene
dynamics at one refresh period and injects its own periodic modulation. Split-half
reliability diagnostics go negative in a pattern consistent with windows
sampling fixed phases of that modulation — so the "how fast can the scene
change" axis (and the t_min vs modulation frequency law) cannot be probed on
this source. The 16 ms bin sits at the lower edge of detectability for
display-driven content and is treated as a display-period artifact, not a
fundamental limit, pending the chopper data.

### 2.4 Current frontier: the corrected superk setup + chopper (in progress, unresolved)

The illumination failure that drove the display detour is fixed. The new front end
is a **collimated superk beam projected onto a translucent screen** — a perfectly
divergent source that the lens cannot focus to a point, which was the first
attempt's failure mode — with the **Coded Events-derived diffractive element in the
beam path**, so the sensor sees the coded PSF under correctly divergent
illumination. The 18-LED chopper wheel (960 rev/s, 12 windows → 11 520 Hz per-pixel
chop, constant aggregate flux) supplies the fast temporal probe the display could
not. Raw recordings exist for 475–675 nm (`data/raw/evt3_raw/960hz-chopper_*.raw`),
and the first analysis pass has been run on four of them (500–575 nm) into
`results/spectral_correlation_chopper/`. **The first result is not yet a
demonstration of discrimination:** the pairwise correlation matrix is
near-saturated (cross-color r between 0.947 and 0.996, mean ≈ 0.97), i.e. the
shared chopping structure dominates the correlation and the spectral
difference is currently invisible under this pipeline. Two caveats from the
run metadata: the trigger sidecars were empty during capture (integration
relies on whole-revolution alignment at nominal 960 rev/s), and the analysis
used the legacy folded-polarity/`log1p` variant at 10.4 ms accumulation. The
signed estimator, trigger-aligned integration, and the planned frequency
ladder (97 / 211 / 503 Hz, incommensurate with 60 Hz, plus one commensurate
control and a chopper-off baseline) are the immediate next steps — and the
reprocessed captures will be the first true test of laser-line discrimination
through the coded element. The predicted scaling to verify: **t_min ∝ 1/f**,
equivalently results collapsing onto a single curve in *events per window*.

### 2.5 What practice has *not* yet demonstrated

- Laser-line discrimination through the coded diffractive element under the
  corrected illumination — chopper captures are in hand; the analysis awaits the
  signed rework.
- A recovered **spectrum** (the deliverable so far is a pairwise correlation
  fingerprint, not an estimated spectral cube or RGB value; the 80 % result was
  reached on display colors, not laser lines).
- Discrimination under **controlled fast modulation** with a clean analysis (the
  chopper rework above).
- A phase mask **optimized for wavelength coding**: the in-beam element follows the
  Coded Events design (event-based PSF engineering, tracking-oriented); re-deriving
  the mask objective for spectral information under the corrected framework is
  future work.

---

## 3. Track B — In theory (the information bound)

### 3.1 What the derivation establishes

`proposed_CRLB_Derivation.pdf` builds the estimation-theoretic target
framework from first principles:

- **Model.** Pixels are independent asynchronous detectors; an event fires
  when local log-intensity change crosses contrast threshold C (Eq. 14).
  Event rate is modeled as Poisson with rate
  Λ(u,v,t) = C·|∂ ln I(u,v,t)/∂t| + Λ₀ (Eq. 22).
- **Result.** A per-pixel Fisher information via the chain rule
  (I(q_i) = Δt/Λ · (∂Λ/∂q_i)², Eqs. 23–25), additive over the array
  (Eq. 26), and a **joint 9-parameter FIM** over dynamic source parameters
  θ_s = {v_u, v_v, ΔI, Δλ, ΔI} and static optical parameters
  θ_h = {φ, u₀, v₀, I₀} (Eqs. 27–28), whose off-diagonal I_{Δλ,φ} terms are
  exactly the spectral-encoding coupling a phase mask must maximize.
- **Scaling claim.** Because signal generation is contrast-normalized
  (Eq. 29) while background Λ₀(N) grows with photon count, the event-sensor
  CRLB grows linearly with total photon count N — the opposite of frame
  cameras (CRLB ∝ 1/N) — implying an optimal low-light operating regime for
  event sensors (Fig. S2).
- **Positioning vs CodedEvents.** Shah et al.'s Gaussian pseudo-frame
  approximation is valid only for sufficiently long integration, which
  creates an "adverse incentive" since information allegedly degrades with
  accumulation time in EBS; time is implicit there and velocity is absent.
  The 4D derivation extends the bound to space, time, and spectra.

### 3.2 What the response corrects

`Proposed_CRLB_response.pdf` is a rigorous audit that keeps the goal but
rebuilds the foundations. Its verdict, item by item (Section 8 audit table):

| Original claim | Correction |
|---|---|
| Poisson event likelihood from photon arrivals (Eqs. 17–22) | Poisson count algebra is right, but photon arrivals do **not** make events Poisson; a noiseless log ramp fires periodic events. Event frequency scales ~1/C. |
| FIM products from |∂Λ/∂θ| (Eqs. 23–26) | Must carry the **sign** derivative and any intensity dependence of noise/sensitivity; full-stream information lives in **timestamps and polarity**, not binned counts. |
| The 9×9 symbolic system matrix (Eqs. 15, 27–28) | Not a derived hyperspectral system matrix: a spectrum needs multiple spectral coefficients with an **incoherent sum before the log**; a near-sensor DOE is generally space-variant, not a shift-invariant PSF. |
| Condition number 3.9 × 10¹⁹ (Fig. S1) | Requires rescaling and rank analysis before inversion; FIM and inverse-FIM correlations differ. **Test identifiability** — check the rank of the event Jacobian, not merely PSF dissimilarity. |
| EBS CRLB grows ∝ N; low-light optimum (Eqs. 29–30, Fig. S2) | Brightness cancellation is **conditional, not a noise law**; no universal CRLB-vs-N or low-light optimum follows without separating source intensity, additive background, threshold noise, and bandwidth. |
| "Information degrades with accumulation time" (vs Shah et al.) | Longer observation with **retained events cannot reduce** information about fixed parameters; binning is what discards timing information. CodedEvents is a two-time-position model, not simply a Gaussian intensity-difference model. |
| CRLB from quantized Shannon units (intro) | Bits/nats only set the log base; Fisher information is local KL curvature, not quantized information. |

### 3.3 The corrected framework (what the response puts in its place)

The response is constructive, not just critical. It supplies the machinery
the demonstration must use:

1. **Correct likelihood for timestamped, signed events:** a marked point
   process on (u, polarity, t) with conditional event rate and a log-likelihood
   including the survival integral — "no events" carries information too
   (Eqs. 5–7). The naive independent-Poisson approximation is retained but
   explicitly labeled as a design-exploration tool with known failure modes
   (sub-threshold oscillations, refractory dynamics).
2. **The spectral sensitivity to optimize:** a quotient-rule derivative of the
   normalized temporal response — the spectral analogue of the localization
   derivative — measuring how the *temporal* event response changes with each
   spectral coefficient, not simply differences between monochromatic PSFs
   (Eq. 4). Verified against central differences to 1.8 × 10⁻¹⁰ relative
   error in a three-band test.
3. **Identifiability and gauge:** with zero reference and brightness-free
   event noise, global brightness is unobservable even under dither — fix a
   scale gauge, estimate the normalized spectral shape, or add an intensity
   anchor. With nuisance parameters, use the effective information
   J_eff = J_ss − J_sa J_aa⁻¹ J_as (Eq. 12); more events cannot remove the
   kernel of the operator under fixed motion and gating.
4. **A concrete acquisition scheme that restores spectral sensitivity:**
   *reference gating* — gate the scene against a calibrated, nonzero additive
   reference held outside the gate (Eq. 9) — or scene/pattern dither.
   Never put a zero baseline inside the logarithm.
5. **The design objective and the practical test:** optimize surface + gating
   + temporal probe to minimize the trace of J_eff⁻¹ over design scenes
   (Eq. 13); calibrate narrowband spatial responses and event dynamics first,
   then test held-out spectral mixtures against a spectrometer. The decisive
   experiment is comparing reference gating vs dither to show **whether the
   designed spatial code survives event conversion**.

---

## 4. Where the two tracks meet — and where they don't (yet)

| Requirement for the demonstration | Theory says | Practice has | Gap |
|---|---|---|---|
| Spectral encoding mechanism | Chromatic dispersion of a phase mask multiplexes spectra into spatial patterns; quantify via I_{Δλ,φ} coupling | Coded Events-derived DOE **in the beam path** of the corrected superk setup | **Demonstration + optimization** — element is real; wavelength-coding performance through event conversion unproven; mask not yet optimized for spectral information |
| Forward model | Calibrated diffractive operator (space-variant allowed), incoherent intensity sum *before* log; validate against data | Empirical activity frames; no calibrated optical operator fitted | **Calibration** |
| Event likelihood | Marked point process on timestamps + polarity; survival integral; labeled Poisson approximation for design only | Binned 10 ms activity frames, ON−OFF signed estimator (empirically validated) | **Estimator upgrade**: binned frames discard the timestamp information the theory says is essential |
| Identifiability | Rank of event Jacobian; nuisance-marginalized J_eff; scale gauge | Split-half noise ceiling (within-recording reliability) is the practice analogue — and it was corrupted by the 60 Hz artifact on the display detour | **Analysis** — Jacobian-rank/observability checks not yet run on any real data |
| Temporal probe | Known motion, modulation, or finite-dimensional dynamics model required (static scene + static optics ⇒ no events) | 60 Hz LCD blocker resolved by the corrected superk + chopper setup; captures exist, first analysis saturated (~0.97) | **Hardware + pipeline** — signed rework, trigger alignment, frequency ladder pending |
| Illumination geometry | Divergent/diffuse source so the coded PSF is imaged, not a focused point | Collimated beam → translucent screen implemented after the mis-focused first attempt | **Verified by the chopper rework** |
| Bound to beat | tr(J_eff⁻¹) minimized over design (Eq. 13) | Empirical targets (80 % cross-color separation — reached on the display target at T ≥ 0.5–1 s) | **None structural** — but numerical CRLB claims require the calibrated operator + likelihood first |
| Ultimate deliverable | Spectrum / spectral image cube | Pairwise correlation fingerprint only | **Decoding** — no spectral reconstruction demonstrated yet |

The honest one-paragraph version: **practice has demonstrated a working
color-fingerprint estimator (80 % separation reached on the display reference
target, FPS-invariance settled) but not yet hyperspectral event sensing on laser
lines** — no spectrum is recovered, the Coded Events-derived diffractive element is
in the beam of the corrected superk setup but its wavelength coding through event
conversion is unproven, and the fast-modulation regime that the theory says is
mandatory (events require temporal change) is the current experimental frontier:
the chopper captures exist, with the first analysis pass saturated (~0.97) pending
the signed rework. **Theory has a correct
skeleton** (marked point-process likelihood, effective information with
nuisance marginalization, identifiability-first workflow) **but its first
quantitative artifact — the 4D CRLB derivation — has been audited and its
central quantitative claims (universal N-scaling, low-light optimum, the 9×9
system matrix as a hyperspectral bound) are downgraded pending re-derivation
on a calibrated forward operator.** The two tracks are aiming at the same
target from both sides; the response's Section 8 test plan and the
chopper/re-gating protocol are, in effect, the same experiment described in
two languages.

---

## 5. What remains to demonstrate (prioritized)

1. **Fix the chopper analysis** (practice): trigger-aligned, signed (ON−OFF)
   re-processing of the existing 475–675 nm chopper recordings; separate the
   chopping structure from the spectral pattern (e.g. phase-resolved or
   per-revolution analysis) so cross-color r is no longer saturated. This is the
   first genuine test of laser-line discrimination through the coded element under
   the corrected illumination. Then run
   the frequency ladder (97 / 211 / 503 Hz + commensurate control + chopper-off
   baseline) and test t_min ∝ 1/f / events-per-window collapse.
2. **Re-derive the bound on the corrected model** (theory): implement the
   response's Eqs. (5)–(9) likelihood and Eq. (4) spectral sensitivity on a
   calibrated diffractive operator; recompute J_eff with nuisance blocks and
   report identifiability (Jacobian rank, condition number after rescaling) —
   only then attach numbers to any CRLB claim.
3. **Close theory to practice with the gating experiment** (both): the single
   most decisive next experiment, named identically in both documents — gate
   the scene against a calibrated nonzero reference (or dither) with the coded
   element in the beam, and check whether the designed spatial code
   survives event conversion (theory's Section 8 test) while measuring the
   empirical noise ceiling against it (practice's split-half machinery).
4. **Decode, don't just correlate** (practice): move the deliverable from
   pairwise Pearson fingerprints to an estimated spectral value/cube, with the
   spectrometer ground truth the response prescribes for held-out mixtures.
5. **Optimize the encoder by information** (theory → hardware): the in-beam
   element follows the Coded Events design; re-derive the phase-profile objective
   for wavelength coding — tr(J_eff⁻¹) under fabrication and
   event-rate/bandwidth constraints (Eq. 13) — fabricate, and re-run 3–4 with the
   optimized mask in the loop.

---

## 6. Document and repository state (as of 2026-09-26)

- `weekly_report_2026-09-18.md` (+ `.tex`/`.pdf`) — committed; the empirical
  baseline for this summary.
- `proposed_CRLB_Derivation.pdf` and `Proposed_CRLB_response.pdf` — **new,
  currently untracked in git**; this summary recommends committing them
  alongside it (message suggestion: `docs(theory): add 4D FIM derivation and
  corrected response note`).
- Chopper capture + analysis scripts have uncommitted modifications
  (`spectral_correlation_chopper.py`, `spectral_correlation.py`); the chopper
  results directory exists only in the untracked data image, not in git.
- Decks (`reports/decks/*.pptx`) are generated artifacts of the committed
  results and remain regenerable via the documented commands.
