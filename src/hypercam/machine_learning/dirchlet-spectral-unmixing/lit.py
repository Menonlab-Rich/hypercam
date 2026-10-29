# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Lightning module wrapping SpectralDirichletNet + DirichletEvidenceLoss.

Per-split scalars (withdoe logging convention): ``loss`` (total), ``nll``,
``kl``, ``rmse_d2`` (simplex RMSE = sqrt(mean ||p_hat - y||^2)), ``mae``
(mean absolute per-bin residual), ``s_mean``/``s_max`` (evidence strength,
kept visible because NLL alone is unbounded in S).

Optimizer policy (design.md §5.2, chosen over withdoe's plain AdamW):
AdamW with CosineAnnealingLR(T_max=max_epochs).
"""

from __future__ import annotations

import torch
import lightning as L

import loss as loss_mod
import model as model_mod


class LitDirichletNet(L.LightningModule):
    """Trainable wrapper: forward, loss, metrics, optimizer schedule."""

    def __init__(
        self,
        num_spectral_bins: int,
        in_channels: int = 1,
        channels: tuple[int, ...] = (32, 64, 128),
        hidden_dim: int = 256,
        pool_spatial: int = 4,
        num_groups: int = 8,
        eps: float = 1e-7,
        kl_lambda: float = 0.05,
        kl_warmup_epochs: int = 10,
        kl_modulated: bool = True,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        max_epochs: int = 100,
    ):
        super().__init__()
        self.save_hyperparameters()
        self.net = model_mod.SpectralDirichletNet(
            num_spectral_bins=num_spectral_bins,
            in_channels=in_channels,
            channels=tuple(channels),
            hidden_dim=hidden_dim,
            pool_spatial=pool_spatial,
            num_groups=num_groups,
        )
        self.criterion = loss_mod.DirichletEvidenceLoss(
            eps=eps,
            kl_lambda=kl_lambda,
            kl_warmup_epochs=kl_warmup_epochs,
            kl_modulated=kl_modulated,
        )

    def forward(self, x: torch.Tensor, density: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(x, density)

    def _shared_step(self, batch, stage: str) -> torch.Tensor:
        x, y, _meta, density = batch
        alpha = self.net(x, density)
        out = self.criterion(alpha, y, epoch=self.current_epoch)
        s = alpha.sum(dim=-1)
        p_hat = alpha / s.unsqueeze(-1)
        residual = p_hat - y
        rmse_d2 = torch.sqrt((residual.pow(2).sum(dim=-1)).mean())
        self.log(f"{stage}/loss", out["total"], prog_bar=(stage == "train"))
        self.log(f"{stage}/nll", out["nll"], prog_bar=(stage != "train"))
        self.log(f"{stage}/kl", out["kl"])
        self.log(f"{stage}/rmse_d2", rmse_d2, prog_bar=(stage != "train"))
        self.log(f"{stage}/mae", residual.abs().mean())
        self.log(f"{stage}/s_mean", s.mean())
        self.log(f"{stage}/s_max", s.max())
        return out["total"]

    def training_step(self, batch, batch_idx):
        return self._shared_step(batch, "train")

    def validation_step(self, batch, batch_idx):
        return self._shared_step(batch, "val")

    def test_step(self, batch, batch_idx):
        return self._shared_step(batch, "test")

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.hparams.lr,
            weight_decay=self.hparams.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(int(self.hparams.max_epochs), 1)
        )
        return [optimizer], [scheduler]


if __name__ == "__main__":
    torch.manual_seed(0)
    bins = 16
    lit = LitDirichletNet(num_spectral_bins=bins, max_epochs=5)
    x = torch.rand(2, 4, 128, 128)
    density = torch.rand(2, 3)
    y = torch.distributions.Dirichlet(torch.full((bins,), 2.0)).sample((2,))
    alpha = lit(x, density)
    assert alpha.shape == (2, bins)
    out = lit.criterion(alpha, y, epoch=0)
    assert torch.isfinite(out["total"])
    (out["total"] / 2).backward()
    grads = [p.grad for p in lit.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)
    batch = (x, y, [{"i": 0}, {"i": 1}], density)
    lit.training_step(batch, 0)
    lit.eval()
    lit.validation_step(batch, 0)
    lit.test_step(batch, 0)
    optimizers, schedulers = lit.configure_optimizers()
    assert len(optimizers) == 1 and len(schedulers) == 1
    print("LIT SELFTEST OK")
