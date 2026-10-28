import Mathlib.Data.Real.Basic
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Data.Matrix.Basic
import Mathlib.LinearAlgebra.Basis.Defs
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
-- This is the file you just found:
import Mathlib.LinearAlgebra.StdBasis
import Mathlib.LinearAlgebra.Matrix.PosDef
import Mathlib.MeasureTheory.Measure.MeasureSpaceDef
import Mathlib.MeasureTheory.Integral.Bochner.Basic

open BigOperators
open Matrix
open Module 
open MeasureTheory

variable {ι : Type} [Fintype ι] [DecidableEq ι]

-- Parameter Space: ι → ℝ
abbrev Theta (ι : Type) := ι → ℝ

instance : NormedAddCommGroup (Theta ι) := Pi.normedAddCommGroup
noncomputable instance : NormedSpace ℝ (Theta ι) := Pi.normedSpace

instance : NormedAddCommGroup (Matrix ι ι ℝ) := Pi.normedAddCommGroup
noncomputable instance : NormedSpace ℝ (Matrix ι ι ℝ) := Pi.normedSpace

-- Sensor Variables
variable {Raw : Type}
variable (g : Theta ι → Raw → ℝ)
variable (sigma : Raw → ℝ)

/-- 
  General Fisher Information for any basis.
-/
noncomputable def fisher_info_basis
  (b : Basis ι ℝ (Theta ι)) 
  (θ : Theta ι) 
  (x : Raw) : Matrix ι ι ℝ :=
  let grad := fderiv ℝ (fun p => g p x) θ 
  let noise_var := g θ x + (sigma x)^2    
  Matrix.of (fun i j => 
    (grad (b i) * grad (b j)) / noise_var
  )

/-- 
  Standard Fisher Information using the canonical basis (Pi.basisFun).
-/
noncomputable def fisher_info (θ : Theta ι) (x : Raw) : Matrix ι ι ℝ :=
  fisher_info_basis g sigma (Pi.basisFun ℝ ι) θ x

/--
  The Total Fisher Information Matrix for an image (Equation 13).
-/
noncomputable def image_fim (θ : Theta ι) (FOV : Finset Raw) : Matrix ι ι ℝ :=
  ∑ x ∈  FOV, fisher_info g sigma θ x

/--
 Estimator estimates the parameters θ given a raw pixel Matrix
-/
noncomputable def Estimator (ι : Type) (Raw : Type) := (Raw -> ℝ) -> Theta ι 



def error_vector (θ_hat  : Theta ι) (θ : Theta ι ) : Theta ι := θ_hat - θ

def error_matrix (δ : Theta ι) : Matrix ι ι ℝ :=
  Matrix.of (fun i j => δ i * δ j)


/-- 
  An estimator is unbiased if its expected value over the 
  data distribution μ is equal to the true parameter θ.
-/
def is_unbiased 
  (estimator : (Raw → ℝ) → Theta ι) 
  (θ : Theta ι) 
  (μ : Measure (Raw → ℝ)) : Prop :=
  ∫ d, estimator d ∂μ = θ

/-- 
  The Covariance Matrix C is the expected value of the error matrix.
  C = E[(θ_hat - θ)(θ_hat - θ)ᵀ]
-/
noncomputable def covariance_matrix 
  (d : Estimator ι Raw) 
  (θ : Theta ι) 
  (μ : Measure (Raw → ℝ)) : Matrix ι ι ℝ :=
  ∫ m, error_matrix (error_vector (d m) θ) ∂μ

/-- 
  The Cramér-Rao Lower Bound Theorem:
  For an unbiased estimator d, the Covariance Matrix C is bounded by 
  the inverse of the Fisher Information Matrix F.
-/
theorem cramer_rao_inequality 
  (θ : Theta ι) 
  (F : Matrix ι ι ℝ) 
  (d : Estimator ι Raw)
  (μ : Measure (Raw → ℝ))
  (h_unbiased : is_unbiased d θ μ) 
  (h_invertible : Invertible F) :
  let C := covariance_matrix d θ μ
  PosSemidef (C - F⁻¹) := by
  sorry


