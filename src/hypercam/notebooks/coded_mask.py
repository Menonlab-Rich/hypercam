# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-05
# Notice:        This file was authored or modified with the assistance of
#                Kilo (Qwen3.8-flash).
# ==============================================================================

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Coded DOE: Inverse Design of a Diffractive Optical Element for Hyperspectral Localization

    A **coded-aperture** camera places a thin diffractive optical element (DOE) --
    a micron-scale relief thickness map $t(x, y)$ in a polymer of index
    $n(\lambda)$ -- just in front of the intermediate image plane of a 35 mm lens.
    Defocus between the DOE and that plane converts the DOE's *chromatic phase*
    into *wavelength-dependent point-spread functions* (PSFs), so a single sensor
    exposure encodes both where a point source is and what color it is.

    This notebook **inversely designs** that relief. In forward design you pick a
    surface and simulate the image it makes; here the order is flipped:

    1. the surface is **parameterized** (a small neural network maps DOE
       coordinates to thickness),
    2. a differentiable **physics model** renders the images it would produce,
    3. an estimation-theoretic **objective** -- the Cramer-Rao lower bound (CRLB)
       on localizing $(x, y, \lambda)$ -- scores those images,
    4. **gradient descent** back-propagates through the wave optics into the
       geometry.

    The pipeline, cell by cell: configuration and headless (CHPC) TOML overrides;
    the optical model (angular-spectrum propagation, the DOE + relay operator,
    the incoherent Monte Carlo stack); the simulated object and material
    dispersion; the neural thickness parameterization; the Fisher/CRLB objective;
    training; diagnostics and fabrication export; and finally evaluation of the
    trained DOE on a real hyperspectral video.

    *Assumed background: Fourier optics (PSFs, NA, coherent cutoff) and Poisson
    photon counting. No experience with neural networks or marimo is assumed --
    marimo is a reactive notebook: editing any cell re-runs everything that
    depends on it, and the cell graph below is the program.*
    """)
    return


@app.cell(hide_code=True)
def _():
    import os

    os.putenv('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    return (os,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Running modes: editor vs. headless batch (CHPC)

    **In the marimo editor** (`marimo edit coded_mask.py`): toggle the `RUN_*`
    switches in the config cell, browse for a Cauchy material table, and step
    through the cells.

    **On the CHPC** the same file runs as a plain script. Point
    `CODED_MASK_CONFIG` at a TOML file and every default below can be overridden
    without touching the code:

    ```bash
    CODED_MASK_CONFIG=/scratch/baird/hypercam/run.toml python coded_mask.py
    ```

    TOML sections mirror the config cell: `[design]` physical variables,
    `[run]` execution switches and `seed`, `[paths]` the Cauchy material table
    and data/output locations, `[training]` keyword overrides forwarded to
    `train_mask`. See `coded_mask.example.toml` for the annotated schema; a
    complete SLURM sketch appears at the end of this notebook. When the variable
    is unset (the editor), every default applies unchanged.
    """)
    return


@app.cell(hide_code=True)
def _(os):
    import torch
    import torch.nn as nn
    import numpy as np
    import pandas as pd
    from scipy.interpolate import CubicSpline
    from pathlib import Path
    import marimo as mo

    # ------------------------------------------------------------------
    # Headless (CHPC) configuration. When this notebook runs as a plain
    # script, point CODED_MASK_CONFIG at a TOML file whose sections
    # [design], [run], [paths], and [training] override the defaults
    # below; unset variables keep the defaults, so the marimo editor is
    # unaffected:
    #
    #   CODED_MASK_CONFIG=/scratch/run.toml python coded_mask.py
    #
    # See coded_mask.example.toml for the full schema.
    # ------------------------------------------------------------------
    import tomllib

    config_path = os.environ.get("CODED_MASK_CONFIG", "")
    if config_path:
        with open(config_path, "rb") as config_handle:
            CONFIG = tomllib.load(config_handle)
    else:
        CONFIG = {}

    def _get(table, key, default):
        """TOML value with a default; JSON-style lists become tuples."""
        value = table.get(key, default)
        return tuple(value) if isinstance(value, list) else value

    design = CONFIG.get("design", {})
    run_cfg = CONFIG.get("run", {})
    paths_cfg = CONFIG.get("paths", {})

    device = torch.device(_get(
        run_cfg, "device", "cuda" if torch.cuda.is_available() else "cpu",
    ))
    # Centralized execution switches. Change these here (or in the TOML
    # [run] section) rather than searching through the notebook.
    RUN_TRAINING = bool(_get(run_cfg, "run_training", True))
    RUN_DEBUG_TRAINING = bool(_get(run_cfg, "run_debug_training", False))
    SAVE = bool(_get(run_cfg, "save", True))
    RUN_HYPERSPECTRAL = bool(_get(run_cfg, "run_hyperspectral", True))
    CREATE_VIDEO = bool(_get(run_cfg, "create_video", True))
    CREATE_RGB_VIDEO = bool(_get(run_cfg, "create_rgb_video", False))
    VIDEO_CODEC = str(_get(run_cfg, "video_codec", "FFV1"))
    # Reproducibility: when [run].seed is set it seeds the torch RNG
    # (MLP init) and the hyperspectral Monte Carlo phase screens; unset
    # keeps the interactive behavior of fresh randomness per run.
    SEED = run_cfg.get("seed", None)
    SEED = None if SEED is None else int(SEED)
    if SEED is not None:
        torch.manual_seed(SEED)
    # ------------------------------------------------------------------
    # Physical design variables. Every model, training, and evaluation
    # cell reads these through marimo references, so changing a value
    # here re-runs and re-parameterizes the whole pipeline.
    # ------------------------------------------------------------------
    # Sensor sampling raster (H, W) in detector pixels.
    SENSOR_RASTER = _get(design, "sensor_raster", (720, 1280))
    # Physical pitch of one detector pixel (m). Wave propagation and the
    # Monte Carlo image formation run on this grid.
    SENSOR_PIXEL_PITCH = float(_get(design, "sensor_pixel_pitch", 3.45e-6))
    # Physical pitch of one DOE cell (m). Set DOE_PIXEL_PITCH >
    # SENSOR_PIXEL_PITCH so a single lithographic DOE structure covers
    # DOE_PIXEL_PITCH / SENSOR_PIXEL_PITCH detector pixels per side; the
    # DOE relief is upsampled piecewise-constant (nearest) onto the sensor
    # grid before the phase mask is applied. A finer DOE than the sensor
    # is representable but the sensor grid remains the sampling bottleneck.
    DOE_PIXEL_PITCH = float(_get(design, "doe_pixel_pitch", 3.45e-6 * 3))
    # DOE raster: sized so the DOE's physical extent matches the sensor
    # field of view, SENSOR_RASTER * SENSOR_PIXEL_PITCH.
    DOE_RASTER = (
        int(round(SENSOR_RASTER[0] * SENSOR_PIXEL_PITCH / DOE_PIXEL_PITCH)),
        int(round(SENSOR_RASTER[1] * SENSOR_PIXEL_PITCH / DOE_PIXEL_PITCH)),
    )
    # Peak DOE relief thickness (m): the MLP Softplus output is scaled
    # to this many meters.
    DOE_MAX_THICKNESS = float(_get(design, "doe_max_thickness", 5e-6))
    # Search range for the trainable DOE-to-focal-plane offset delta (m).
    # The DOE sits this far BEFORE the focal plane (lens side).
    DOE_GAP_RANGE = _get(design, "doe_gap_range", (1e-5, 1e-3))
    # Nominal DOE-to-focal-plane offset: the optimizer's starting point
    # and the evaluation fallback when no trained gap was saved.
    DOE_GAP = float(_get(design, "doe_gap", 500e-6))
    # Spectral simulation band [min, max) in nm with the given step.
    WAVELENGTH_BAND_NM = _get(design, "wavelength_band_nm", (380.0, 750.0))
    WAVELENGTH_STEP_NM = float(_get(design, "wavelength_step_nm", 5.0))
    # Entrance aperture: "rect" passes the full raster; "circular" keeps
    # a disk whose radius is APERTURE_RADIUS_FRACTION of the half-width
    # of the smaller raster dimension.
    APERTURE_TYPE = str(_get(design, "aperture_type", "rect"))
    APERTURE_RADIUS_FRACTION = float(_get(design, "aperture_radius_fraction", 0.5))
    # Cauchy material table with columns "Wavelength (m)" and "n".
    MATERIAL_XLSX = str(_get(paths_cfg, "material_xlsx", "mat_maP1275.xlsx"))
    # Hyperspectral source sequence and transformed-frame output directory.
    HYPERSPECTRAL_DIR = str(_get(
        paths_cfg, "hyperspectral_dir",
        "../../data/hyperspectral/Dyna_Spec_release/running-frog",
    ))
    TRANSFORMED_DIR = str(_get(paths_cfg, "transformed_dir", "transformed_running_frog"))
    # Keyword arguments forwarded to train_mask(); override any key in the
    # TOML [training] section (epochs, learning_rate, patch_size, ...).
    TRAINING_CONFIG = dict(
        epochs=1000,
        learning_rate=1e-4,
        photons_per_bin=1e5,
        background_photons=1.0,
        # Sensor-pitch patch: near-focus phase-to-intensity conversion
        # cannot be represented on a pooled-down grid.
        patch_size=256,
        print_every=100,
        monte_carlo_samples=2,
        optim_space=False,
        # "event" (default: the hypercam is an event sensor; Fisher blocks
        # from consecutive-frame log-ratio pairs, Shah et al. Eq. (13)) or
        # "frame" (blinking-particle Poisson baseline, their Eq. (10)).
        sensor="event",
        # Frame-mode weighting only: "poisson" (exact) or "gaussian"
        # (shot + read-noise variance). Overridable in the TOML [training].
        noise_model="poisson",
    )
    TRAINING_CONFIG.update(CONFIG.get("training", {}))
    return (
        APERTURE_RADIUS_FRACTION,
        APERTURE_TYPE,
        CREATE_RGB_VIDEO,
        CREATE_VIDEO,
        CubicSpline,
        DOE_GAP,
        DOE_GAP_RANGE,
        DOE_MAX_THICKNESS,
        DOE_PIXEL_PITCH,
        DOE_RASTER,
        HYPERSPECTRAL_DIR,
        MATERIAL_XLSX,
        Path,
        RUN_DEBUG_TRAINING,
        RUN_HYPERSPECTRAL,
        RUN_TRAINING,
        SAVE,
        SEED,
        SENSOR_PIXEL_PITCH,
        SENSOR_RASTER,
        TRAINING_CONFIG,
        TRANSFORMED_DIR,
        VIDEO_CODEC,
        WAVELENGTH_BAND_NM,
        WAVELENGTH_STEP_NM,
        device,
        mo,
        nn,
        np,
        pd,
        torch,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### What the design variables mean

    | Variable | Physical meaning |
    | --- | --- |
    | `SENSOR_RASTER`, `SENSOR_PIXEL_PITCH` | the detector: where the wave optics is sampled. All propagation runs on this grid. |
    | `DOE_PIXEL_PITCH`, `DOE_RASTER` | the DOE's own lithographic cell grid. A coarser `DOE_PIXEL_PITCH` makes one mask structure cover a block of detector pixels; `DOE_RASTER` is derived so the DOE's physical extent matches the sensor field of view. |
    | `DOE_MAX_THICKNESS` | the optimizer's height budget. The phase excursion is $2\pi\,[n(\lambda)-1]\,t/\lambda$, so 5 um at $n \approx 1.5$ gives about 6 waves at 400 nm. |
    | `DOE_GAP_RANGE`, `DOE_GAP` | the defocus $\delta$ that converts phase into intensity. $\delta$ is *learned* inside the range; `DOE_GAP` seeds the search and is the evaluation fallback. |
    | `WAVELENGTH_BAND_NM`, `WAVELENGTH_STEP_NM` | the spectral bins of the incoherent sum. |
    | `APERTURE_TYPE`, `APERTURE_RADIUS_FRACTION` | the stop applied to the DOE relief by the near-field point-source PSF model (`rect` = open, transmission 1). |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The optical model

    ### Incoherent image formation through a defocused phase mask

    The lens forms an intermediate image of intensity $M(x, y; \lambda)$ in its
    focal plane. A pure phase mask *in that plane* would change nothing: the
    sensor records $\big|\sqrt{M}\,e^{i\phi}\big|^2 = M$. Information appears
    only when the DOE sits a distance $\delta$ away, because propagation is
    **linear in the field** while the sensor is **quadratic in it** --
    neighbouring image points interfere and the phase structure of $t(x,y)$
    becomes intensity structure.

    Per wavelength the model is four operations on the focal-plane complex
    field $U = \sqrt{M}\,e^{i\psi}$:

    1. **back-propagate** by $-\delta$ to the DOE plane (angular spectrum),
    2. **apply the DOE**: $\;U \mapsto U\,\exp\!\big(i\,\tfrac{2\pi}{\lambda}\,[n(\lambda)-1]\,t\big)$,
    3. **propagate** by $+\delta$ back to the focal plane -- the
       phase-to-intensity conversion,
    4. **relay** 1:1 to the sensor. At $f/1.65$ the relay's coherent cutoff
       $\mathrm{NA}/\lambda \approx 5.7\times 10^{5}$ cy/m exceeds the Nyquist
       of the 3.45 um grid, so the relay is a perfect inversion -- a flip.

    Steps 1-4 are exactly the function `to_focal` defined below. Each
    propagation uses the angular-spectrum transfer function

    $$
    H(f_x, f_y) = \exp\!\left[\,i\,\frac{2\pi\delta}{\lambda}
    \sqrt{1 - (\lambda f_x)^2 - (\lambda f_y)^2}\;\right],
    $$

    exact for propagating spatial frequencies, with evanescent components
    zeroed. This is why the simulation grid must run at (or below) the physical
    sensor pitch: the conversion over $\delta$ needs the frequencies with
    $\pi \lambda \delta f^2 \sim 1$, which a pooled-down grid cannot represent.

    ### We are in the near field -- and the model never assumes otherwise

    No Fraunhofer (far-field) approximation is used anywhere in the image
    formation. A quick Fresnel-number check shows why that matters: the DOE
    half-width is $a \approx 2.2$ mm, so at $\lambda = 550$ nm and
    $\delta = 100$ um the Fresnel number is

    $$
    N_F = \frac{a^2}{\lambda\,\delta} \approx \frac{(2.2\times 10^{-3})^2}
    {5.5\times 10^{-7} \times 10^{-4}} \sim 10^{4} \gg 1,
    $$

    deep in the Fresnel region even at the smallest gap in `DOE_GAP_RANGE`.
    The angular-spectrum transfer function is the exact plane-to-plane
    propagator across that whole regime (the Fraunhofer limit is merely its
    asymptotic tail), so the same `to_focal` operator is correct at every
    gap the optimizer explores -- nothing is re-derived for far-field
    convenience.

    ### Why Monte Carlo, and why the phase screens are fixed

    Incoherent superposition means intensities -- not fields -- add across
    mutually independent emitters. The model emulates that with $K$ *fixed*
    random phase screens $\psi_k$: build one coherent field per screen,
    propagate it through `to_focal`, square its magnitude, and average.
    Because the screens never change during training, the average is a
    deterministic, differentiable surrogate for the incoherent sum -- and it is
    what makes activation checkpointing exact (a recomputed bin reproduces the
    identical field).

    The same operator applied to the derivative fields
    $\partial U/\partial\sigma = \tfrac{1}{2}\,\big(\partial M/\partial\sigma\big)/\sqrt{M}\;e^{i\psi_k}$
    yields the intensity derivatives
    $\partial I/\partial\sigma = 2\,\mathrm{Re}\big\{\overline{\mathcal{L}U}\;\mathcal{L}U'\big\}$
    -- these are the $dx$/$dy$ channels that feed the Fisher information.

    ### Memory: checkpointed wavelength bins

    Rendering every wavelength bin keeps its FFT graph alive; 74 bins x 2
    screens x 3 fields at sensor pitch exceeds GPU memory. Each bin is
    therefore wrapped in `torch.utils.checkpoint`, trading one recomputation
    per bin for holding the whole graph.

    ### Grids: DOE cells vs. sensor pixels

    The thickness map is accepted on the DOE cell grid and resampled
    piecewise-constant (nearest) onto the sensor grid before the phase screen
    is formed -- one DOE structure, one block of detector pixels, exactly as it
    would be lithographed. Autograd flows through the resample, so the MLP
    still receives gradients on its own cell grid.
    """)
    return


@app.cell(hide_code=True)
def _(torch):
    def angular_spectrum_propagate(field, wavelength, distance, pixel_pitch):
        """Propagate a complex field a signed ``distance`` (m) on a Cartesian grid.

        Applies the band-limited angular-spectrum transfer function
        ``H = exp(i 2 pi distance / lambda * sqrt(1 - (lambda fx)^2 - (lambda fy)^2))``
        on the trailing two dimensions, so batched ``(N, H, W)`` fields
        propagate together. Evanescent components (where the square-root
        argument is negative) are zeroed.
        """
        h, w = field.shape[-2:]
        fy = torch.fft.fftfreq(h, d=pixel_pitch, device=field.device)
        fx = torch.fft.fftfreq(w, d=pixel_pitch, device=field.device)
        fy, fx = torch.meshgrid(fy, fx, indexing="ij")
        argument = 1.0 - (wavelength * fx) ** 2 - (wavelength * fy) ** 2
        propagating = argument.clamp_min(0.0)
        transfer = torch.exp(1j * (2 * torch.pi / wavelength) * distance * torch.sqrt(propagating))
        transfer = transfer * (argument >= 0).to(transfer.dtype)
        spectrum = torch.fft.fft2(field, norm="ortho")
        return torch.fft.ifft2(spectrum * transfer, norm="ortho")

    return (angular_spectrum_propagate,)


@app.cell(hide_code=True)
def _(angular_spectrum_propagate, torch):
    def to_focal(field, wavelength, doe_transmission, defocus, pixel_pitch):
        """Image a focal-plane field through the defocused DOE onto the sensor.

        The four-step chain from the section above: back-propagate by
        ``-defocus`` to the DOE plane, multiply by the DOE complex
        transmission ``exp(i phase)``, propagate by ``+defocus`` back to the
        focal plane (the interference there converts the chromatic phase into
        intensity), then apply the unit-magnification relay, which is a flip
        at sensor pitch.

        Returns the complex field at the sensor plane; callers form
        intensities ``abs(.).**2`` or the Fisher cross terms from it.
        """
        # Focal plane -> DOE plane.
        field = angular_spectrum_propagate(field, wavelength, -defocus, pixel_pitch)
        # The DOE imparts its chromatic phase.
        field = field * doe_transmission
        # DOE plane -> focal plane: phase becomes intensity here.
        field = angular_spectrum_propagate(field, wavelength, defocus, pixel_pitch)
        # 1:1 relay inversion.
        return torch.flip(field, dims=(-2, -1))

    return (to_focal,)


@app.cell(hide_code=True)
def _(nn, np, torch):
    class SineLayer(nn.Module):
        def __init__(self, in_features, out_features, bias=True, is_first=False, omega_0=30):
            super().__init__()
            self.omega_0 = omega_0
            self.is_first = is_first
            self.linear = nn.Linear(in_features, out_features, bias=bias)
            self.init_weights()

        def init_weights(self):
            with torch.no_grad():
                if self.is_first:
                    self.linear.weight.uniform_(-1 / self.linear.in_features, 
                                                 1 / self.linear.in_features)
                else:
                    self.linear.weight.uniform_(-np.sqrt(6 / self.linear.in_features) / self.omega_0, 
                                                 np.sqrt(6 / self.linear.in_features) / self.omega_0)

        def forward(self, x):
            return torch.sin(self.omega_0 * self.linear(x))


    class MaskThicknessMLP(nn.Module):
        def __init__(self, in_features=2, hidden_features=128, out_features=1):
            super().__init__()

            # 4-layer MLP as specified in the paper
            self.net = nn.Sequential(
                SineLayer(in_features, hidden_features, is_first=True),
                SineLayer(hidden_features, hidden_features),
                SineLayer(hidden_features, hidden_features),
                nn.Linear(hidden_features, out_features),
                nn.Softplus() # Enforce non-negative physical thickness
            )

            # Initialize final linear layer weights
            with torch.no_grad():
              self.net[3].weight.normal_(mean=0.0, std=0.02)
              self.net[3].bias.zero_()

        def forward(self, coords):
            # coords shape: (..., 2) representing (u, v)
            thickness = self.net(coords)
            return thickness

    return (MaskThicknessMLP,)


@app.cell(hide_code=True)
def _(DOE_GAP, SENSOR_PIXEL_PITCH, to_focal, torch):
    def generate_psf_stack(thickness_map, wavelengths, n_lambda, aperture_mask,
                           device, defocus=DOE_GAP, pixel_pitch=SENSOR_PIXEL_PITCH):
        """Near-field point-source PSF stack -- the quick intuition model.

        No Fraunhofer shortcut: the bench is deep in the Fresnel region (see
        the Fresnel-number estimate above), so the PSF is built from the same
        exact propagator as the Monte Carlo model. For a point source the
        lens's own Airy spot (~lambda * F-number, sub-pixel here) is a unit
        delta on the sensor-pitch grid; feeding that delta through ``to_focal``
        back-propagates a flat angular spectrum to the DOE plane, applies the
        chromatic mask ``aperture * exp(i 2pi/lambda (n-1) t)``, propagates
        back, and relays -- the near-field PSF per wavelength, normalized to
        unit flux.

        ``pixel_pitch`` must match the grid ``thickness_map`` lives on (pass
        DOE_PIXEL_PITCH for the MLP cell's map); ``defocus`` is the
        DOE-to-focal-plane offset delta (m).

        thickness_map: Tensor of shape (H, W) in meters
        wavelengths: Tensor of shape (K,) in meters
        n_lambda: Tensor of shape (K,) refractive index per wavelength
        aperture_mask: Binary transmission on the same grid
        """
        H, W = thickness_map.shape
        K = wavelengths.shape[0]
        wl = wavelengths.view(K, 1, 1).to(device=device, dtype=torch.float32)
        n_l = n_lambda.view(K, 1, 1).to(device=device, dtype=torch.float32)
        thickness = thickness_map.to(device=device, dtype=torch.float32)

        # Chromatic DOE transmission on the cell grid, stopped by the aperture.
        phase = (2 * torch.pi / wl) * (n_l - 1.0) * thickness
        doe = aperture_mask.to(device=device, dtype=torch.float32) * torch.exp(1j * phase)

        # Point source at the focal plane: unit delta at the array center.
        field = torch.zeros((K, H, W), device=device, dtype=torch.cfloat)
        field[:, H // 2, W // 2] = 1.0

        # Same -delta / DOE / +delta / relay chain the Monte Carlo model uses.
        relayed = to_focal(field, wl, doe, defocus, pixel_pitch)
        psf_stack = relayed.abs().square()

        # Normalize each PSF to sum to 1 (energy conservation).
        psf_stack = psf_stack / psf_stack.sum(dim=(-2, -1), keepdim=True)

        return psf_stack

    return (generate_psf_stack,)


@app.cell(hide_code=True)
def _(DOE_GAP_RANGE, SENSOR_PIXEL_PITCH, to_focal, torch):
    from torch.utils.checkpoint import checkpoint

    def generate_incoherent_relay_stack(
        thickness_map,
        wavelengths,
        n_lambda,
        morphology,
        d_morphology,
        d_morphology_y,
        pixel_pitch=SENSOR_PIXEL_PITCH,
        doe_offset=DOE_GAP_RANGE,
        monte_carlo_samples=4,
        random_phases=None,
        raw_gap=1,
    ):
        """Monte Carlo incoherent image formation through a near-focus DOE.

        Bench geometry: the 35 mm compound lens (working F-number ~1.65) forms
        its intermediate image at the focal plane; the DOE sits ``delta``
        before that plane (lens side); a unit-magnification 4f relay re-images
        the focal plane onto the sensor.

        Model, per wavelength:
          1. ``morphology`` is the focal-plane intensity. The field there is
             back-propagated (-delta) to the DOE plane.
          2. The DOE imparts its chromatic phase exp(i 2pi/lambda (n-1) t).
          3. The field is propagated (+delta) back to the focal plane. This
             propagation is where the phase converts into intensity: a phase
             mask placed in the plane that the relay images would cancel in
             |.|^2 and encode nothing.
          4. The relay is a 1:1 inversion on these grids -- its coherent
             cutoff (NA/lambda ~ 5.7e5 cy/m at f/1.65) exceeds the Nyquist of
             a 3.45 um pitch -- so it is applied as a flip.

        Steps 1-4 are the ``to_focal`` operator, shared verbatim with the
        hyperspectral evaluation pipeline so training and evaluation use the
        same physics.

        ``thickness_map`` may be a single (H, W) map or a per-frame (F, H, W)
        stack of windows of a larger DOE, so each frame samples the DOE region
        its object sits on. Fixed random phase screens emulate mutually
        incoherent spatial contributions; the derivative fields (dM/dsigma)
        pass through the same linear operator.

        The grid must run at (or below) the physical sensor pitch: the
        phase-to-intensity conversion over delta requires spatial frequencies
        with pi*lambda*delta*f^2 ~ 1, which a pooled-down grid cannot
        represent. ``thickness_map`` may be given on the coarser DOE cell
        grid; it is upsampled piecewise-constant onto the sensor grid here.
        """
        device = thickness_map.device
        dtype = thickness_map.dtype
        h, w = morphology.shape[-2:]

        if random_phases is None:
            random_phases = 2 * torch.pi * torch.rand(
                (monte_carlo_samples, morphology.shape[0], h, w),
                device=device,
                dtype=dtype,
            )
        else:
            random_phases = random_phases.to(device=device, dtype=dtype)
        # When phases are supplied by the training loop, their leading
        # dimension is authoritative. This avoids a mismatch with the
        # helper's standalone default.
        monte_carlo_samples = random_phases.shape[0]

        if thickness_map.ndim == 2:
            thickness = thickness_map[None].expand(morphology.shape[0], -1, -1)
        else:
            thickness = thickness_map

        # The DOE may live on its own cell grid (DOE_RASTER at
        # DOE_PIXEL_PITCH) coarser than the sensor simulation grid. Resample
        # piecewise-constant (nearest) so a single DOE structure covers a
        # block of detector pixels; autograd flows through the resample.
        if thickness.shape[-2:] != (h, w):
            thickness = torch.nn.functional.interpolate(
                thickness[:, None], size=(h, w), mode="nearest-exact"
            )[:, 0]

        z_min, z_max = doe_offset

        outputs = torch.zeros((morphology.shape[0], len(wavelengths), h, w), device=device, dtype=dtype)
        dx_outputs = torch.zeros_like(outputs)
        dy_outputs = torch.zeros_like(outputs)

        def wavelength_response(thickness_in, raw_gap_in, wavelength, index):
            """Incoherent Monte Carlo response for a single wavelength bin.

            During training this callable runs under activation checkpointing:
            the FFT graph for every wavelength bin and its phase screens is
            rebuilt one bin at a time in backward, instead of holding the
            whole ``wavelengths x monte_carlo_samples`` graph live at once.
            The fixed ``random_phases`` screens and the constant morphology
            fields make that recomputation deterministic.
            """
            raw_gap_in = torch.as_tensor(raw_gap_in, device=device, dtype=dtype)
            z_gap = z_min + (z_max - z_min) * torch.sigmoid(raw_gap_in)
            phase = (2 * torch.pi / wavelength) * (index - 1.0) * thickness_in
            doe = torch.exp(1j * phase)

            sample_images_sum = 0
            sample_dx_sum = 0
            sample_dy_sum = 0

            for s in range(monte_carlo_samples):
                random_phase = torch.exp(1j * random_phases[s])
                field = torch.sqrt(morphology.clamp_min(0.0)) * random_phase
                field_x = (0.5 * d_morphology / torch.sqrt(morphology.clamp_min(1e-12))) * random_phase
                field_y = (0.5 * d_morphology_y / torch.sqrt(morphology.clamp_min(1e-12))) * random_phase

                # to_focal: -delta to the DOE, apply doe, +delta back, relay flip.
                relay_field = to_focal(field, wavelength, doe, z_gap, pixel_pitch)
                relay_field_x = to_focal(field_x, wavelength, doe, z_gap, pixel_pitch)
                relay_field_y = to_focal(field_y, wavelength, doe, z_gap, pixel_pitch)

                sample_images_sum = sample_images_sum + torch.abs(relay_field).square()
                sample_dx_sum = sample_dx_sum + (2 * torch.real(torch.conj(relay_field) * relay_field_x))
                sample_dy_sum = sample_dy_sum + (2 * torch.real(torch.conj(relay_field) * relay_field_y))

            return (
                sample_images_sum / monte_carlo_samples,
                sample_dx_sum / monte_carlo_samples,
                sample_dy_sum / monte_carlo_samples,
            )

        for k, (wavelength, index) in enumerate(zip(wavelengths, n_lambda)):
            wavelength = wavelength.to(dtype=dtype)
            index = index.to(dtype=dtype)
            # Checkpoint only when a backward pass will actually consume the
            # graph; eval/no-grad calls take the direct path.
            trainable = torch.is_grad_enabled() and (
                thickness.requires_grad
                or (torch.is_tensor(raw_gap) and raw_gap.requires_grad)
            )
            if trainable:
                out_k, dx_k, dy_k = checkpoint(
                    wavelength_response,
                    thickness, raw_gap, wavelength, index,
                    use_reentrant=False,
                )
            else:
                out_k, dx_k, dy_k = wavelength_response(thickness, raw_gap, wavelength, index)

            outputs[:, k] = out_k
            dx_outputs[:, k] = dx_k
            dy_outputs[:, k] = dy_k

        return outputs, dx_outputs, dy_outputs

    return (generate_incoherent_relay_stack,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The simulated object

    The inverse design needs an *object* whose images it can score. Here it is a
    Gaussian blob of width $\sigma$ translating across the field of view over
    100 frames -- a stand-in for a point source scanned through the scene. Two
    things matter for the estimator:

    - Each frame's blob **centroid** is the position parameter to be localized.
      The analytic derivatives $\partial M/\partial\sigma_x$,
      $\partial M/\partial\sigma_y$ are the spatial *score components*: through
      the optical model they become $\partial I/\partial x$ and
      $\partial I/\partial y$, two of the three Fisher-information columns.
      (For a symmetric Gaussian, shifting the blob and widening it produce the
      same local intensity gradients, which is why $M\,x^2/\sigma^3$ appears.)
    - Because the blob *moves*, each frame samples a different patch of the
      DOE. Training therefore crops a sensor-pitch window around each centroid
      and the matching DOE-cell window from the full thickness map -- see the
      training section.
    """)
    return


@app.cell(hide_code=True)
def _(SENSOR_RASTER, WAVELENGTH_BAND_NM, WAVELENGTH_STEP_NM, np):
    wavelengths = np.arange(
        WAVELENGTH_BAND_NM[0], WAVELENGTH_BAND_NM[1], WAVELENGTH_STEP_NM
    )
    shape = SENSOR_RASTER
    x = np.arange(0, shape[1])
    y = np.arange(0, shape[0])

    # Increased sigma for macroscopic object dimensions
    sigma_x = 50.0 
    sigma_y = 50.0
    return shape, sigma_x, sigma_y, wavelengths, x, y


@app.cell(hide_code=True)
def _(np, shape, sigma_x, sigma_y, x, y):
    # Simulation parameters
    v_x = 500.0  # Velocity in x (px/s)
    v_y = 250.0  # Velocity in y (px/s)
    tau = 0.01  # 10 ms time interval (equivalent to 100 FPS)
    num_frames = 100 # Number of discrete time steps

    # Initialize stacks for the sequence
    M_stack = np.zeros((num_frames, shape[0], shape[1]))
    dM_dsigma_x_stack = np.zeros_like(M_stack)
    dM_dsigma_y_stack = np.zeros_like(M_stack)

    # Define the initial center coordinates
    x_center_init = shape[1] // 2
    y_center_init = shape[0] // 2

    for i in range(num_frames):
        t = i * tau

        # Calculate shifted geometric centers
        x_c = x_center_init + (v_x * t)
        y_c = y_center_init + (v_y * t)

        # Generate translated meshgrid
        xv, yv = np.meshgrid(x - x_c, y - y_c)

        # Calculate shifted morphology and analytical derivatives
        M = np.exp(-(xv**2) / (2 * sigma_x**2) - (yv**2) / (2 * sigma_y**2))

        M_stack[i] = M
        dM_dsigma_x_stack[i] = M * (xv**2) / (sigma_x**3)
        dM_dsigma_y_stack[i] = M * (yv**2) / (sigma_y**3)
    return M_stack, dM_dsigma_x_stack, dM_dsigma_y_stack


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Spectral encoding: the 1/lambda scaling and material dispersion

    The relief imprints the phase

    $$
    \phi(x, y; \lambda) = \frac{2\pi}{\lambda}\,\big[n(\lambda) - 1\big]\,h(x, y),
    $$

    and *two* distinct mechanisms make it wavelength-dependent. The first is
    the explicit $1/\lambda$: even a dispersionless material ($n = n_0$
    constant) gives $\phi \propto (n_0 - 1)h/\lambda$, so a fixed relief acts
    like a diffractive lens whose power scales with wavelength -- PSF
    structure varies across the band with no material dispersion at all. The
    second is the polymer's dispersion $n(\lambda)$ itself, which modulates
    the numerator and adds further (nonlinear) channel separation on top of
    the $1/\lambda$ scaling. The model carries both exactly: every phase
    screen is evaluated per spectral bin as $2\pi[n(\lambda_k) - 1]\,t/\lambda_k$
    (and the angular-spectrum transfer function contributes its own
    $\lambda$-dependence to the propagation).

    $n(\lambda)$ comes from a measured Cauchy table (an Excel file with
    columns `"Wavelength (m)"` and `"n"`), cubic-spline interpolated onto the
    simulation bins. A useful sanity check of the first mechanism: evaluate
    `generate_psf_stack` with a flat `n_lambda` -- the PSFs still change
    strongly across the band, purely from $1/\lambda$.

    In the editor, browse for a different material below; leave the browser
    empty to use `MATERIAL_XLSX`. Headless runs always read
    `[paths].material_xlsx` from the TOML -- the browser has no effect there.
    """)
    return


@app.cell(hide_code=True)
def _(MATERIAL_XLSX, Path, mo):
    # Browse for an alternative Cauchy table; the browser starts in the
    # configured material directory so it also works headless, where no
    # selection is possible and the interpolation cell falls back to
    # MATERIAL_XLSX.
    cauchy = mo.ui.file_browser(
        filetypes=['.csv', '.xls', '.xlsx'],
        initial_path=str(Path(MATERIAL_XLSX).resolve().parent),
    )
    cauchy
    return (cauchy,)


@app.cell(hide_code=True)
def _(CubicSpline, MATERIAL_XLSX, cauchy, pd, torch, wavelengths):
    # 1. Load the target material data: the file-browser selection overrides
    # the configured MATERIAL_XLSX default when a file is picked.
    material_path = cauchy.value[0].path if cauchy.value else MATERIAL_XLSX
    df = pd.read_excel(material_path)
    raw_wl = df['Wavelength (m)'].values
    raw_n = df['n'].values

    wavelengths_m = wavelengths * 1e-9

    # 3. Interpolate n(lambda) onto the 5nm simulation bins
    interpolator = CubicSpline(raw_wl, raw_n)
    n_interpolated = interpolator(wavelengths_m)

    # 4. Convert to PyTorch tensor for the forward model
    n_lambda = torch.tensor(n_interpolated, dtype=torch.float32)
    wavelengths_tensor = torch.tensor(wavelengths_m, dtype=torch.float32)

    print(f"Tensor shape: {n_lambda.shape}") # Should output torch.Size([74])
    wavelengths_tensor
    return n_lambda, wavelengths_tensor


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Parameterizing the design: a neural thickness map

    The DOE relief is stored as a **continuous function**, not a pixel array: a
    small MLP maps normalized DOE coordinates $(u, v) \in [-1, 1]^2$ to a
    thickness value. Its layers use sine activations,
    $x \mapsto \sin(\omega_0 W x + b)$ with $\omega_0 = 30$ -- a *SIREN*
    network, chosen because sinusoidal basis functions naturally represent the
    smooth, oscillatory phase profiles that diffractive optics care about; a
    ReLU net would bias the design toward piecewise-linear blazed gratings.
    A Softplus output keeps $t \geq 0$ (you cannot etch negative photoresist),
    and the final scale sets the height budget `DOE_MAX_THICKNESS`.

    Why a network instead of a free pixel map?

    - **Resolution independence** -- the same design evaluates on `DOE_RASTER`
      or on a finer fabrication grid.
    - **Smoothness prior** -- low-frequency structure is easier to lithograph
      and less prone to overfitting the Monte Carlo noise.
    - **Differentiability** -- gradients from the optical model flow straight
      into the geometry. This is the essence of inverse design: the design
      space is the network's weights, and the loss is a physics simulation.

    The cell below also builds the entrance `aperture_mask` from
    `APERTURE_TYPE`/`APERTURE_RADIUS_FRACTION` -- the stop applied to the DOE
    relief by the near-field point-source PSF model
    (`APERTURE_TYPE = "rect"` is simply always-open transmission 1).
    """)
    return


@app.cell(hide_code=True)
def _(
    APERTURE_RADIUS_FRACTION,
    APERTURE_TYPE,
    DOE_MAX_THICKNESS,
    DOE_RASTER,
    MaskThicknessMLP,
    torch,
):
    # The MLP parameterizes the DOE relief on its own cell grid; the
    # normalized coordinates span the full DOE physical extent.
    H, W = DOE_RASTER
    y_model = torch.linspace(-1, 1, H)
    x_model = torch.linspace(-1, 1, W)
    yy, xx = torch.meshgrid(y_model, x_model, indexing='ij')
    coords = torch.stack([xx, yy], dim=-1)

    mlp = MaskThicknessMLP()
    # Generate thickness map in meters, scaled by the configured peak relief.
    thickness_flat = mlp(coords.reshape(-1, 2))
    thickness_map = thickness_flat.reshape(H, W) * DOE_MAX_THICKNESS

    if APERTURE_TYPE == "circular":
        # Stop band outside a disk of radius APERTURE_RADIUS_FRACTION of
        # the half-width of the smaller raster dimension.
        radius_px = APERTURE_RADIUS_FRACTION * min(H, W) / 2.0
        rows = torch.arange(H, dtype=torch.float32)[:, None] - (H - 1) / 2.0
        cols = torch.arange(W, dtype=torch.float32)[None, :] - (W - 1) / 2.0
        aperture_mask = ((rows * rows + cols * cols) <= radius_px**2).float()
    elif APERTURE_TYPE == "rect":
        aperture_mask = torch.ones((H, W)) # Full rectangular aperture
    else:
        raise ValueError(
            f"unknown APERTURE_TYPE {APERTURE_TYPE!r}; use 'rect' or 'circular'"
        )

    # Near-field point-source PSF stack for quick intuition (no Monte Carlo).
    # The map lives on the DOE grid, so pass DOE_PIXEL_PITCH as the pitch:
    #psf_stack = generate_psf_stack(thickness_map, wavelengths_tensor, n_lambda,
    #                               aperture_mask, device, pixel_pitch=DOE_PIXEL_PITCH)
    #print("Generated PSF Stack Shape:", psf_stack.shape) # Expected: (K, H_doe, W_doe)
    return aperture_mask, coords, mlp


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The objective: Fisher information and the Cramer-Rao lower bound

    For Poisson photon counts with mean $\mu_p = N_{\mathrm{ph}} I_p(\theta) + b$
    at sensor pixel $p$, the Fisher information matrix of
    $\theta = (x, y, \lambda)$ is

    $$
    F_{ij} = \sum_p \frac{1}{\mu_p}\,
    \frac{\partial \mu_p}{\partial \theta_i}\,
    \frac{\partial \mu_p}{\partial \theta_j},
    \qquad
    \mathrm{Cov}(\hat\theta) \succeq F^{-1},
    $$

    the Cramer-Rao lower bound: no unbiased estimator can beat $F^{-1}$, so
    minimizing it makes *any* downstream decoder's job easier -- the objective
    is estimator-agnostic, which is what makes this an optimal-design problem
    rather than a learning problem.

    The three Jacobian columns are exactly what the optical model produced:
    $\partial I/\partial x$ and $\partial I/\partial y$ from the Monte Carlo
    derivative channels (the $2\,\mathrm{Re}\{\overline{\mathcal{L}U}\mathcal{L}U'\}$
    terms), and $\partial I/\partial\lambda$ from central differences across
    adjacent wavelength bins. Each column is pre-multiplied by a
    `parameter_scales` factor (50 nm, 50 nm, 100 nm) so $F$ is dimensionless
    and the three uncertainties enter the loss comparably; the returned CRLB
    diagonal is un-scaled back to $\mathrm{nm}^2$.

    **A-optimal design**: minimize $\mathrm{tr}\,F^{-1}$, the sum of the
    variance lower bounds. A tiny ridge keeps $F^{-1}$ finite in the first
    epochs, when the random-init DOE is nearly informationless and $F$ is
    singular.

    ### Cross-check against Shah et al. (CodedEvents)

    The paper derives the FI from the score variance (their Eq. (8)),
    $I(\theta)_{ij} = E[(\partial_i \log f)(\partial_j \log f)]$, for the
    *event-camera* measurement $O_t = \log\!\big(I_{t,b}/I_{t-\tau,b}\big)$
    -- a ratio of two Poisson frame sums. Two results matter here:

    - **Flashing source, their Eq. (10):** when the pre-interval frame is
      blank, the measurement reduces to $O_t = \log I_{t,b}$ and the FI is
      $$
      I_{ij} = \sum_n \frac{1}{h(n) + b}\,
      \frac{\partial h(n)}{\partial \theta_i}\,
      \frac{\partial h(n)}{\partial \theta_j},
      $$
      the standard Poisson FI, which the paper explicitly notes is "the same
      result" as the classical CMOS Fisher-mask formulation. This is exactly
      what `crlb_from_images` assembles: $h$ is the unit-flux PSF,
      $\mu_n = N_{\mathrm{ph}}\,h(n) + b$, and the Jacobian columns carry the
      $N_{\mathrm{ph}}$ factor.
    - **General case, their Eq. (12)-(13):** for non-blank intervals the
      Poisson *ratio* is approximated by a single Normal (Griffin's result),
      and evaluating the score variance under that Gaussian PDF yields the
      $a, b, c$ polynomial entries and the $1/[2(\mu\nu + \cdots)]$
      prefactor of Eq. (13).

    The Gaussian-PDF approximation exists **only because event cameras
    measure the log-ratio** -- and the hypercam *is* an event sensor, so the
    paper's generalization below, not just Eq. (10), is the design-relevant
    object. For comparison against the paper's Gaussian-style treatment of a
    frame-like readout -- and to fold in read/thermal noise --
    `crlb_from_images` also offers `noise_model="gaussian"`, which weights by
    $1/(\mu_n + \sigma_{\mathrm{read}}^2)$ with $\sigma_{\mathrm{read}}^2$
    taken equal to `background_photons` (the paper likewise "adds Gaussian
    noise to simulate other noise sources" in its simulations). The two
    coincide as the background term vanishes.

    ### Event-camera objective: Eq. (11)-(21), `sensor="event"` (default)

    The event measurement over one frame interval $\tau$ is
    $O_t = \log\!\big(I^b_t / I^b_{t-\tau}\big)$. The paper approximates the
    Poisson ratio (their Eq. (12)) by a single Normal,

    $$
    \frac{I^b_t}{I^b_{t-\tau}} \;\sim\;
    \mathcal{N}\!\left(\frac{\nu}{\mu},\; \frac{\nu}{\mu^2} + \frac{\nu^2}{\mu^3}\right),
    \qquad \mu = \lambda_{t-\tau},\;\; \nu = \lambda_t,
    $$

    and evaluates the score variance (Eq. (8)) under that PDF to get the
    per-pixel Fisher block of Eq. (13):
    $\mathcal{I}(\theta) = \sum_n \frac{\mathcal{D}\mathcal{D}^{\mathsf T}}{2(\mu+\nu)^2} \odot M$,
    where $M$ is the $6\times 6$ block matrix carrying $a$ over the
    previous-frame parameters, $c$ over the current-frame parameters, and $b$
    across, with (Eqs. (19)-(21))

    $$
    a = 2\mu^2\nu + 4\mu^2 + 2\mu\nu^2 + 12\mu\nu + 9\nu^2,\quad
    b = -(2\mu^2\nu + 2\mu^2 + 2\mu\nu^2 + 7\mu\nu + 6\nu^2),\quad
    c = 2\mu^2\nu + \mu^2 + 2\mu\nu^2 + 4\mu\nu + 4\nu^2,
    $$

    and the score vector (Eq. (18))

    $$
    \mathcal{D} = \big[\; \mu_x/\mu,\; \mu_y/\mu,\; \mu_\lambda/\mu,\;
    \nu_x/\nu,\; \nu_y/\nu,\; \nu_\lambda/\nu \;\big].
    $$

    The parameter set is six-dimensional -- position and wavelength at the
    *current and the previous frame*, $(x_t, y_t, \lambda_t, x_{t-\tau},
    y_{t-\tau}, \lambda_{t-\tau})$; we substitute the spectral parameter for
    the paper's depth $z$. `crlb_event_from_pairs` implements exactly this
    (the $a,b,c$ polynomials verified symbolically against the score variance
    of the Eq. (12) Normal), and `train_mask` with `sensor="event"` pairs
    consecutive strided frames automatically: the MC model already renders
    every frame, so each pair member gets its own mean image and $dx/dy$
    channels, and the loss is again an A-optimal trace, now over the six
    tracking parameters.

    The frame-integrating Poisson objective remains selectable with
    `sensor="frame"` -- the blinking-particle baseline of Eq. (10), useful
    for comparing what the event temporal structure adds.
    """)
    return


@app.cell(hide_code=True)
def _(torch):
    def crlb_from_images(
        mean_image, dx_image, dy_image, wavelengths_nm,
        photons_per_bin=1e5, background_photons=1.0, frame_stride=10,
        parameter_scales=(50.0, 50.0, 100.0), ridge=1e-8, eps=1e-12,
        spatial=True, spectral=True, noise_model="poisson"
    ):
        """Joint CRLB for images already generated by the optical model.

        Matches Eq. (10) of Shah et al. (CodedEvents, CVPR 2024) for its
        flashing-particle case -- which is this camera's regime. The photon
        count at pixel n is Poisson with mean

            mu_n = photons_per_bin * h(n) + background_photons,

        where h(n) is the unit-flux PSF intensity, so the exact Poisson
        Fisher information (score variance, their Eq. (8)-(10)) is

            I_ij = sum_n (1 / mu_n) * dmu_n/dtheta_i * dmu_n/dtheta_j,

        with columns dmu/dtheta = photons_per_bin * dh/dtheta: the dx/dy
        channels from the Monte Carlo derivative fields and dh/dlambda from
        central differences across bins. The paper notes this reduces to the
        classical CMOS Fisher-mask result -- the Gaussian-PDF machinery of
        its Eq. (12)-(13) (a Normal approximation to the *ratio* of two
        Poisson frame sums, giving the a/b/c polynomial entries of Eq. (13))
        is specific to event cameras, whose measurement is
        O_t = log(I_{t,b} / I_{t-tau,b}). For a frame-integrating readout no
        ratio appears, so the Poisson FI here is exact, not an approximation;
        the event-sensor version of this objective is
        ``crlb_event_from_pairs`` (selected via train_mask's sensor="event").

        ``noise_model`` selects the weighting inside the sum:
          "poisson"  -- 1/mu_n (default; exact for photon counting).
          "gaussian" -- Gaussian approximation with variance
                        sigma_n^2 = mu_n + background_photons, i.e. shot
                        noise plus a read/thermal floor (the paper adds
                        Gaussian noise in the same spirit for non-shot
                        sources). Identical to "poisson" when
                        background_photons -> 0.
        """
        mean_image = mean_image[::frame_stride]
        dx_image = dx_image[::frame_stride]
        dy_image = dy_image[::frame_stride]
        dlambda = wavelengths_nm[2:] - wavelengths_nm[:-2]
        wavelength_image = (mean_image[:, 2:] - mean_image[:, :-2]) / dlambda[None, :, None, None]
        expected = photons_per_bin * mean_image[:, 1:-1] + background_photons
        scales = torch.as_tensor(parameter_scales, device=mean_image.device, dtype=mean_image.dtype)
        spatial_jacobian = torch.stack((
            photons_per_bin * dx_image[:, 1:-1],
            photons_per_bin * dy_image[:, 1:-1],
        ), dim=-1)

        # Keep the parameter dimension explicit.  The selected parameters are
        # the two spatial coordinates followed by wavelength, so this works
        # for all four combinations of ``spatial`` and ``spectral``.
        jacobian_parts = []
        selected_scales = []
        if spatial:
            jacobian_parts.append(spatial_jacobian)
            selected_scales.append(scales[:2])
        if spectral:
            jacobian_parts.append((photons_per_bin * wavelength_image).unsqueeze(-1))
            selected_scales.append(scales[2:3])
        if not jacobian_parts:
            raise ValueError("at least one of spatial or spectral must be enabled")

        jacobian = torch.cat(jacobian_parts, dim=-1)
        selected_scales = torch.cat(selected_scales)
        jacobian = jacobian * selected_scales
        if noise_model == "poisson":
            # Exact Poisson score variance, Eq. (10) of Shah et al.
            weights = 1.0 / expected.clamp_min(eps)
        elif noise_model == "gaussian":
            # Gaussian approximation: shot noise plus a read/thermal floor.
            variance = expected + background_photons
            weights = 1.0 / variance.clamp_min(eps)
        else:
            raise ValueError(f"unknown noise_model {noise_model!r}; use 'poisson' or 'gaussian'")
        jacobian = jacobian.reshape(-1, jacobian.shape[-1])
        weights = weights.reshape(-1)
        fisher = torch.einsum("ni,nj,n->ij", jacobian, jacobian, weights)
        identity = torch.eye(jacobian.shape[-1], device=fisher.device, dtype=fisher.dtype)
        scaled_covariance = torch.linalg.solve(fisher + ridge * identity, identity)
        covariance = (
            scaled_covariance
            * selected_scales[:, None]
            * selected_scales[None, :]
        )
        return torch.diagonal(covariance), fisher

    return (crlb_from_images,)


@app.cell
def _(torch):
    def crlb_event_from_pairs(
        mean_prev, mean_cur, dx_prev, dy_prev, dx_cur, dy_cur, wavelengths_nm,
        photons_per_bin=1e5, background_photons=1.0,
        parameter_scales=(50.0, 50.0, 100.0, 50.0, 50.0, 100.0),
        ridge=1e-8, eps=1e-12, spatial=True, spectral=True,
    ):
        """Event-camera CRLB: Eq. (13)-(21) of Shah et al. (CodedEvents).

        The sensor reports O_t = log(I^b_t / I^b_{t-tau}), a per-pixel ratio
        of two Poisson frame sums. Following the paper, the ratio is
        approximated by a single Normal (their Eq. (12))

            ratio ~ N(nu/mu, nu/mu^2 + nu^2/mu^3),

        with mu = photons_per_bin*h_prev + b (previous frame, their
        lambda_{t-tau}, Eq. (14)) and nu = photons_per_bin*h_cur + b (current
        frame, their lambda_t, Eq. (15)). Evaluating the score variance
        (their Eq. (8)) under that PDF gives the per-pixel Fisher block

            I_ij = sum_n [1 / (2 (mu_n + nu_n)^2)] D_ni D_nj M_ij(n),

        where M carries a = 2mu^2 nu + 4mu^2 + 2mu nu^2 + 12mu nu + 9nu^2
        (their Eq. 19) over the previous-frame parameter block,
        b = -(2mu^2 nu + 2mu^2 + 2mu nu^2 + 7mu nu + 6nu^2) (Eq. 20) across
        blocks, and c = 2mu^2 nu + mu^2 + 2mu nu^2 + 4mu nu + 4nu^2 (Eq. 21)
        over the current-frame block, with the score vector

            D = [mu_x/mu, mu_y/mu, mu_lam/mu, nu_x/nu, nu_y/nu, nu_lam/nu]

        (Eq. 18, depth z replaced by wavelength for this hyperspectral
        bench). Parameters: (x_t, y_t, lam_t, x_{t-tau}, y_{t-tau},
        lam_{t-tau}); the diagonal CRLB follows in the same order after
        applying ``parameter_scales``.

        Inputs are matched pairs of MC-model stacks: ``*_prev`` frames
        (P, K, H, W) and ``*_cur`` frames (P, K, H, W) with P = number of
        consecutive-frame pairs; dx/dy are the model's derivative channels
        (dM/dsigma fields) and the wavelength column is a central difference
        across bins.
        """
        dlambda = wavelengths_nm[2:] - wavelengths_nm[:-2]
        mu = (photons_per_bin * mean_prev[:, 1:-1] + background_photons).clamp_min(eps)
        nu = (photons_per_bin * mean_cur[:, 1:-1] + background_photons).clamp_min(eps)
        wavelength_prev = (mean_prev[:, 2:] - mean_prev[:, :-2]) / dlambda[None, :, None, None]
        wavelength_cur = (mean_cur[:, 2:] - mean_cur[:, :-2]) / dlambda[None, :, None, None]

        scales = torch.as_tensor(parameter_scales, device=mean_prev.device, dtype=mean_prev.dtype)
        # Score components D_i = (1/mu) dmu/dtheta_i for the previous-frame
        # parameters and (1/nu) dnu/dtheta_i for the current-frame ones.
        u_parts, v_parts, s_u, s_v = [], [], [], []
        if spatial:
            u_parts.append(photons_per_bin * dx_prev[:, 1:-1])
            v_parts.append(photons_per_bin * dx_cur[:, 1:-1])
            s_u.append(scales[0]); s_v.append(scales[3])
            u_parts.append(photons_per_bin * dy_prev[:, 1:-1])
            v_parts.append(photons_per_bin * dy_cur[:, 1:-1])
            s_u.append(scales[1]); s_v.append(scales[4])
        if spectral:
            u_parts.append(photons_per_bin * wavelength_prev)
            v_parts.append(photons_per_bin * wavelength_cur)
            s_u.append(scales[2]); s_v.append(scales[5])
        if not u_parts:
            raise ValueError("at least one of spatial or spectral must be enabled")
        s_u = torch.stack(s_u)
        s_v = torch.stack(s_v)

        U = (torch.stack(u_parts, dim=-1) / mu[..., None] * s_u).reshape(-1, len(u_parts))
        V = (torch.stack(v_parts, dim=-1) / nu[..., None] * s_v).reshape(-1, len(v_parts))
        mu_flat = mu.reshape(-1)
        nu_flat = nu.reshape(-1)
        weight = 0.5 / (mu_flat + nu_flat).square()
        a = (2 * mu_flat.square() * nu_flat + 4 * mu_flat.square()
             + 2 * mu_flat * nu_flat.square() + 12 * mu_flat * nu_flat + 9 * nu_flat.square())
        b = -(2 * mu_flat.square() * nu_flat + 2 * mu_flat.square()
              + 2 * mu_flat * nu_flat.square() + 7 * mu_flat * nu_flat + 6 * nu_flat.square())
        c = (2 * mu_flat.square() * nu_flat + mu_flat.square()
             + 2 * mu_flat * nu_flat.square() + 4 * mu_flat * nu_flat + 4 * nu_flat.square())
        wa, wb, wc = weight * a, weight * b, weight * c

        # Assemble the 6x6 Eq. (13) block matrix: a over the previous-frame
        # score block, c over the current-frame block, b across.
        n_u, n_v = U.shape[-1], V.shape[-1]
        fisher = torch.zeros(n_u + n_v, n_u + n_v, device=U.device, dtype=U.dtype)
        fisher[:n_u, :n_u] = torch.einsum("ni,n,nj->ij", U, wa, U)
        fisher[:n_u, n_u:] = torch.einsum("ni,n,nj->ij", U, wb, V)
        fisher[n_u:, :n_u] = torch.einsum("ni,n,nj->ij", V, wb, U)
        fisher[n_u:, n_u:] = torch.einsum("ni,n,nj->ij", V, wc, V)
        identity = torch.eye(fisher.shape[-1], device=fisher.device, dtype=fisher.dtype)
        scaled_covariance = torch.linalg.solve(fisher + ridge * identity, identity)
        selected_scales = torch.cat((s_u, s_v))
        covariance = (
            scaled_covariance
            * selected_scales[:, None]
            * selected_scales[None, :]
        )
        return torch.diagonal(covariance), fisher

    return (crlb_event_from_pairs,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Training loop: back-propagating through wave optics

    `train_mask` is the inverse-design engine. One epoch:

    1. **Evaluate the design** -- the MLP is queried at every DOE cell center,
       giving `thickness_full` on `DOE_RASTER` (meters).
    2. **Crop windows** -- for each frame, the sensor-patch around the blob
       centroid and the *physically aligned* DOE-cell window (patch starts are
       snapped to DOE cell boundaries so the two windows cover the same region).
    3. **Render** -- `generate_incoherent_relay_stack` produces the mean image
       and the $dx$/$dy$ derivative channels; each wavelength bin runs under
       activation checkpointing (memory), recomputing its FFT graph in
       backward.
    4. **Score** -- the objective is chosen by ``sensor``: ``"event"`` pairs
       consecutive frames and assembles the six-parameter log-ratio Fisher
       matrix of Eq. (13) (`crlb_event_from_pairs`); ``"frame"`` uses the
       blinking-particle Poisson CRLB of Eq. (10) (`crlb_from_images`).
       Either way the loss is the trace of the CRLB (A-optimal design).
    5. **Descend** -- Adam updates the MLP weights *and* the defocus gap. The
       gap is stored as a logit and squashed into `DOE_GAP_RANGE` by a
       sigmoid, so no update can leave the physical interval; gradients are
       norm-clipped because the CRLB surface is rough early on.

    Every epoch that improves the loss snapshots the weights, DOE windows,
    image stack, and gap -- the diagnostics and export cells use the *best*
    epoch, not the last one. All knobs (epochs, learning rate, patch size,
    photon budget, which parameters to optimize, ...) are keyword arguments
    with defaults set in the config cell's `TRAINING_CONFIG`, overridable by
    the TOML `[training]` section.
    """)
    return


@app.cell(hide_code=True)
def _(
    DOE_GAP,
    DOE_GAP_RANGE,
    DOE_MAX_THICKNESS,
    DOE_PIXEL_PITCH,
    SENSOR_PIXEL_PITCH,
    crlb_event_from_pairs,
    crlb_from_images,
    nn,
    torch,
):
    def train_mask(
        mlp,
        coords,
        wavelengths,
        n_lambda,
        aperture_mask,
        generate_psf_stack,
        generate_incoherent_relay_stack,
        morphology,
        d_morphology,
        d_morphology_y,
        epochs=1000,
        learning_rate=1e-4,
        photons_per_bin=1e5,
        background_photons=1.0,
        patch_size=256,
        print_every=100,
        monte_carlo_samples=2,
        frame_stride=10,
        trainable_gap=True,
        initial_gap=DOE_GAP,
        random_seed=None,
        doe_offset=DOE_GAP_RANGE,
        optim_space=True,
        optim_spectral=True,
        noise_model="poisson",
        sensor="event",
    ):
        """Optimize a near-focus image-plane DOE with fixed-phase incoherent MC.

        ``sensor`` selects the estimation objective: "event" scores
        consecutive frame pairs with the event-camera log-ratio Fisher
        information of Shah et al. Eq. (13) (six parameters: x, y, wavelength
        at the current and previous frame); "frame" uses the frame-based
        Poisson CRLB (their blinking-particle Eq. (10)), weighted per
        ``noise_model``.

        The simulation runs at the physical sensor pitch on a ``patch_size``
        window cropped around each frame's blob centroid: near-focus
        phase-to-intensity conversion needs spatial frequencies that a pooled
        grid cannot represent. The matching DOE windows are cropped from the
        full thickness map on the DOE cell grid every epoch, so each frame
        samples the mask region its object sits on. Sensor patches are snapped
        to DOE cell boundaries so the two windows cover the same physical
        region.
        """
        z_min, z_max = doe_offset
        initial_position = torch.as_tensor(
            (initial_gap - z_min) / (z_max - z_min),
            device=coords.device, dtype=coords.dtype,
        ).clamp(1e-5, 1 - 1e-5)
        raw_gap_value = torch.logit(initial_position)
        raw_gap = nn.Parameter(raw_gap_value, requires_grad=trainable_gap)
        parameters = list(mlp.parameters()) + ([raw_gap] if trainable_gap else [])
        optimizer = torch.optim.Adam(parameters, lr=learning_rate)
        history = []
        best_loss = float('inf')
        best_thickness = None
        best_psf = None
        best_gap = None
        best_state = None
        flat_coords = coords.reshape(-1, 2)
        p = patch_size
        morphology = morphology[::frame_stride]
        d_morphology = d_morphology[::frame_stride]
        d_morphology_y = d_morphology_y[::frame_stride]

        # Locate each frame's blob by its intensity centroid so the sensor-pitch
        # patch can follow the object across the DOE.
        with torch.no_grad():
            weight = morphology.clamp_min(0.0)
            norm = weight.sum(dim=(-2, -1)).clamp_min(1e-12)
            rows = torch.arange(weight.shape[-2], device=weight.device, dtype=weight.dtype)
            cols = torch.arange(weight.shape[-1], device=weight.device, dtype=weight.dtype)
            centroid_y = (weight.sum(-1) * rows).sum(-1) / norm
            centroid_x = (weight.sum(-2) * cols).sum(-1) / norm
        full_h, full_w = morphology.shape[-2:]
        doe_h, doe_w = coords.shape[:2]
        # Detector pixels covered by one DOE cell per side.
        sensor_px_per_doe_cell = DOE_PIXEL_PITCH / SENSOR_PIXEL_PITCH
        p_doe = min(max(1, int(round(p / sensor_px_per_doe_cell))), doe_h, doe_w)
        windows = []      # sensor-pitch patches: (y0, x0), size p
        doe_windows = []  # DOE-cell windows: (y0, x0), size p_doe
        for i in range(morphology.shape[0]):
            y0_d = int(torch.round((centroid_y[i] - p / 2) / sensor_px_per_doe_cell))
            x0_d = int(torch.round((centroid_x[i] - p / 2) / sensor_px_per_doe_cell))
            y0_d = max(0, min(y0_d, doe_h - p_doe))
            x0_d = max(0, min(x0_d, doe_w - p_doe))
            # Snap the sensor patch to the DOE cell start so both windows
            # cover the same physical region.
            y0 = max(0, min(int(round(y0_d * sensor_px_per_doe_cell)), full_h - p))
            x0 = max(0, min(int(round(x0_d * sensor_px_per_doe_cell)), full_w - p))
            windows.append((y0, x0))
            doe_windows.append((y0_d, x0_d))

        def crop_stack(stack):
            return torch.stack([stack[i, y0:y0 + p, x0:x0 + p] for i, (y0, x0) in enumerate(windows)])

        morphology = crop_stack(morphology)
        d_morphology = crop_stack(d_morphology)
        d_morphology_y = crop_stack(d_morphology_y)

        if random_seed is not None:
            generator = torch.Generator(device=morphology.device)
            generator.manual_seed(random_seed)
        else:
            generator = None
        random_phases = 2 * torch.pi * torch.rand(
            (monte_carlo_samples, morphology.shape[0], p, p),
            device=morphology.device, dtype=coords.dtype,
            generator=generator,
        )

        for epoch in range(epochs):
            optimizer.zero_grad(set_to_none=True)
            thickness_full = mlp(flat_coords).reshape(coords.shape[:2]) * DOE_MAX_THICKNESS
            thickness_windows = torch.stack(
                [thickness_full[y0:y0 + p_doe, x0:x0 + p_doe] for (y0, x0) in doe_windows]
            )
            mean_image, dx_image, dy_image = generate_incoherent_relay_stack(
                thickness_windows, wavelengths, n_lambda,
                morphology,
                d_morphology,
                d_morphology_y,
                doe_offset=doe_offset,
                random_phases=random_phases,
                raw_gap=raw_gap
            )
            if sensor == "event":
                # Consecutive (strided) frames form the log-ratio pairs the
                # event measurement compares.
                if mean_image.shape[0] < 2:
                    raise ValueError(
                        "event FI needs at least two frames to form a pair; "
                        "reduce frame_stride or add frames"
                    )
                crlb, fisher = crlb_event_from_pairs(
                    mean_image[:-1], mean_image[1:],
                    dx_image[:-1], dx_image[1:],
                    dy_image[:-1], dy_image[1:], wavelengths * 1e9,
                    photons_per_bin=photons_per_bin,
                    background_photons=background_photons,
                    spatial=optim_space, spectral=optim_spectral,
                )
            else:
                crlb, fisher = crlb_from_images(
                    mean_image, dx_image, dy_image, wavelengths * 1e9,
                    photons_per_bin=photons_per_bin,
                    background_photons=background_photons,
                    frame_stride=1, spatial=optim_space, spectral=optim_spectral,
                    noise_model=noise_model
                )
            # Joint A-optimal design: minimize the sum of diagonal CRLBs.
            loss = crlb.sum()
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite CRLB loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, max_norm=10.0)
            optimizer.step()
            history.append(float(loss.detach()))

            if loss.item() < best_loss:
                best_loss = loss.detach().item()
                # Keep snapshots for visualization without retaining the
                # current epoch's autograd/FFT graph.
                best_thickness = thickness_windows.detach().clone()
                best_psf = mean_image.detach().clone()
                best_gap = raw_gap.detach().clone()
                best_state = {
                    name: value.detach().clone() for name, value in mlp.state_dict().items()
                }

            if print_every and (epoch == 0 or (epoch + 1) % print_every == 0):
                print(
                    f"epoch {epoch + 1:5d}/{epochs}: "
                    f"mean CRLB={history[-1]:.5g} nm^2, "
                    f"mean FI={float(fisher.mean().detach()):.5g}"
                )

        return history, best_loss, best_thickness, best_psf, best_gap, best_state

    return (train_mask,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Run the inverse design

    The cell below executes the loop on the GPU (or CPU fallback), then
    restores the best-epoch weights and regenerates the **full** DOE map --
    the training windows are only patches, but fabrication and evaluation need
    the complete `DOE_RASTER` relief. Set `RUN_TRAINING = False` (or the TOML
    `[run].run_training`) to skip it and reuse the saved artifacts.
    """)
    return


@app.cell(hide_code=True)
def _(
    DOE_MAX_THICKNESS,
    M_stack,
    RUN_TRAINING,
    TRAINING_CONFIG,
    aperture_mask,
    coords,
    dM_dsigma_x_stack,
    dM_dsigma_y_stack,
    device,
    generate_incoherent_relay_stack,
    generate_psf_stack,
    mlp,
    n_lambda,
    torch,
    train_mask,
    wavelengths_tensor,
):
    if RUN_TRAINING:
        with torch.amp.autocast('cuda', enabled=False):
            history, loss, thickness, psf, gap, best_state = train_mask(
                mlp.to(device),
                coords.to(device),
                wavelengths_tensor.to(device),
                n_lambda.to(device),
                aperture_mask.to(device),
                generate_psf_stack,
                generate_incoherent_relay_stack,
                torch.from_numpy(M_stack).to(device),
                torch.from_numpy(dM_dsigma_x_stack).to(device),
                torch.from_numpy(dM_dsigma_y_stack).to(device),
                # All optimizer/simulation knobs come from TRAINING_CONFIG:
                # the defaults above plus any [training] TOML overrides.
                **TRAINING_CONFIG,
            )
        # Restore the best-epoch weights and regenerate the full DOE map used
        # by the saved profile and the hyperspectral evaluation pipeline.
        mlp.load_state_dict(best_state)
        with torch.no_grad():
            thickness_full = (
                mlp(coords.reshape(-1, 2).to(device)).reshape(coords.shape[:2]) * DOE_MAX_THICKNESS
            ).cpu()
    else:
        history, loss, thickness, psf, gap, best_state = [], float('inf'), None, None, None, None
        thickness_full = None
    return gap, psf, thickness, thickness_full


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Reading the diagnostics

    **Phase panels** (left column of the first figure): the DOE window
    thickness, the wrapped phase $\phi \bmod 2\pi$, and the phase in *cycles*
    -- all at 550 nm on the DOE cell grid. The cycles panel is the one to look
    at for manufacturability: plateaus separated by steep jumps are blazed
    grating structures; anything beyond a few waves is aliasing territory.

    **Intensity panels** (right column): the Monte Carlo mean PSF at 550 nm,
    its logarithm (where the speckle-like sidelobe structure is visible), and
    the wavelength-averaged output. The second figure compares the outputs at
    the band edges -- the difference image *is* the spectral encoding this
    design produces. If the 380 nm and 750 nm PSFs look identical, the design
    is not encoding color and the spectral CRLB will reflect it.

    Both panels span the same physical patch; extents are drawn in microns on
    each grid's own pitch.
    """)
    return


@app.cell(hide_code=True)
def _(
    DOE_GAP_RANGE,
    DOE_PIXEL_PITCH,
    SENSOR_PIXEL_PITCH,
    gap,
    mo,
    n_lambda,
    psf,
    thickness,
    torch,
    wavelengths_tensor,
):
    from matplotlib import pyplot as plt
    def _():
        """Diagnostic plots for DOE phase and propagated incoherent intensity."""
        z_min, z_max = DOE_GAP_RANGE
        if thickness is not None and psf is not None:
            z = z_min + (z_max - z_min) * torch.sigmoid(gap)
            print(f"Optimal z distance: {z.detach().cpu().item()}" )
            # ``thickness`` is the per-frame DOE window stack [frame, y, x] on
            # the DOE cell grid; ``psf`` is the [frame, wavelength, y, x] stack
            # on the sensor grid. Both span the same physical patch.
            image_stack = psf.detach().cpu()
            thickness_window = thickness.detach().cpu()[0]

            frame_index = 0
            wavelength_index = int(torch.argmin(torch.abs(
                wavelengths_tensor.detach().cpu() - 550e-9
            )))
            wavelength = wavelengths_tensor[wavelength_index].detach().cpu()
            refractive_index = n_lambda[wavelength_index].detach().cpu()

            phase = (
                2 * torch.pi / wavelength
                * (refractive_index - 1.0)
                * thickness_window
            )
            wrapped_phase = torch.angle(torch.exp(1j * phase))
            phase_cycles = phase / (2 * torch.pi)
            intensity = image_stack[frame_index, wavelength_index]
            log_intensity = torch.log10(intensity.clamp_min(1e-12))

            fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
            # Each grid gets its own physical pitch; both extents cover the
            # same patch of the scene.
            extent_doe = [0, thickness_window.shape[1] * DOE_PIXEL_PITCH * 1e6,
                          thickness_window.shape[0] * DOE_PIXEL_PITCH * 1e6, 0]
            extent_sensor = [0, intensity.shape[1] * SENSOR_PIXEL_PITCH * 1e6,
                             intensity.shape[0] * SENSOR_PIXEL_PITCH * 1e6, 0]

            plots = [
                (thickness_window * 1e6, extent_doe, "viridis", "Thickness (µm)", "DOE window thickness"),
                (wrapped_phase, extent_doe, "twilight", None, "Wrapped DOE phase"),
                (phase_cycles, extent_doe, "RdBu_r", None, "DOE phase (cycles)"),
                (intensity, extent_sensor, "gray", None, "Mean output intensity"),
                (log_intensity, extent_sensor, "magma", None, "Log output intensity"),
                (image_stack[frame_index].mean(0), extent_sensor, "gray", None,
                 "Wavelength-averaged intensity"),
            ]
            for ax, (data, extent, cmap, label, title) in zip(axes.flat, plots):
                im = ax.imshow(data.numpy(), extent=extent, cmap=cmap, aspect="auto")
                ax.set_title(title)
                ax.set_xlabel(r"x ($\mu$m)")
                ax.set_ylabel(r"y ($\mu$m)")
                if label is not None:
                    fig.colorbar(im, ax=ax, label=label, shrink=0.85)
                else:
                    fig.colorbar(im, ax=ax, shrink=0.85)

            fig.suptitle(f"DOE diagnostics at {wavelength.item() * 1e9:.0f} nm")
            return mo.mpl.interactive(fig)
        else:
            return print("Run training first to generate thickness and image-stack diagnostics.")


    _()
    return (plt,)


@app.cell(hide_code=True)
def _(n_lambda, plt, psf, thickness, torch, wavelengths_tensor):
    def _():
        """Multi-wavelength phase and per-wavelength output diagnostics."""
        if thickness is not None and psf is not None:
            thickness_window = thickness[0].detach()
            wavelength_indices = torch.linspace(
                0, wavelengths_tensor.numel() - 1, 5, dtype=torch.long
            )
            fig, axes = plt.subplots(2, 5, figsize=(18, 7), constrained_layout=True)
            for column, k in enumerate(wavelength_indices.tolist()):
                phase = (2 * torch.pi / wavelengths_tensor[k]) * (n_lambda[k] - 1.0) * thickness_window
                wrapped = torch.angle(torch.exp(1j * phase)).cpu()
                cycles = (phase / (2 * torch.pi)).cpu()
                wavelength_nm = wavelengths_tensor[k].item() * 1e9
                im0 = axes[0, column].imshow(wrapped, cmap="twilight", vmin=-torch.pi, vmax=torch.pi)
                axes[0, column].set_title(f"{wavelength_nm:.0f} nm")
                fig.colorbar(im0, ax=axes[0, column], shrink=0.75, label="rad")
                im1 = axes[1, column].imshow(cycles, cmap="RdBu_r")
                fig.colorbar(im1, ax=axes[1, column], shrink=0.75, label="cycles")
            fig.suptitle("DOE phase variation across wavelength")
            plt.show()

            # Per-wavelength sensor images and their difference: the spectral
            # encoding this design actually produces.
            image_stack = psf[0].detach().cpu()
            lo = image_stack[0]
            hi = image_stack[-1]
            fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
            axes[0].imshow(thickness_window.cpu() * 1e6, cmap="viridis")
            axes[0].set_title("DOE window thickness (µm)")
            axes[1].imshow(lo / lo.max(), cmap="gray")
            axes[1].set_title(f"Output @ {wavelengths_tensor[0].item() * 1e9:.0f} nm")
            diff = (hi - lo) / lo.max()
            im2 = axes[2].imshow(diff, cmap="RdBu_r", vmin=-0.5, vmax=0.5)
            axes[2].set_title(f"Output diff @ {wavelengths_tensor[-1].item() * 1e9:.0f} nm")
            fig.colorbar(im2, ax=axes[2], shrink=0.8)
            for ax in axes[:2]:
                ax.set_axis_off()
        return plt.show()


    _()
    return


@app.cell(hide_code=True)
def _(
    M_stack,
    MaskThicknessMLP,
    RUN_DEBUG_TRAINING,
    coords,
    dM_dsigma_x_stack,
    dM_dsigma_y_stack,
    device,
    generate_incoherent_relay_stack,
    generate_psf_stack,
    mlp,
    n_lambda,
    plt,
    torch,
    train_mask,
    wavelengths_tensor,
):
    def _():
        """Optional short runs for testing seed/Monte Carlo stability."""
        debug_results = {}
        if RUN_DEBUG_TRAINING:
            base_state = {name: value.detach().clone() for name, value in mlp.state_dict().items()}
            for monte_carlo_samples, seed in ((1, 0), (1, 1), (4, 0)):
                debug_model = MaskThicknessMLP().to(device)
                debug_model.load_state_dict(base_state)
                result = train_mask(
                    debug_model, coords.to(device), wavelengths_tensor.to(device), n_lambda.to(device),
                    torch.ones_like(torch.from_numpy(M_stack[0]).to(device)),
                    generate_psf_stack, generate_incoherent_relay_stack,
                    torch.from_numpy(M_stack).to(device), torch.from_numpy(dM_dsigma_x_stack).to(device),
                    torch.from_numpy(dM_dsigma_y_stack).to(device), epochs=20, learning_rate=1e-4,
                    patch_size=128, monte_carlo_samples=monte_carlo_samples, random_seed=seed, print_every=0,
                )
                debug_results[(monte_carlo_samples, seed)] = result[0]
            fig, ax = plt.subplots(figsize=(8, 4))
            for (samples, seed), history in debug_results.items():
                ax.plot(history, label=f"MC={samples}, seed={seed}")
            ax.set(xlabel="Epoch", ylabel="CRLB loss", title="Debug training stability")
            ax.legend(); ax.grid(True, alpha=0.3); plt.show()
        else:
            return print("Debug training disabled. Set RUN_DEBUG_TRAINING=True to run it.")


    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Exporting the mask for fabrication and evaluation

    Three artifacts, written to the working directory:

    - `profile.npy` -- the full thickness map on `DOE_RASTER`, in meters, at
      `DOE_PIXEL_PITCH`. This is the fabrication input: one DOE cell per array
      element, piecewise-constant by construction.
    - `psf.npy` -- the best-epoch sensor-pitch image stack
      (frame x wavelength x y x x), for offline analysis.
    - `gap.npy` -- the *learned* DOE-to-focal-plane offset. The evaluation
      pipeline reads it so the simulated bench matches the design that was
      actually optimized, rather than the nominal `DOE_GAP`.
    """)
    return


@app.cell(hide_code=True)
def _(DOE_GAP_RANGE, SAVE, gap, np, psf, thickness_full, torch):
    if SAVE and thickness_full is not None:
        # Full DOE thickness map (DOE_RASTER at DOE_PIXEL_PITCH, meters) for the
        # hyperspectral evaluation pipeline, plus the trained DOE-to-focal-plane
        # offset so evaluation uses the gap that was actually optimized.
        np.save("profile", thickness_full.numpy())
        np.save("psf", psf.cpu().numpy())
        z_min, z_max = DOE_GAP_RANGE
        np.save("gap", z_min + (z_max - z_min) * float(torch.sigmoid(gap)))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Evaluation on real hyperspectral video

    The trained relief is applied to the DynaSpec *running-frog* cube with
    **the same physics used in training** -- `to_focal` -- so the video shows
    what the designed camera would actually record, not a different model. The
    pipeline is deliberately streaming, because a hyperspectral video does not
    fit in memory:

    - `transform_hyperspectral_slice` -- one wavelength slice through the DOE:
      resample the DOE raster onto the slice raster (piecewise-constant),
      draw fixed random phase screens, propagate, square. Runs under
      `inference_mode` on the GPU, one slice at a time.
    - `iter_hyperspectral_mat` -- one temporal frame's MAT file (v7.3/HDF5):
      the files are chunked with *all* wavelengths per chunk, so one frame is
      loaded into CPU RAM once and slices are moved to the GPU individually.
    - `iter_hyperspectral_sequence` -- every numbered MAT frame in a directory.
    - `transform_hyperspectral_sequence` -- per temporal frame, sums the
      transformed spectral slices on the CPU (the coded-aperture exposure:
      all bands hit the sensor simultaneously) and writes `frame_*.npy`.

    `monte_carlo_samples` controls the incoherent-sum averaging; 4 is a good
    speed/quality trade for video.
    """)
    return


@app.cell(hide_code=True)
def _(DOE_GAP, SENSOR_PIXEL_PITCH, to_focal, torch):
    def transform_hyperspectral_slice(
        intensity_slice,
        wavelength,
        thickness_map,
        refractive_index,
        pixel_pitch=SENSOR_PIXEL_PITCH,
        doe_gap=DOE_GAP,
        monte_carlo_samples=1,
        generator=None,
    ):
        """Apply the near-focus DOE model to one ``(H, W)`` wavelength slice.

        ``intensity_slice`` is the focal-plane intensity of the 35 mm lens at
        this wavelength. One fixed random phase screen per Monte Carlo sample
        turns it into a field, which passes through ``to_focal`` --
        back-propagation (-doe_gap) to the DOE plane, the DOE phase,
        propagation (+doe_gap) to the focal plane where the chromatic phase
        converts to intensity, and the 1:1 relay flip -- and the sample
        intensities are averaged.

        ``thickness_map`` may be on the DOE cell grid; it is resampled
        piecewise-constant onto the slice raster, so one DOE structure stays
        one block of detector pixels. Both rasters are assumed to span the
        same physical field of view.
        """
        if intensity_slice.ndim != 2:
            raise ValueError(f"intensity_slice must be 2D, got {tuple(intensity_slice.shape)}")
        device = thickness_map.device
        dtype = thickness_map.dtype
        wavelength = torch.as_tensor(wavelength, device=device, dtype=dtype)
        refractive_index = torch.as_tensor(refractive_index, device=device, dtype=dtype)
        intensity_slice = intensity_slice.to(device=device, dtype=dtype).clamp_min(0.0)
        thickness_map = thickness_map.to(device=device, dtype=dtype)
        if thickness_map.shape != intensity_slice.shape:
            # The learned DOE lives on its own cell raster. Resample it
            # piecewise-constant (nearest) onto the target slice raster rather
            # than relying on implicit broadcasting; bilinear would smear a
            # single lithographic structure across cell boundaries.
            thickness_map = torch.nn.functional.interpolate(
                thickness_map[None, None], size=intensity_slice.shape,
                mode="nearest-exact",
            ).squeeze(0).squeeze(0)
        phase = (2 * torch.pi / wavelength) * (refractive_index - 1.0) * thickness_map
        doe = torch.exp(1j * phase)
        outputs = []
        for _ in range(monte_carlo_samples):
            random_phase = 2 * torch.pi * torch.rand(
                intensity_slice.shape, device=device, dtype=dtype, generator=generator
            )
            field = torch.sqrt(intensity_slice) * torch.exp(1j * random_phase)
            if doe_gap > 0:
                # The same operator the training model uses.
                relayed = to_focal(field, wavelength, doe, doe_gap, pixel_pitch)
            else:
                # Zero gap: the mask sits in the imaged plane; only the relay
                # inversion remains and the phase encodes nothing.
                relayed = torch.flip(field * doe, dims=(-2, -1))
            outputs.append(relayed.abs().square())
        return torch.stack(outputs).mean(0)

    return (transform_hyperspectral_slice,)


@app.cell(hide_code=True)
def _(DOE_GAP, SENSOR_PIXEL_PITCH, torch, transform_hyperspectral_slice):
    def iter_hyperspectral_mat(
        mat_path,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=SENSOR_PIXEL_PITCH,
        doe_gap=DOE_GAP,
        wavelength_stride=1,
        wavelength_range=None,
        monte_carlo_samples=1,
        device=None,
        random_seed=None,
    ):
        """Yield transformed ``(wavelength, image)`` pairs from a v7.3 MAT file."""
        import h5py
        import numpy as np

        if not h5py.is_hdf5(mat_path):
            raise ValueError("Streaming requires a MATLAB v7.3/HDF5 MAT file")
        if device is None:
            device = thickness_map.device
        with h5py.File(mat_path, "r") as mat:
            img = mat["img"]
            wavelengths = np.asarray(mat["wavelength"]).squeeze()
            if wavelength_range:
                # Select by value against the file's own wavelength axis rather
                # than assuming a fixed 400 nm / 2 nm grid.
                lo = int(np.searchsorted(wavelengths, wavelength_range[0], side="left"))
                hi = int(np.searchsorted(wavelengths, wavelength_range[1], side="right"))
                wavelengths = wavelengths[lo:hi]
                img = img[lo:hi, :, :]
            if img.shape[0] != wavelengths.size:
                raise ValueError(f"expected img.shape[0] == len(wavelength), got {img.shape} and {wavelengths.shape}")
            source_wavelengths = wavelengths.astype(np.float64)
            if np.nanmax(np.abs(source_wavelengths)) < 1e-3:
                source_wavelengths = source_wavelengths * 1e9
            indices = list(range(0, len(source_wavelengths), wavelength_stride))
            # These files are chunked with all wavelengths in each chunk:
            # (151, 204, 1). Reading each wavelength directly would cause
            # repeated decompression. Load only this one temporal frame into
            # CPU RAM, then transfer one slice at a time to the GPU.
            img_cpu = np.asarray(img[...])
            local_thickness = thickness_map.to(device=device)
            generator = torch.Generator(device=device)
            if random_seed is not None:
                generator.manual_seed(random_seed)
            for index in indices:
                wavelength_nm = float(source_wavelengths[index])
                wavelength_m = wavelength_nm * 1e-9
                n_value = n_for_wavelength(wavelength_nm)
                source_slice = torch.from_numpy(img_cpu[index].astype(np.float32, copy=False))
                with torch.inference_mode():
                    transformed = transform_hyperspectral_slice(
                        source_slice, wavelength_m, local_thickness, n_value,
                        pixel_pitch=pixel_pitch, doe_gap=doe_gap,
                        monte_carlo_samples=monte_carlo_samples,
                        generator=generator,
                    )
                yield wavelength_nm, transformed.detach().cpu()

    return (iter_hyperspectral_mat,)


@app.cell(hide_code=True)
def _(DOE_GAP, SENSOR_PIXEL_PITCH, iter_hyperspectral_mat):
    def iter_hyperspectral_sequence(
        sequence_dir,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=SENSOR_PIXEL_PITCH,
        doe_gap=DOE_GAP,
        wavelength_stride=1,
        monte_carlo_samples=1,
        device=None,
        random_seed=None,
    ):
        """Yield transformed spectral slices from all numbered MAT frames."""
        from pathlib import Path

        paths = sorted(Path(sequence_dir).glob("*.mat"))
        if not paths:
            raise FileNotFoundError(f"No MAT files found in {sequence_dir}")
        for frame_index, mat_path in enumerate(paths):
            for wavelength_nm, transformed_slice in iter_hyperspectral_mat(
                mat_path,
                thickness_map,
                n_for_wavelength,
                pixel_pitch=pixel_pitch,
                doe_gap=doe_gap,
                wavelength_stride=wavelength_stride,
                monte_carlo_samples=monte_carlo_samples,
                device=device,
                random_seed=None if random_seed is None else random_seed + frame_index,
            ):
                yield frame_index, wavelength_nm, transformed_slice

    return


@app.cell(hide_code=True)
def _(DOE_GAP, SENSOR_PIXEL_PITCH, iter_hyperspectral_mat, torch):
    def transform_hyperspectral_sequence(
        sequence_dir,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=SENSOR_PIXEL_PITCH,
        doe_gap=DOE_GAP,
        wavelength_stride=1,
        wavelength_range=None,
        monte_carlo_samples=1,
        device=None,
        random_seed=0,
        output_dir=None,
    ):
        """Process all temporal frames and yield one summed sensor frame at a time.

        Each wavelength is transformed independently. The resulting spectral
        images are accumulated on the CPU, so only one source slice and one
        transformed slice occupy GPU memory at any moment.
        """
        from pathlib import Path
        import numpy as np

        paths = sorted(Path(sequence_dir).glob("*.mat"))
        if not paths:
            raise FileNotFoundError(f"No MAT files found in {sequence_dir}")
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        for frame_index, mat_path in enumerate(paths):
            frame_sum = None
            wavelengths_for_frame = []
            for wavelength_nm, transformed_slice in iter_hyperspectral_mat(
                mat_path,
                thickness_map,
                n_for_wavelength,
                pixel_pitch=pixel_pitch,
                doe_gap=doe_gap,
                wavelength_stride=wavelength_stride,
                wavelength_range=wavelength_range,
                monte_carlo_samples=monte_carlo_samples,
                device=device,
                random_seed=None if random_seed is None else random_seed + frame_index,
            ):
                if frame_sum is None:
                    frame_sum = torch.zeros_like(transformed_slice)
                frame_sum += transformed_slice
                wavelengths_for_frame.append(wavelength_nm)

            if frame_sum is None:
                raise RuntimeError(f"No wavelength slices found in {mat_path}")
            if output_dir is not None:
                np.save(output_dir / f"frame_{frame_index:04d}.npy", frame_sum.numpy())
                if frame_index == 0:
                    np.save(output_dir / "wavelengths_nm.npy", np.asarray(wavelengths_for_frame))
            yield frame_index, np.asarray(wavelengths_for_frame), frame_sum


    return (transform_hyperspectral_sequence,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Run the evaluation and render the video

    The cell below loads `profile.npy` (and the trained `gap.npy` when
    present), interpolates the Cauchy table onto each source wavelength, and
    streams the whole sequence. The two video cells then encode the frames
    losslessly (FFV1) with a *global* intensity mapping so the video does not
    flicker, plus an optional RGB comparison rendered straight from the source
    cube.

    ### A complete CHPC batch script

    ```bash
    #!/bin/bash
    #SBATCH --job-name=coded-doe
    #SBATCH --partition=gpu
    #SBATCH --gres=gpu:1
    #SBATCH --cpus-per-task=8
    #SBATCH --mem=32G
    #SBATCH --time=8:00:00
    cd /scratch/baird/hypercam/src/notebooks
    export CODED_MASK_CONFIG=/scratch/baird/hypercam/run.toml
    uv run python coded_mask.py
    ```

    Everything the batch needs comes from the TOML: material and data paths,
    `seed` for reproducibility, and the switches -- set
    `create_video = false` if OpenCV/FFmpeg are unavailable on the compute
    nodes, and point `[paths].transformed_dir` at your scratch area.
    """)
    return


@app.cell(hide_code=True)
def _(
    CubicSpline,
    DOE_GAP,
    HYPERSPECTRAL_DIR,
    MATERIAL_XLSX,
    Path,
    RUN_HYPERSPECTRAL,
    SEED,
    TRANSFORMED_DIR,
    np,
    pd,
    torch,
    transform_hyperspectral_sequence,
):
    import random
    def _():
        """Process the complete running-frog sequence one frame/slice at a time."""
        if RUN_HYPERSPECTRAL:
            sequence_dir = Path(HYPERSPECTRAL_DIR)
            output_dir = Path(TRANSFORMED_DIR)
            material = pd.read_excel(MATERIAL_XLSX)
            thickness = torch.from_numpy(np.load('profile.npy'))
            # Prefer the DOE-to-focal-plane offset that was actually trained;
            # fall back to the nominal DOE_GAP when no training result exists.
            gap_path = Path("gap.npy")
            doe_gap = float(np.load(gap_path)) if gap_path.exists() else DOE_GAP
            n_interpolator = CubicSpline(
                material["Wavelength (m)"].to_numpy(),
                material["n"].to_numpy(),
            )

            def n_for_wavelength(wavelength_nm):
                return float(n_interpolator(wavelength_nm * 1e-9))

            for frame_index, wavelengths_nm, transformed_frame in transform_hyperspectral_sequence(
                sequence_dir,
                thickness,
                n_for_wavelength,
                doe_gap=doe_gap,
                wavelength_stride=1,
                #wavelength_range=(540, 560),
                monte_carlo_samples=4,
                device=thickness.device,
                random_seed=SEED if SEED is not None else random.randint(0, 2048),
                output_dir=output_dir,
            ):
                print(
                    f"frame {frame_index + 1}: "
                    f"{len(wavelengths_nm)} wavelengths, "
                    f"output shape={tuple(transformed_frame.shape)}"
                )
        else:
            return print("Hyperspectral sequence processing disabled. Set RUN_HYPERSPECTRAL=True to run it.")


    _()
    return


@app.cell(hide_code=True)
def _(CREATE_VIDEO, Path, TRANSFORMED_DIR, VIDEO_CODEC, np):
    def _():
        """Write the transformed running-frog frames as a 1/40 FPS video."""
        if CREATE_VIDEO:
            import cv2

            transformed_dir = Path(TRANSFORMED_DIR)
            video_path = transformed_dir / "running_frog_transformed_lossless.mkv"
            frame_paths = sorted(transformed_dir.glob("frame_*.npy"))
            if not frame_paths:
                raise FileNotFoundError(f"No transformed frames found in {transformed_dir}")

            # Scan all frames first so the same intensity mapping is used for the
            # entire video. Per-frame normalization would create artificial flicker.
            global_min = np.inf
            global_max = -np.inf
            for frame_path in frame_paths:
                frame = np.load(frame_path, mmap_mode="r")
                global_min = min(global_min, float(np.nanmin(frame)))
                global_max = max(global_max, float(np.nanmax(frame)))
            if not np.isfinite(global_min) or not np.isfinite(global_max) or global_max <= global_min:
                raise ValueError(f"Invalid frame intensity range: {global_min}, {global_max}")

            first = np.load(frame_paths[0], mmap_mode="r")
            height, width = first.shape[-2:]
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*VIDEO_CODEC),
                30,
                (width, height),
                True,
            )
            if not writer.isOpened():
                raise RuntimeError(f"Could not open video writer for {video_path}")

            try:
                for frame_path in frame_paths:
                    frame = np.asarray(np.load(frame_path), dtype=np.float32)
                    normalized = np.clip(
                        (frame - global_min) / (global_max - global_min), 0.0, 1.0
                    )
                    frame_u8 = np.ascontiguousarray((normalized * 255.0).round().astype(np.uint8))
                    writer.write(cv2.cvtColor(frame_u8, cv2.COLOR_GRAY2BGR))
            finally:
                writer.release()

            print(f"Wrote {len(frame_paths)} frames to {video_path} at {1.0 / 40.0:.3f} FPS")
        else:
            return print("Video writing disabled. Set CREATE_VIDEO=True after installing OpenCV.")


    _()
    return


@app.cell(hide_code=True)
def _(
    CREATE_RGB_VIDEO,
    HYPERSPECTRAL_DIR,
    Path,
    TRANSFORMED_DIR,
    VIDEO_CODEC,
    np,
):
    def _():
        """Write an interpolated RGB comparison video from the source spectra."""
        if CREATE_RGB_VIDEO:
            import cv2
            import h5py

            sequence_dir = Path(HYPERSPECTRAL_DIR)
            output_dir = Path(TRANSFORMED_DIR)
            video_path = output_dir / "running_frog_rgb_comparison_lossless.mkv"
            mat_paths = sorted(sequence_dir.glob("*.mat"))
            if not mat_paths:
                raise FileNotFoundError(f"No MAT files found in {sequence_dir}")

            rgb_wavelengths = np.array([450.0, 550.0, 650.0], dtype=np.float64)

            def interpolate_rgb(img, wavelengths_nm):
                """Linearly interpolate a (K,H,W) cube to B,G,R wavelength planes."""
                channels = []
                for target_nm in rgb_wavelengths:
                    upper = int(np.searchsorted(wavelengths_nm, target_nm, side="left"))
                    upper = min(max(upper, 1), len(wavelengths_nm) - 1)
                    lower = upper - 1
                    fraction = (target_nm - wavelengths_nm[lower]) / (
                        wavelengths_nm[upper] - wavelengths_nm[lower]
                    )
                    channel = (
                        (1.0 - fraction) * img[lower].astype(np.float32)
                        + fraction * img[upper].astype(np.float32)
                    )
                    channels.append(channel)
                return np.stack(channels, axis=-1)  # B, G, R order for OpenCV

            # Establish one shared normalization across all temporal frames and
            # color channels so the video does not flicker.
            global_min = np.full(3, np.inf, dtype=np.float64)
            global_max = np.full(3, -np.inf, dtype=np.float64)
            for mat_path in mat_paths:
                with h5py.File(mat_path, "r") as mat:
                    img = np.asarray(mat["img"][...])
                    wavelengths_nm = np.asarray(mat["wavelength"]).reshape(-1).astype(np.float64)
                    rgb = interpolate_rgb(img, wavelengths_nm)
                    global_min = np.minimum(global_min, np.nanmin(rgb, axis=(0, 1)))
                    global_max = np.maximum(global_max, np.nanmax(rgb, axis=(0, 1)))

            height, width = rgb.shape[:2]
            writer = cv2.VideoWriter(
                str(video_path),
                cv2.VideoWriter_fourcc(*VIDEO_CODEC),
                1.0 / 40.0,
                (width, height),
                True,
            )
            if not writer.isOpened():
                raise RuntimeError(f"Could not open video writer for {video_path}")

            try:
                for mat_path in mat_paths:
                    with h5py.File(mat_path, "r") as mat:
                        img = np.asarray(mat["img"][...])
                        wavelengths_nm = np.asarray(mat["wavelength"]).reshape(-1).astype(np.float64)
                    rgb = interpolate_rgb(img, wavelengths_nm)
                    rgb = np.clip(
                        (rgb - global_min[None, None, :])
                        / (global_max - global_min)[None, None, :],
                        0.0,
                        1.0,
                    )
                    writer.write(np.ascontiguousarray((rgb * 255.0).round().astype(np.uint8)))
            finally:
                writer.release()

            print(f"Wrote {len(mat_paths)} RGB frames to {video_path} at {1.0 / 40.0:.3f} FPS")
        else:
            return print("RGB video writing disabled. Set CREATE_RGB_VIDEO=True after installing OpenCV.")


    _()
    return


if __name__ == "__main__":
    app.run()
