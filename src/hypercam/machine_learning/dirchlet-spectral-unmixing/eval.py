# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-29
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Evaluate a trained checkpoint across frame densities (design.md §7).

The headline validation metric is ACCURACY vs EFFECTIVE FPS: for every
configured density (n_frames, frame_ms) the test split is re-clipped at that
density — the spectral target is constant per recording regardless of
density — and scored.  effective_fps = n_frames / acc_time = 1000/frame_ms.

Per density we also produce the §7 diagnostics: RMSE(lambda) on the
wavelength axis, the residual covariance (block-averaged for plotting), and
MACE calibration of the evidence strength S.  Artifacts land under
outputs/eval/<tag>/ with a top-level sweep table + figure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

import data as data_mod
from lit import LitDirichletNet

PROJECT_ROOT = Path(__file__).resolve().parent


def find_checkpoint(run_dir: Path, ckpt: Path | None) -> Path:
    """Resolve an explicit checkpoint or the newest one under a run dir."""
    if ckpt is not None:
        return ckpt
    candidates = sorted(run_dir.glob("checkpoints/*.ckpt"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(f"no checkpoints under {run_dir}/checkpoints")
    return candidates[-1]


def load_config(run_dir: Path) -> dict:
    """Read the resolved Hydra config saved with the run."""
    hydra_config = run_dir / ".hydra" / "config.yaml"
    if not hydra_config.is_file():
        raise SystemExit(f"resolved config not found: {hydra_config}")
    import yaml

    return yaml.safe_load(hydra_config.read_text())


def mace(s: np.ndarray, num_bins: int) -> np.ndarray:
    """Dirichlet mean-across-components expected squared error given (S, K)."""
    return (1.0 / num_bins) * (num_bins + s) / (s + 1.0)


@torch.no_grad()
def predict_split(model: LitDirichletNet, loader):
    """Collect expected spectrum, target, evidence S, and band per sample."""
    model.eval()
    device = next(model.parameters()).device
    expected, targets, strengths, bands = [], [], [], []
    for frames, ys, metas, density in loader:
        out = model.net.predict(frames.to(device), density.to(device))
        expected.append(out["expected_spectrum"].float().cpu())
        targets.append(ys.float())
        strengths.append(out["confidence"].squeeze(-1).float().cpu())
        bands.append(torch.tensor([meta["band_label"] for meta in metas]))
    return (
        torch.cat(expected).numpy(),
        torch.cat(targets).numpy(),
        torch.cat(strengths).numpy(),
        torch.cat(bands).numpy(),
    )


def compute_diagnostics(
    expected: np.ndarray, target: np.ndarray, strength: np.ndarray, num_bins: int
) -> dict:
    """RMSE(lambda), realized vs MACE squared error, and residual covariance."""
    residual = expected - target
    squared_error = (residual**2).sum(axis=1)
    return {
        "rmse_lambda": np.sqrt((residual**2).mean(axis=0)),
        "rmse_overall": float(np.sqrt((residual**2).mean())),
        "mae": float(np.abs(residual).mean()),
        "squared_error": squared_error,
        "predicted_mace": mace(strength, num_bins),
        "covariance": np.cov(residual, rowvar=False),
    }


def downsample_bins(values: np.ndarray, axis: int, max_bins: int) -> np.ndarray:
    """Block-average a long axis to at most ``max_bins`` for readable plots."""
    length = values.shape[axis]
    if length <= max_bins:
        return values
    factor = int(np.ceil(length / max_bins))
    keep = (length // factor) * factor
    sliced = np.take(values, np.arange(keep), axis=axis)
    shape = list(sliced.shape)
    shape[axis] = sliced.shape[axis] // factor
    shape.insert(axis + 1, factor)
    moved = sliced.reshape(shape)
    return moved.mean(axis=axis + 1)


def make_density_plots(
    wavelength: np.ndarray,
    diagnostics: dict,
    strength: np.ndarray,
    expected: np.ndarray,
    target: np.ndarray,
    out_dir: Path,
    label: str,
) -> list[Path]:
    """Render RMSE(lambda), covariance, MACE calibration, and overlays."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(wavelength, diagnostics["rmse_lambda"], lw=0.8)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("RMSE(λ)")
    ax.set_title(f"Per-wavelength RMSE — {label}")
    fig.tight_layout()
    path = out_dir / "rmse_lambda.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    paths.append(path)

    cov = downsample_bins(diagnostics["covariance"], 0, 128)
    cov = downsample_bins(cov, 1, 128)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cov, cmap="bwr", vmin=-np.abs(cov).max(), vmax=np.abs(cov).max())
    ax.set_title(f"Residual covariance (block-averaged) — {label}")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    path = out_dir / "residual_covariance.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    paths.append(path)

    min_per_bucket = max(1, len(strength) // 20)
    bins = np.quantile(strength, np.linspace(0, 1, 11))
    centers, realized, predicted = [], [], []
    for low, high in zip(bins[:-1], bins[1:]):
        mask = (strength >= low) & (strength <= high)
        if mask.sum() < min_per_bucket:
            continue
        centers.append(float(strength[mask].mean()))
        realized.append(float(diagnostics["squared_error"][mask].mean()))
        predicted.append(float(diagnostics["predicted_mace"][mask].mean()))
    if centers and min(centers) > 0:
        realized = [max(v, 1e-15) for v in realized]
        predicted = [max(v, 1e-15) for v in predicted]
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(centers, realized, "o-", label="realized MSE")
        ax.plot(centers, predicted, "s--", label="MACE (predicted)")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("evidence strength S (bucket mean)")
        ax.set_ylabel("squared error")
        ax.set_title(f"Calibration: realized vs MACE — {label}")
        ax.legend()
        fig.tight_layout()
        path = out_dir / "calibration_mace.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        paths.append(path)

    rng = np.random.default_rng(0)
    indices = rng.choice(len(expected), size=min(6, len(expected)), replace=False)
    fig, axes = plt.subplots(1, len(indices), figsize=(3.2 * len(indices), 3), sharey=True)
    for axis, index in zip(np.atleast_1d(axes), indices):
        axis.plot(wavelength, target[index], label="true", lw=0.9)
        axis.plot(wavelength, expected[index], label="pred", lw=0.9)
        axis.set_xlabel("nm")
    np.atleast_1d(axes)[0].legend(fontsize=7)
    fig.suptitle(f"Predicted vs true spectrum — {label}", y=1.02)
    fig.tight_layout()
    path = out_dir / "spectrum_overlays.png"
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def plot_sweep(rows: list[dict], out_dir: Path) -> Path:
    """The headline figure: accuracy vs effective fps across densities."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    fps = np.array([r["effective_fps"] for r in rows])
    rmse = np.array([r["rmse_overall"] for r in rows])
    mae = np.array([r["mae"] for r in rows])
    s_mean = np.array([r["mean_evidence_S"] for r in rows])
    for (n_frames, frame_ms), group in _group(rows):
        ax1.plot(
            [g["effective_fps"] for g in group],
            [g["rmse_overall"] for g in group],
            "o-",
            label=f"n={n_frames}",
        )
    ax1.set_xscale("log")
    ax1.set_xlabel("effective fps (n_frames / acc_time)")
    ax1.set_ylabel("simplex RMSE (lower is better)")
    ax1.set_title("Accuracy vs effective fps")
    ax1.legend()
    ax2.plot(fps, s_mean, "s-", color="tab:purple")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("effective fps")
    ax2.set_ylabel("mean evidence S")
    ax2.set_title("Evidence strength vs effective fps")
    fig.tight_layout()
    path = out_dir / "accuracy_vs_effective_fps.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def _group(rows: list[dict]):
    grouped: dict[tuple[int, float], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["n_frames"], row["frame_ms"]), []).append(row)
    yield from sorted(grouped.items())


def evaluate(run_dir: Path, ckpt_path: Path | None, split: str) -> dict:
    """Sweep every configured density on the given split; save all artifacts."""
    cfg = load_config(run_dir)
    checkpoint = find_checkpoint(run_dir, ckpt_path)
    manifest_path = PROJECT_ROOT / cfg["data"]["manifest"]
    grid = np.load(manifest_path.parent / "wavelength_grid.npy")
    num_bins = int(len(grid))

    model = LitDirichletNet.load_from_checkpoint(checkpoint)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    common = dict(
        library_dir=PROJECT_ROOT / cfg["evt3"]["library_dir"],
        cache_dir=PROJECT_ROOT / cfg["data"]["cache_dir"],
        polarity_mode=cfg["evt3"]["polarity_mode"],
        accumulation_us=int(cfg["evt3"]["accumulation_us"]),
        min_accumulations_per_frame=int(cfg["data"]["min_accumulations_per_frame"]),
        transform=cfg["data"]["transform"],
        clips_per_density=cfg["data"]["clips_per_density"],
        max_recordings=cfg["data"].get("max_recordings"),
        crop=cfg["data"]["crop"],
        highpass_px=int(cfg["data"]["highpass_px"]),
        normalize=cfg["data"]["normalize"],
    )
    out_root = PROJECT_ROOT / "outputs/eval" / run_dir.parent.name
    rows: list[dict] = []
    for density in cfg["data"]["densities"]:
        n_frames, frame_ms = int(density["n_frames"]), float(density["frame_ms"])
        dataset = data_mod.ManifestDataset(
            manifest_path, split, densities=[{"n_frames": n_frames, "frame_ms": frame_ms}], **common
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=int(cfg["training"]["batch_size"]), shuffle=False,
            num_workers=0, collate_fn=data_mod.collate,
        )
        expected, target, strength, bands = predict_split(model, loader)
        diagnostics = compute_diagnostics(expected, target, strength, num_bins)
        label = f"n{n_frames}@{frame_ms:g}ms"
        figures = make_density_plots(
            grid, diagnostics, strength, expected, target,
            out_root / f"density_{label}", label,
        )
        row = {
            "n_frames": n_frames,
            "frame_ms": frame_ms,
            "acc_time_ms": n_frames * frame_ms,
            "effective_fps": 1000.0 / frame_ms,
            "num_samples": int(len(expected)),
            "rmse_overall": diagnostics["rmse_overall"],
            "mae": diagnostics["mae"],
            "mean_squared_error": float(diagnostics["squared_error"].mean()),
            "mean_mace": float(diagnostics["predicted_mace"].mean()),
            "mean_evidence_S": float(strength.mean()),
            "band_counts": {int(b): int((bands == b).sum()) for b in np.unique(bands)},
            "figures": [str(p) for p in figures],
        }
        row["calibration_ratio"] = row["mean_squared_error"] / max(row["mean_mace"], 1e-12)
        rows.append(row)
        print(
            f"{label:>16}: eff_fps={row['effective_fps']:6.1f}  "
            f"rmse={row['rmse_overall']:.5f}  mae={row['mae']:.6f}  "
            f"S={row['mean_evidence_S']:.0f}  cal={row['calibration_ratio']:.2f}"
        )

    sweep_figure = plot_sweep(rows, out_root)
    summary = {
        "run_dir": str(run_dir),
        "checkpoint": str(checkpoint),
        "split": split,
        "num_bins": num_bins,
        "densities": rows,
        "sweep_figure": str(sweep_figure),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="outputs/train/<tag>/<timestamp> directory")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="explicit .ckpt (default: newest under run dir)")
    parser.add_argument("--split", default="test", choices=("test", "val", "train"))
    return parser


if __name__ == "__main__":
    args = make_parser().parse_args()
    result = evaluate(args.run_dir, args.checkpoint, args.split)
    print(json.dumps({k: v for k, v in result.items() if k != "densities"}, indent=2))
