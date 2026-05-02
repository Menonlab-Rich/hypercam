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

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_default_dtype(torch.float64)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    The ideal image $I_t$ is given where $(u, v)$ represent the sensor plane and $u_0, $v_0$ represent specific points on that plane:
    $$ I_t = \delta\left(u - \frac{f}{z}x(t), v - \frac{f}{z}y(t)\right) = \delta\left(u-u_0, v - v_0\right)  $$
    To account for blur, the real image $I^b_t$ is given as the convolution of the PSF $h_z(t)$ and the ideal image $I_t$, with the subscrip $z$ implying that $h$ is depth variant.
    $$I_t^b(u,v) = [h_z(t) * I_t](u, v)$$
    The mapping of location $(x, y)$ to $(u, v)$ is given where z is the ideal focal plane, $\Delta{z}$ is the distance from that plane of the object, and $f$ is the focal distance of the objective.
    $$u = f \frac{x(t)}{z + \Delta z(t)}, \quad v = f \frac{y(t)}{z + \Delta z(t)}$$
    Because $f$ and $z$ are constant we can prescale $(x, y)$ using a scaling factor $S$:
    $$\text{scaling factor} = \frac{f}{z} = S$$
    $$ (u, v) \approx S ⋅ (x(t), y(t)) $$

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
    return FIM_pixel, a, b, c, mu, nu


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
    def get_sensor_qe_function():
        """
        Returns a function that performs PCHIP interpolation on the sensor's 
        Quantum Efficiency (QE) data.
        """
        # Data points including the UV anchor provided in your snippet
        wavelengths = np.array([369, 455, 505, 625, 850, 940])
        qe_values = np.array([30, 88, 100, 92, 39, 18])

        # Create the interpolator object once
        # PCHIP is chosen because it preserves the monotonicity of the data 
        # and prevents artificial oscillations (overshooting).
        interp = PchipInterpolator(wavelengths, qe_values)

        def interpolate_qe(wl):
            """
            Calculates QE (%) for wavelength(s) 'wl' in nm.
            Accepts scalars or numpy arrays.
            """
            # clip ensures values remain physically valid [0, 100]
            return np.clip(interp(wl), 0, 100) / 100

        return interpolate_qe

    def get_human_efficacy_function():
        """
        Returns a function that performs PCHIP interpolation on the efficacy of the human eye data
        """
        # Data points including the UV anchor provided in your snippet
        efficacy = {"380":0.027,"390":0.082,"400":0.27,"410":0.826,"420":2.732,"430":7.923,"440":15.709,"450":25.954,"460":40.98,"470":62.139,"480":94.951,"490":142.078,"500":220.609,"507":303.464,"510":343.549,"520":484.93,"530":588.746,"540":651.582,"550":679.551,"555":683,"560":679.585,"570":650.216,"580":594.21,"590":517.031,"600":430.973,"610":343.549,"620":260.223,"630":180.995,"640":119.525,"650":73.081,"660":41.663,"670":21.856,"680":11.611,"690":5.607,"700":2.802,"710":1.428,"720":0.715,"730":0.355,"740":0.17,"750":0.082,"760":0.041,"770":0.02}

        # Create the interpolator object once
        # PCHIP is chosen because it preserves the monotonicity of the data 
        # and prevents artificial oscillations (overshooting).
        interp = PchipInterpolator(list(efficacy.keys()), list(efficacy.values()))

        def interpolate_qe(wl):
            """
            Calculates QE (%) for wavelength(s) 'wl' in nm.
            Accepts scalars or numpy arrays.
            """
            # clip ensures values remain physically valid [0, 100]
            return interp(wl)

        return interpolate_qe



    return get_human_efficacy_function, get_sensor_qe_function


@app.cell
def _(a, b, c, get_human_efficacy_function, get_sensor_qe_function, mu, nu):
    efficacy_fn = get_human_efficacy_function()
    qe_fn = get_sensor_qe_function()

    def calculate_radiometry(rho, A_obj, NA, f, z, wavelength, pixel_pitch=4.86e-6, E_v=10e3, alpha=45):
        """
        Calculates physical target photoelectron rate and ambient background noise.
        """
        c = 2.99792458e8
        h = 6.62607015e-34

        K_lambda = efficacy_fn(wavelength) 
        qe = qe_fn(wavelength)
        J = (c * h) / (wavelength * 1e-9) 

        # Target Photon Radiance
        L_v_target = (rho * E_v) / np.pi
        L_p_target = (L_v_target / K_lambda) / J

        # Cloud Base Photon Radiance (CIE Overcast Model)
        L_z = E_v * 9 / (7 * np.pi)
        L_v_bg = L_z * (1 + 2 * np.sin(np.radians(alpha))) / 3
        L_p_bg = (L_v_bg / K_lambda) / J

        # Geometry
        A_lens = np.pi * (f * NA)**2
        omega_target = A_lens / (z**2)
        omega_lens = np.pi * NA**2 
        A_pixel = pixel_pitch**2

        # Photoelectron Rates
        R_target = L_p_target * A_obj * omega_target * qe
        beta_bg = L_p_bg * A_pixel * omega_lens * qe

        return R_target, beta_bg

    def apply_atmospheric_turbulence(field, shape, aperture_radius, D, z, wavelength=560e-9, Cn2=5e-14):
        """
        Constructs and applies a Kolmogorov phase screen.
        """
        k = 2 * np.pi / wavelength
        r0 = (0.423 * k**2 * Cn2 * z)**(-3/5)
        std_scaling = (D / r0)**(5/6)

        std_devs = {
            "Tilt Y": np.sqrt(0.448), "Tilt X": np.sqrt(0.448),
            "Defocus": np.sqrt(0.0232), "Astigmatism": np.sqrt(0.0232),
            "Coma": np.sqrt(0.00619), "Spherical": np.sqrt(0.00238)
        }

        aberrations = [
            (1, -1, "Tilt Y"), (1, 1, "Tilt X"), (2, 0, "Defocus"),
            (2, 2, "Astigmatism"), (3, 1, "Coma"), (4, 0, "Spherical")
        ]

        phase_screen = torch.zeros(shape, device=device)

        for n, m, name in aberrations:
            # Generate basis on the current field grid (3um spacing)
            z_poly = zernike(shape, n, m, aperture_radius).to(device)
            amplitude = torch.randn(1, device=device).item() * std_devs[name] * std_scaling
            phase_screen += amplitude * z_poly

        field.data *= torch.exp(1j * phase_screen)
        return field

    def _():
        N_side = 60
        pixel_size = 10e-6  # 10 microns
        f = 0.05            # 50mm focal length
        beta = 0.1          # Background photons
        wavelength = 550e-9 
        aperture = 0.01

        # Create the sensor coordinate grid (u, v)
        half_size = (N_side * pixel_size) / 2
        u_vals = np.linspace(-half_size, half_size, N_side)
        v_vals = np.linspace(-half_size, half_size, N_side)
        u_grid, v_grid = np.meshgrid(u_vals, v_vals)
        # Numerical Evaluation
        a_func = sp.lambdify((mu, nu), a, "numpy")
        b_func = sp.lambdify((mu, nu), b, "numpy")
        c_func = sp.lambdify((mu, nu), c, "numpy")
        # --- 3. Numerical Evaluation Setup ---
        # Define test trajectories (Object moving 1mm in x and y)
        x_tau, y_tau, z_tau = 0.0, 0.0, 1.0     # Position at t-tau
        x_t, y_t, z_t = 0.001, 0.001, 1.0      # Position at t



        def airy_disk_psf(u_grid, v_grid, x, y, z):
            # Mapping 3D (x,y,z) to 2D sensor coordinates (u0, v0)
            u0 = f * x / z
            v0 = f * y / z

            rho = np.sqrt((u_grid - u0)**2 + (v_grid - v0)**2)

            # Scale factor kappa changes with z (defocus approximation)
            w = (1.22 * wavelength * z) / aperture
            k = 3.8317 / w 

            val = k * rho
            val = np.where(val == 0, 1e-12, val)
            psf = (2 * j1(val) / val)**2

            return psf / np.sum(psf)

        def get_full_grad(x, y, z, step=1e-4):
            """Calculates numerical gradients w.r.t x, y, and z."""
            # x gradient
            g_x = (airy_disk_psf(u_grid, v_grid, x + step, y, z) - 
                   airy_disk_psf(u_grid, v_grid, x - step, y, z)) / (2 * step)
            # y gradient
            g_y = (airy_disk_psf(u_grid, v_grid, x, y + step, z) - 
                   airy_disk_psf(u_grid, v_grid, x, y - step, z)) / (2 * step)
            # z gradient
            g_z = (airy_disk_psf(u_grid, v_grid, x, y, z + step) - 
                   airy_disk_psf(u_grid, v_grid, x, y, z - step)) / (2 * step)

            return np.stack([g_x, g_y, g_z], axis=-1)


        # Generate intensities (mu, nu) and their gradients
        mu_grid = airy_disk_psf(u_grid, v_grid, x_tau, y_tau, z_tau) + beta
        nu_grid = airy_disk_psf(u_grid, v_grid, x_t, y_t, z_t) + beta

        grad_mu = get_full_grad(x_tau, y_tau, z_tau)  # Shape (60, 60, 3)
        grad_nu = get_full_grad(x_t, y_t, z_t)        # Shape (60, 60, 3)

        # --- 4. Fisher Information Calculation ---
        # Evaluate a, b, c coefficients across the grid
        a_grid = a_func(mu_grid, nu_grid)
        b_grid = b_func(mu_grid, nu_grid)
        c_grid = c_func(mu_grid, nu_grid)

        # Vectorized summation using Einstein summation
        # 'uv' indices are pixels, 'i'/'j' are the 3D params (x,y,z)
        A_total = np.einsum('uv,uvi,uvj->ij', a_grid, grad_mu, grad_mu)
        C_total = np.einsum('uv,uvi,uvj->ij', c_grid, grad_nu, grad_nu)
        B_total = np.einsum('uv,uvi,uvj->ij', b_grid, grad_mu, grad_nu)

        # Assemble 6x6 Matrix
        I_total = np.block([
            [A_total,   B_total],
            [B_total.T, C_total]
        ])

        # --- 5. Result: CRLB ---
        # Invert to get the variance-covariance matrix
        try:
            crlb_matrix = np.linalg.inv(I_total)
            std_devs = np.sqrt(np.diag(crlb_matrix))

            print("--- Tracking Precision (Standard Deviation) ---")
            print(f"Time t-tau: x={std_devs[0]:.2e}, y={std_devs[1]:.2e}, z={std_devs[2]:.2e}")
            print(f"Time t:     x={std_devs[3]:.2e}, y={std_devs[4]:.2e}, z={std_devs[5]:.2e}")
        except np.linalg.LinAlgError:
            print("Matrix is singular! The PSF might be too symmetric or the signal-to-noise is too low.")


    _()
    return (calculate_radiometry,)


@app.cell
def _():



    #device = 'cpu'

    logging.basicConfig(
        filename="crlb.log",
        encoding="utf-8",
        filemode="a",
        format="{asctime} - {levelname} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M",
        level=logging.DEBUG,
    )



    class FIMCoefficients(nn.Module):
        def __init__(self, beta_rate=0.1, threshold=0.2):
            super().__init__()
            self.beta_rate = beta_rate
            self.threshold = threshold # Event threshold (T)
            self.var_quantization = 1.0 / 3 # Variance of Uniform(-1, 1) quantization error

        def forward(self, nu, mu, t):
            # Add background photon noise to the signal
            beta = self.beta_rate * t
            nu = nu + beta
            mu = mu + beta
            T = self.threshold

            # 1. Base Mean and Variance of the approximated event frame
            # var = (1/nu + 1/mu) / T^2 + Var(epsilon)
            var = (1.0 / nu + 1.0 / mu) / (T**2) + self.var_quantization

            # 2. Closed-form partial derivatives of the mean
            dm_dmu = -1.0 / (mu * T)
            dm_dnu = 1.0 / (nu * T)

            # 3. Closed-form partial derivatives of the variance
            dv_dmu = -1.0 / ((mu**2) * (T**2))
            dv_dnu = -1.0 / ((nu**2) * (T**2))

            # 4. Calculate Fisher Information coefficients
            a = (1 / var) * (dm_dmu**2) + (1 / (2 * var**2)) * (dv_dmu**2)
            b = (1 / var) * (dm_dmu * dm_dnu) + (1 / (2 * var**2)) * (dv_dmu * dv_dnu)
            c = (1 / var) * (dm_dnu**2) + (1 / (2 * var**2)) * (dv_dnu**2)

            return a, b, c

    def get_full_grad_torch(theta, custom_mask, base_beam, lens, dt, R_rate, f=(35e-3, 19e-3)):
            x, y, z = theta[:, 0], theta[:, 1], theta[:, 2]
            pixel_pitch = 4.86e-6

            # Sub-pixel shift for lateral gradients
            step_xy = (0.1 * pixel_pitch * z[0]) / f[0] 

            # 1% depth shift for longitudinal gradients
            step_z = z[0] * 0.01 

            # Use step_xy for X and Y, and step_z for Z
            t_x_plus = torch.stack([x + step_xy, y, z], dim=-1)
            t_x_minus = torch.stack([x - step_xy, y, z], dim=-1)
            gx = (simulate_intensity(t_x_plus, custom_mask, base_beam, lens, dt, R_rate, f) - 
                  simulate_intensity(t_x_minus, custom_mask, base_beam, lens, dt, R_rate, f)) / (2 * step_xy)

            t_y_plus = torch.stack([x, y + step_xy, z], dim=-1)
            t_y_minus = torch.stack([x, y - step_xy, z], dim=-1)
            gy = (simulate_intensity(t_y_plus, custom_mask, base_beam, lens, dt, R_rate, f) - 
                  simulate_intensity(t_y_minus, custom_mask, base_beam, lens, dt, R_rate, f)) / (2 * step_xy)

            t_z_plus = torch.stack([x, y, z + step_z], dim=-1)
            t_z_minus = torch.stack([x, y, z - step_z], dim=-1)
            gz = (simulate_intensity(t_z_plus, custom_mask, base_beam, lens, dt, R_rate, f) - 
                  simulate_intensity(t_z_minus, custom_mask, base_beam, lens, dt, R_rate, f)) / (2 * step_z)

            return torch.stack([gx, gy, gz], dim=-1)

    def apply_phase_tilt(base_beam, x, y, z, wavelength=560e-9, spacing=3e-6, z_focus=1):
        # Ensure x, y, z are batched and broadcastable: [Batch, 1, 1]
        x = x.view(-1, 1, 1)
        y = y.view(-1, 1, 1)
        z = z.view(-1, 1, 1)

        shape = base_beam.shape[-1] 

        coords = torch.arange(-shape // 2, shape // 2, device=device) * spacing
        v, u = torch.meshgrid(coords, coords, indexing='ij')

        # total_phase broadcasts to [Batch, H, W]
        phase_ramp = (2 * torch.pi / (wavelength * z)) * (x * u + y * v)
        phase_defocus = (torch.pi / wavelength) * (1.0 / z - 1.0 / z_focus) * (u**2 + v**2)
        total_phase = phase_ramp + phase_defocus

        # Bypass PhaseModulator and apply the complex exponent directly to the field data
        batched_data = base_beam.data * torch.exp(1j * total_phase)

        # Reconstruct the Field object with the modified data
        shifted_beam = Field(
            data=batched_data,
            wavelength=base_beam.wavelength,
            z=base_beam.z, # Maintained from base_beam
            spacing=base_beam.spacing,
            offset=base_beam.offset
        ).to(device)

        return shifted_beam

    def simulate_intensity(theta, phase_tensor, base_beam, lenses, dt, R_rate, f=(35e-3, 19e-3)):
        current_max_photons = (R_rate * dt)
        # Expand the base beam data to include the batch dimension [Batch, H, W]
        batch_size = theta.shape[0]
        batched_beam_data = base_beam.data.expand(batch_size, -1, -1).clone().to(device)

        fresh_beam = Field(
            data=batched_beam_data,
            wavelength=base_beam.wavelength,
            z=0.0,
            spacing=base_beam.spacing,
            offset=base_beam.offset
        ).to(device)

        # Extract batched coordinates
        x, y, z = theta[:, 0], theta[:, 1], theta[:, 2]

        shifted_beam = apply_phase_tilt(fresh_beam, x, y, z)
        lens_obj, relay_l1, relay_l2 = lenses

        # 1. Apply Objective Lens at z = 0
        field = lens_obj(shifted_beam)

        # 2. Propagate to Relay Lens 1 (z = f_obj + f_relay)
        field = field.propagate_to_z(f[0] + f[1])
        field = relay_l1(field)

        # 3. Propagate to 4f Fourier Plane (z = f_obj + 2 * f_relay)
        field = field.propagate_to_z(f[0] + 2 * f[1])

        # Apply Phase Mask
        mask_modulator = PhaseModulator(phase=phase_tensor, z=f[0] + 2 * f[1]).to(device)
        field = mask_modulator(field)

        # 4. Propagate to Relay Lens 2 (z = f_obj + 3 * f_relay)
        field = field.propagate_to_z(f[0] + 3 * f[1])
        field = relay_l2(field)

        # 5. Propagate to Sensor (z = f_obj + 4 * f_relay)
        field_sensor = field.propagate_to_z(f[0] + 4 * f[1])

        raw_intensity = field_sensor.intensity()


        raw_intensity = field_sensor.intensity()
        scale_factor = 3.0 / 4.86
        pixel_intensity = F.interpolate(
                raw_intensity.unsqueeze(1), 
                scale_factor=scale_factor, 
                mode='area'
            ).squeeze(1)

        # 3. Normalize and scale to the integrated photon count
        norm = pixel_intensity.sum(dim=(0, 1), keepdim=True) + 1e-12
        final_intensity = (pixel_intensity / norm) * current_max_photons
        return final_intensity + 1e-12 # Non-zero

    def compute_fim(theta_tau, theta_t, phase_tensor, base_beam, fim_module, dt, R_rate, lenses, f):
        theta_tau = theta_tau.clone().detach().to(device)
        theta_t = theta_t.clone().detach().to(device)

        mu = simulate_intensity(theta_tau, phase_tensor, base_beam, lenses, dt, R_rate, f)
        nu = simulate_intensity(theta_t, phase_tensor, base_beam, lenses, dt, R_rate, f)

        grad_mu = get_full_grad_torch(theta_tau, phase_tensor, base_beam, lenses, dt, R_rate, f)
        grad_nu = get_full_grad_torch(theta_t, phase_tensor, base_beam, lenses, dt, R_rate, f)

        a, b, c = fim_module(nu, mu, dt)

        # b = batch, u/v = spatial pixels, i/j = 3D parameters (x, y, z)
        # Output is a stack of FIM matrices: [Batch, 3, 3]
        A_total = torch.einsum('buv,buvi,buvj->bij', a, grad_mu, grad_mu)
        C_total = torch.einsum('buv,buvi,buvj->bij', c, grad_nu, grad_nu)
        B_total = torch.einsum('buv,buvi,buvj->bij', b, grad_mu, grad_nu)

        # Assemble the [Batch, 6, 6] matrix
        row_1 = torch.cat([A_total, B_total], dim=2)
        row_2 = torch.cat([B_total.transpose(1, 2), C_total], dim=2)
        FIM_total = torch.cat([row_1, row_2], dim=1)

        return FIM_total

    @torch.no_grad()
    def validate_sampling_bounds(device, wavelength=560e-9, f=19e-3, shape=335, spacing=3e-6, z_focus=1.0, z_min=0.45, z_max=0.85, radius=1e-3):
        """
        Sweeps the z-axis to validate phase aliasing in the pupil and PSF sampling at the sensor.
        """
        # 1. Setup Pupil Grid
        coords = torch.arange(-shape // 2, shape // 2, device=device) * spacing
        v, u = torch.meshgrid(coords, coords, indexing='ij')

        # Generate test distances
        z_vals = torch.linspace(z_min, z_max, steps=10, device=device)

        max_phase_grads = []
        fwhm_pixels = []

        beam = Field(circle(shape=shape, radius=radius)).to(device)

        for z in z_vals:
            # --- Aliasing Check (Pupil Plane) ---
            phase_defocus = (torch.pi / wavelength) * (1.0 / z - 1.0 / z_focus) * (u**2 + v**2)

            # Calculate gradients (phase difference between adjacent pixels)
            dp_du = torch.abs(torch.diff(phase_defocus, dim=1))
            dp_dv = torch.abs(torch.diff(phase_defocus, dim=0))
            max_grad = max(dp_du.max().item(), dp_dv.max().item())
            max_phase_grads.append(max_grad)

            # --- Sampling Check (Sensor Plane) ---
            modulator = PhaseModulator(phase=phase_defocus).to(device)
            shifted_beam = modulator(beam)

            system = System(Lens(shape=shape, focal_length=f, z=f)).to(device)
            field_sensor = system(shifted_beam).propagate_to_z(2 * f)

            intensity = field_sensor.intensity().cpu().numpy()

            # Approximate FWHM in pixels
            max_val = intensity.max()
            half_max_mask = intensity >= (max_val / 2.0)
            # Summing along the axes to get the width of the bounding box of the half-max region
            fwhm_y = np.max(np.sum(half_max_mask, axis=0))
            fwhm_x = np.max(np.sum(half_max_mask, axis=1))
            fwhm_pixels.append(max(fwhm_x, fwhm_y))

        # --- Print Diagnostics ---
        print(f"{'z (m)':<10} | {'Max Phase Grad (rad/px)':<25} | {'FWHM (pixels)':<15} | {'Status'}")
        print("-" * 75)
        for i, z in enumerate(z_vals):
            grad = max_phase_grads[i]
            fwhm = fwhm_pixels[i]

            # Determine status
            status = "PASS"
            if grad > np.pi:
                status = "FAIL (Aliasing)"
            elif fwhm < 2.0:
                status = "FAIL (Under-sampled)"

            print(f"{z.item():<10.3f} | {grad:<25.3f} | {fwhm:<15} | {status}")

        # --- Visual Confirmation at Extrema ---
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))

        # Plot Near Field (Worst Aliasing Risk)
        ax[0].set_title(f"Near Field PSF (z={z_min}m)")
        # Re-run for z_min
        p_min = (torch.pi / wavelength) * (1.0 / z_min - 1.0 / z_focus) * (u**2 + v**2)
        sys_min = System(Lens(shape=shape, focal_length=f, z=f)).to(device)
        int_min = sys_min(PhaseModulator(phase=p_min).to(device)(beam)).propagate_to_z(2 * f).intensity()
        ax[0].imshow(int_min.cpu().numpy(), cmap='inferno')

        # Plot Far Field (Worst Sampling Risk)
        ax[1].set_title(f"Far Field PSF (z={z_max}m)")
        # Re-run for z_max
        p_max = (torch.pi / wavelength) * (1.0 / z_max - 1.0 / z_focus) * (u**2 + v**2)
        sys_max = System(Lens(shape=shape, focal_length=f, z=f)).to(device)
        int_max = sys_max(PhaseModulator(phase=p_max).to(device)(beam)).propagate_to_z(2 * f).intensity()
        ax[1].imshow(int_max.cpu().numpy(), cmap='inferno')

        plt.show()

    return FIMCoefficients, compute_fim, validate_sampling_bounds


@app.cell
def _(compute_fim):
    def generate_random_walk_trajectories(num_particles, num_steps, dt, initial_z=1.0):
        # 1. Lateral (X, Y) relative tracking error: ~2 m/s
        target_speeds_xy = torch.empty(num_particles, 1, 1).uniform_(1.5, 2.5)
        expected_step_size_xy = target_speeds_xy * dt
        std_devs_xy = expected_step_size_xy * torch.sqrt(torch.tensor(torch.pi / 8.0))

        # 2. Longitudinal (Z) relative tracking error: <= 1 m/s
        target_speeds_z = torch.empty(num_particles, 1, 1).uniform_(0.1, 1.0)
        expected_step_size_z = target_speeds_z * dt
        std_devs_z = expected_step_size_z * torch.sqrt(torch.tensor(torch.pi / 8.0))

        # Generate displacements independently
        displacements_x = torch.randn(num_particles, num_steps, 1) * std_devs_xy
        displacements_y = torch.randn(num_particles, num_steps, 1) * std_devs_xy
        displacements_z = torch.randn(num_particles, num_steps, 1) * std_devs_z

        displacements = torch.cat([displacements_x, displacements_y, displacements_z], dim=2)

        # Accumulate into trajectories
        trajectories = torch.cumsum(displacements, dim=1)

        # Offset by starting position
        start_pos = torch.tensor([0.0, 0.0, initial_z]).view(1, 1, 3)
        trajectories = trajectories + start_pos

        return trajectories

    # Generate Trajectories


    def total_variation_loss(phase_tensor, alpha=0.1):
        # Map phase to complex plane
        complex_field = torch.exp(1j * phase_tensor)

        # Calculate finite differences of the complex vectors
        tv_x = torch.mean(torch.abs(complex_field[:, 1:] - complex_field[:, :-1]))
        tv_y = torch.mean(torch.abs(complex_field[1:, :] - complex_field[:-1, :]))
        return alpha * (tv_x + tv_y)

    def optimize(beam, shape, static_lenses, f_obj, f_relay, fim_calculator, epochs=50, dt=1e-3, initial_z=1.0, R_rate=1.0):
        paths = generate_random_walk_trajectories(num_particles=1, num_steps=500, dt=dt, initial_z=initial_z)
        theta_tau = paths[:, :-1, :] 
        theta_t = paths[:, 1:, :]

        t_shape = torch.tensor(shape)
        U = (-t_shape // 2)[0].item()
        V = (t_shape // 2)[1].item()
        coords = torch.arange(U, V, device=device) * 3e-6
        v, u = torch.meshgrid(coords, coords, indexing='ij')

        initial_astigmatism = 0.5 * (u**2 - v**2)
        learnable_phase = torch.nn.Parameter(initial_astigmatism)

        optimizer = torch.optim.Adam([learnable_phase], lr=1e-2)
        epsilon = 1e-6
        batch_size = paths.shape[0]

        progress = tqdm(desc="Epochs", total=epochs)

        # 1. Initialize tracking variables
        best_loss = float('inf')
        best_phase = None

        for epoch in range(epochs):
            optimizer.zero_grad()

            bounded_phase = torch.sigmoid(learnable_phase) * 4 * torch.pi

            # Process all 100 particles simultaneously
            # Extract shapes [Batch, 3]
            pos_tau = theta_tau[:, 0, :] 
            pos_t = theta_t[:, 0, :]     

            # fim shape: [Batch, 6, 6]
            fim = compute_fim(pos_tau, pos_t, bounded_phase, beam, fim_calculator, dt, R_rate, static_lenses, f=(f_obj, f_relay))

            # Expand identity to match batch size: [Batch, 6, 6]
            identity = torch.eye(6, device=device).expand(batch_size, 6, 6)

            # Epsilon regularization is strictly required here to prevent -inf logdet
            epsilon = 1e-6
            fim_logdet = torch.logdet(fim + epsilon * identity)

            # Mean across the batch for scalar loss
            loss = (-fim_logdet.mean()) + total_variation_loss(bounded_phase, 0.03)

            loss.backward()
            optimizer.step()

            # 2. Evaluate and checkpoint the best model
            current_loss = loss.item()
            if current_loss < best_loss:
                best_loss = current_loss
                # Detach and clone to prevent memory leaks and isolate from further graph updates
                best_phase = learnable_phase.detach().clone()

            # 3. Update progress bar to monitor both current and best loss
            progress.set_postfix({'Loss': f'{current_loss:.3e}', 'Best': f'{best_loss:.3e}'})
            progress.update(1)

        # 4. Return the checkpointed phase instead of the final active parameter
        return best_phase

        optimize_btn = mo.ui.button(
            label="Optimize",
            on_click=lambda _: True,
            value=False
        )
        return generate_random_walk_trajectories, optimize, optimize_btn

    return (generate_random_walk_trajectories,)


@app.cell
def _(validate_sampling_bounds):
    f_obj = 35e-3
    f_relay = 19e-3
    NA = 0.0559
    target_wavelength = 560 # nm
    aperture_diameter = 2 * (35e-3 * 0.0559) # ~3.91mm
    aperture_radius = f_obj * NA
    aperture_radius_grid = aperture_radius # Your existing torchoptics grid radius
    shape = (1306, 1306) # Your existing grid shape

    torchoptics.set_default_wavelength(target_wavelength)
    torchoptics.set_default_spacing(3e-6)


    static_lenses = (
            Lens(shape=shape, focal_length=f_obj, z=0.0).to(device),
            Lens(shape=shape, focal_length=f_relay, z=f_obj + f_relay).to(device),
            Lens(shape=shape, focal_length=f_relay, z=f_obj + 3 * f_relay).to(device)
        )

    validate_sampling_bounds(device='cpu', z_min=0.45, z_max=0.85, z_focus=0.65, radius=34e-3)
    optimize_btn = mo.ui.button(lambda _: True, value=False, label="Optimze")
    optimize_btn
    return (
        aperture_radius_grid,
        f_obj,
        f_relay,
        optimize_btn,
        shape,
        static_lenses,
        target_wavelength,
    )


@app.cell
def _(
    FIMCoefficients,
    aperture_radius_grid,
    calculate_radiometry,
    compute_fim,
    f_obj,
    f_relay,
    generate_random_walk_trajectories,
    optimize_btn,
    shape,
    static_lenses,
    target_wavelength,
):
    def evaluate_and_plot(optimized_phase, current_dt, beam, fim_calculator, R_rate, f_obj, f_relay, initial_z=1):
        # --- 1. Physical Conversion (Mask Height) ---
        wavelength = 560e-9
        n_material = 1.46  # Fused Silica
        n_medium = 1.0     # Air

        wrapped_phase = torch.remainder(optimized_phase, 2 * torch.pi)
        height_map_um = (wrapped_phase * wavelength) / (2 * torch.pi * (n_material - n_medium)) * 1e6

        # --- 2. FIM and CRLB Calculation ---
        epsilon = 1e-8

        paths = generate_random_walk_trajectories(num_particles=1, num_steps=500, dt=current_dt, initial_z=initial_z)
        theta_tau = paths[:, :-1, :] 
        theta_t = paths[:, 1:, :]

        p_tau = theta_tau[0, 0, :].to(device)
        p_t = theta_t[0, 0, :].to(device)
        z = p_t[2].item()

        p_tau = p_tau.unsqueeze(0)
        p_t = p_t.unsqueeze(0)

        custom_mask = PhaseModulator(phase=optimized_phase).to(device)

        with torch.no_grad():
            fim = compute_fim(p_tau, p_t, optimized_phase, beam, fim_calculator, current_dt, R_rate, static_lenses, (f_obj, f_relay))

            # Remove the batch dimension: [1, 6, 6] -> [6, 6]
            fim = fim.squeeze(0)

            # Use Moore-Penrose pseudo-inverse instead of torch.inverse + epsilon.
            # rcond sets the singular value threshold to filter out numerical noise.
            inv_fim = torch.linalg.pinv(fim, rcond=1e-15)

            # Apply absolute value to the diagonal to prevent NaN errors from negative noise
            std_devs = torch.sqrt(torch.abs(torch.diag(inv_fim)))
            if std_devs[5].item() % 10 == 0:
                print('Warning! Z dev is a power of 10')

            # --- 3. Data Logging ---
            df = pd.DataFrame({
                    'dt': [current_dt], 
                    'sigma_x': [std_devs[3].item()], 
                    'sigma_y': [std_devs[4].item()], 
                    'sigma_z': [std_devs[5].item()],
                    'z': initial_z,
                })

            csv_path = 'crlb_results.csv'
            write_header = not os.path.exists(csv_path)
            df.to_csv(csv_path, mode='a', header=write_header, index=False)


    # --- Execution Block ---
    if optimize_btn.value:
        dts_us = [100, 500, 1000, 10000]
        distances = [50, 100, 300, 500]

        expected_dts = [x / 1e6 for x in dts_us]

        existing_pairs = set()
        if os.path.exists('crlb_results.csv'):
            existing_df = pd.read_csv('crlb_results.csv')
            # Create a set of (dt, z) to check against
            # We round to avoid floating point mismatch issues
            existing_pairs = set(zip(existing_df['dt'].round(6), existing_df['z']))

        # Instantiate static dependencies once
        fim_calculator = FIMCoefficients(beta_rate=0.1).to(device)
        final_fig = None
        start_phrase_printed = False
        for distance in distances:
            R_signal, beta_background = calculate_radiometry(
            rho=0.5, A_obj=1, NA=0.0559, f=35e-3, 
            z=distance, wavelength=target_wavelength, 
            pixel_pitch=4.86e-6, E_v=10e3, alpha=45
        )

            # 2. Initialize FIM calculator with the physically accurate background noise
            fim_calculator = FIMCoefficients(
            beta_rate=beta_background,
        ).to(device)
            for _dt in dts_us:
                current_dt = _dt * 1e-6
                if (round(current_dt, 6), distance) in existing_pairs:
                        continue
                if not start_phrase_printed:
                    print(f"Starting at dt = {current_dt * 1e6}, dist = {distance}")
                    start_phrase_printed = True
                # Optimize mask for the current integration time
                base_beam = Field(circle(shape=shape, radius=aperture_radius_grid)).to(device)

                # 4. Apply distance-dependent atmospheric turbulence
                # For now we will ignore this
                # base_beam = apply_atmospheric_turbulence(
                #     field=base_beam,
                #     shape=shape,
                #     aperture_radius=aperture_radius_grid,
                #     D=aperture_diameter,
                #     z=distance,
                #     wavelength=target_wavelength * 1e-9,
                #     Cn2=5e-14
                # )
                #optimized_phase = optimize(base_beam, shape, static_lenses, f_obj, f_relay, fim_calculator, 50, dt=current_dt, initial_z=distance, R_rate=R_signal)
                zero_phase = torch.zeros(shape, dtype=torch.float64, device=device)
                # Write to CSV and generate plot
                evaluate_and_plot(zero_phase, current_dt, base_beam, fim_calculator, R_signal, f_obj, f_relay, initial_z=distance)
        print("Evaluation Complete")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
