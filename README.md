# Hypercam — spectral correlation from event cameras

This project measures how diffraction patterns depend on wavelength by
recording scenes with a **Prophesee event camera (EVT3)** while a superk
varia continuum laser sweeps across 425–675 nm. Each recording is decoded
through [OpenEVT](https://github.com/richbai90/openevt) (a git submodule)
into consecutive 10 ms per-pixel activity frames, averaged, cropped to the
common signal window, high-passed to remove large-scale background, and
correlated pairwise with the Pearson coefficient over pixels that are active
in either frame. The question: **is the spatial correlation between two
wavelengths a usable fingerprint of color for a frame-free sensor?**

Headline result so far (see `reports/weekly_report_2026-09-18.md`): the
cross-color correlation is flat in effective frame rate (10 → 10 000 FPS)
and grows only with total averaging time — "it's not the FPS, it's the total
duration."

---

## Repository map

```
hypercam/
├── README.md                  ← you are here: overview, pipeline, commands
├── AGENTS.md                  conventions for AI agents working in this repo
├── pyproject.toml             package + console-script entry points (uv)
├── Containerfile              data+results image (FROM scratch); context staged by the build script
├── openevt/                   git submodule: EVT3 decoder (Rust) + Python bindings
│
├── .github/workflows/
│   └── data-image.yml         CI: build + publish the data image on every commit
│
├── src/hypercam/              the installable Python package
│   ├── analysis/              scripts that produce scientific results
│   │   ├── spectral_correlation.py        main CLI: activity frames → Pearson r   (`hypercam`)
│   │   ├── spectral_correlation_chopper.py  chopper-wheel variant (960 Hz trigger files) (`hypercam-chopper`)
│   │   ├── duration_sweep.py              duration × accumulation-interval sweep (`hypercam-sweep`)
│   │   ├── sweep_frames.py                per-cell frame snapshots + contact sheets (`hypercam-sweep-frames`)
│   │   └── comparison_figure.py           multi-experiment poster figure (`hypercam-compare`)
│   ├── data_versioning/       lakeFS ↔ git alignment (`hypercam-data-*` commands)
│   │   ├── cli.py             commit / checkout / status entry points
│   │   ├── sync.py            transfer planning + commit/checkout flows
│   │   ├── remote.py          lakeFS connection and object transfers
│   │   ├── pointer.py         the data/.lakefs-commit pointer record
│   │   ├── config.py          endpoint/credential/path resolution
│   │   └── git_ops.py         small git plumbing helpers
│   ├── reporting/             deck generators that turn results into deliverables
│   │   ├── summary_deck.py                stakeholder slide deck (run as a module)
│   │   └── report_deck.py                 polarity-verification deck (run as a module)
│   └── notebooks/
│       └── siemens.py         standalone Marimo notebook: Siemens-star exploration
│
├── scripts/
│   ├── capture_gaussian_bands.sh   lab acquisition: sweep superk varia bands → data/raw/evt3_raw
│   ├── data_image_build.sh         build the data image for the current commit and push it to GHCR
│   ├── data_image_mount.sh         pull a commit-tagged data image and mount it as data/ here
│   └── git/hooks/                  optional prepare-commit-msg hook (Data-lakefs-commit trailer)
│
├── data/                      UNTRACKED heavy data (5.6 GB); provenance in data/README.md
│   ├── .lakefs-commit         TRACKED pointer: git commit ↔ lakeFS data snapshot
│   ├── raw/evt3_raw/          *.raw EVT3 recordings + 960 Hz chopper trigger CSVs
│   ├── raw/exported_videos/   mp4 exports of representative recordings
│   ├── cad_models/            3D-printed chopper LED wheel (STEP/STL/3MF + design brief)
│   └── (nothing else)         everything under data/ is regenerable lab data
│
├── results/                   analysis outputs — one directory per experiment (see results/README.md)
│   │                          UNTRACKED: travels with the commit-tagged data image, not git
│   ├── spectral_correlation/  narrowband superk varia sweep (the main experiment)
│   ├── gaussian_correlation/  Gaussian-filtered variant
│   ├── no_filter_correlation/ unfiltered control
│   ├── spectral_correlation_{min1,min5,unmasked,fine_signed}/  parameter variants
│   ├── rgb_raw/               color-camera reference frames
│   └── archive/               superseded runs kept for provenance (untracked)
│
├── reports/                   human-facing deliverables (see reports/README.md)
│   ├── weekly_report_*.md/.tex/.pdf   weekly status reports to the PI
│   ├── figures/               publication figures extracted from results
│   └── decks/                 generated PowerPoint decks (summary, polarity verification)
│
├── docs/references/           key papers (Shah et al. CVPR 2024 + supplemental, inverse design)
└── tests/                     pytest suite for the analysis modules
```

---

## Setup

The Python environment is managed with [uv](https://docs.astral.sh/uv/):

```bash
git clone --recurse-submodules <this repo>   # openevt is a submodule
uv sync                                      # creates .venv and installs hypercam
uv run pytest                                # sanity-check the toolchain
```

The analysis needs the OpenEVT Python extension **and** the RAW-device
plugin library. Build them in two commands — `openevt` is linked into
`libopenevt_plugins.so` as an rlib, so building both packages in a single
invocation unifies the `python` feature across them and stamps the Python
extension's `PyInit_openevt` into the plugin library as well:

```bash
cd openevt
cargo build --release -p openevt --features python
cargo build --release -p openevt-plugins
cd ..
```

Both libraries land side by side in `openevt/target/release`:

- `libopenevt.so` — the Python extension;
- `libopenevt_plugins.so` — the standard device plugins, including the
  `openevt_raw_file` reader that decodes the recordings.

The analysis imports the first and points `OPENEVT_PLUGIN_PATH` at the
directory holding the second.

---

## Running the experiments

| Command | Purpose | Default input | Default output |
|---|---|---|---|
| `uv run hypercam` | main spectral-correlation analysis | `data/raw/evt3_raw/spectral_*.raw` | `results/spectral_correlation/` |
| `uv run hypercam-chopper` | chopper wheel variant: 12 windows at 960 rev/s → 11 520 Hz per-pixel chop; frames integrate whole revolutions | `data/raw/evt3_raw/960hz-chopper_*.raw` | `results/spectral_correlation_chopper/` |
| `uv run hypercam-sweep` | duration × accumulation-interval sweep | `data/raw/evt3_raw/circle_*.raw` | `results/spectral_correlation/` |
| `uv run hypercam-sweep-frames` | contact sheets of per-cell activity frames | same sweep grid | `results/spectral_correlation/sweep_frames/` |
| `uv run hypercam-compare` | 3-panel poster of correlation matrices | `results/{no_filter,gaussian,spectral}_correlation` | `reports/figures/correlation_comparison_poster.svg` |
| `uv run python -m hypercam.reporting.summary_deck` | stakeholder slide deck | `results/spectral_correlation*` | `reports/decks/spectral_correlation_summary.pptx` |
| `uv run python -m hypercam.reporting.report_deck` | polarity-verification deck | `results/spectral_correlation_fine_signed` | `reports/decks/polarity_verification_report.pptx` |

All CLI flags (`--pattern`, `--accumulation-ms`, `--polarity`,
`--transform`, `--crop-margin`, `--highpass-px`, …) are documented in
`--help`. New recordings are captured with `scripts/capture_gaussian_bands.sh`
(see `data/README.md`).

### Method in one paragraph

Each 10 ms frame counts both ON and OFF events at every pixel. Because laser
brightness and event rates differ across recordings, `log1p` is applied to
each frame before the ~500 frames are averaged, so a few extremely active
pixels cannot dominate. Frames are cropped to the common signal window
(`--no-crop` to disable, `--crop-margin` for padding) and high-passed so
structures larger than 64 px are removed (`--highpass-px; 0` disables). Each
pair's coefficient counts only pixels active in either frame, so shared empty
background cannot inflate the similarity.

Each experiment directory contains, among others:

- `pearson_correlation_heatmap.svg` — heat map on a fixed `[-1, 1]` scale;
- `pearson_correlation.csv` / `.npy` — the numerical matrix;
- `frames/*_activity.npy|.png` — lossless accumulated activity frames + previews;
- `frames/*_processed.npy|.png` — cropped, high-passed frames actually correlated;
- `analysis_metadata.json` — inputs, event counts, durations, method.

Recordings are labeled from their filenames: the last number when present
(`spectral_425` → `425`), otherwise the trailing word (`circle_green` →
`green`).

---

## Data version control: aligned git and lakeFS histories

The experiment data (`data/`, ~5.6 GB of EVT3 recordings and CAD models) and
the analysis outputs (`results/`, ~350 MB) are deliberately **not** stored in
git. They are versioned in **two parallel mechanisms that stay aligned**:

1. **lakeFS** (primary): a Git-like versioning layer over object storage.
   Every git commit names, in a tiny tracked pointer file, the lakeFS commit
   that holds the matching data snapshot — so "check out the data for this
   commit" is one command.
2. **Commit-tagged GHCR images** (fallback): the same trees packed into a
   data-only container image, for machines that only need `podman` and no
   lakeFS server.

### lakeFS: the pointer file and the two commands

`data/.lakefs-commit` is tracked by git and contains the binding:

```yaml
repository: hypercam-data
branch: main
commit: 071f8338aba0...   # lakeFS commit holding data/raw, cad_models/, results/
```

Everything else follows from two commands:

| Command | Purpose |
|---|---|
| `hypercam-data-commit` | upload changed `data/{raw,cad_models}` + `results/` (minus `results/archive`) to the lakeFS branch, commit it, write the new hash into the pointer and stage it. Add `--git-commit -m "..."` to also create the git commit, which then carries the hash both in the pointer file and as a `Data-lakefs-commit:` message trailer. |
| `hypercam-data-checkout` | read the pointer at a git ref (default `HEAD`) and make the local trees byte-identical to that snapshot — downloads changed files, restores their timestamps, removes files the snapshot does not contain. |
| `hypercam-data-status` | show the drift between pointer, branch head and local tree in both directions, and whether the histories are aligned. |

The daily loop on the machine with the data:

```bash
hypercam-data-commit --git-commit -m "feat(analysis): new sweep results"
git push
```

Everywhere else (laptop, CI, a collaborator's clone):

```bash
git pull
hypercam-data-checkout          # data for HEAD, byte-exact
hypercam-data-checkout --git-ref HEAD~5   # any historical commit
```

Configuration resolves in order: CLI flags → `HYPERCAM_LAKEFS_*`
environment variables → the standard `LAKECTL_*` variables →
`~/.lakectl.yaml` → defaults (`http://localhost:8000`, repository
`hypercam-data`, branch `main`). The lakeFS server itself is not part of
this repository; point the commands at whatever endpoint you run — a
single-binary deployment is enough:

```bash
lakefs run                       # http://localhost:8000, then visit /setup
hypercam-data-commit --create --storage-namespace s3://<bucket>/hypercam-data
```

(`--storage-namespace` is only needed the first time, to create the
repository; use `local:///path` for a filesystem block store.) Historical
checkouts read an immutable commit — never a mutable branch — so concurrent
checkouts cannot corrupt each other. Change detection is size + modification
time in whole seconds (what lakeFS records per object), the same trade-off
git's index makes; files rewritten within the same second as their previous
sync are re-detected on the next run.

The optional `scripts/git/hooks/prepare-commit-msg` hook mirrors the
pointer into every commit message automatically:

```bash
git config core.hooksPath scripts/git/hooks
```

### GHCR data image: commit-tagged snapshots without a lakeFS server

- `Containerfile` defines an image with no base layer (`FROM scratch`) that
  contains nothing but `data/raw/`, `data/cad_models/` and `results/`
  (minus superseded runs in `results/archive/`), labeled with the commit SHA
  it was built from.
- `scripts/data_image_build.sh` stages those subtrees (hard-linked, so
  nothing is duplicated on disk) and publishes the image as
  `ghcr.io/<owner>/<repo>-data`, tagged `sha-<full-SHA>`, `sha-<short-SHA>`,
  and `latest`. Run it on the lab workstation (or any machine holding the
  data):

  ```bash
  podman login ghcr.io                    # or set GHCR_USER + GHCR_TOKEN
  scripts/data_image_build.sh             # build + tag + push for HEAD
  scripts/data_image_build.sh --no-push   # local build only
  ```

- `scripts/data_image_mount.sh` consumes a snapshot **without copying the
  data out**: it pulls the commit-tagged image, mounts it read-only with
  `podman image mount`, and points `data/raw`, `data/cad_models` and
  `results` at the mount through symlinks, so every analysis command works
  unchanged:

  ```bash
  scripts/data_image_mount.sh                     # data for HEAD
  scripts/data_image_mount.sh --sha <commit>      # data as of a specific commit
  scripts/data_image_mount.sh --status            # what is mounted right now
  scripts/data_image_mount.sh --unmount           # release the mount
  ```

  Rootless podman needs `fuse-overlayfs` (`sudo apt install
  fuse-overlayfs`). The mount state is recorded in `data/.mount`
  (git-ignored). Inside a container you can skip the host mount entirely:
  `podman run --mount type=image,src=ghcr.io/<owner>/<repo>-data:sha-<sha>,target=/data <image>`.
  While an image is mounted, the lakeFS commands refuse to run (they detect
  the symlinked mounts); `--unmount` first, then sync.

- `.github/workflows/data-image.yml` keeps the mapping dense: **every push
  (i.e. every commit)** runs the `build-and-publish` job on a self-hosted
  runner at the lab — the only machine with the data — producing that
  commit's image; unchanged subtrees are content-addressed, so the registry
  stores each layer once. Pull requests run only the `validate` job
  (script syntax checks plus a fixture build — no data needed). Runner
  prerequisites: podman + fuse-overlayfs, a `self-hosted` runner registered
  on the lab machine, and (optionally) a repo variable `HYPERCAM_DATA_DIR`
  pointing at the absolute path of the data directory. The job checks out
  with `clean: false` so `data/` (untracked, git-ignored) survives on the
  runner.

Storage note: the registry deduplicates identical layers, so publishing
unchanged data for new commits is nearly free. Local podman storage does
accumulate one copy per data change; prune stale snapshots with
`podman rmi ghcr.io/<owner>/<repo>-data:sha-<old-sha>`. lakeFS likewise
keeps every snapshot reachable through its history; garbage-collect
superseded blocks server-side when the retention policy allows.

---

## Taking the project over

1. Read the latest `reports/weekly_report_*.md` — it states the current
   scientific question, the definitions in use, and what was just measured.
2. Skim `results/README.md` to see which experiment produced which output,
   then `reports/README.md` for the stakeholder deliverables.
3. Run the test suite: `uv run pytest` (no hardware or openevt build needed).
4. Get the data: either the lab workstation already has it in `data/`, or
   pull the snapshot matching your checkout —
   `hypercam-data-checkout` (lakeFS; see "Data version control"), or
   `scripts/data_image_mount.sh --sha "$(git rev-parse HEAD)"` (GHCR image).
5. Re-run the main analysis end to end:
   `uv run hypercam --pattern 'data/raw/evt3_raw/spectral_*.raw'` and compare
   against `results/spectral_correlation/pearson_correlation.csv`.
6. Open `src/hypercam/notebooks/siemens.py` in Marimo
   (`uvx marimo edit src/hypercam/notebooks/siemens.py`) for the
   Siemens-star exploration that motivates the coded-aperture work.

Conventions for AI agents (and humans who want the same discipline) are in
`AGENTS.md`.
