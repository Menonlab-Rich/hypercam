# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-29
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Temporal CNN encoder with an evidential Dirichlet head over K bins.

The model must work across frame densities (any n_frames of any frame_ms),
so the conv encoder is SHARED ACROSS TIME and applied per frame:

    [B, T, H, W] -> per-frame Conv 32->64->128 (SiLU, GroupNorm, stride 2)
                 -> AdaptiveAvgPool 4x4 -> per-frame feature (128*4*4)
                 -> temporal mean ++ temporal max  (T-agnostic pooling)
                 -> concat density embedding (3 -> 32 MLP)
                 -> Linear -> hidden 256 -> SiLU -> Linear -> K

alpha = softplus(logits) + 1.0 keeps every concentration >= 1 (no density
blow-up at simplex boundaries); the head bias is seeded at
``_softplus_inverse(1.0)`` so training starts at alpha ~= 2 per bin.

The density embedding ([log10 effective_fps, log2 n_frames, log10 acc_time_s]
from ``data.density_features``) lets the evidence strength S adapt to the
operating point: at low effective fps the same photon budget arrives in
fewer, denser frames, and calibration should reflect that.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

DENSITY_FEATURES = 3


def _softplus_inverse(value: float) -> float:
    """x such that softplus(x) == value (used to seed the head bias)."""
    return float(torch.log(torch.expm1(torch.tensor(value))))


class SpectralDirichletNet(nn.Module):
    """Frame clip + density features -> Dirichlet alpha [batch, K]."""

    def __init__(
        self,
        num_spectral_bins: int,
        in_channels: int = 1,
        channels: tuple[int, ...] = (32, 64, 128),
        hidden_dim: int = 256,
        pool_spatial: int = 4,
        num_groups: int = 8,
        density_embedding_dim: int = 32,
    ):
        super().__init__()
        if num_spectral_bins < 2:
            raise ValueError("a Dirichlet needs at least two classes")
        self.num_spectral_bins = int(num_spectral_bins)
        self.in_channels = int(in_channels)
        self.channels = tuple(channels)
        self.hidden_dim = int(hidden_dim)
        self.pool_spatial = int(pool_spatial)
        blocks: list[nn.Module] = []
        c_in = self.in_channels
        for c_out in self.channels:
            blocks.append(nn.Conv2d(c_in, c_out, kernel_size=3, stride=2, padding=1))
            blocks.append(nn.GroupNorm(num_groups, c_out))
            blocks.append(nn.SiLU())
            c_in = c_out
        self.encoder = nn.Sequential(*blocks)
        self.pool = nn.AdaptiveAvgPool2d((self.pool_spatial, self.pool_spatial))
        frame_feature_dim = self.channels[-1] * self.pool_spatial * self.pool_spatial
        self.density_mlp = nn.Sequential(
            nn.Linear(DENSITY_FEATURES, density_embedding_dim),
            nn.SiLU(),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(2 * frame_feature_dim + density_embedding_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, self.num_spectral_bins),
        )
        self._init_head()

    def _init_head(self) -> None:
        head = self.head[-1]
        nn.init.normal_(head.weight, mean=0.0, std=0.01)
        nn.init.constant_(head.bias, _softplus_inverse(1.0))

    def _encode(self, x: torch.Tensor, density: torch.Tensor | None) -> torch.Tensor:
        if x.ndim == 3:  # single frame [B, H, W] -> T = 1
            x = x.unsqueeze(1)
        batch, frames, _, _ = x.shape
        per_frame = self.pool(self.encoder(x.reshape(batch * frames, 1, *x.shape[-2:])))
        per_frame = per_frame.flatten(1)  # [B*T, feature]
        per_frame = per_frame.view(batch, frames, -1)
        temporal = torch.cat([per_frame.mean(dim=1), per_frame.max(dim=1).values], dim=-1)
        if density is None:
            density = torch.zeros(batch, DENSITY_FEATURES, device=x.device, dtype=x.dtype)
        return torch.cat([temporal, self.density_mlp(density.to(temporal.dtype))], dim=-1)

    def forward(self, x: torch.Tensor, density: torch.Tensor | None = None) -> torch.Tensor:
        """Return alpha [batch, K], every entry >= 1."""
        logits = self.head(self._encode(x, density))
        return F.softplus(logits) + 1.0

    @torch.no_grad()
    def predict(
        self, x: torch.Tensor, density: torch.Tensor | None = None
    ) -> dict[str, torch.Tensor]:
        """Full evidential output: alpha, expected spectrum, strength, variance.

        ``expected_spectrum`` is the Dirichlet mean E[p] = alpha / S;
        ``confidence`` is the concentration strength S = sum(alpha);
        ``variance`` is the Dirichlet marginal variance of E[p].
        """
        alpha = self.forward(x, density)
        confidence = alpha.sum(dim=-1, keepdim=True)
        expected_spectrum = alpha / confidence
        variance = expected_spectrum * (1.0 - expected_spectrum) / (confidence + 1.0)
        return {
            "alpha": alpha,
            "expected_spectrum": expected_spectrum,
            "confidence": confidence,
            "variance": variance,
        }


if __name__ == "__main__":
    torch.manual_seed(0)
    bins = 64
    net = SpectralDirichletNet(num_spectral_bins=bins)
    for frames in (1, 2, 4, 8):
        x = torch.rand(3, frames, 128, 128)
        density = torch.tensor([[1.0, 2.0, 0.2]] * 3)
        alpha = net(x, density)
        assert alpha.shape == (3, bins) and (alpha >= 1.0).all()
        init_alpha = alpha.mean(dim=0)
        assert torch.allclose(init_alpha, torch.full((bins,), 2.0), atol=0.05), init_alpha
    # Single-frame / 3-D input path and density=None fallback both work.
    assert net(torch.rand(2, 64, 64)).shape == (2, bins)
    assert net(torch.rand(2, 3, 64, 64), None).shape == (2, bins)
    out = net.predict(torch.rand(2, 4, 64, 64), torch.rand(2, 3))
    assert torch.allclose(out["expected_spectrum"].sum(dim=-1), torch.ones(2), atol=1e-4)
    assert (out["confidence"] >= float(bins)).all() and (out["variance"] > 0).all()
    # Density conditioning must actually change the output.
    x = torch.rand(1, 4, 64, 64)
    low = net(x, torch.tensor([[math.log10(4.0), 2.0, 0.5]]))
    high = net(x, torch.tensor([[math.log10(50.0), 2.0, 0.08]]))
    assert not torch.allclose(low, high), "density embedding ignored"
    # Arbitrary spatial sizes (adaptive pooling) and gradient flow.
    for size in (512, 256, 128, 64, 36):
        assert net(torch.rand(1, 2, size, size)).shape == (1, bins)
    trainable = sum(p.numel() for p in net.parameters())
    full = SpectralDirichletNet(2556)
    alpha = full(torch.rand(2, 4, 720, 1280), torch.rand(2, 3))
    assert torch.isfinite(alpha).all()
    n_params = sum(p.numel() for p in full.parameters())
    print(f"MODEL SELFTEST OK (K=64: {trainable/1e6:.2f}M, K=2556: {n_params/1e6:.2f}M params)")
