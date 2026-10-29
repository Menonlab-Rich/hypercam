# Dirichlet Spectral Unmixing from Event-Camera Activity Frames

Predicts a per-pixel spectral distribution — a Dirichlet over K wavelength
bins — from event-camera activity frames, trained on paired
spectrometer/event-camera recordings from the Hypercam dataset. The design
rationale is in `design.md` (§8 records the event-camera adaptation).

## Architecture

The model operates across **frame densities**: a sample is a clip of
`n_frames` event frames, each accumulating `frame_ms`, spanning
`acc_time = n_frames × frame_ms`; the system's **effective fps** is
`n_frames / acc_time = 1000/frame_ms`. The spectral target is constant per
recording regardless of density — every recording contributes clips at every
configured density.

```
clip [T, 720, 1280] (counts per frame_ms from the event cache, log1p)
  -> per-frame shared Conv 32 -> 64 -> 128 (stride 2, GroupNorm, SiLU)
  -> AdaptiveAvgPool 4x4 per frame
  -> temporal mean ++ temporal max          (T-agnostic)
  -> ++ density embedding (log eff_fps, log2 n_frames, log10 acc_time)
  -> Linear 256 -> SiLU -> Linear K
  -> alpha = softplus(logits) + 1           (alpha_k >= 1, init alpha ~= 2/bin)
```

Loss = Dirichlet NLL(alpha, y) + annealed modulated KL(Dir(alpha_tilde) ||
Dir(1_K)); lambda warms up linearly over `kl_warmup_epochs`. Optimizer:
AdamW + cosine schedule (design §5.2). ~1.8M parameters at K=2556.

The default density grid (`configs/data/default.yaml`) spans **4 to 1000
effective fps**: `frame_ms` in {1, 4, 10, 25, 50, 100, 250} × `n_frames` in
{2, 4, 8}, giving several (n_frames, frame_ms) combinations per effective
fps. **Accumulation floor:** every model frame must contain at least
`data.min_accumulations_per_frame` (=4, empirical) fine accumulation windows
(`evt3.accumulation_us` = 250 µs) — this is what caps the grid at 1000 fps.
Train clip start times are re-randomized every epoch (val/test use fixed,
evenly spaced starts); batches are density-grouped and round-robin across
the epoch so training interleaves densities instead of consuming them in
blocks.

## Data: pairing rule and ground truth

- Spectrum `data/raw/spectra/<stem>.csv|.parquet` and recording
  `data/raw/evt3/<stem>_<capture>.raw` join on `<stem> = %Y-%m-%d_%H-%M-%S`
  (lab-local wall time; the capture timestamp uses colons). The `.csv` files
  are Parquet bytes — the loader sniffs content, never extension.
- Ground truth = reference-normalized transmittance simplex per the
  documented workflow (`src/hypercam/notebooks/spectra/analysis.py`):
  divide by `reference.parquet`, window 420-680 nm, rolling median,
  Savitzky-Golay(40, 2), clip, normalize to sum 1. `data.target_mode`
  switches to `amplitude_corrected_counts` / `raw_counts` for comparison.
- Gates (see `build_manifest.py`): a spectrum is noise iff its RAW counts
  are symmetric about zero — SNR (`mean/std`) < 0.4 **and** the
  positive-vs-negative mean asymmetry < 5. Real spectra score SNR >= 0.74 /
  asymmetry >= 62; the one dark frame scores 0.026 / -0.04. Plus ORPHAN (no
  partner file). 264/265 pairs pass. Band label = weighted-mean lambda of
  raw counts, 25 nm bins.
- Splits hold out whole stimulus bands (train 425 nm x118, val 500 nm x71,
  test 525 nm x75); `--split-mode stratified` splits within bands instead.
- Decoded EVENTS are cached per recording under `outputs/cache/<key>/`
  (idx/t/p columns, ~9 bytes per event) keyed by recording identity + the
  OpenEVT build; clips at any density are assembled from this cache without
  re-decoding, so changing the density grid never triggers a re-decode.

## Prerequisites

- Python >= 3.12 (`uv sync`).
- The repo's OpenEVT build (the EVT3 decoder is a Rust extension; the PyPI
  wheel needs external plugins). From the repository root:

  ```bash
  cargo build --release -p openevt --features python   # Python extension
  cargo build --release -p openevt-plugins             # device plugins
  ```

  Build them with SEPARATE cargo invocations: one combined command unifies
  the `python` feature into the plugins cdylib and the plugin library then
  fails to dlopen (undefined Python symbols). The decoder path is configured
  via `evt3.library_dir` (default `../../../../openevt/target/release`).
- Paired data under `data/raw/{spectra,evt3}/` (lakeFS-managed; see the
  repo README's data-version section or `outputs/investigation/`).

## Running

```bash
uv sync
uv run python build_manifest.py         # pairing, gates, splits, targets
uv run python predecode.py --jobs 22    # CPU-bound EVT3 decode, parallel, ONCE
uv run python train.py                  # full training on GPU (accelerator: auto)
uv run python train.py out.tag=smoke data.max_recordings=2 \
    data.clips_per_density=2 training.max_epochs=2   # smoke
uv run python eval.py --run-dir outputs/train/<tag>/<ts>  # accuracy-vs-fps + §7
uv run pytest                           # module selftests
```

EVT3 decoding is Rust/CPU-bound (no GPU path exists) and dominates wall time
on first contact with the data; `predecode.py` fills the shared event cache
across all cores so `train.py` and `eval.py` never decode — they memory-map
cached event columns, assemble density clips, and run on the GPU. The cache
key is identical to the trainer's (both read `configs/` + the OpenEVT build),
so predecode output is reused verbatim.

`eval.py` is the primary validation gate: it re-clips the held-out split at
EVERY configured density and reports **accuracy vs effective fps**
(`outputs/eval/<tag>/accuracy_vs_effective_fps.png`) plus per-density §7
diagnostics (RMSE(λ), residual covariance, MACE calibration).

Every module (`evt3.py`, `targets.py`, `data.py`, `model.py`, `loss.py`,
`lit.py`) also runs standalone as a selftest: `uv run python model.py`.

MLflow logging (Basic auth) activates when `MLFLOW_TRACKING_URI`,
`MLFLOW_TRACKING_USERNAME`, and `MLFLOW_TRACKING_PASSWORD` are exported;
without them runs degrade to CSV + TensorBoard with a warning.

## Outputs

- `outputs/manifests/` — `manifest.csv`, `gates.json`, `targets/*.npy`,
  `wavelength_grid.npy` (defines K)
- `outputs/cache/` — decoded event columns per recording (regenerable)
- `outputs/train/<tag>/<timestamp>/` — checkpoints (best `val/nll`), CSV +
  TensorBoard + MLflow logs, resolved config
- `outputs/eval/<tag>/` — `summary.json` + RMSE(lambda), residual
  covariance, MACE calibration, spectrum overlay figures
- `outputs/investigation/` — Phase 0 evidence (FINDINGS.md, audits, samples)

## Conventions

- The directory name keeps the repo's existing spelling "dirchlet"
  (matching `design.md`'s location); the code and docs use "Dirichlet".
- EVT3 helpers are vendored in `evt3.py` rather than imported from
  `hypercam.analysis.spectral_correlation`: the repo rebase of 2026-10-27
  dropped that package from tracking, and the plan's sanctioned fallback is
  a self-contained model project.
