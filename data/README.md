# data/ — raw experiment inputs

Everything in this directory is **heavy, untracked lab data** (about 5.6 GB).
It is ignored by git; only this README is versioned, so a fresh clone plus a
copy of `data/` is all a new maintainer needs. Re-create or extend these
recordings with the acquisition script in `scripts/`.

## How this directory is version-controlled

Although the files never enter git, every commit still maps to an exact data
snapshot: `scripts/data_image_build.sh` packs `raw/` and `cad_models/` (plus
the untracked `results/` outputs) into a `FROM scratch` container image (see
the repo-root `Containerfile`) and publishes it to GHCR tagged with the
commit SHA. The build runs from this machine (or the lab's self-hosted CI
runner) on every push — see `.github/workflows/data-image.yml`.

On a machine **without** local data, fetch and mount the snapshot matching
your checkout without copying it out of the image:

```bash
scripts/data_image_mount.sh --sha "$(git rev-parse HEAD)"
```

That mounts the image read-only and points `data/raw`, `data/cad_models` and
`results` at it via symlinks; `--unmount` releases it. See the root README's
"Data version control" section for the full picture.

## Layout

```
data/
├── raw/
│   ├── evt3_raw/            Prophesee EVT3 recordings (*.raw) + trigger logs
│   └── exported_videos/     human-viewable mp4 exports of selected recordings
└── cad_models/              3D-printable chopper LED wheel (design + review renders)
```

## raw/evt3_raw/ — recordings

All EVT3 streams are 720 × 1280 (Prophesee sensor, TRT009S-E evaluation
module) written by the Arena SDK `Cpp_SaveRaw` example. Naming convention:
`<condition>_<wavelength nm>.raw` — the analysis labels a recording by the
last number in its filename, or by the trailing word when there is none.

| Prefix | Stimulus | Wavelength tag |
|---|---|---|
| `spectral_` | superk varia continuum, 50 nm band | 425–675 in 25 nm steps |
| `gaussian_` | same bands through a Gaussian diffuser/filter | 425–650 |
| `nofilter_` | no spectral filter (control) | 425–675 |
| `960hz-chopper_` | rotating chopper wheel at 960 Hz + `*_triggers.csv` with per-revolution trigger timestamps | 425–675 |
| `circle_` | LCD target: red/green/blue circles (color discrimination control) | `blue` / `green` / `red` |
| `siemens` / `seimens` | Siemens-star target (resolution / coded-aperture study) | — |
| `laser_safety_od6_` | laser safety verification through OD6 attenuator | — |
| `TRT009S-E_*` | bare sensor evaluation dumps with sidecar `.raw.json` metadata | — |

The `_triggers.csv` files belong to the `960hz-chopper_` recordings and hold
the chopper photodiode trigger times; they are consumed by the chopper
variant of the analysis (`hypercam-chopper`).

`baseline.raw` and `output.raw` are ad-hoc capture tests kept for reference.

The spectral band sweep is produced by
`scripts/capture_gaussian_bands.sh`, which steps the superk varia across
`400–450 … 650–700 nm` (band midpoints 425…675) and records 5 s per band
into this directory.

## cad_models/ — chopper LED wheel

- `chopper_led_wheel.step` / `.stl` / `.3mf` — printable model;
- `chopper_led_wheel.step.py` — CadQuery/build123d source that generates it;
- `chopper_led_wheel_brief.md` — design brief (aperture count, LED placement);
- `chopper_led_wheel_snapshot_job.json` — render-job specification used to
  produce the review images in `review/`;
- `review/` — orthographic renders used for design sign-off.
