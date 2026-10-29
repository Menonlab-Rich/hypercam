#!/usr/bin/env bash
# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-29
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/z-ai/glm-5.3-flash).
# ==============================================================================

# ==============================================================================
# Slurm driver for the full Dirichlet spectral-unmixing pipeline:
#
#   1. build_manifest.py  — pair spectra/recordings, apply gates, assign splits
#   2. predecode.py       — parallel EVT3 decode into the shared event cache
#   3. train.py           — GPU training, logged to MLflow under a UNIQUE tag
#
# The unique tag flows into Hydra's `out.tag`, which names the run directory
# (outputs/train/<tag>/<timestamp>) AND prefixes the MLflow run name
# (train.py: run_name = f"{cfg.out.tag}-{run_dir.name}"). The tag combines the
# git SHA (code version), a wall-clock stamp, and the Slurm job id, so every
# HPC submission is distinguishable in the MLflow experiment.
#
# MLflow uses HTTP Basic auth (configs/logging/default.yaml). Credentials are
# NEVER stored in this script — export them at submission time so the default
# `--export=ALL` propagates them into the job environment:
#
#   MLFLOW_TRACKING_USERNAME=... MLFLOW_TRACKING_PASSWORD=... sbatch train_hpc.slurm
#
# If the server is unreachable, train.py degrades to CSV + TensorBoard and
# continues (never kills the run), but a warning will appear in the log.
#
# Submit from anywhere:
#   sbatch src/hypercam/machine_learning/dirchlet-spectral-unmixing/train_hpc.slurm
#
# Quick smoke run on the short QOS (from the project directory):
#   sbatch --qos=rai-gpu-grn-short --time=01:00:00 --job-name=dirichlet-smoke \
#       --wrap='uv run python train.py out.tag=smoke data.max_recordings=2 \
#       data.clips_per_density=1 training.max_epochs=2'
# ==============================================================================

#SBATCH --job-name=dirichlet-unmix
#SBATCH --output=logs/train_%j.out
#SBATCH --error=logs/train_%j.err
#SBATCH --account=rai
#SBATCH --partition=rai-gpu-grn
#SBATCH --qos=rai-gpu-grn               # use rai-gpu-grn-short for smoke runs only
#SBATCH --gres=gpu:1                    # accelerator: auto -> one CUDA device
#SBATCH --cpus-per-task=32              # predecode is CPU-bound and uses all of these
#SBATCH --mem=64G                       # event decoding + cached column memory-maps
#SBATCH --time=12:00:00                 # manifest+predecode ~1h; training dominates
#SBATCH --export=ALL                    # propagate MLflow_* credentials from submit env

set -euo pipefail

# ------------------------------------------------------------------------------
# Locate the model project regardless of the submission directory. Batch jobs
# start in the directory sbatch was invoked from, not the script's directory.
# ------------------------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "${PROJECT_DIR}/../../../.." && pwd)"   # src/hypercam/machine_learning/<project> -> repo root
cd "${PROJECT_DIR}"

mkdir -p logs

step_banner() {
    echo ""
    echo "=================================================================="
    echo "[step] $1"
    echo "[ $(date '+%Y-%m-%d %H:%M:%S') ] node=$(hostname) job=${SLURM_JOB_ID:-none}"
    echo "=================================================================="
}

# ------------------------------------------------------------------------------
# Cluster environment. Module names vary per site; uncomment and adjust.
# A CUDA module is only needed if the driver/toolkit is not already visible —
# PyTorch wheels bundle their own CUDA runtime and just need a matching driver.
# ------------------------------------------------------------------------------
# module load cuda/12.6
# module load uv/0.5

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found on PATH. Load it via 'module load' or install it." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# MLflow tracking environment. The URI falls back to the config default
# (https://mlflow.rbaird.me); username/password MUST come from the submit
# environment — nothing secret is ever written to this script or the configs.
# ------------------------------------------------------------------------------
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-https://mlflow.rbaird.me}"
if [[ -z "${MLFLOW_TRACKING_USERNAME:-}" || -z "${MLFLOW_TRACKING_PASSWORD:-}" ]]; then
    echo "WARNING: MLFLOW_TRACKING_USERNAME/PASSWORD not set; MLflow auth will fail" >&2
    echo "         and training will degrade to CSV + TensorBoard logging." >&2
fi
echo "MLflow tracking URI: ${MLFLOW_TRACKING_URI}"

# ------------------------------------------------------------------------------
# Threading hygiene: honor the CPU allocation instead of letting BLAS/OpenMP
# spawn one thread per node core (which oversubscribes the cgroup and slows
# both predecode workers and the dataloader).
# ------------------------------------------------------------------------------
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

# ------------------------------------------------------------------------------
# Unique experiment tag: git SHA + timestamp + Slurm job id. `set -o pipefail`
# keeps a failing git from being silently swallowed; a missing git repo falls
# back to "nogit" rather than aborting the run.
# ------------------------------------------------------------------------------
GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || true)"
GIT_SHA="${GIT_SHA:-nogit}"
RUN_TAG="hpc-${GIT_SHA}-$(date +%Y%m%d_%H%M%S)-j${SLURM_JOB_ID:-local}"
echo "RUN_TAG=${RUN_TAG}"

# ==============================================================================
# Step 0 — environment sync + OpenEVT build check
# ==============================================================================
step_banner "uv sync (locked environment)"
uv sync --frozen

# The EVT3 decoder is the repo's Rust extension; the PyPI wheel needs external
# plugins and is not used. Pre-building on the login node is preferable — a GPU
# allocation should not burn time on cargo. Build here only if the library is
# missing. The two cargo invocations MUST stay separate: one combined command
# unifies the `python` feature into the plugins cdylib, which then fails to
# dlopen (undefined Python symbols) — see the repo README.
EVT3_LIB_DIR="${REPO_ROOT}/openevt/target/release"
if ! ls "${EVT3_LIB_DIR}"/*.so >/dev/null 2>&1; then
    step_banner "building OpenEVT (missing ${EVT3_LIB_DIR})"
    if ! command -v cargo >/dev/null 2>&1; then
        echo "ERROR: openevt library missing and cargo unavailable on this node." >&2
        echo "       Pre-build from the repo root:  cargo build --release -p openevt --features python" >&2
        echo "                                   cargo build --release -p openevt-plugins" >&2
        exit 1
    fi
    cargo build --release -p openevt --features python
    cargo build --release -p openevt-plugins
else
    echo "openevt library found at ${EVT3_LIB_DIR}; skipping cargo build"
fi

# ==============================================================================
# Step 1 — generate the manifest
# Pairs spectra with EVT3 recordings, applies noise/orphan gates, builds
# simplex targets, and writes outputs/manifests/{manifest.csv,gates.json,targets/}.
# Exits non-zero when the gates FAIL (train.py would refuse anyway); failing
# here is cheaper than discovering it after the GPU is booked.
# ==============================================================================
step_banner "build_manifest.py (pairing, gates, splits, targets)"
uv run python build_manifest.py

# ==============================================================================
# Step 2 — prepare the data
# EVT3 decoding is the pipeline bottleneck (Rust + numpy, CPU-bound) and is
# done ONCE across all allocated cores into outputs/cache/. The cache key
# matches the trainer's exactly (recording identity + openevt build), so
# train.py reuses this output verbatim and never decodes inline. Worker count
# is capped at the Slurm allocation — never all node cores (HPC etiquette).
# ==============================================================================
step_banner "predecode.py (parallel EVT3 decode into the event cache)"
uv run python predecode.py --jobs "${SLURM_CPUS_PER_TASK:-$(nproc)}"

# ==============================================================================
# Step 3 — training under the unique tag
# out.tag drives BOTH the run directory (outputs/train/<tag>/<timestamp>) and
# the MLflow run name (<tag>-<timestamp>), so the MLflow experiment and the
# local artifacts stay cross-referenceable. accelerator=auto selects the GPU.
# ==============================================================================
step_banner "train.py (out.tag=${RUN_TAG})"
uv run python train.py "out.tag=${RUN_TAG}"

step_banner "pipeline complete — tag: ${RUN_TAG}"
echo "Artifacts: ${PROJECT_DIR}/outputs/train/${RUN_TAG}/<timestamp>/"
echo "Logs:      logs/train_${SLURM_JOB_ID:-?}.out"
