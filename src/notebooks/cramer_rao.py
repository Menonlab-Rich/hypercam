import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")

with app.setup:
    import json
    import logging
    import os

    import marimo as mo
    import numpy as np
    import pandas as pd
    import sympy as sp
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torchoptics
    from matplotlib import pyplot as plt
    from scipy.interpolate import PchipInterpolator
    from scipy.special import j1
    from torch.utils.checkpoint import checkpoint
    from torchoptics import Field, System
    from torchoptics.elements import Lens, PhaseModulator
    from torchoptics.profiles import circle, zernike
    from tqdm import tqdm

    from nan_detector import NaNDetector

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_default_dtype(torch.float64)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    The ideal image $I_t$ is given where $(u, v)$ represent the sensor plane and $u_0, v_0$ represent specific points on that plane:
    $$ I_t = \delta\left(u - \frac{f}{z}x(t), v - \frac{f}{z}y(t)\right) = \delta\left(u-u_0, v - v_0\right)  $$
    To account for blur, the real image $I^b_t$ is given as the convolution of the PSF $h_z(t)$ and the ideal image $I_t$, with the subscrip $z$ implying that $h$ is depth variant.
    $$I_t^b(u,v) = [h_z(t) * I_t](u, v)$$
    The mapping of location $(x, y)$ to $(u, v)$ is given where z is the ideal focal plane, $\Delta{z}$ is the distance from that plane of the object, and $f$ is the focal distance of the objective.
    $$u = f \frac{x(t)}{z + \Delta z(t)}, \quad v = f \frac{y(t)}{z + \Delta z(t)}$$
    Because $f$ and $z$ are constant we can prescale $(x, y)$ using a scaling factor $S$:
    $$\text{scaling factor} = \frac{f}{z} = S$$
    $$ (u, v) \approx S \cdot (x(t), y(t)) $$

    The authors make a simplified leap here and state that when you consider accumulated events over a sufficiently long interval, the result is approximately a log difference of the intensity at time t and t - $\tau$.

    $$O_{t} = \log(I_{t}^{b}) - \log(I_{t-\tau}^{b})$$
    The fisher information is given by
    $$\mathcal{I}(\theta)_{i,j} = \mathbb{E} \left[ \left( \frac{\partial}{\partial \theta_i} \log f(X; \theta) \right) \left( \frac{\partial}{\partial \theta_j} \log f(X; \theta) \right) \Bigg| \theta \right]$$

    Breaking this down, the components are as follows:

    * **Expected Image:** $X$ - the expected image sampled from a probability density function (PDF) generated with $\lambda$ = $I^b_t$
    * **Score:** $\frac{\partial}{\partial \theta} \log f(X; \theta)$ - How much the expected image $X$ changes with respect to $\theta$.
    * **Parameter set:** $\theta$ - The parameters that form the image. For a single blinking point $\theta$ = $\{x_t, y_t, z_t\}$. For a moving object $\theta$ = $\{x_t, y_t, z_t, x_{t-\tau}, y_{t-\tau}, z_{t-\tau} \}$
    * **PDF:** $f$ is the probability density function (PDF) used to generate $X$. (Normal in the case of the paper)

    In Summary:
    The Fisher Information is the Expected Value of the covariance of the Score Function.
    Specifically:
    * The Score Function: This is the term $\frac{\partial}{\partial \theta_i} \log f(X; \theta)$. It represents the sensitivity of the log-likelihood to a tiny change in a specific parameter (like $z$).
    * The Product: The term $(\dots)_i (\dots)_j$ is the product of these sensitivities.
    * The Averaging: The $\mathbb{E}[\dots | \theta]$ operator calculates the average of that product across all possible noisy realizations $X$ that could be drawn from the sensor.
      ---
      Summary Table
      ---

    | Component       | Physical Meaning                                | Role in Optimization                      |
    |-----------------|-------------------------------------------------|-------------------------------------------|
    | Object θ        | The ground-truth 3D position(s).                | The unknown variable we want to recover.  |
    | Ideal $I_t$     | A "perfect" pin-hole projection (Dirac Delta).  | The input to the optical model.           |
    | PSF $h_z$       | The depth-dependent blur pattern.               | The design variable (engineered mask).    |
    | Image $I_t^b$   | The "clean" blurred frame on the sensor.        | The mean (λ) of the distribution.         |
    | Measurement $X$ | The noisy, binned event frame Ot​.               | The actual data the CNN receives.         |
    | PDF $f$         | The generative noise model (Normal).            | The tool used to calculate information.   |
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    **Given sufficiently large $\lambda$**: $X \sim \text{Poisson}(\lambda) \approx \mathcal{N}(\lambda, \lambda)$

    The probability density function (PDF) and exact moments for the ratio of two Poisson variables, $\frac{X}{Y}$, do not have a closed-form expression and cannot be solved algebraically. To account for this, the authors use the first-order Taylor polynomial expansion of the moments of a ratio (the Delta method), which states:

    $$\mathbb{E}\left[\frac{X}{Y}\right] \approx \frac{\mu_X}{\mu_Y},$$
    $$\text{Var}\left(\frac{X}{Y}\right) \approx \frac{\text{Var}(X)}{\mu_Y^2} + \frac{\mu_X^2 \text{Var}(Y)}{\mu_Y^4} - \frac{2\mu_X}{\mu_Y^3}\text{Cov}(X,Y)$$

    In this paper, $X = I^b_t$ and $Y = I^b_{t-\tau}$. Because these two values are independent, their covariance (the measure of the impact of one variable on another) is 0.

    It is a fundamental property of the Poisson distribution that $\text{Var}(X) = \mathbb{E}[X] = \lambda$. Substituting these known values into the expression above yields:

    $$\mathbb{E}\left[\frac{I_t^b}{I_{t-\tau}^b}\right] \approx \frac{\lambda_t}{\lambda_{t-\tau}},$$
    $$\text{Var}\left(\frac{I_t^b}{I_{t-\tau}^b}\right) \approx \frac{\lambda_t}{(\lambda_{t-\tau})^2} + \frac{(\lambda_t)^2 \cdot \lambda_{t-\tau}}{(\lambda_{t-\tau})^4} - 0$$

    Which after simplification becomes:
    $$\mu = \frac{\lambda_t}{\lambda_{t-\tau}}$$
    $$\sigma^2 = \frac{\lambda_t}{\lambda_{t-\tau}^2} + \frac{\lambda_t^2}{\lambda_{t-\tau}^3}$$

    Therefore, the Normal approximation of the measurement is:
    $$\frac{I^b_t}{I^b_{t-\tau}} \sim \mathcal{N}\left(\frac{\lambda_t}{\lambda_{t - \tau}}, \frac{\lambda_t}{\lambda_{t-\tau}^2} + \frac{\lambda_t^2}{\lambda_{t-\tau}^3}\right)$$

    The formula for the PDF of a normal distribution $f(X;\mu,\sigma^2)$ is given:

    $$f(X; \mu, \sigma^2) = \frac{1}{\sqrt{2\pi\sigma^2}} \exp\left( -\frac{(X - \mu)^2}{2\sigma^2} \right)$$

    To calculate the Fisher Information (FI) you need to get the log likelihood, the log value of this PDF. This becomes:

    $$\ln(f) = -\ln(\sqrt{2\pi\sigma^2}) - \frac{(X - \mu)^2}{2\sigma^2}$$
    """)
    return


@app.cell
def _():
    # 1. Define the 6 position parameters (theta)
    x_t, y_t, z_t = sp.symbols('x_t y_t z_t')
    x_tau, y_tau, z_tau = sp.symbols('x_tau y_tau z_tau')
    theta = [x_t, y_t, z_t, x_tau, y_tau, z_tau]

    # 2. Define intensities and noise
    # mu (prev) and nu (curr) are treated as intermediate functions of theta
    mu, nu = sp.symbols('mu nu') 
    beta = sp.symbols('beta')
    X = sp.symbols('X') # The measurement ratio

    # 1. Define the mean and variance using derived results
    mean_X = nu / mu
    var_X = (nu / mu**2) + (nu**2 / mu**3)

    # 2. Compute the partial derivatives of the mean and variance w.r.t mu and nu
    dm_dmu = sp.diff(mean_X, mu)
    dm_dnu = sp.diff(mean_X, nu)

    dv_dmu = sp.diff(var_X, mu)
    dv_dnu = sp.diff(var_X, nu)

    # 3. Derive a, b, c algebraically using the Gaussian Fisher Information identity
    # a = I(mu, mu)
    a_raw = (1 / var_X) * (dm_dmu * dm_dmu) + (1 / (2 * var_X**2)) * (dv_dmu * dv_dmu)

    # b = I(mu, nu)
    b_raw = (1 / var_X) * (dm_dmu * dm_dnu) + (1 / (2 * var_X**2)) * (dv_dmu * dv_dnu)

    # c = I(nu, nu)
    c_raw = (1 / var_X) * (dm_dnu * dm_dnu) + (1 / (2 * var_X**2)) * (dv_dnu * dv_dnu)

    den = sp.UnevaluatedExpr(2 * mu**2 * (mu + nu)**2)

    # 4. Simplify to extract the polynomials
    a = sp.factor(sp.simplify(a_raw))
    b = sp.factor(sp.simplify(b_raw))
    c = sp.factor(sp.simplify(c_raw))

    # 3. Create symbols for the spatial derivatives (mu_i, nu_i) 
    # for each of the 6 parameters in theta
    mu_grad = sp.symbols('mu_x_t mu_y_t mu_z_t mu_x_tau mu_y_tau mu_z_tau')
    nu_grad = sp.symbols('nu_x_t nu_y_t nu_z_t nu_x_tau nu_y_tau nu_z_tau')

    # 4. Construct the 6x6 Fisher Information Matrix for one pixel
    FIM_pixel = sp.Matrix(6, 6, lambda i, j: 
        a * mu_grad[i] * mu_grad[j] + 
        b * (mu_grad[i] * nu_grad[j] + nu_grad[i] * mu_grad[j]) + 
        c * nu_grad[i] * nu_grad[j]
    )
    return FIM_pixel, a, b, c


@app.cell
def _(a, b, c):
    (a, b, c)
    return


@app.cell
def _(FIM_pixel):
    FIM_pixel
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Radiometric and Photometric Equations for Optical Sensors

    This document compiles the foundational radiometric models and photometric distributions required for evaluating event-based sensors under non-uniform illumination. Relevant equations, derivations, and a practical application example are provided.

    ## 1. Lambertian Surface Reflection and Luminance

    A perfectly diffuse surface reflects light such that its luminance remains constant regardless of the observer's viewing angle.

    **Lambert's Cosine Law**
    $$I_{diffuse} = I_0 \cos(\theta)$$
    Where $I_{diffuse}$ is the luminous intensity at a viewing angle $\theta$ from the surface normal, and $I_0$ is the peak intensity along the normal.

    **Hemispherical Integration of Luminance**
    To relate total incoming illuminance ($E_v$) to outgoing luminance ($L_v$), energy conservation requires integrating over the 3D hemisphere.
    $$M_v = \int_{\text{hemisphere}} L_v \cos(\theta) \, d\Omega$$
    $$d\Omega = \sin(\theta) \, d\theta \, d\phi$$

    Evaluating the integral:
    $$M_v = L_v \int_0^{2\pi} 1 d\phi \int_0^{\pi/2} \cos(\theta) \sin(\theta) \, d\theta$$
    $$M_v = L_v (2\pi) \left(\frac{1}{2}\right) = L_v \pi$$

    Since Luminous Exitance ($M_v$) equals reflected Illuminance multiplied by reflectance ($M_v = \rho E_v$):
    $$L_v = \frac{\rho E_v}{\pi}$$

    ## 2. CIE Standard Overcast Sky Distribution

    Unlike a Lambertian surface, an overcast sky exhibits non-uniform luminance. The Moon and Spencer (1942) model dictates that the zenith is three times brighter than the horizon.

    **Sky Luminance Distribution**
    $$L(\gamma) = L_z \frac{1 + 2 \sin(\gamma)}{3}$$
    Where $L(\gamma)$ is the luminance at an elevation angle $\gamma$ above the horizon, and $L_z$ is the peak luminance at the zenith.

    **Horizontal Illuminance Relationship**
    By integrating the spatial distribution across the sky vault, the horizontal illuminance $E_v$ on the ground is mapped directly to the zenith luminance.
    $$E_v = L_z \frac{7\pi}{9}$$

    ## 3. Sensor Received Photon Rate

    The fundamental expression for radiometric flux evaluates the total photon rate entering a receiving aperture from a distant extended source.

    **Solid Angle**
    $$\Omega = \frac{A_{lens}}{z^2}$$

    **Received Flux Equation**
    $$R(z) = L_p \cdot A_{obj} \cdot \Omega = \frac{L_p \cdot A_{obj} \cdot A_{lens}}{z^2}$$
    Where $R(z)$ is the total photon rate, $L_p$ is the photon radiance of the target, $A_{obj}$ is the cross-sectional area of the target, $A_{lens}$ is the aperture area, and $z$ is the tracking distance.

    ## 4. Application Example: Ground-to-Cloud Base Tracking

    The following calculations model a ground-based dynamic vision sensor tracking an object against an overcast cloud base at a 45-degree elevation.

    **Assumptions:**
    * **Horizontal Illuminance ($E_v$):** 10,000 lux
    * **Target Reflectance ($\rho$):** 0.5 (Lambertian)
    * **Target Area ($A_{obj}$):** 0.1 m²
    * **Lens:** 35mm focal length, NA 0.0559 ($A_{lens} \approx 1.19 \times 10^{-5}$ m²)
    * **Wavelength ($\lambda$):** 560 nm (Efficacy = 683 lm/W, Photon Energy $\approx 3.55 \times 10^{-19}$ J)

    **Step-by-Step Calculation:**

    1.  **Zenith Luminance ($L_z$):** $$L_z = 10,000 \cdot \frac{9}{7\pi} \approx 4,092 \text{ cd/m}^2$$
    2.  **Cloud Base Luminance at 45° ($L_{45}$):**
        $$L_{45} = 4,092 \cdot \frac{1 + 2\sin(45^\circ)}{3} \approx 3,293 \text{ cd/m}^2$$
    3.  **Target Luminance ($L_v$):**
        $$L_v = \frac{0.5 \cdot 10,000}{\pi} \approx 1,591 \text{ cd/m}^2$$
    4.  **Target Photon Radiance ($L_p$):**
        $$L_e = \frac{1,591}{683} \approx 2.33 \text{ W/(m}^2\text{sr)}$$
        $$L_p = \frac{2.33}{3.55 \times 10^{-19}} \approx 6.56 \times 10^{18} \text{ photons/(s} \cdot \text{m}^2 \cdot \text{sr)}$$
    5.  **Received Rate at 1m ($R(1)$):**
        $$R(1) = 6.56 \times 10^{18} \cdot 0.1 \cdot \frac{1.19 \times 10^{-5}}{1^2} \approx 7.8 \times 10^{12} \text{ photons/s}$$
    6.  **Received Rate at 500m ($R(500)$):**
        $$R(500) = \frac{7.8 \times 10^{12}}{500^2} \approx 3.1 \times 10^7 \text{ photons/s}$$

    ## 5. References

    1. **Moon, P., & Spencer, D. E.**, *Illumination from a Non-Uniform Sky*, 1942.
       *Note:* Validates the non-uniform luminance distribution $L(\gamma) = L_z (1 + 2 \sin\gamma) / 3$ for overcast sky models.
    2. **ISO/CIE**, *ISO 15469:2004 / CIE S 011:2003 - Spatial Distribution of Daylight: CIE Standard General Sky*, 2004.
       *Note:* Validates the integration parameters for horizontal illuminance from zenith luminance via the $7\pi/9$ factor.
    3. **Mobley, C. D.**, *Lambertian BRDFs - Ocean Optics Web Book*, 2021.
       *Note:* Validates the derivation of the $\pi$ factor through the hemispherical solid-angle integration.
    4. **Saikia, S.**, *Deriving Lambertian BRDF from first principles*, 2019.
       *Note:* Validates the specific spherical coordinate trigonometric integration steps ($d\Omega = \sin\theta d\theta d\phi$) that result in the $\pi$ denominator.
    """)
    return


@app.cell
def _():
    from typing import Dict, Tuple

    import seaborn as sns
    from scipy.optimize import minimize
    class BairdTheoryValidation:
        """
        Accurate implementation of Baird's intensity-based quantization ceiling
        """
        def __init__(self, sensor_size=64, wavelength=500e-9, NA=0.3, 
                     pixel_size=2.0e-6, threshold_tau=0.1):

            self.sensor_size = sensor_size
            self.wavelength = wavelength  
            self.NA = NA
            self.pixel_size = pixel_size
            self.threshold_tau = threshold_tau  

            self.sigma0 = 1.22 * wavelength / (2 * NA) / pixel_size
            self.ZR = np.pi * (self.sigma0 * pixel_size)**2 / wavelength
            self.ZR_pixels = self.ZR / pixel_size

            self.sigma_q2 = (threshold_tau**2) / 12  

            print(f"🎯 BAIRD'S THEORY VALIDATION SETUP:")
            print(f"   Scenario: Pure intensity-based z-estimation")
            print(f"   σ₀ = {self.sigma0:.2f} pixels")  
            print(f"   ZR = {self.ZR_pixels:.1f} pixels")
            print(f"   τ = {threshold_tau:.3f} (log threshold)")
            print(f"   σ²q = {self.sigma_q2:.6f} (CONSTANT quantization variance)")

            coords = torch.linspace(-sensor_size//2, sensor_size//2-1, sensor_size)
            self.xx, self.yy = torch.meshgrid(coords, coords, indexing='ij')

        def intensity_psf(self, xc, yc, zc, N_photons):
            if abs(zc) < 1e-6:
                sigma_z = self.sigma0
            else:
                sigma_z = self.sigma0 * np.sqrt(1 + (zc / self.ZR_pixels)**2)

            r2 = (self.xx - xc)**2 + (self.yy - yc)**2
            psf = torch.exp(-r2 / (2 * sigma_z**2))
            psf = psf / psf.sum() * N_photons  

            return psf, sigma_z

        def compute_intensity_temporal_derivative(self, position, velocity, N_photons):
            xc, yc, zc = position
            vx, vy, vz = velocity  
            dz = 1e-4

            # Central finite differences for robust spatial derivatives
            I_prev, _ = self.intensity_psf(xc, yc, zc - dz, N_photons)
            I_curr, sigma_current = self.intensity_psf(xc, yc, zc, N_photons)
            I_next, _ = self.intensity_psf(xc, yc, zc + dz, N_photons)

            dI_dz = (I_next - I_prev) / (2 * dz)
            d2I_dz2 = (I_next - 2 * I_curr + I_prev) / (dz**2)

            # Macroscopic parameters per-pixel
            mu = I_curr
            nu = torch.abs(dI_dz * vz)

            # Spatial mapping derivatives per-pixel (Jacobian elements)
            dmu_dz = dI_dz
            dnu_dz = torch.sign(dI_dz * vz) * (d2I_dz2 * vz)

            return {
                'psf': I_curr,
                'sigma': sigma_current,
                'mu': mu,        # 2D Tensor
                'nu': nu,        # 2D Tensor
                'dmu_dz': dmu_dz, # 2D Tensor
                'dnu_dz': dnu_dz, # 2D Tensor
                'valid': torch.sum(mu) > 0
            }

        def baird_fisher_information(self, mu, nu, dmu_dz, dnu_dz):
                    mask = mu > 1e-9
                    mu_v = mu[mask]
                    nu_v = nu[mask]
                    dmu_v = dmu_dz[mask]
                    dnu_v = dnu_dz[mask]

                    if len(mu_v) == 0:
                        return {'fisher': 0, 'crlb': float('inf'), 'valid': False}

                    var_M = 2 / (mu_v) + self.sigma_q2
                    dM_dz = (mu_v * dnu_v - nu_v * dmu_v) / (mu_v**2)

                    fisher_per_pixel = (dM_dz**2) / var_M
                    fisher_z = torch.sum(fisher_per_pixel).item()
                    crlb_z = 1.0 / fisher_z if fisher_z > 0 else float('inf')

                    # Compare Informational Ceilings rather than raw variances
                    fisher_photon_only = torch.sum((dM_dz**2) / (nu_v / (mu_v**2))).item()
                    fisher_quant_only = torch.sum((dM_dz**2) / self.sigma_q2).item()

                    # If the quantization-only limit provides less information, it is the bottleneck
                    quantization_dominates = fisher_quant_only < fisher_photon_only

                    return {
                        'fisher': fisher_z,
                        'crlb': crlb_z,
                        'quantization_dominates': quantization_dominates,
                        'valid': True
                    }

        def cmos_photon_limited_crlb(self, mu, dmu_dz):
            """Evaluate baseline CMOS bound via direct FIM to ensure matched assumptions"""
            mask = mu > 1e-9
            if len(mu[mask]) == 0:
                return float('inf')

            fisher_per_pixel = (dmu_dz[mask]**2) / mu[mask]
            fisher_z = torch.sum(fisher_per_pixel).item()

            return 1.0 / fisher_z if fisher_z > 0 else float('inf')

        def run_baird_validation(self, integration_times):
                    photon_rate = 10000  # Increased to push deeper into the limit faster
                    position = [32.0, 32.0, 2.0]  
                    velocity = [0.0, 0.0, 1.0]    

                    results = {
                        'times': integration_times,
                        'photon_counts': [],
                        'cmos_crlb': [],
                        'event_crlb': [],
                        'quantization_dominated': [],
                        'mu_values': [],
                        'nu_values': []
                    }

                    print(f"\n🎯 BAIRD'S VALIDATION: Intensity-based z-estimation")
                    print(f"   Pure axial motion: vz = {velocity[2]} pixels/s")
                    print(f"   Defocus: z = {position[2]} pixels (for intensity sensitivity)")
                    print(f"   Expected: Event cameras hit quantization ceiling")
                    print(f"   Expected: CMOS maintains photon-limited scaling")

                    for i, T in enumerate(integration_times):
                        N_photons = photon_rate * T
                        results['photon_counts'].append(N_photons)

                        intensity_result = self.compute_intensity_temporal_derivative(
                            position, velocity, N_photons
                        )

                        if not intensity_result['valid']:
                            results['cmos_crlb'].append(float('inf'))
                            results['event_crlb'].append(float('inf'))
                            results['quantization_dominated'].append(False)
                            results['mu_values'].append(0)
                            results['nu_values'].append(0)
                            continue

                        mu_tensor = intensity_result['mu']
                        nu_tensor = intensity_result['nu']
                        dmu_dz = intensity_result['dmu_dz']
                        dnu_dz = intensity_result['dnu_dz']

                        results['mu_values'].append(torch.sum(mu_tensor).item())
                        results['nu_values'].append(torch.sum(nu_tensor).item())

                        cmos_crlb = self.cmos_photon_limited_crlb(mu_tensor, dmu_dz)
                        results['cmos_crlb'].append(cmos_crlb)

                        event_result = self.baird_fisher_information(mu_tensor, nu_tensor, dmu_dz, dnu_dz)

                        if event_result['valid']:
                            results['event_crlb'].append(event_result['crlb'])
                            results['quantization_dominated'].append(event_result['quantization_dominates'])

                            # Log more frequently at the start to monitor the transition
                            if i < 10 or i % 5 == 0:
                                ratio = event_result['crlb'] / cmos_crlb if cmos_crlb > 0 else float('inf')
                                status = "🔴" if event_result['quantization_dominates'] else "🟡"
                                print(f"  {status} T={T:.2e}s: N={N_photons:.0f}, ratio={ratio:.1f}")
                        else:
                            results['event_crlb'].append(float('inf'))
                            results['quantization_dominated'].append(False)

                    return results

    def plot_baird_validation(results):

        """Plot Baird's quantization ceiling validation"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        times = np.array(results['times'])
        photons = np.array(results['photon_counts'])
        cmos = np.array(results['cmos_crlb'])
        events = np.array(results['event_crlb'])
        quant_dom = np.array(results['quantization_dominated'])

        # Filter valid values
        valid_cmos = np.isfinite(cmos) & (cmos > 0)
        valid_events = np.isfinite(events) & (events > 0)

        # Main comparison: CRLB vs integration time
        if np.any(valid_cmos):
            ax1.loglog(times[valid_cmos], cmos[valid_cmos], 'b-', linewidth=3, 
                      label='CMOS (Photon-Limited)', alpha=0.9)

        if np.any(valid_events):        # Color-code by quantization dominance        
            quant_mask = valid_events & quant_dom
            photon_mask = valid_events & ~quant_dom    
            if np.any(quant_mask):
                ax1.loglog(times[quant_mask], events[quant_mask], 'r-', linewidth=3,
                          label='Event (Quantization Limited)', alpha=0.9)


            if np.any(photon_mask):
                ax1.loglog(times[photon_mask], events[photon_mask], 'orange', linewidth=3,
                          linestyle='--', label='Event (Photon Limited)', alpha=0.9)

        ax1.set_xlabel('Integration Time [s]')
        ax1.set_ylabel('CRLB [pixels²]')
        ax1.set_title("BAIRD'S THEORY: Intensity-Based Z-Estimation", fontweight='bold')

        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Performance ratio showing ceiling

        if np.any(valid_cmos & valid_events):
            common_mask = valid_cmos & valid_events
            ratio = events[common_mask] / cmos[common_mask]
            ax2.loglog(times[common_mask], ratio, 'purple', linewidth=3)
            ax2.axhline(y=1, color='black', linestyle='--', alpha=0.7)
            ax2.set_xlabel('Integration Time [s]')
            ax2.set_ylabel('Performance Ratio (Event/CMOS)')
            ax2.set_title('Quantization Ceiling Effect')
            ax2.grid(True, alpha=0.3)

        # μ vs ν parameter space

        mu_vals = np.array(results['mu_values'])

        nu_vals = np.array(results['nu_values'])

        valid_params = (mu_vals > 0) & (nu_vals > 0)

        if np.any(valid_params):

            scatter = ax3.scatter(mu_vals[valid_params], nu_vals[valid_params], 

                                 c=times[valid_params], cmap='viridis', s=50, alpha=0.7)

            ax3.set_xlabel('μ (Total Photons)')

            ax3.set_ylabel('ν (Temporal Derivative)')

            ax3.set_title('Baird Parameter Space')

            plt.colorbar(scatter, ax=ax3, label='Integration Time [s]')

        # Quantization dominance timeline

        if len(quant_dom) > 0:

            ax4.semilogx(times, quant_dom.astype(float), 'ro-', markersize=6)

            ax4.set_xlabel('Integration Time [s]')

            ax4.set_ylabel('Quantization Dominates')

            ax4.set_title('Quantization vs Photon Noise')

            ax4.grid(True, alpha=0.3)

            ax4.set_ylim(-0.1, 1.1)

        plt.tight_layout()

        return fig

    def main():
        print("🎯 BAIRD'S THEORY VALIDATION")
        print("="*60)
        print("Scenario: Pure intensity-based z-position estimation")
        print("Expected: Event cameras hit fundamental quantization ceiling")
        print("Expected: CMOS maintains photon-limited performance")
        print("="*60)

        baird_sim = BairdTheoryValidation(
            sensor_size=128,
            wavelength=500e-9,
            NA=1,
            pixel_size=4.0e-6,
            threshold_tau=0.1 
        )

        # Use logspace to properly sample the knee and the asymptote
        integration_times = np.logspace(-6, 10, 60)

        results = baird_sim.run_baird_validation(integration_times)

        return results
    optim_btn = mo.ui.run_button(label="Run Sim")
    optim_btn
    return main, optim_btn, plot_baird_validation


@app.cell
def _(main, optim_btn, plot_baird_validation):
    mo.stop(not optim_btn.value)
    results = main()

    _fig = plot_baird_validation(results)

    valid_events = np.isfinite(results['event_crlb']) & (np.array(results['event_crlb']) > 0)
    if np.sum(valid_events) > 5:
        event_crlb = np.array(results['event_crlb'])[valid_events]
        cmos_crlb = np.array(results['cmos_crlb'])[valid_events]

        min_ratio = np.min(event_crlb / cmos_crlb)
        max_ratio = np.max(event_crlb / cmos_crlb)

        print(f"\n📊 BAIRD'S THEORY VALIDATION RESULTS:")
        print(f"   Best Event/CMOS ratio: {min_ratio:.1f}× ")
        print(f"   Worst Event/CMOS ratio: {max_ratio:.0f}×")
        print(f"   Quantization ceiling confirmed: {max_ratio > 100}")

        if max_ratio > 100:
            print(f"✅ Baird's quantization ceiling confirmed!")
            print(f"   Event cameras severely limited by intensity quantization")
        else:
            print(f"❓ Results differ from Baird's prediction")
    mo.mpl.interactive(_fig)
    return (results,)


@app.cell
def _(results):
    def plot_baird_validation_2(results):
            import matplotlib.pyplot as plt
            from matplotlib.ticker import FuncFormatter
            import numpy as np

            # Set up a single focused plot matching the image aspect ratio
            fig, ax = plt.subplots(figsize=(12, 6))

            times = np.array(results['times'])
            cmos = np.array(results['cmos_crlb'])
            events = np.array(results['event_crlb'])
            quant_dom = np.array(results['quantization_dominated'])

            # 4. Plot update rate in Hz (1 / integration time)
            update_rate = 1.0 / times

            # 3. Plot accuracy (standard deviation) instead of variance
            std_cmos = np.sqrt(cmos)
            std_events = np.sqrt(events)

            valid_cmos = np.isfinite(cmos) & (cmos > 0)
            valid_events = np.isfinite(events) & (events > 0)

            # 1. Change colors and styles to match the attached image
        
            # Spatial, spectral or temporal information (Blue dashed line)
            if np.any(valid_cmos):
                ax.plot(update_rate[valid_cmos], std_cmos[valid_cmos], 
                        color='#3282b8', linestyle='--', linewidth=2, 
                        label='Spatial, spectral or temporal information')

            # Event-Based Imaging (Gray dashed line)
            photon_mask = valid_events & ~quant_dom
            if np.any(photon_mask):
                ax.plot(update_rate[photon_mask], std_events[photon_mask], 
                        color='#8a90a0', linestyle='--', linewidth=2, 
                        label='Event-Based Imaging')

            # Quantization Floor (Purple dashed line)
            quant_mask = valid_events & quant_dom
            if np.any(quant_mask):
                ax.plot(update_rate[quant_mask], std_events[quant_mask], 
                        color='#A13335', linestyle='--', linewidth=2, 
                        label='Quantization Floor')

            # 2. Change X and Y axis labels
            ax.set_xlabel('Update rate (Hz)', fontsize=20, fontweight='bold', color='#013352')
            ax.set_ylabel('Accuracy / Distance', fontsize=20, fontweight='bold', color='#013352')

            # Set Log Scales
            ax.set_xscale('log')
            ax.set_yscale('log')

            # Autoscale to the data limits, but keep the inverted y-axis orientation
            ax.invert_yaxis()

            # Match exact string formatting from the image dynamically
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0E}".replace('E', '.E') if y > 0 else ""))
        
            ax.tick_params(axis='both', colors='#013352', labelsize=12, width=2)
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight('bold')

            # Add background grid
            ax.grid(True, which='major', linestyle='-', color='#f0f0f0')
    
            # Add thick blue border matching the image
            for spine in ax.spines.values():
                spine.set_linewidth(2.5)
                spine.set_color('#013352')

            # Add legend matching label colors to line colors
            ax.legend(frameon=False, loc='lower left', fontsize=11, labelcolor='linecolor')

            plt.tight_layout()
            return fig
    mo.mpl.interactive(plot_baird_validation_2(results))
    return


if __name__ == "__main__":
    app.run()
