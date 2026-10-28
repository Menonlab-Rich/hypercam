import Maths.CramerRao
import Mathlib.Topology.Instances.Real.Lemmas
import Mathlib.Analysis.Asymptotics.Defs
import Mathlib.Analysis.Asymptotics.Theta
import Mathlib.Topology.Defs.Filter
import Mathlib.Order.Filter.AtTopBot.Defs
import Mathlib.Analysis.SpecialFunctions.Sqrt
import Mathlib.Topology.UniformSpace.Basic

open Matrix
open MeasureTheory
open BigOperators
open Filter
open Topology
open Uniform
open Asymptotics

variable {ι : Type} [Fintype ι] [DecidableEq ι]
variable {Raw : Type}

variable (T_thresh : ℝ) -- The log-comparator threshold 𝒯

/--
  Event Sensor Forward Model approximation (Log-Intensity).
  μ : Expected intensity at t - τ (previous frame)
  ν : Expected intensity at t (current frame)
-/
noncomputable def event_mean (μ ν T_thresh : ℝ) : ℝ := 
  (Real.log ν - Real.log μ) / T_thresh

/--
  Partial derivatives of the Normal approximation moments 
  with respect to the intensities μ and ν.
-/
noncomputable def d_mean_dμ (μ ν T_thresh : ℝ) : ℝ := 
  -1 / (T_thresh * μ)
  
noncomputable def d_mean_dν (μ ν T_thresh : ℝ) : ℝ := 
  1 / (T_thresh * ν)

noncomputable def d_var_dμ (μ ν T_thresh : ℝ) : ℝ := 
  -1 / (T_thresh^2 * μ^2)
  
noncomputable def d_var_dν (μ ν T_thresh : ℝ) : ℝ := 
  -1 / (T_thresh^2 * ν^2)

variable (C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T : ℝ)

/--
  The gradient of the mean log-intensity w.r.t the spatial parameter.
  Notice that time (T) has algebraically canceled out of this term.
-/
noncomputable def M_grad (C_mu C_nu grad_Cmu grad_Cnu T_thresh : ℝ) : ℝ :=
  (grad_Cnu / (T_thresh * C_nu)) - (grad_Cmu / (T_thresh * C_mu))

/--
  The gradient of the variance component. 
  Time (T) will be factored out when constructing the final FIM.
-/
noncomputable def D_grad (C_mu C_nu grad_Cmu grad_Cnu T_thresh : ℝ) : ℝ :=
  (-grad_Cmu / (T_thresh^2 * C_mu^2)) + (-grad_Cnu / (T_thresh^2 * C_nu^2))

/--
  Total variance for the binned interval.
  Combines the inverse-time Poisson scaling with the constant quantization noise 
  floor introduced by the discrete thresholding mechanism.
-/
noncomputable def event_var (C_mu C_nu T_thresh sigma_q T : ℝ) : ℝ :=
  (1 / (T_thresh^2 * T)) * ((1 / C_nu) + (1 / C_mu)) + sigma_q

/--
  The total scalar Fisher Information for the Event Camera.
  Constructed from the Normal approximation: I = (∇E)²/V + (∇V)²/(2V²)
-/
noncomputable def event_fim_scalar (C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T : ℝ) : ℝ :=
  let M := M_grad C_mu C_nu grad_Cmu grad_Cnu T_thresh
  let V := event_var C_mu C_nu T_thresh sigma_q T
  let D := D_grad C_mu C_nu grad_Cmu grad_Cnu T_thresh
  (M^2 / V) + ((D / T)^2 / (2 * V^2))

noncomputable def event_error_scalar (C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T : ℝ) : ℝ :=
  1 / Real.sqrt (event_fim_scalar C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T)

/--
  Regime 1: The Quantization Plateau (Long Integration Time).
  Because the mean log-signal is constant w.r.t T, as T → ∞ the Poisson 
  variance vanishes, leaving only the quantization error sigma_q.
  The CRLB standard error plateaus to a constant value.

**Justification:** As T → ∞, the Poisson variance component vanishes, leaving only 
  the constant quantization noise floor σ_q. This forces the Fisher Information 
  to a non-zero constant, resulting in an accuracy plateau where error no longer 
  decreases with time.
-/
lemma event_std_error_quantization_limit (h_sigma : sigma_q > 0) :
  IsTheta atTop 
    (fun T => event_error_scalar C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T) 
    (fun _ => 1 : ℝ → ℝ) := by
  sorry

/--
  Regime 2: Ideal Poisson Scaling (Zero Quantization Noise).
  If we assume an idealized sensor with no discrete threshold quantization (sigma_q = 0), 
  the error recovers the classic inverse-square-root scaling with time.

**Justification:** When quantization noise is absent (σ_q = 0), the total variance 
  scales strictly with 1/T. Substituting this into the FIM formula recovers the 
  classic 1/√T scaling for standard error, demonstrating that event cameras 
  obey traditional photon-statistics limits in the absence of quantization 
  error.
-/
lemma event_std_error_ideal_poisson_limit (h_sigma : sigma_q = 0) :
  IsTheta atTop 
    (fun T => event_error_scalar C_mu C_nu grad_Cmu grad_Cnu T_thresh sigma_q T) 
    (fun T => 1 / Real.sqrt T) := by
  sorry

variable (Phi_mu Phi_nu beta sigma2 T_thresh s_m grad_sm : ℝ)

/-- 
  The Fisher Information scalar for a standard CMOS sensor.
  Derived from F = (∇g)² / (g + σ²) where g = Phi * T * s_m + beta * T.
-/
noncomputable def cmos_fim_scalar (Phi beta sigma2 s_m grad_sm T : ℝ) : ℝ :=
  let signal_grad := Phi * T * grad_sm
  let variance := Phi * T * s_m + beta * T + sigma2
  signal_grad^2 / variance

/--
  The critical integration time where CMOS enters the Read-Noise Limited regime.
  Calculated as the point where read noise equals accumulated photon variance.
-/
noncomputable def T_critical (Phi beta sigma2 s_m : ℝ) : ℝ :=
  sigma2 / (Phi * s_m + beta)

/--
  Comparison Lemma: High-Speed Advantage.
  For integration times shorter than T_critical, the Event sensor 
  provides strictly more information than the CMOS sensor.

**Justification:** At microsecond scales (T < T_critical), standard CMOS sensors 
  are dominated by fixed read noise σ², leading to O(T²) Fisher Information 
  scaling. Event sensors bypass this floor by triggering on log-contrast, 
  maintaining O(T) scaling and higher information density at high 
  speeds.
-/
lemma event_vs_cmos_high_speed (hT : T < T_critical Phi_mu beta sigma2 s_m) :
  event_fim_scalar Phi_mu Phi_nu beta T_thresh 0 T grad_sm > 
  cmos_fim_scalar Phi_mu beta sigma2 s_m grad_sm T := by
  sorry
