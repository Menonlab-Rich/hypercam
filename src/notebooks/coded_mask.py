import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import os

    os.putenv('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    return


@app.cell
def _():
    import torch
    import torch.nn as nn
    import numpy as np
    import torch.nn.functional as F
    import pandas as pd
    from scipy.interpolate import CubicSpline
    from scipy.io import loadmat
    from pathlib import Path

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Centralized execution switches. Change these here rather than searching
    # through the notebook for individual run cells.
    RUN_TRAINING = True
    RUN_DEBUG_TRAINING = False
    SAVE = True
    RUN_HYPERSPECTRAL = True
    CREATE_VIDEO = True
    CREATE_RGB_VIDEO = False
    DOE_GAP = 500e-6
    VIDEO_CODEC = "FFV1"
    return (
        CREATE_RGB_VIDEO,
        CREATE_VIDEO,
        CubicSpline,
        DOE_GAP,
        F,
        Path,
        RUN_DEBUG_TRAINING,
        RUN_HYPERSPECTRAL,
        RUN_TRAINING,
        SAVE,
        VIDEO_CODEC,
        device,
        nn,
        np,
        pd,
        torch,
    )


@app.cell
def _(F, nn, np, torch):
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


    def generate_psf_stack(thickness_map, wavelengths, n_lambda, aperture_mask, device):
        """
        thickness_map: Tensor of shape (H, W) in meters
        wavelengths: Tensor of shape (K,) in meters
        n_lambda: Tensor of shape (K,) representing refractive index per wavelength
        aperture_mask: Binary tensor of shape (H, W)
        """
        H, W = thickness_map.shape
        K = wavelengths.shape[0]

        # Reshape for broadcasting: (K, 1, 1)
        wl = wavelengths.view(K, 1, 1)
        n_l = n_lambda.view(K, 1, 1)

        # 1. Calculate phase delay for all wavelengths
        # phi shape: (K, H, W)
        phi = (2 * torch.pi / wl) * (n_l - 1.0) * thickness_map

        # 2. Construct complex pupil function
        # P shape: (K, H, W)
        P = aperture_mask.unsqueeze(0) * torch.exp(1j * phi)

        # 3. Fourier transform to get the PSF
        # Use 2D FFT, shifting the zero-frequency component to the center
        fft_field = torch.fft.fft2(P, norm="ortho").to(device)
        fft_field_shifted = torch.fft.fftshift(fft_field, dim=(-2, -1))

        # 4. Calculate intensity (squared magnitude)
        psf_stack = torch.abs(fft_field_shifted)**2

        # Normalize each PSF to sum to 1 (energy conservation)
        psf_stack = psf_stack / psf_stack.sum(dim=(-2, -1), keepdim=True)

        return psf_stack


    def _angular_spectrum(field, wavelength, distance, pixel_pitch):
        """Propagate a complex field on a fixed Cartesian grid."""
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


    def generate_incoherent_relay_stack(
        thickness_map,
        wavelengths,
        n_lambda,
        morphology,
        d_morphology,
        d_morphology_y,
        pool_size=128,
        pixel_pitch=3.45e-6,
        doe_offset=(1e-5, 1e-3),
        relay_focal_length=19.0e-3,
        relay_f_number=19.0 / 11.9,
        monte_carlo_samples=4,
        random_phases=None,
        raw_gap=1,
    ):
        """Monte Carlo incoherent image formation through an image-plane DOE.

        ``morphology`` is interpreted as the intensity in the primary-lens
        intermediate image plane. Independent fixed random phases emulate
        mutually incoherent spatial contributions. The DOE is one millimeter
        after that plane, followed by an equal-focal-length 4f relay.

        The calculation is performed at ``pool_size`` resolution for memory
        reasons. The effective pixel pitch is scaled with the horizontal
        downsampling factor.
        """
        target = (pool_size, pool_size) if isinstance(pool_size, int) else pool_size
        h, w = target
        device = thickness_map.device
        dtype = thickness_map.dtype

        def resize(x):
            if x.ndim == 2:
                # Single spatial map: add batch and channel dimensions.
                return F.adaptive_avg_pool2d(x[None, None], target).squeeze(0).squeeze(0)
            if x.ndim == 3:
                # Frame stack: add only the channel dimension.
                return F.adaptive_avg_pool2d(x.unsqueeze(1), target).squeeze(1)
            raise ValueError(f"expected a 2D map or 3D frame stack, got shape {tuple(x.shape)}")

        # The optimization grid is reduced before wave propagation. Use the
        # horizontal scale so the physical propagation grid remains explicit.
        effective_pitch = pixel_pitch * thickness_map.shape[-1] / w
        thickness = resize(thickness_map)
        morphology = resize(morphology)
        d_morphology = resize(d_morphology)
        d_morphology_y = resize(d_morphology_y)

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

        # The MAP051919-A relay has a 19 mm focal length and approximately
        # 11.9 mm entrance pupil, corresponding to about f/1.60.
        yy, xx = torch.meshgrid(
            (torch.arange(h, device=device, dtype=dtype) - (h - 1) / 2) * effective_pitch,
            (torch.arange(w, device=device, dtype=dtype) - (w - 1) / 2) * effective_pitch,
            indexing="ij",
        )
        relay_radius = relay_focal_length / (2 * relay_f_number)
        relay_aperture = ((xx.square() + yy.square()) <= relay_radius**2).to(dtype)
        z_min, z_max = doe_offset

        def thin_lens(field, wavelength):
            lens_phase = -torch.pi * (xx.square() + yy.square()) / (
                wavelength * relay_focal_length
            )
            return field * relay_aperture * torch.exp(1j * lens_phase)

        def relay(field, wavelength):
            # Input plane -> f -> lens 1 -> 2f -> lens 2 -> f -> output.
            # The Fourier plane is at the midpoint between the relay lenses.
            field = _angular_spectrum(field, wavelength, relay_focal_length, effective_pitch)
            field = thin_lens(field, wavelength)
            field = _angular_spectrum(field, wavelength, 2 * relay_focal_length, effective_pitch)
            field = thin_lens(field, wavelength)
            return _angular_spectrum(field, wavelength, relay_focal_length, effective_pitch)

        outputs = []
        dx_outputs = []
        dy_outputs = []
        for k, (wavelength, index) in enumerate(zip(wavelengths, n_lambda)):
            wavelength = wavelength.to(dtype=dtype)
            phase = (2 * torch.pi / wavelength) * (index.to(dtype) - 1.0) * thickness
            doe = torch.exp(1j * phase)
            sample_images = []
            sample_dx = []
            sample_dy = []

            z_gap = z_min + (z_max - z_min) * torch.sigmoid(raw_gap)
            for s in range(monte_carlo_samples):
                random_phase = torch.exp(1j * random_phases[s])
                field = torch.sqrt(morphology.clamp_min(0.0)) * random_phase
                field_x = (0.5 * d_morphology / torch.sqrt(morphology.clamp_min(1e-12))) * random_phase
                field_y = (0.5 * d_morphology_y / torch.sqrt(morphology.clamp_min(1e-12))) * random_phase
                field = _angular_spectrum(field, wavelength, z_gap, effective_pitch) * doe
                field_x = _angular_spectrum(field_x, wavelength, z_gap, effective_pitch) * doe
                field_y = _angular_spectrum(field_y, wavelength, z_gap, effective_pitch) * doe
                relay_field = relay(field, wavelength)
                relay_field_x = relay(field_x, wavelength)
                relay_field_y = relay(field_y, wavelength)
                sample_images.append(torch.abs(relay_field).square())
                sample_dx.append(2 * torch.real(torch.conj(relay_field) * relay_field_x))
                sample_dy.append(2 * torch.real(torch.conj(relay_field) * relay_field_y))
            outputs.append(torch.stack(sample_images).mean(0))
            dx_outputs.append(torch.stack(sample_dx).mean(0))
            dy_outputs.append(torch.stack(sample_dy).mean(0))

        return torch.stack(outputs, dim=1), torch.stack(dx_outputs, dim=1), torch.stack(dy_outputs, dim=1)

    return (
        MaskThicknessMLP,
        generate_incoherent_relay_stack,
        generate_psf_stack,
    )


@app.cell
def _(np):
    wavelengths = np.arange(380, 750, 5)
    shape = (720, 1280)
    x = np.arange(0, shape[1])
    y = np.arange(0, shape[0])

    # Increased sigma for macroscopic object dimensions
    sigma_x = 50.0 
    sigma_y = 50.0
    return shape, sigma_x, sigma_y, wavelengths, x, y


@app.cell
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


@app.cell
def _(CubicSpline, pd, torch, wavelengths):
    # 1. Load the target material data
    df = pd.read_excel('mat_maP1275.xlsx')
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
    return n_lambda, wavelengths_tensor


@app.cell
def _(
    MaskThicknessMLP,
    device,
    generate_psf_stack,
    n_lambda,
    torch,
    wavelengths_tensor,
):
    H, W = 720, 1280
    y_model = torch.linspace(-1, 1, H)
    x_model = torch.linspace(-1, 1, W)
    yy, xx = torch.meshgrid(y_model, x_model, indexing='ij')
    coords = torch.stack([xx, yy], dim=-1)

    mlp = MaskThicknessMLP()
    # Generate thickness map in meters (scaled by max expected height, e.g., 5 micrometers)
    thickness_flat = mlp(coords.reshape(-1, 2))
    thickness_map = thickness_flat.reshape(H, W) * 5e-6 

    aperture_mask = torch.ones((H, W)) # Open circular or full rectangular aperture

    # Compute the multi-wavelength PSF stack
    psf_stack = generate_psf_stack(thickness_map, wavelengths_tensor, n_lambda, aperture_mask, device)
    print("Generated PSF Stack Shape:", psf_stack.shape) # Expected: (74, 720, 1280)
    return aperture_mask, coords, mlp


@app.cell
def _(nn, torch):
    def crlb_from_images(
        mean_image, dx_image, dy_image, wavelengths_nm,
        photons_per_bin=1e5, background_photons=1.0, frame_stride=10,
        parameter_scales=(50.0, 50.0, 100.0), ridge=1e-8, eps=1e-12,
        spatial=True, spectral=True
    ):
        """Joint CRLB for images already generated by the optical model."""
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
        weights = 1.0 / expected.clamp_min(eps)
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
        pool_size=120,
        print_every=100,
        monte_carlo_samples=1,
        frame_stride=10,
        trainable_gap=True,
        initial_gap=5e-4,
        random_seed=None,
        doe_offset=(1e-5, 1e-3),
        optim_space=True,
        optim_spectral=True,
    ):
        """Optimize an image-plane DOE with fixed-phase incoherent MC."""
        z_min, z_max = 1e-5, 1e-3
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
        flat_coords = coords.reshape(-1, 2)
        target = (pool_size, pool_size) if isinstance(pool_size, int) else pool_size
        morphology = morphology[::frame_stride]
        d_morphology = d_morphology[::frame_stride]
        d_morphology_y = d_morphology_y[::frame_stride]
        if random_seed is not None:
            generator = torch.Generator(device=morphology.device)
            generator.manual_seed(random_seed)
        else:
            generator = None
        random_phases = 2 * torch.pi * torch.rand(
            (monte_carlo_samples, morphology.shape[0], target[0], target[1]),
            device=morphology.device, dtype=coords.dtype,
            generator=generator,
        )

        for epoch in range(epochs):
            optimizer.zero_grad(set_to_none=True)
            thickness_map = mlp(flat_coords).reshape(coords.shape[:2]) * 5e-6
            mean_image, dx_image, dy_image = generate_incoherent_relay_stack(
                thickness_map, wavelengths, n_lambda,
                morphology,
                d_morphology,
                d_morphology_y,
                pool_size=pool_size,
                doe_offset=doe_offset,
                random_phases=random_phases,
                raw_gap=raw_gap
            )
            crlb, fisher = crlb_from_images(
                mean_image, dx_image, dy_image, wavelengths * 1e9,
                photons_per_bin=photons_per_bin,
                background_photons=background_photons,
                frame_stride=1, spatial=optim_space, spectral=optim_spectral
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
                best_thickness = thickness_map.detach().clone()
                best_psf = mean_image.detach().clone()
                best_gap = raw_gap.detach().clone()

            if print_every and (epoch == 0 or (epoch + 1) % print_every == 0):
                print(
                    f"epoch {epoch + 1:5d}/{epochs}: "
                    f"mean CRLB={history[-1]:.5g} nm^2, "
                    f"mean FI={float(fisher.mean().detach()):.5g}"
                )

        return history, best_loss, best_thickness, best_psf, best_gap

    return (train_mask,)


@app.cell
def _(
    M_stack,
    RUN_TRAINING,
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
            history, loss, thickness, psf, gap = train_mask(
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
                epochs=1000,
                learning_rate=1e-4,
                photons_per_bin=1e5,
                background_photons=1.0,
                pool_size=64,
                print_every=100,
                monte_carlo_samples=4,
                optim_space=False,
            )
    else:
        history, loss, thickness, psf, gap = [[], float('inf'), None, None, None]
    return gap, psf, thickness


@app.cell
def _(gap, n_lambda, psf, thickness, torch, wavelengths_tensor):
    from matplotlib import pyplot as plt
    import marimo as mo
    def _():
        """Diagnostic plots for DOE phase and propagated incoherent intensity."""
        z_min = 1e-5
        z_max = 1e-3
        if thickness is not None and psf is not None:
            z = z_min + (z_max - z_min) * torch.sigmoid(gap)
            print(f"Optimal z distance: {z.detach().cpu().item()}" )
            thickness_cpu = thickness.detach().cpu()
            image_stack = psf.detach().cpu()

            # The optical stack is [frame, wavelength, y, x].
            frame_index = 0
            wavelength_index = int(torch.argmin(torch.abs(
                wavelengths_tensor.detach().cpu() - 550e-9
            )))
            wavelength = wavelengths_tensor[wavelength_index].detach().cpu()
            refractive_index = n_lambda[wavelength_index].detach().cpu()

            # Match the 128x128 propagation grid used by the relay simulation.
            thickness_small = torch.nn.functional.adaptive_avg_pool2d(
                thickness_cpu[None, None], (image_stack.shape[-2], image_stack.shape[-1])
            ).squeeze()
            phase = (
                2 * torch.pi / wavelength
                * (refractive_index - 1.0)
                * thickness_small
            )
            wrapped_phase = torch.angle(torch.exp(1j * phase))
            phase_cycles = phase / (2 * torch.pi)
            intensity = image_stack[frame_index, wavelength_index]
            log_intensity = torch.log10(intensity.clamp_min(1e-12))

            fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
            full_extent = [0, thickness_cpu.shape[1] * 3.45,
                           thickness_cpu.shape[0] * 3.45, 0]
            small_pitch = 3.45 * thickness_cpu.shape[1] / image_stack.shape[-1]
            small_extent = [0, image_stack.shape[-1] * small_pitch,
                            image_stack.shape[-2] * small_pitch, 0]

            plots = [
                (thickness_cpu * 1e6, full_extent, "viridis", "Thickness (µm)", "DOE thickness"),
                (wrapped_phase, small_extent, "twilight", None, "Wrapped DOE phase"),
                (phase_cycles, small_extent, "RdBu_r", None, "DOE phase (cycles)"),
                (intensity, small_extent, "gray", None, "Mean output intensity"),
                (log_intensity, small_extent, "magma", None, "Log output intensity"),
                (image_stack[frame_index].mean(0), small_extent, "gray", None,
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


@app.cell
def _(n_lambda, plt, psf, thickness, torch, wavelengths_tensor):
    def _():
        """Multi-wavelength phase and relay-aperture diagnostics."""
        if thickness is not None and psf is not None:
            output_size = psf.shape[-1]
            thickness_small = torch.nn.functional.adaptive_avg_pool2d(
                thickness[None, None], (output_size, output_size)
            ).squeeze()
            wavelength_indices = torch.linspace(
                0, wavelengths_tensor.numel() - 1, 5, dtype=torch.long
            )
            fig, axes = plt.subplots(2, 5, figsize=(18, 7), constrained_layout=True)
            for column, k in enumerate(wavelength_indices.tolist()):
                phase = (2 * torch.pi / wavelengths_tensor[k]) * (n_lambda[k] - 1.0) * thickness_small
                wrapped = torch.angle(torch.exp(1j * phase)).detach().cpu()
                cycles = (phase / (2 * torch.pi)).detach().cpu()
                wavelength_nm = wavelengths_tensor[k].item() * 1e9
                im0 = axes[0, column].imshow(wrapped, cmap="twilight", vmin=-torch.pi, vmax=torch.pi)
                axes[0, column].set_title(f"{wavelength_nm:.0f} nm")
                fig.colorbar(im0, ax=axes[0, column], shrink=0.75, label="rad")
                im1 = axes[1, column].imshow(cycles, cmap="RdBu_r")
                fig.colorbar(im1, ax=axes[1, column], shrink=0.75, label="cycles")
            fig.suptitle("DOE phase variation across wavelength")
            plt.show()

            effective_pitch = 3.45e-6 * thickness.shape[-1] / output_size
            coordinate = (torch.arange(output_size, dtype=thickness.dtype) - (output_size - 1) / 2) * effective_pitch
            yy, xx = torch.meshgrid(coordinate, coordinate, indexing="ij")
            relay_radius = 11.9e-3 / 2
            aperture = ((xx.square() + yy.square()) <= relay_radius**2).cpu()
            fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
            axes[0].imshow(aperture, cmap="gray")
            axes[0].set_title("Relay aperture")
            axes[1].imshow(thickness_small.detach().cpu() * 1e6, cmap="viridis")
            axes[1].set_title("Downsampled thickness (µm)")
            axes[2].imshow(psf[0].detach().cpu().mean(0), cmap="gray")
            axes[2].set_title("Mean output, frame 0")
            for ax in axes:
                ax.set_axis_off()
        return plt.show()


    _()
    return


@app.cell
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
                    pool_size=32, monte_carlo_samples=monte_carlo_samples, random_seed=seed, print_every=0,
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


@app.cell
def _(SAVE, np, psf, thickness):
    if SAVE:
        np.save("profile", thickness.cpu())
        np.save("psf", psf.cpu())
    return


@app.cell
def _(torch):
    def make_relay_operator(
        height,
        width,
        device,
        dtype,
        pixel_pitch=3.45e-6,
        relay_focal_length=19.0e-3,
        relay_f_number=19.0 / 11.9,
    ):
        """Build reusable wavelength-dependent propagation operators."""
        yy, xx = torch.meshgrid(
            (torch.arange(height, device=device, dtype=dtype) - (height - 1) / 2) * pixel_pitch,
            (torch.arange(width, device=device, dtype=dtype) - (width - 1) / 2) * pixel_pitch,
            indexing="ij",
        )
        fy = torch.fft.fftfreq(height, d=pixel_pitch, device=device)
        fx = torch.fft.fftfreq(width, d=pixel_pitch, device=device)
        fy, fx = torch.meshgrid(fy, fx, indexing="ij")
        relay_radius = relay_focal_length / (2 * relay_f_number)
        relay_aperture = ((xx.square() + yy.square()) <= relay_radius**2).to(dtype)

        def propagate(field, wavelength, distance):
            argument = 1.0 - (wavelength * fx) ** 2 - (wavelength * fy) ** 2
            transfer = torch.exp(
                1j * (2 * torch.pi / wavelength) * distance * torch.sqrt(argument.clamp_min(0.0))
            )
            transfer = transfer * (argument >= 0).to(transfer.dtype)
            return torch.fft.ifft2(
                torch.fft.fft2(field, norm="ortho") * transfer, norm="ortho"
            )

        def relay(field, wavelength):
            lens_phase = -torch.pi * (xx.square() + yy.square()) / (
                wavelength * relay_focal_length
            )
            lens = relay_aperture * torch.exp(1j * lens_phase)
            field = propagate(field, wavelength, relay_focal_length) * lens
            field = propagate(field, wavelength, 2 * relay_focal_length) * lens
            return propagate(field, wavelength, relay_focal_length)

        return propagate, relay


    def transform_hyperspectral_slice(
        intensity_slice,
        wavelength,
        thickness_map,
        refractive_index,
        pixel_pitch=3.45e-6,
        doe_gap=1e-5,
        relay_focal_length=19.0e-3,
        relay_f_number=19.0 / 11.9,
        monte_carlo_samples=1,
        propagate=None,
        relay=None,
        generator=None,
    ):
        """Transform one ``(H, W)`` wavelength slice without retaining a cube."""
        if intensity_slice.ndim != 2:
            raise ValueError(f"intensity_slice must be 2D, got {tuple(intensity_slice.shape)}")
        device = thickness_map.device
        dtype = thickness_map.dtype
        height, width = intensity_slice.shape
        if propagate is None or relay is None:
            propagate, relay = make_relay_operator(
                height, width, device, dtype, pixel_pitch,
                relay_focal_length, relay_f_number,
            )
        wavelength = torch.as_tensor(wavelength, device=device, dtype=dtype)
        refractive_index = torch.as_tensor(refractive_index, device=device, dtype=dtype)
        intensity_slice = intensity_slice.to(device=device, dtype=dtype).clamp_min(0.0)
        thickness_map = thickness_map.to(device=device, dtype=dtype)
        if thickness_map.shape != intensity_slice.shape:
            # The learned design and video sensor may have different raster
            # sizes. Resample the physical thickness map once per target
            # raster rather than relying on implicit broadcasting.
            thickness_map = torch.nn.functional.interpolate(
                thickness_map[None, None], size=intensity_slice.shape,
                mode="bilinear", align_corners=False,
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
                field = propagate(field, wavelength, doe_gap)
            output_field = relay(field * doe, wavelength)
            outputs.append(output_field.abs().square())
        return torch.stack(outputs).mean(0)


    def iter_hyperspectral_mat(
        mat_path,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=3.45e-6,
        doe_gap=1e-5,
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
                min_lambda_idx, max_lambda_idx = (int((w-400)/2) for w in wavelength_range)

                wavelengths = wavelengths[min_lambda_idx:max_lambda_idx]

                img = img[min_lambda_idx:max_lambda_idx, :, :]
            if img.shape[0] != wavelengths.size:
                raise ValueError(f"expected img.shape[0] == len(wavelength), got {img.shape} and {wavelengths.shape}")
            source_wavelengths = wavelengths.astype(np.float64)
            if np.nanmax(np.abs(source_wavelengths)) < 1e-3:
                source_wavelengths = source_wavelengths * 1e9
            indices = list(range(0, len(source_wavelengths), wavelength_stride))
            height, width = img.shape[-2:]
            # These files are chunked with all wavelengths in each chunk:
            # (151, 204, 1). Reading each wavelength directly would cause
            # repeated decompression. Load only this one temporal frame into
            # CPU RAM, then transfer one slice at a time to the GPU.
            img_cpu = np.asarray(img[...])
            local_thickness = thickness_map.to(device=device)
            propagate, relay = make_relay_operator(
                height, width, device, local_thickness.dtype, pixel_pitch
            )
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
                        propagate=propagate, relay=relay, generator=generator,
                    )
                yield wavelength_nm, transformed.detach().cpu()


    def iter_hyperspectral_sequence(
        sequence_dir,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=3.45e-6,
        doe_gap=1e-5,
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


    def transform_hyperspectral_sequence(
        sequence_dir,
        thickness_map,
        n_for_wavelength,
        pixel_pitch=3.45e-6,
        doe_gap=1e-5,
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


@app.cell
def _(
    CubicSpline,
    DOE_GAP,
    Path,
    RUN_HYPERSPECTRAL,
    np,
    pd,
    torch,
    transform_hyperspectral_sequence,
):
    import random
    def _():
        """Process the complete running-frog sequence one frame/slice at a time."""
        if RUN_HYPERSPECTRAL:
            sequence_dir = Path("../../data/hyperspectral/Dyna_Spec_release/running-frog")
            output_dir = Path("transformed_running_frog")
            material = pd.read_excel("mat_maP1275.xlsx")
            thickness = torch.from_numpy(np.load('profile.npy'))
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
                doe_gap=DOE_GAP,
                wavelength_stride=1,
                #wavelength_range=(540, 560),
                monte_carlo_samples=4,
                device=thickness.device,
                random_seed=random.randint(0, 2048),
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


@app.cell
def _(CREATE_VIDEO, Path, VIDEO_CODEC, np):
    def _():
        """Write the transformed running-frog frames as a 1/40 FPS video."""
        if CREATE_VIDEO:
            import cv2

            transformed_dir = Path("transformed_running_frog")
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


@app.cell
def _(CREATE_RGB_VIDEO, Path, VIDEO_CODEC, np):
    def _():
        """Write an interpolated RGB comparison video from the source spectra."""
        if CREATE_RGB_VIDEO:
            import cv2
            import h5py

            sequence_dir = Path("../../data/hyperspectral/Dyna_Spec_release/running-frog")
            output_dir = Path("transformed_running_frog")
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
