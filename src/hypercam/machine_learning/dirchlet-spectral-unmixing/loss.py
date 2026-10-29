# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Dirichlet NLL + annealed KL-to-uniform regularizer (design.md §4).

NLL (design §4.1), with ``S = sum(alpha)`` and ``y`` clamped away from the
simplex corners:

    L_NLL = -lgamma(S) + sum_k lgamma(alpha_k)
            - sum_k (alpha_k - 1) * log(y_k + eps)

KL toward the flat prior Dir(1_K) (design §4.2), K-generic — the withdoe
prior art hardcodes ``lgamma(3)`` and a ``-1.5`` digamma constant; here both
are computed at runtime from ``K = alpha.shape[-1]``:

    KL(Dir(alpha) || Dir(1_K)) = lgamma(S) - lgamma(K) - sum_k lgamma(alpha_k)
                                 + sum_k (alpha_k - 1)(digamma(alpha_k) - digamma(S))

The evidence term uses the Sensoy-style modulation
``alpha_tilde = y + (1 - y) * alpha`` so correct evidence is not penalized.
``lambda(e) = kl_lambda * min(1, e / kl_warmup_epochs)`` anneals the KL on.

Note: the withdoe KL helper is an approximation (it uses a constant
``-1.5`` in place of ``-digamma(K)`` and flips the digamma difference);
this module implements the exact closed form from design.md §4.2, verified
by Monte Carlo in the selftest.
"""

from __future__ import annotations

import torch
import torch.nn as nn


def dirichlet_nll(alpha: torch.Tensor, y: torch.Tensor, eps: float = 1e-7) -> torch.Tensor:
    """Negative log-likelihood of target simplex y under Dir(alpha), per sample."""
    y = torch.clamp(y, eps, 1.0 - eps)
    s = alpha.sum(dim=-1, keepdim=True)
    log_gamma_s = torch.lgamma(s)
    sum_log_gamma_alpha = torch.lgamma(alpha).sum(dim=-1, keepdim=True)
    weighted_log_y = ((alpha - 1.0) * torch.log(y)).sum(dim=-1, keepdim=True)
    return -(log_gamma_s - sum_log_gamma_alpha + weighted_log_y).squeeze(-1)


def kl_dirichlet_to_uniform(alpha: torch.Tensor) -> torch.Tensor:
    """Exact KL(Dir(alpha) || Dir(1_K)); zero at alpha = ones, K-generic."""
    num_bins = alpha.shape[-1]
    s = alpha.sum(dim=-1, keepdim=True)
    log_gamma_k = float(torch.lgamma(torch.tensor(float(num_bins))).item())
    t1 = torch.lgamma(s) - log_gamma_k - torch.lgamma(alpha).sum(dim=-1, keepdim=True)
    t2 = ((alpha - 1.0) * (torch.digamma(alpha) - torch.digamma(s))).sum(dim=-1, keepdim=True)
    return (t1 + t2).squeeze(-1)


def modulated_alpha(alpha: torch.Tensor, y: torch.Tensor, eps: float = 1e-7) -> torch.Tensor:
    """alpha_tilde = y + (1 - y) * alpha (design §4.2 evidence masking)."""
    y = torch.clamp(y, eps, 1.0 - eps)
    return y + (1.0 - y) * alpha


class DirichletEvidenceLoss(nn.Module):
    """NLL + annealed (optionally modulated) KL-to-uniform evidence loss."""

    def __init__(
        self,
        eps: float = 1e-7,
        kl_lambda: float = 0.05,
        kl_warmup_epochs: int = 10,
        kl_modulated: bool = True,
    ):
        super().__init__()
        self.eps = float(eps)
        self.kl_lambda = float(kl_lambda)
        self.kl_warmup_epochs = max(int(kl_warmup_epochs), 1)
        self.kl_modulated = bool(kl_modulated)

    def lambda_eff(self, epoch: int) -> float:
        """Linear warmup of the KL weight: kl_lambda * min(1, epoch/warmup)."""
        return self.kl_lambda * min(1.0, max(int(epoch), 0) / self.kl_warmup_epochs)

    def forward(
        self, alpha: torch.Tensor, y: torch.Tensor, epoch: int = 0
    ) -> dict[str, torch.Tensor]:
        nll = dirichlet_nll(alpha, y, self.eps)
        alpha_tilde = modulated_alpha(alpha, y, self.eps) if self.kl_modulated else alpha
        kl = kl_dirichlet_to_uniform(alpha_tilde)
        lam = self.lambda_eff(epoch)
        total = nll + lam * kl
        return {
            "total": total.mean(),
            "nll": nll.mean(),
            "kl": kl.mean(),
            "lambda_eff": torch.tensor(lam, device=alpha.device),
            "per_sample": total,
        }


if __name__ == "__main__":
    torch.manual_seed(0)

    # Exact KL verification by Monte Carlo against sampled Dirichlets, K=3
    # and K=5 (the withdoe constants only exist for K=3; ours is general).
    for bins, alpha_true in ((3, [5.0, 2.0, 1.0]), (5, [3.0, 3.0, 3.0, 2.0, 2.0])):
        concentration = torch.tensor(alpha_true)
        samples = torch.distributions.Dirichlet(concentration).sample((200_000,))
        log_p = torch.distributions.Dirichlet(concentration).log_prob(samples)
        uniform = torch.distributions.Dirichlet(torch.ones(bins))
        log_q = uniform.log_prob(samples)
        mc_kl = (log_p - log_q).mean().item()
        analytic = kl_dirichlet_to_uniform(concentration.unsqueeze(0)).item()
        assert abs(mc_kl - analytic) < 0.02, (bins, mc_kl, analytic)

    # Zero at alpha = ones for any K; strictly positive otherwise.
    for bins in (3, 8, 2556):
        assert abs(kl_dirichlet_to_uniform(torch.ones(1, bins)).item()) < 1e-4
        assert kl_dirichlet_to_uniform(torch.full((1, bins), 5.0)).item() > 0.0

    # NLL ordering: aligned evidence beats uniform beats misaligned.
    y = torch.tensor([[0.6, 0.3, 0.1]])
    nll_aligned = dirichlet_nll(torch.tensor([[7.0, 4.0, 2.0]]), y).item()
    nll_uniform = dirichlet_nll(torch.ones(1, 3), y).item()
    nll_misaligned = dirichlet_nll(torch.tensor([[2.0, 7.0, 4.0]]), y).item()
    assert nll_aligned < nll_uniform < nll_misaligned

    loss_fn = DirichletEvidenceLoss(kl_lambda=0.05, kl_warmup_epochs=10)
    assert loss_fn.lambda_eff(0) == 0.0
    assert 0.0 < loss_fn.lambda_eff(5) < loss_fn.kl_lambda
    assert loss_fn.lambda_eff(100) == loss_fn.kl_lambda

    # K=4096-scale numerics: finite loss and gradients, edge targets.
    big_alpha = torch.full((4, 4096), 2.0, requires_grad=True)
    big_y = torch.full((4, 4096), 1.0 / 4096.0)
    big_y[0, 0] = 1.0
    big_y = big_y / big_y.sum(dim=-1, keepdim=True)
    out = loss_fn(big_alpha, big_y, epoch=20)
    assert torch.isfinite(out["total"]), out
    out["total"].backward()
    assert torch.isfinite(big_alpha.grad).all() and big_alpha.grad.norm() > 0

    print("LOSS SELFTEST OK")
