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

/-- 
  The exact parameter set defined in Gerwe & Idell (2003), Section 3.
  α:  Orientation angle
  xc: Translation in x
  yc: Translation in y
  zc: Translation in z (Extension of the paper's original model)
  N:  Total expected signal photoelectrons
  b:  Expected background photoelectrons per pixel
-/
inductive GIParam
  | α | xc | yc | zc | N | b
  deriving Fintype, DecidableEq

abbrev GITheta := Theta GIParam

variable {Pixel : Type}

-- s_m is the normalized signal at the pixel, dependent on orientation and translation.
variable (s : ℝ -> ℝ -> ℝ -> ℝ → Pixel -> ℝ) 

/-- 
  Extended Forward Model: 
  Mean photoelectron count at a given pixel m.
-/
noncomputable def gi_forward_model (θ : GITheta) (m : Pixel) : ℝ :=
  let α  := θ GIParam.α
  let xc := θ GIParam.xc
  let yc := θ GIParam.yc
  let z  := θ GIParam.zc
  let N  := θ GIParam.N
  let b  := θ GIParam.b
  
  -- g_m(θ) = N * s_m(α, x_c, y_c, z) + b
  N * s α xc yc z m + b

/--
  The total Fisher Information Matrix for the extended parameter set.
-/
noncomputable def gi_fisher_info 
  (θ : GITheta) 
  (FOV : Finset Pixel) 
  (sigma_r : Pixel → ℝ) : Matrix GIParam GIParam ℝ :=
  image_fim (gi_forward_model s) sigma_r θ FOV

variable (N b sigma2 s_m Phi beta : ℝ)

noncomputable def std_error_scalar (Phi beta sigma2 s_m T : ℝ) : ℝ :=
  Real.sqrt ((Phi * T * s_m + beta * T + sigma2) / (Phi^2 * T^2 * s_m^2))

/--
  Regime 1: Photon-Noise Limited (Long Integration Time).

**Justification:** For long integration times (T → ∞), the accumulated signal and 
  background photons dominate the constant electronic read noise floor (σ²). In 
  this regime, the total noise variance scales linearly with T, causing the 
  Fisher Information to scale linearly with T and the resulting standard error 
  to scale as 1/√T.
-/
lemma std_error_photon_limit (h_Phi : Phi > 0) (h_sm : s_m > 0) (h_beta : beta ≥ 0) :
  IsTheta atTop (fun T => std_error_scalar Phi beta sigma2 s_m T) (fun T => 1 / Real.sqrt T) := by
  -- Target constant for g(T)/f(T)
  let C := Real.sqrt ((Phi^2 * s_m^2) / (Phi * s_m + beta))
  
  apply Asymptotics.isTheta_of_div_tendsto_nhds_ne_zero (c := C)
  · -- Evaluate the limit of the ratio at infinity
    -- (1 / sqrt(T)) / std_error_scalar(T) = sqrt((Phi^2 * s_m^2) / (Phi * s_m + beta + sigma2 / T))
    have h_ratio : ∀ᶠ T in atTop, 
      (1 / Real.sqrt T) / (std_error_scalar Phi beta sigma2 s_m T) = 
      Real.sqrt ((Phi^2 * s_m^2) / (Phi * s_m + beta + sigma2 / T)) := by
      filter_upwards [eventually_gt_atTop 0] with T hT
      sorry 

    apply (tendsto_congr' h_ratio).mpr
    
    have h_inside_limit : Tendsto (fun T => (Phi^2 * s_m^2) / (Phi * s_m + beta + sigma2 / T)) 
      atTop (𝓝 ((Phi^2 * s_m^2) / (Phi * s_m + beta + 0))) := by
      sorry 

    rw [add_zero] at h_inside_limit
    exact Continuous.tendsto Real.continuous_sqrt _ |>.comp h_inside_limit
  · -- Prove C ≠ 0
    intro h_zero
    rw [Real.sqrt_eq_zero] at h_zero
    · have h_num_pos : Phi^2 * s_m^2 > 0 := by positivity
      have h_den_pos : Phi * s_m + beta > 0 := by positivity
      have h_div_pos : (Phi^2 * s_m^2) / (Phi * s_m + beta) > 0 := div_pos h_num_pos h_den_pos
      linarith
    · positivity

/--
  Regime 2: Read-Noise Limited (Short Integration Time).

**Justification:** For very short integration times (T → 0), the constant 
  electronic read noise σ² dominates the vanishing photon-dependent noise. 
  Since the mean signal scales linearly with T while the noise remains constant, 
  the Fisher Information scales quadratically (T²), causing the standard error 
  to scale as 1/T.
-/
lemma std_error_read_noise_limit (h_Phi : Phi > 0) (h_sm : s_m > 0) (h_sigma : sigma2 > 0) :
  IsTheta (𝓝[>] 0) (fun T => std_error_scalar Phi beta sigma2 s_m T) (fun T => 1 / T) := by
  -- Target constant for g(T)/f(T)
  let C := Real.sqrt ((Phi^2 * s_m^2) / sigma2)
  
  apply Asymptotics.isTheta_of_div_tendsto_nhds_ne_zero (c := C)
  · -- Evaluate the limit of the ratio at 0
    -- (1 / T) / std_error_scalar(T) = sqrt((Phi^2 * s_m^2) / (Phi * T * s_m + beta * T + sigma2))
    have h_ratio : ∀ᶠ T in 𝓝[>] 0, 
      (1 / T) / (std_error_scalar Phi beta sigma2 s_m T) = 
      Real.sqrt ((Phi^2 * s_m^2) / (Phi * T * s_m + beta * T + sigma2)) := by
      filter_upwards [self_mem_nhdsWithin] with T hT
      sorry

    apply (tendsto_congr' h_ratio).mpr
    
    have h_inside_limit : Tendsto (fun T => (Phi^2 * s_m^2) / (Phi * T * s_m + beta * T + sigma2)) 
      (𝓝[>] 0) (𝓝 ((Phi^2 * s_m^2) / (0 + 0 + sigma2))) := by
      sorry 

    rw [zero_add, zero_add] at h_inside_limit
    exact Continuous.tendsto Real.continuous_sqrt _ |>.comp h_inside_limit
  · -- Prove C ≠ 0
    intro h_zero
    rw [Real.sqrt_eq_zero] at h_zero
    · have h_num_pos : Phi^2 * s_m^2 > 0 := by positivity
      have h_div_pos : (Phi^2 * s_m^2) / sigma2 > 0 := div_pos h_num_pos h_sigma
      linarith
    · positivity
