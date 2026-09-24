#!/usr/bin/env bash
#
#==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
#==============================================================================
#
# Pull a commit-tagged experiment-data image from GHCR and expose it on this
# machine WITHOUT copying the data out: the image is mounted read-only with
# `podman image mount` and data/raw + data/cad_models become symlinks into
# the mount, so every analysis command works as if the data were checked out.
#
# The mounted image acts as the version-controlled "data volume": pass
# --sha to check out exactly the data that belongs to a given commit.
#
# Rootless podman needs fuse-overlayfs to mount images; install it with
# `sudo apt install fuse-overlayfs` if the mount step complains.
#
# Usage:
#   data_image_mount.sh [--sha <git-sha> | --tag <tag>] [--image <ref>]
#                       [--data-dir <path>] [--unmount] [--status]
#
# Options:
#   --sha       mount the data snapshot for this commit (tag: sha-<sha>;
#               default: HEAD of this checkout)
#   --tag       mount an explicit image tag instead (e.g. latest)
#   --image     full image reference, e.g. ghcr.io/richbai90/hypercam-data
#               (default: derived from the git origin, overridable with the
#               HYPERCAM_DATA_IMAGE environment variable)
#   --data-dir  where to place the symlinks (default: data/ under the repo
#               root; overridable with HYPERCAM_DATA_DIR)
#   --unmount   remove the symlinks and release the image mount
#   --status    print the currently mounted snapshot, if any
#
# State is recorded in data/.mount (git-ignored), so --unmount knows exactly
# which image mount to release. Inside a podman container you can skip the
# host mount entirely: podman run --mount type=image,src=<ref>,target=/data

set -euo pipefail

usage() {
    cat <<'EOF'
Pull a commit-tagged experiment-data image (data + results) and expose it
on this machine without copying the data out: `podman image mount` mounts
it read-only and data/raw, data/cad_models and data/results become
symlinks into the mount.

Usage:
  data_image_mount.sh [--sha <git-sha> | --tag <tag>] [--image <ref>]
                      [--data-dir <path>] [--unmount] [--status]

Options:
  --sha       mount the data snapshot for this commit (default: HEAD)
  --tag       mount an explicit image tag instead (e.g. latest)
  --image     full image reference (default: derived from git origin,
              overridable with HYPERCAM_DATA_IMAGE)
  --data-dir  where to place the symlinks (default: data/ under the repo
              root; overridable with HYPERCAM_DATA_DIR)
  --unmount   remove the symlinks and release the image mount
  --status    print the currently mounted snapshot, if any

Rootless podman needs fuse-overlayfs to mount images.

Environment:
  PODMAN_STORAGE_DRIVER  optional storage-driver override (e.g. vfs)
EOF
}

podman_cmd=(podman)
if [[ -n ${PODMAN_STORAGE_DRIVER:-} ]]; then
    podman_cmd+=(--storage-driver "$PODMAN_STORAGE_DRIVER")
fi

action=mount
sha_arg=""
tag_arg=""
image_arg="${HYPERCAM_DATA_IMAGE:-}"
data_dir_arg="${HYPERCAM_DATA_DIR:-data}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sha) sha_arg=$2; shift ;;
        --tag) tag_arg=$2; shift ;;
        --image) image_arg=$2; shift ;;
        --data-dir) data_dir_arg=$2; shift ;;
        --unmount) action=unmount ;;
        --status) action=status ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PWD")
data_dir=$data_dir_arg
[[ $data_dir == /* ]] || data_dir="$repo_root/$data_dir"
state_file=$data_dir/.mount

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
image=${image,,}

# ---------------------------------------------------------------------------
# status: report what is currently wired up
# ---------------------------------------------------------------------------
if [[ $action == status ]]; then
    if [[ -f $state_file ]]; then
        . "$state_file"
        printf 'Mounted image: %s\n' "$MOUNTED_REF"
        printf 'Host path:     %s\n' "$MOUNT_POINT/data"
        printf 'Linked into:   %s/{raw,cad_models,results}\n' "$data_dir"
    else
        printf 'No data image is currently mounted (no %s).\n' "$state_file"
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# unmount: undo exactly what a previous mount recorded
# ---------------------------------------------------------------------------
if [[ $action == unmount ]]; then
    [[ -f $state_file ]] || {
        printf 'Error: no mount recorded in %s; nothing to unmount.\n' "$state_file" >&2
        exit 1
    }
    . "$state_file"
    for entry in $MOUNTED_ENTRIES; do
        link=$data_dir/$entry
        if [[ -L $link && $(readlink "$link") == "$MOUNT_POINT/data/$entry" ]]; then
            rm "$link"
            printf 'Removed symlink %s\n' "$link"
        elif [[ -e $link ]]; then
            printf 'Warning: %s is not a symlink into the mount; leaving it alone.\n' "$link" >&2
        fi
    done
    "${podman_cmd[@]}" image unmount "$MOUNTED_REF" >/dev/null
    printf 'Unmounted %s\n' "$MOUNTED_REF"
    rm -f "$state_file"
    exit 0
fi

# ---------------------------------------------------------------------------
# mount: pull the image and wire data/raw + data/cad_models + data/results to it
# ---------------------------------------------------------------------------
command -v podman >/dev/null 2>&1 || {
    printf 'Error: podman is not installed or not in PATH.\n' >&2
    exit 2
}

ref=${tag_arg:-}
if [[ -z $ref ]]; then
    sha=${sha_arg:-$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)}
    [[ -n $sha ]] || {
        printf 'Error: no --sha/--tag given and %s is not a git checkout.\n' "$repo_root" >&2
        exit 2
    }
    ref="sha-$sha"
fi

command -v fuse-overlayfs >/dev/null 2>&1 || {
    printf 'Warning: fuse-overlayfs not found; rootless `podman image mount`\n' >&2
    printf '         will likely fail. Install it: sudo apt install fuse-overlayfs\n' >&2
}

# If a different snapshot is currently mounted, release it first so the
# symlinks we are about to repoint do not leave a stale mount behind.
if [[ -f $state_file ]]; then
    . "$state_file"
    if [[ $MOUNTED_REF != "$image:$ref" ]]; then
        printf 'Switching snapshots: %s -> %s:%s\n' "$MOUNTED_REF" "$image" "$ref"
    fi
fi

if ! podman image exists "$image:$ref"; then
    printf 'Pulling %s:%s from the registry...\n' "$image" "$ref"
    "${podman_cmd[@]}" pull "$image:$ref"
fi

mount_point=$("${podman_cmd[@]}" image mount "$image:$ref" | tail -n1)
data_root=$mount_point/data
mkdir -p "$data_dir"
[[ -d $data_root/raw && -d $data_root/cad_models && -d $data_root/results ]] || {
    printf 'Error: %s does not look like a hypercam data image\n' "$image:$ref" >&2
    printf '       (missing raw/, cad_models/ or results/).\n' >&2
    "${podman_cmd[@]}" image unmount "$image:$ref" >/dev/null
    exit 3
}

declare -a mounted_entries=(raw cad_models results)
for entry in "${mounted_entries[@]}"; do
    link=$data_dir/$entry
    source=$data_root/$entry
    if [[ -L $link ]]; then
        rm "$link"
    elif [[ -d $link ]]; then
        if [[ -n $(ls -A "$link") ]]; then
            printf 'Error: %s already holds real data.\n' "$link" >&2
            printf '       This machine has native experiment data; unmount is not needed here.\n' >&2
            printf '       Move it aside first if you really want to serve it from the image.\n' >&2
            "${podman_cmd[@]}" image unmount "$image:$ref" >/dev/null
            exit 4
        fi
        rmdir "$link"
    fi
    ln -s "$source" "$link"
    printf 'Linked %s -> %s\n' "$link" "$source"
done

cat >"$state_file" <<EOF
MOUNTED_REF="$image:$ref"
MOUNT_POINT="$mount_point"
MOUNTED_ENTRIES="${mounted_entries[*]}"
SHA="${sha_arg:-}"
MOUNTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF

printf 'Mounted %s (commit-tagged data snapshot).\n' "$image:$ref"
printf 'Host access: %s\n' "$data_root"
printf 'Container access: podman run -v %s:/workspace/data:ro <image> ...\n' "$data_root"
printf "Run '%s --unmount' to release it.\n" "${BASH_SOURCE[0]##*/}"
