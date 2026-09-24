#!/usr/bin/env bash
#
#==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
#==============================================================================
#
# Build the experiment-data container image and (optionally) publish it to
# GHCR. The image copies the untracked lab data (see data/README.md) into a
# data-only image and tags it with the current commit SHA, so every commit
# maps 1:1 to a reproducible snapshot of the experiment data.
#
# This must run on a machine that HAS the data (the lab workstation or a
# self-hosted GitHub Actions runner there). To consume the data on another
# machine, use scripts/data_image_mount.sh instead.
#
# Usage:
#   data_image_build.sh [--no-push] [--image <ref>] [--sha <git-sha>]
#                       [--data-dir <path>]
#
# Options:
#   --no-push    build and tag locally only; skip the GHCR push
#   --image      full image reference, e.g. ghcr.io/richbai90/hypercam-data
#                (default: derived from the git origin, overridable with the
#                HYPERCAM_DATA_IMAGE environment variable)
#   --sha        commit SHA to tag with (default: HEAD of this checkout)
#   --data-dir   directory holding raw/ and cad_models/ (default: data/ under
#                the repo root; overridable with HYPERCAM_DATA_DIR)
#
# Environment:
#   GHCR_USER    registry username when pushing with a token (default: the
#                currently logged-in podman user is kept)
#   GHCR_TOKEN   registry password/token; when set the script logs in to
#                ghcr.io before pushing (used by CI with secrets.GITHUB_TOKEN)
#   PODMAN_STORAGE_DRIVER  optional podman storage driver override (e.g. vfs
#                on hosts where the overlay driver cannot be used)

set -euo pipefail

usage() {
    cat <<'EOF'
Build the experiment-data image (data/ + results/) and publish it to GHCR,
tagged with the current commit SHA so every commit maps 1:1 to a snapshot.

Usage:
  data_image_build.sh [--no-push] [--image <ref>] [--sha <git-sha>]
                      [--data-dir <path>]

Options:
  --no-push    build and tag locally only; skip the GHCR push
  --image      full image reference (default: derived from git origin,
               overridable with HYPERCAM_DATA_IMAGE)
  --sha        commit SHA to tag with (default: HEAD)
  --data-dir   directory holding raw/ and cad_models/ (default: data/
               under the repo root; overridable with HYPERCAM_DATA_DIR)

results/ from the current repo checkout is always included in the image
(superseded runs under results/archive/ are excluded).

Environment:
  GHCR_USER    registry username when pushing with a token
  GHCR_TOKEN   registry token; when set the script logs in before pushing
  PODMAN_STORAGE_DRIVER  optional storage-driver override (e.g. vfs)
EOF
}

podman_cmd=(podman)
if [[ -n ${PODMAN_STORAGE_DRIVER:-} ]]; then
    podman_cmd+=(--storage-driver "$PODMAN_STORAGE_DRIVER")
fi

no_push=0
sha_arg=""
image_arg="${HYPERCAM_DATA_IMAGE:-}"
data_dir_arg="${HYPERCAM_DATA_DIR:-data}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-push) no_push=1 ;;
        --image) image_arg=$2; shift ;;
        --sha) sha_arg=$2; shift ;;
        --data-dir) data_dir_arg=$2; shift ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

command -v podman >/dev/null 2>&1 || {
    printf 'Error: podman is not installed or not in PATH.\n' >&2
    exit 2
}

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PWD")
data_dir=$data_dir_arg
[[ $data_dir == /* ]] || data_dir="$repo_root/$data_dir"
results_dir=$repo_root/results

for entry in raw cad_models; do
    [[ -d $data_dir/$entry ]] || {
        printf 'Error: %s is missing; this machine does not have the experiment data.\n' \
            "$data_dir/$entry" >&2
        printf '       Build from the lab workstation (or a self-hosted runner there);\n' >&2
        printf '       on other machines use scripts/data_image_mount.sh to consume the image.\n' >&2
        exit 3
    }
done
[[ -d $results_dir ]] || {
    printf 'Error: %s is missing; analysis results are part of the data image.\n' \
        "$results_dir" >&2
    exit 3
}

# Guard against silently publishing an essentially empty snapshot (e.g. a
# runner whose checkout cleaned the data): the real recordings are gigabytes.
raw_size_mb=$(du -sm "$data_dir/raw" | cut -f1)
if ((raw_size_mb < 50)); then
    printf 'Error: %s holds only %d MiB; the real EVT3 recordings are gigabytes.\n' \
        "$data_dir/raw" "$raw_size_mb" >&2
    printf '       Refusing to publish a data-less snapshot.\n' >&2
    exit 3
fi

sha=${sha_arg:-$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)}
[[ -n $sha ]] || {
    printf 'Error: no commit SHA given and %s is not a git checkout.\n' "$repo_root" >&2
    exit 2
}
short_sha=${sha:0:9}

# Derive the GHCR image reference from the git origin when not given
# explicitly. Registry references must be lowercase.
strip_tag_if_present() {
    # Keep everything before the first ':' when the ':' sits after the last
    # '/' (i.e. it separates a tag, not a registry port). localhost:5000/x
    # keeps its port; localhost/x:tag loses the tag.
    local ref=$1
    local slash_part slash_pos=-1 colon_pos
    if [[ $ref == */* ]]; then
        slash_part=${ref%/*}
        slash_pos=${#slash_part}
    fi
    local before_colon=${ref%%:*}
    colon_pos=${#before_colon}
    if ((colon_pos > slash_pos && colon_pos < ${#ref})); then
        printf '%s' "${ref:0:colon_pos}"
    else
        printf '%s' "$ref"
    fi
}

default_image() {
    local origin owner repo_name
    origin=$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)
    if [[ $origin =~ github.com[:/]([^/]+)/([^/]+?)(\.git)?$ ]]; then
        owner=${BASH_REMATCH[1]}
        repo_name=${BASH_REMATCH[2]}
        printf 'ghcr.io/%s/%s-data' "$owner" "$repo_name"
    else
        printf 'ghcr.io/richbai90/hypercam-data'
    fi
}
image=${image_arg:-$(default_image)}
image=$(strip_tag_if_present "$image")
image=${image,,}

source_url=$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)
if [[ $source_url =~ ^git@github\.com:(.+)(\.git)?$ ]]; then
    source_url="https://github.com/${BASH_REMATCH[1]}"
fi
source_url=${source_url%.git}
source_url=${source_url:-https://github.com/richbai90/hypercam}
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Assemble the build context in a staging directory: hard-linked copies of
# the subtrees that belong in the image. Hard links cost no extra disk space
# and no copy time, and they let the data live outside the repo checkout;
# fall back to a real copy when the source sits on another filesystem.
copy_into_stage() {
    local source=$1 target=$2
    if cp -al "$source" "$target" 2>/dev/null; then
        return 0
    fi
    printf 'Note: hard-link staging failed for %s (crossing filesystems?); copying instead.\n' \
        "$source" >&2
    cp -a "$source" "$target"
}

stage=$(mktemp -d /tmp/hypercam-data-image.XXXXXX)
trap 'rm -rf "$stage"' EXIT
copy_into_stage "$data_dir/raw" "$stage/raw"
copy_into_stage "$data_dir/cad_models" "$stage/cad_models"
copy_into_stage "$results_dir" "$stage/results"
# Superseded runs are kept on disk for provenance but do not belong in the
# published snapshot.
rm -rf "$stage/results/archive"

printf 'Commit:        %s\n' "$sha"
printf 'Data source:   %s\n' "$data_dir"
printf 'Results:       %s\n' "$results_dir"
printf 'Image:         %s\n' "$image"

if ((no_push == 0)); then
    if [[ -n ${GHCR_TOKEN:-} ]]; then
        printf 'Logging in to ghcr.io as %s\n' "${GHCR_USER:-github-actions}"
        printf '%s' "$GHCR_TOKEN" | "${podman_cmd[@]}" login ghcr.io \
            -u "${GHCR_USER:-github-actions}" --password-stdin >/dev/null
    else
        "${podman_cmd[@]}" login --get-login ghcr.io >/dev/null 2>&1 || {
            printf 'Error: not logged in to ghcr.io.\n' >&2
            printf '       Run: podman login ghcr.io   (or set GHCR_USER/GHCR_TOKEN)\n' >&2
            exit 4
        }
        printf 'Using existing ghcr.io login: %s\n' "$("${podman_cmd[@]}" login --get-login ghcr.io)"
    fi
fi

printf 'Building data+results image (this packages ~%.1f GiB)...\n' \
    "$(du -sm "$data_dir/raw" "$data_dir/cad_models" "$results_dir" | awk '{s+=$1} END {print s/1024}')"
"${podman_cmd[@]}" build \
    --build-arg SOURCE_COMMIT="$sha" \
    --build-arg SOURCE_URL="$source_url" \
    --build-arg BUILT_AT="$built_at" \
    -t "$image:sha-$sha" \
    -t "$image:sha-$short_sha" \
    -t "$image:latest" \
    -f "$repo_root/Containerfile" \
    "$stage"

if ((no_push)); then
    printf 'Built locally (--no-push); tags:\n'
    printf '  %s:sha-%s\n  %s:sha-%s\n  %s:latest\n' \
        "$image" "$sha" "$image" "$short_sha" "$image"
    exit 0
fi

# Three manifest-level tags point at the same layer set; the registry stores
# the (large) layers only once, so this is cheap.
for tag in "sha-$sha" "sha-$short_sha" "latest"; do
    printf 'Pushing %s:%s\n' "$image" "$tag"
    "${podman_cmd[@]}" push "$image:$tag"
done

printf 'Published %s tagged for commit %s.\n' "$image" "$sha"
