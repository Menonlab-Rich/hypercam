# results/ — analysis outputs

This directory is **untracked by git** (the outputs are large binaries); it
travels with the code through the commit-tagged data image instead — see the
root README's "Data version control" section and
`scripts/data_image_{build,mount}.sh`. Only this README is versioned, so a
fresh clone can still learn what belongs here. Superseded runs live in
`archive/` and are excluded from the image as well.

Every analysis run writes a self-contained directory: **inputs, parameters
and outputs travel together**, so a directory can be interpreted (and
reproduced) without reading the code. Directories follow the naming
`<experiment>` or `<experiment>_<variant>`.

## Directory inventory

| Directory | Command that produced it | What it answers |
|---|---|---|
| `spectral_correlation/` | `hypercam` on `spectral_*.raw` (+ `hypercam-sweep` on `circle_*.raw`) | main experiment: narrowband superk varia sweep, 425–675 nm; also hosts the duration × accumulation sweep and per-cell `sweep_frames/` |
| `gaussian_correlation/` | `hypercam` on `gaussian_*.raw` | same pipeline through the Gaussian path |
| `no_filter_correlation/` | `hypercam` on `nofilter_*.raw` | unfiltered control |
| `spectral_correlation_min1/`, `spectral_correlation_min5/` | `hypercam-sweep` variants | minimum-frame-count robustness checks (1 and 5 frames) |
| `spectral_correlation_unmasked/` | `hypercam-sweep` variant | sweep without the active-pixel support mask |
| `spectral_correlation_fine_signed/` | `hypercam-sweep --polarity signed` variant | fine sweep with signed polarity → `discernibility_curves.*` used by the polarity deck |
| `rgb_raw/` | `hypercam` on RGB-camera captures | color-camera reference for the LCD target |
| `archive/` | superseded earlier runs | provenance only; also excluded from the data image, may be deleted |
| `spectral_correlation_chopper/` | `hypercam-chopper` (when run) | chopper-wheel recordings with trigger alignment |

## What one analysis directory contains

- `analysis_metadata.json` — the full recipe: method description, polarity,
  transform, accumulation interval, crop window, high-pass cut-off, and one
  record per input recording (path, shape, event counts, frames averaged,
  duration). Reproduce a run from these parameters alone.
- `pearson_correlation.csv` / `.npy` — the pairwise Pearson matrix (labels in
  metadata order).
- `pearson_correlation_heatmap.svg` — heat map on the fixed `[-1, 1]` scale
  used across all experiments.
- `frames/<label>_activity.npy|.png` — lossless accumulated activity frame
  and a robustly scaled preview.
- `frames/<label>_processed.npy|.png` — cropped, high-passed frame actually
  fed to the correlation.
- Sweep directories additionally carry `duration_accumulation_sweep.{csv,json,png,svg}`
  (mean cross-color correlation vs. total duration and effective frame rate)
  and, for the fine/signed variant, `discernibility_curves.*`.

## Regenerating

Each table row above maps to a console command (see the root README's
"Running the experiments"); e.g.

```bash
uv run hypercam --pattern 'data/raw/evt3_raw/spectral_*.raw' \
                --output results/spectral_correlation
```

Derived stakeholder figures and decks live in `reports/` — those are
regenerated from these directories, never edited by hand.
