# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Hydra training entrypoint for the Dirichlet spectral-unmixing model.

Usage:
  uv run python train.py
  uv run python train.py out.tag=smoke data.max_recordings=2 \
      data.clips_per_density=1 training.max_epochs=2
  uv run python train.py data.crop=128 data.highpass_px=64
  uv run python train.py 'data.densities=[{n_frames:4,frame_ms:50.0}]'

Artifacts under outputs/train/<tag>/<timestamp>/ (CSV, TensorBoard,
checkpoints, resolved config). Training REFUSES to start when the manifest
gate failed (outputs/manifests/gates.json) unless force=true. K (number of
spectral bins) comes from the manifest's wavelength grid;
model.spectral_bins only overrides it deliberately.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
import lightning as L
import torch
from hydra.core.hydra_config import HydraConfig
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
from lightning.pytorch.loggers import CSVLogger, TensorBoardLogger
from omegaconf import DictConfig, OmegaConf

import data as data_mod
from lit import LitDirichletNet

PROJECT_ROOT = Path(__file__).resolve().parent


def load_manifest_bins(cfg: DictConfig) -> tuple[int, dict]:
    """Read K (and the gate summary) from the built manifest artifacts."""
    gates_path = PROJECT_ROOT / cfg.data.gates
    if not gates_path.is_file():
        raise SystemExit(
            f"{gates_path} missing — run build_manifest.py first (or point "
            "data.gates at an existing gates.json)"
        )
    gates = json.loads(gates_path.read_text())
    if not gates.get("passed") and not cfg.force:
        raise SystemExit(
            "manifest gate FAILED "
            f"({gates.get('num_pairs', 0)} usable pairs, "
            f"{len(gates.get('excluded', []))} excluded). "
            "Fix the data or re-run with force=true."
        )
    bins = int(gates["spectral_bins"])
    if cfg.model.spectral_bins is not None:
        bins = int(cfg.model.spectral_bins)
    if bins < 2:
        raise SystemExit(f"suspicious spectral_bins={bins}; refusing to train")
    return bins, gates


def build_loggers(cfg: DictConfig):
    """CSV + TensorBoard always; MLflow when enabled and reachable.

    MLflow credentials come from the environment (MLFLOW_TRACKING_USERNAME /
    MLFLOW_TRACKING_PASSWORD against the Basic-auth server); nothing secret
    is stored in configs. A failing MLflow connection degrades to local
    logging with a warning instead of killing the run.
    """
    run_dir = Path(HydraConfig.get().runtime.output_dir)
    loggers = [
        CSVLogger(save_dir=run_dir, name="csv"),
        TensorBoardLogger(save_dir=run_dir, name="tensorboard"),
    ]
    if cfg.logging.mlflow.enabled:
        try:
            from lightning.pytorch.loggers import MLflowLogger

            uri = os.environ.get("MLFLOW_TRACKING_URI", cfg.logging.mlflow.tracking_uri)
            logger = MLflowLogger(
                tracking_uri=uri,
                experiment_name=cfg.logging.mlflow.experiment_name,
                run_name=f"{cfg.out.tag}-{run_dir.name}",
                log_model=False,
            )
            logger.experiment  # force connection; raises when unreachable
            loggers.append(logger)
        except Exception as error:  # noqa: BLE001 - degrade, never kill training
            print(f"WARNING: MLflow unavailable ({error}); continuing locally")
    return loggers


@hydra.main(version_base="1.3", config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    # INFO to stdout AND train.log so long decode/build phases show progress.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logger = logging.getLogger("train")
    print(OmegaConf.to_yaml(cfg))
    L.seed_everything(int(cfg.training.seed), workers=True)

    spectral_bins, gates = load_manifest_bins(cfg)
    logger.info(
        "manifest: %d pairs, K=%d, splits=%s",
        gates["num_pairs"], spectral_bins, gates["split_counts"],
    )

    logger.info("building dataloaders (uncached recordings decode inline here; "
                "run predecode.py --jobs 22 once to avoid this)")
    loaders = data_mod.build_dataloaders(
        cfg, batch_size=int(cfg.training.batch_size), num_workers=int(cfg.data.num_workers)
    )
    logger.info("dataloaders ready; constructing model")
    model = LitDirichletNet(
        num_spectral_bins=spectral_bins,
        channels=tuple(cfg.model.channels),
        hidden_dim=int(cfg.model.hidden_dim),
        **OmegaConf.to_container(cfg.model.loss, resolve=True),
        lr=float(cfg.training.lr),
        weight_decay=float(cfg.training.weight_decay),
        max_epochs=int(cfg.training.max_epochs),
    )

    callbacks = [
        ModelCheckpoint(
            dirpath=Path(HydraConfig.get().runtime.output_dir) / "checkpoints",
            monitor="val/nll",
            mode="min",
            save_top_k=2,
            filename="epoch{epoch:03d}",
        ),
        EarlyStopping(monitor="val/nll", mode="min", patience=int(cfg.training.patience)),
    ]
    trainer = L.Trainer(
        accelerator=cfg.training.accelerator,
        devices=cfg.training.devices,
        max_epochs=int(cfg.training.max_epochs),
        callbacks=callbacks,
        logger=build_loggers(cfg),
        default_root_dir=HydraConfig.get().runtime.output_dir,
        enable_progress_bar=True,
    )
    if not torch.cuda.is_available() and cfg.training.accelerator == "auto":
        print("NOTE: no CUDA available; Lightning will run on CPU")
    trainer.fit(model, train_dataloaders=loaders["train"], val_dataloaders=loaders["val"])
    if "test" in loaders:
        trainer.test(model, dataloaders=loaders["test"], ckpt_path="best")


if __name__ == "__main__":
    main()
