# Technical Design Document: High-Dimensional Continuous Dirichlet Spectral Unmixing from DOE-Collapsed Sensor Planes

**System Focus:** Inverting $1280 \times 720$ DOE Spatial Intensity Fields into 4096-Bin Continuous Spectral Distributions via Evidential Dirichlet Regression (PyTorch Lightning + Hydra)

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Physical Inverse Problem
Modern high-throughput optical assays rely on Diffractive Optical Elements (DOEs) to compress spectral distributions into 2D spatial patterns on a monochrome image sensor. This physical forward measurement operator $\mathcal{A}$ projects a high-dimensional continuous spectrum $S(\lambda)$ into a spatial intensity map $I(x, y)$:

$$\mathcal{A}: L^2(\mathbb{R}) \to L^2(\mathbb{R}^2), \quad I(x, y) = \int_{\lambda_{\min}}^{\lambda_{\max}} \mathcal{K}(x, y; \lambda) S(\lambda) \, d\lambda + \eta$$

where $\mathcal{K}(x, y; \lambda)$ is the spatial-spectral Point Spread Function (PSF) kernel of the DOE, and $\eta$ is physical sensor noise.

### 1.2 Hilbert Space Transition
* **Target Domain ($\mathcal{H}_{4096}$):** The true ground-truth spectrum $S(\lambda)$ is measured by a physical reference spectrometer at $K = 4096$ discrete wavelength samples ($\text{wavelength\_nm} \in [\lambda_1, \dots, \lambda_{4096}]$). Normalized by total integrated counts, $S(\lambda)$ forms a probability vector $\mathbf{y}$ on a 4095-simplex ($\Delta^{4095}$):
  $$\mathbf{y} = [y_1, y_2, \dots, y_{4096}]^T, \quad \sum_{k=1}^{4096} y_k = 1.0, \quad y_k \ge 0$$
* **Measurement Domain ($L^2(\mathbb{R}^2)$):** The sensor captures a collapsed 2D Euclidean spatial intensity tensor $\mathbf{X} \in \mathbb{R}^{1 \times 720 \times 1280}$.

Because square-law detection ($I(x,y) = |E(x,y)|^2$) discards phase coherence, reversing $\mathcal{A}$ is ill-posed. Instead of attempting spatial image reconstruction, our inverse model $f_\Theta(\mathbf{X})$ directly predicts the continuous Dirichlet concentration parameters $\boldsymbol{\alpha} \in \mathbb{R}_{+}^{4096}$ over the 4095-simplex, yielding the expected spectral distribution $\mathbf{\hat{p}}$ and model confidence $S$.

---

## 2. Dataset Schema & Ingestion Pipeline

### 2.1 Spectrometer Ground Truth (Parquet Schema)
Reference spectra are stored as single row-group Parquet files containing $K = 4096$ spectral bins per acquisition:

```
# Arrow Schema
spectrum_index:      int64       (0 to 4095)
acquired_utc_ms:     int64       (Timestamp)
tick:                uint64      (Hardware timer tick)
exposure_ms:         double      (Spectrometer integration time)
hw_average:          int64       (Hardware frame averaging count)
triggered:           boolean     (Trigger status)
amplitude_corrected: boolean     (Dark-subtracted & calibrated)
wavelength_nm:       double      (Wavelength axis, e.g., 350.0 to 1050.0 nm)
intensity_counts:    double      (Raw energy counts)
```

### 2.2 Spectrum Normalization
For each spectrometer event, the target vector $\mathbf{y} \in \Delta^{4095}$ is computed by normalizing the calibrated intensity counts across all 4096 sorted wavelength rows:

$$y_k = \frac{\text{intensity\_counts}_k}{\sum_{j=1}^{4096} \text{intensity\_counts}_j + \epsilon}$$

### 2.3 Spatial Sensor Tensor
* **Dimensions:** $1280 \times 720$ pixels (Monochrome uint16 or dark-subtracted float32).
* **Pre-processing:** Dark-frame subtraction, flat-field correction, and cropping/rescaling to $[1, 1, 720, 1280]$.

---

## 3. Mathematical Formulation of Evidential Dirichlet Regression

### 3.1 Model Output & Parameterization
Given input frame $\mathbf{X} \in \mathbb{R}^{1 \times 720 \times 1280}$, the neural network outputs 4096 positive concentration parameters:

$$\boldsymbol{\alpha}(\mathbf{X}) = f_\Theta(\mathbf{X}) = \text{Softplus}(g_\Theta(\mathbf{X})) + 1.0, \quad \boldsymbol{\alpha} \in \mathbb{R}_{+}^{4096}$$

Adding $1.0$ enforces $\alpha_k \ge 1.0$, preventing probability density blow-up ($\alpha_k < 1.0$) at the boundary faces of the high-dimensional simplex.

### 3.2 Expected Spectrum & Total Precision (Confidence)
* **Expected Spectral Distribution ($\mathbf{\hat{p}}$):**
  $$\hat{p}_k = \mathbb{E}[y_k] = \frac{\alpha_k}{S}, \quad \text{where } S = \sum_{k=1}^{4096} \alpha_k$$
* **Total Confidence / Evidence ($S$):** The sum $S$ parameterizes the precision of the Dirichlet distribution. Higher $S$ corresponds to narrow variance around the expected spectrum $\mathbf{\hat{p}}$.
* **Per-Bin Spectral Variance:**
  $$\text{Var}(y_k) = \frac{\hat{p}_k (1 - \hat{p}_k)}{S + 1}$$

---

## 4. Loss Function & Annealed Regularization

Training directly minimizes the Negative Log-Likelihood (NLL) of the predicted Dirichlet distribution given ground-truth vector $\mathbf{y} \in \Delta^{4095}$, supplemented by an annealed Kullback-Leibler (KL) divergence penalty toward a uniform prior $\text{Dir}(\mathbf{1}_{4096})$.

### 4.1 Dirichlet Negative Log-Likelihood
$$\mathcal{L}_{\text{NLL}}(\boldsymbol{\alpha}, \mathbf{y}) = -\ln \Gamma(S) + \sum_{k=1}^{4096} \ln \Gamma(\alpha_k) - \sum_{k=1}^{4096} (\alpha_k - 1) \ln(y_k + \epsilon)$$

### 4.2 Annealed KL Regularization
Because NLL alone is unbounded with respect to $S$ (which can cause overconfidence on ambiguous spatial patterns), we penalize the KL divergence between the predicted Dirichlet distribution and a uniform flat prior $\text{Dir}(\mathbf{1}_{4096})$ ($S = 4096$):

$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{NLL}}(\boldsymbol{\alpha}, \mathbf{y}) + \lambda(e) \cdot \mathcal{D}_{\text{KL}}\left(\text{Dir}(\boldsymbol{\tilde{\alpha}}) \parallel \text{Dir}(\mathbf{1}_{4096})\right)$$

where $\boldsymbol{\tilde{\alpha}} = \mathbf{y} + (1 - \mathbf{y}) \odot \boldsymbol{\alpha}$ masks out target truth to avoid penalizing correct evidence, and the annealing factor $\lambda(e)$ scales linearly during warmup:

$$\lambda(e) = \min\left(1.0, \frac{e}{\text{warmup\_epochs}}\right)$$

---

## 5. Hydra Configuration & PyTorch Lightning Implementation

### 5.1 Hydra Configuration Structure (`configs/config.yaml`)

```yaml
# configs/config.yaml
defaults:
  - model: spatial_encoder
  - data: parquet_sensor
  - trainer: default
  - _self_

dataset:
  data_dir: "/data/experiment_run_02"
  batch_size: 16
  num_workers: 8
  image_height: 720
  image_width: 1280
  num_spectral_bins: 4096

model:
  learning_rate: 1e-4
  weight_decay: 1e-5
  warmup_epochs: 10
  kl_max_weight: 1.0

trainer:
  max_epochs: 100
  accelerator: "gpu"
  devices: 1
  precision: "16-mixed"
```

### 5.2 PyTorch Lightning Module & DataModule

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
import pyarrow.parquet as pq
import numpy as np
import hydra
from omegaconf import DictConfig

# -----------------------------------------------------------------------------
# 1. Dirichlet Evidential Loss Module
# -----------------------------------------------------------------------------
class Dirichlet4096Loss(nn.Module):
    def __init__(self, eps: float = 1e-7):
        super().__init__()
        self.eps = eps

    def forward(self, alpha: torch.Tensor, y_target: torch.Tensor, kl_weight: float = 1.0) -> torch.Tensor:
        y_target = torch.clamp(y_target, self.eps, 1.0 - self.eps)
        S = torch.sum(alpha, dim=-1, keepdim=True)
        
        # Dirichlet NLL
        log_gamma_S = torch.lgamma(S)
        sum_log_gamma_alpha = torch.sum(torch.lgamma(alpha), dim=-1, keepdim=True)
        weighted_log_y = torch.sum((alpha - 1.0) * torch.log(y_target), dim=-1, keepdim=True)
        nll = -(log_gamma_S - sum_log_gamma_alpha + weighted_log_y)
        
        # KL Regularization toward Uniform Dir(1)
        tilde_alpha = y_target + (1.0 - y_target) * alpha
        tilde_S = torch.sum(tilde_alpha, dim=-1, keepdim=True)
        
        kl = torch.lgamma(tilde_S) - torch.lgamma(torch.tensor(4096.0, device=alpha.device)) \
             - torch.sum(torch.lgamma(tilde_alpha), dim=-1, keepdim=True) \
             + torch.sum((tilde_alpha - 1.0) * (torch.digamma(tilde_alpha) - torch.digamma(tilde_S)), dim=-1, keepdim=True)
        
        total_loss = nll + kl_weight * kl
        return torch.mean(total_loss)

# -----------------------------------------------------------------------------
# 2. PyTorch Lightning System Module
# -----------------------------------------------------------------------------
class SpectralUnmixingLightningModule(pl.LightningModule):
    def __init__(self, cfg: DictConfig):
        super().__init__()
        self.save_hyperparameters()
        self.cfg = cfg
        
        # Encoder backbone mapping [B, 1, 720, 1280] -> [B, 4096]
        self.stem = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3),  # [B, 64, 360, 640]
            nn.BatchNorm2d(64),
            nn.SiLU(),
            nn.MaxPool2d(2)                                       # [B, 64, 180, 320]
        )
        self.encoder = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),# [B, 128, 90, 160]
            nn.BatchNorm2d(128),
            nn.SiLU(),
            nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1),# [B, 256, 45, 80]
            nn.BatchNorm2d(256),
            nn.SiLU(),
            nn.AdaptiveAvgPool2d((1, 1))                          # [B, 256, 1, 1]
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256, 1024),
            nn.SiLU(),
            nn.Linear(1024, cfg.dataset.num_spectral_bins)
        )
        
        self.loss_fn = Dirichlet4096Loss()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.encoder(x)
        logits = self.head(x)
        return F.softplus(logits) + 1.0  # Enforce alpha_k >= 1.0

    def _get_kl_weight(self) -> float:
        warmup_epochs = self.cfg.model.warmup_epochs
        if self.current_epoch < warmup_epochs:
            return self.cfg.model.kl_max_weight * (self.current_epoch / warmup_epochs)
        return self.cfg.model.kl_max_weight

    def training_step(self, batch, batch_idx):
        images, y_target = batch
        alpha = self.forward(images)
        kl_weight = self._get_kl_weight()
        loss = self.loss_fn(alpha, y_target, kl_weight=kl_weight)
        
        S = torch.sum(alpha, dim=-1).mean()
        self.log("train/loss", loss, on_step=True, on_epoch=True, prog_bar=True)
        self.log("train/mean_confidence_S", S, on_epoch=True)
        return loss

    def validation_step(self, batch, batch_idx):
        images, y_target = batch
        alpha = self.forward(images)
        loss = self.loss_fn(alpha, y_target, kl_weight=1.0)
        
        # Calculate expected blend RMSE across Delta^4095
        S = torch.sum(alpha, dim=-1, keepdim=True)
        p_hat = alpha / S
        rmse = torch.sqrt(torch.mean((p_hat - y_target) ** 2))
        
        self.log("val/loss", loss, on_epoch=True, prog_bar=True)
        self.log("val/rmse_simplex", rmse, on_epoch=True, prog_bar=True)
        return loss

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.cfg.model.learning_rate,
            weight_decay=self.cfg.model.weight_decay
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=self.cfg.trainer.max_epochs
        )
        return [optimizer], [scheduler]

# -----------------------------------------------------------------------------
# 3. Entry point using Hydra
# -----------------------------------------------------------------------------
@hydra.main(version_base="1.3", config_path="configs", config_name="config")
def main(cfg: DictConfig):
    model = SpectralUnmixingLightningModule(cfg)
    # data_module = ParquetSensorDataModule(cfg) # DataModule instantiation
    
    trainer = pl.Trainer(
        max_epochs=cfg.trainer.max_epochs,
        accelerator=cfg.trainer.accelerator,
        devices=cfg.trainer.devices,
        precision=cfg.trainer.precision
    )
    # trainer.fit(model, datamodule=data_module)

if __name__ == "__main__":
    main()
```

---

## 6. Execution Protocol & Hyperparameter Management

With Hydra and PyTorch Lightning, training runs, architectures, and hyperparameters are modularly launched and logged:

```bash
# Default run
python train.py

# Override hyperparameters for high-resolution test
python train.py dataset.batch_size=8 model.learning_rate=5e-5 trainer.precision=32

# Multi-GPU training over sweep
python train.py --multirun model.learning_rate=1e-4,3e-4 model.warmup_epochs=5,10
```

---

## 7. Planned Diagnostic Protocol & Experimental Analysis

To evaluate the upcoming experiment, the following post-acquisition analysis pipeline will be executed on the test dataset across the full 4096-channel continuous spectrum.

### 7.1 Spectral Resolution & Wavelength-Dependent Error Mapping
Rather than evaluating aggregate metrics alone, we will compute the per-wavelength Root Mean Squared Error $\text{RMSE}(\lambda_k)$ across all 4096 bins on the test set:

$$\text{RMSE}(\lambda_k) = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left( \hat{p}_{i, k} - y_{i, k} \right)^2}, \quad k \in \{1, \dots, 4096\}$$

* **Objective:** Map $\text{RMSE}(\lambda_k)$ against the physical wavelength axis $\text{wavelength\_nm} \in [\lambda_1, \dots, \lambda_{4096}]$.
* **Expected Diagnostic Utility:** This curve will explicitly identify where the DOE's spatial-spectral dispersion transfer function $\mathcal{K}(x, y; \lambda)$ succeeds or fails. Regions with low $\text{RMSE}(\lambda_k)$ indicate distinct, well-resolved spatial diffraction modes. Peaks in $\text{RMSE}(\lambda_k)$ pinpoint specific spectral bands where the DOE phase profile introduces spatial-mode overlap and optical degeneracy.

### 7.2 Inter-Bin Covariance & Physical Degeneracy Analysis
To test for local spectral cross-talk or physical phase-wrapping degeneracies, we will calculate the residual error covariance matrix $\mathbf{C} \in \mathbb{R}^{4096 \times 4096}$ across test predictions:

$$C_{j, k} = \text{Cov}\left( (\hat{p}_j - y_j), (\hat{p}_k - y_k) \right)$$

* **Objective:** Identify off-diagonal negative correlations ($C_{j, k} < 0$).
* **Expected Diagnostic Utility:** Anti-correlated residual pairs ($\Delta y_j = -\Delta y_k$) will isolate exact wavelength bands where energy is systematically swapped. This will distinguish whether reconstruction errors stem from local spectral blurring or long-range diffractive phase-wrapping over-saturation.

### 7.3 High-Dimensional Evidential Uncertainty Calibration
We will validate the reliability of the predicted total concentration $S = \sum_{k=1}^{4096} \alpha_k$ by binning test samples into $10$ ordinal confidence buckets based on $S$.

* **Objective:** Plot predicted Dirichlet variance $\text{Var}(y_k) = \frac{\hat{p}_k (1 - \hat{p}_k)}{S + 1}$ against observed Simplex Mean Squared Error $\frac{1}{4096}\|\mathbf{\hat{p}} - \mathbf{y}\|_2^2$ per bucket, and measure Mean Absolute Calibration Error (MACE).
* **Expected Diagnostic Utility:** Confirms whether $S$ acts as a true metric of spatial pattern ambiguity. High $S$ must reliably map to low reconstruction error, allowing downstream automated pipelines to flag ambiguous spatial exposures without ground-truth reference spectra.