"""Small RGB -> hyperspectral baseline for generating synthetic test data.

This is intentionally a prior-based reconstruction, not a physically exact
inverse.  RGB contains only three measurements, so the spectrum is recovered
by assuming that spectra are smooth and resemble spectra in an optional
reference cube.

Examples
--------
Fit a model from a reference cube and reconstruct an RGB image::

    python rgb_to_hyperspectral.py fit reference.npy model.npz
    python rgb_to_hyperspectral.py predict image.png model.npz output.npy

Without a reference cube::

    python rgb_to_hyperspectral.py generic image.png output.npy --bands 31
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def gaussian_camera_response(wavelengths_nm: np.ndarray) -> np.ndarray:
    """Return approximate normalized R/G/B spectral sensitivities."""
    wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float32)
    centers = np.array([610.0, 545.0, 460.0], dtype=np.float32)
    widths = np.array([45.0, 38.0, 32.0], dtype=np.float32)
    response = np.exp(-0.5 * ((wavelengths_nm[None, :] - centers[:, None]) / widths[:, None]) ** 2)
    response /= np.maximum(response.sum(axis=1, keepdims=True), 1e-8)
    return response.astype(np.float32)


def _as_hwc(array: np.ndarray, channels: int | None = None) -> np.ndarray:
    """Accept HWC or CHW arrays and return HWC."""
    array = np.asarray(array)
    if array.ndim != 3:
        raise ValueError(f"expected a 3-D array, got shape {array.shape}")
    if channels is not None and array.shape[-1] == channels:
        return array
    if channels is not None and array.shape[0] == channels:
        return np.moveaxis(array, 0, -1)
    raise ValueError(f"could not identify {channels} channels in shape {array.shape}")


class RGBToHyperspectral:
    """Ridge-regression spectral prior with a smoothness regularizer."""

    def __init__(self, wavelengths_nm: np.ndarray, coefficients: np.ndarray, bias: np.ndarray):
        self.wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float32)
        self.coefficients = np.asarray(coefficients, dtype=np.float32)  # 3 x bands
        self.bias = np.asarray(bias, dtype=np.float32)

    @classmethod
    def fit(
        cls,
        cube: np.ndarray,
        wavelengths_nm: np.ndarray | None = None,
        ridge: float = 1e-3,
        max_samples: int = 200_000,
    ) -> "RGBToHyperspectral":
        """Fit RGB-to-spectrum coefficients from an HWC/CHW reference cube."""
        cube = np.asarray(cube, dtype=np.float32)
        if cube.ndim != 3:
            raise ValueError("reference cube must have shape HxWxBands or BandsxHxW")
        # If wavelengths are supplied they disambiguate the layout. Otherwise
        # use the usual convention that the spectral axis is the shortest one.
        hinted_bands = None if wavelengths_nm is None else int(np.asarray(wavelengths_nm).size)
        bands = hinted_bands or cube.shape[int(np.argmin(cube.shape))]
        cube = _as_hwc(cube, bands)
        if wavelengths_nm is None:
            wavelengths_nm = np.linspace(400.0, 700.0, bands, dtype=np.float32)
        wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float32)
        if wavelengths_nm.size != bands:
            raise ValueError("wavelength count must equal the number of cube bands")

        pixels = cube.reshape(-1, bands)
        rng = np.random.default_rng(0)
        if pixels.shape[0] > max_samples:
            pixels = pixels[rng.choice(pixels.shape[0], max_samples, replace=False)]
        scale = np.percentile(pixels, 99.5, axis=0).mean()
        scale = max(float(scale), 1e-8)
        spectra = np.clip(pixels / scale, 0.0, None)

        response = gaussian_camera_response(wavelengths_nm)
        rgb = spectra @ response.T
        # Include an intercept so dark/offset sensor values do not distort fit.
        design = np.concatenate([rgb, np.ones((rgb.shape[0], 1), dtype=np.float32)], axis=1)
        regularizer = ridge * np.eye(4, dtype=np.float32)
        regularizer[-1, -1] = 0.0
        params = np.linalg.solve(design.T @ design + regularizer, design.T @ spectra)
        return cls(wavelengths_nm, params[:3], params[3])

    @classmethod
    def generic(cls, bands: int = 31, start_nm: float = 400.0, end_nm: float = 700.0) -> "RGBToHyperspectral":
        """Create a smooth, plausible prior without a training cube."""
        wavelengths = np.linspace(start_nm, end_nm, bands, dtype=np.float32)
        response = gaussian_camera_response(wavelengths)
        # Gaussian response pseudoinverse gives the least-complex spectrum that
        # explains RGB; a small flat component prevents implausible negatives.
        coefficients = np.linalg.pinv(response).T.astype(np.float32)
        coefficients += 0.03
        return cls(wavelengths, coefficients, np.zeros(bands, dtype=np.float32))

    def predict(self, rgb: np.ndarray, input_range: float | None = None) -> np.ndarray:
        """Convert an HWC/CHW RGB image to an HWC floating-point cube."""
        rgb = _as_hwc(np.asarray(rgb), 3).astype(np.float32)
        if input_range is None:
            input_range = 255.0 if rgb.max(initial=0.0) > 1.5 else 1.0
        rgb = np.clip(rgb / float(input_range), 0.0, 1.0)
        cube = rgb.reshape(-1, 3) @ self.coefficients + self.bias
        return np.clip(cube.reshape(*rgb.shape[:2], -1), 0.0, 1.0).astype(np.float32)

    def save(self, path: str | Path) -> None:
        np.savez(path, wavelengths_nm=self.wavelengths_nm, coefficients=self.coefficients, bias=self.bias)

    @classmethod
    def load(cls, path: str | Path) -> "RGBToHyperspectral":
        with np.load(path) as data:
            return cls(data["wavelengths_nm"], data["coefficients"], data["bias"])


def load_rgb(path: str | Path) -> np.ndarray:
    path = Path(path)
    if path.suffix.lower() == ".npy":
        return _as_hwc(np.load(path), 3)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image files; use an RGB .npy or install Pillow") from exc
    return np.asarray(Image.open(path).convert("RGB"))


def load_mat_cube(
    path: str | Path,
    img_key: str = "img",
    wavelengths_key: str | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Load the ``img`` and wavelength datasets used by ``coded_mask.py``.

    The v7.3/HDF5 format is loaded with h5py. Classic MATLAB files use
    scipy.io.loadmat. The returned cube is HWC and wavelengths are nanometers.
    ``coded_mask.py`` uses both ``wavelength`` and ``wavelengths`` in related
    contexts, so either key is accepted automatically.
    """
    path = Path(path)
    requested_wavelength_key = wavelengths_key
    try:
        import h5py
    except ImportError:
        h5py = None

    if h5py is not None and h5py.is_hdf5(path):
        with h5py.File(path, "r") as mat:
            if img_key not in mat:
                raise KeyError(f"{path} does not contain dataset {img_key!r}")
            candidates = [requested_wavelength_key] if requested_wavelength_key else ["wavelengths", "wavelength"]
            wavelength_key = next((key for key in candidates if key and key in mat), None)
            if wavelength_key is None:
                raise KeyError(f"{path} does not contain wavelengths/wavelength dataset")
            cube = np.asarray(mat[img_key][...])
            wavelengths = np.asarray(mat[wavelength_key][...]).squeeze()
    else:
        try:
            from scipy.io import loadmat
        except ImportError as exc:
            raise RuntimeError("MAT support requires h5py (v7.3) or scipy (classic MAT files)") from exc
        mat = loadmat(path)
        if img_key not in mat:
            raise KeyError(f"{path} does not contain variable {img_key!r}")
        candidates = [requested_wavelength_key] if requested_wavelength_key else ["wavelengths", "wavelength"]
        wavelength_key = next((key for key in candidates if key and key in mat), None)
        if wavelength_key is None:
            raise KeyError(f"{path} does not contain wavelengths/wavelength variable")
        cube = np.asarray(mat[img_key])
        wavelengths = np.asarray(mat[wavelength_key]).squeeze()

    wavelengths = wavelengths.astype(np.float32)
    if wavelengths.ndim != 1:
        raise ValueError(f"wavelengths must be one-dimensional, got {wavelengths.shape}")
    if np.nanmax(np.abs(wavelengths)) < 1e-3:
        wavelengths *= 1e9  # meters -> nm, as in coded_mask.py
    if cube.ndim != 3:
        raise ValueError(f"img must be a 3-D cube, got {cube.shape}")
    if cube.shape[0] == wavelengths.size:
        cube = np.moveaxis(cube, 0, -1)  # K,H,W -> H,W,K
    elif cube.shape[-1] != wavelengths.size:
        raise ValueError(f"cannot align img shape {cube.shape} with {wavelengths.shape} wavelengths")
    return cube.astype(np.float32, copy=False), wavelengths


def load_reference_cube(path: str | Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Load either a NumPy cube or a MATLAB cube."""
    if Path(path).suffix.lower() == ".mat":
        return load_mat_cube(path)
    return np.load(path), None


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fit = sub.add_parser("fit", help="fit a model from a hyperspectral .npy cube")
    fit.add_argument("cube", help="reference .npy cube or MATLAB .mat file containing img and wavelengths")
    fit.add_argument("model")
    fit.add_argument("--wavelengths", help="optional .npy wavelength vector")
    pred = sub.add_parser("predict", help="reconstruct an RGB image using a saved model")
    pred.add_argument("image")
    pred.add_argument("model")
    pred.add_argument("output")
    generic = sub.add_parser("generic", help="reconstruct using a generic smooth prior")
    generic.add_argument("image")
    generic.add_argument("output")
    generic.add_argument("--bands", type=int, default=31)
    args = parser.parse_args()
    if args.command == "fit":
        cube, mat_wavelengths = load_reference_cube(args.cube)
        wavelengths = np.load(args.wavelengths) if args.wavelengths else mat_wavelengths
        RGBToHyperspectral.fit(cube, wavelengths).save(args.model)
    else:
        model = RGBToHyperspectral.generic(args.bands) if args.command == "generic" else RGBToHyperspectral.load(args.model)
        cube = model.predict(load_rgb(args.image))
        np.save(args.output, cube)
        np.save(str(args.output).replace(".npy", "_wavelengths_nm.npy"), model.wavelengths_nm)


if __name__ == "__main__":
    _cli()
