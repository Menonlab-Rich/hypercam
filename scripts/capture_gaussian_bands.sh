#!/usr/bin/env bash
#
#==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
#==============================================================================
#
# Sweep the superk varia continuum source across 50 nm-wide bands centered on
# 425..675 nm (25 nm steps) and record 5 s of EVT3 for each band with the
# Arena SDK's Cpp_SaveRaw example. Recordings land in data/raw/evt3_raw/ as
# <prefix>_<midpoint nm>.raw, matching the naming the analysis CLI expects.

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export LD_LIBRARY_PATH=/opt/ArenaSDK_Linux_x64/Qt/lib:/opt/ArenaSDK_Linux_x64/lib64:/opt/ArenaSDK_Linux_x64/OutputDirectory/Linux/x64Release:/opt/ArenaSDK_Linux_x64/GenICam/library/lib/Linux64_x64/:/opt/ArenaSDK_Linux_x64/ffmpeg/:/opt/ArenaSDK_Linux_x64/Metavision/lib/:${LD_LIBRARY_PATH:-}

capture_program=/opt/ArenaSDK_Linux_x64/Examples/Arena/Cpp_SaveRaw/Cpp_SaveRaw
capture_duration=5
prefix="$1"
raw_dir="$repo_root/data/raw/evt3_raw"
mkdir -p "$raw_dir"

command -v superk varia >/dev/null 2>&1 || {
    printf 'Error: varia is not available in PATH.\n' >&2
    exit 1
}

if [[ ! -x $capture_program ]]; then
    printf 'Error: capture program is not executable: %s\n' "$capture_program" >&2
    exit 1
fi

for ((n = 400; n <= 650; n += 25)); do
    upper=$((n + 50))
    midpoint=$((n + 25))
    destination="$raw_dir/${prefix}_${midpoint}.raw"

    printf 'Capturing band %d-%d nm -> %s\n' "$n" "$upper" "$destination"

    if [[ -e $destination ]]; then
        printf 'Skipping band %d-%d nm; destination already exists: %s\n' \
            "$n" "$upper" "$destination"
        continue
    fi

    superk varia band "$n" "$upper" || {
        printf 'Error: failed to set the Varia band to %d-%d nm.\n' "$n" "$upper" >&2
        exit 1
    }

    "$capture_program" \
        -d "$capture_duration" \
        -o "$destination"
    capture_status=$?

    if ((capture_status != 0)); then
        printf 'Error: capture program exited unexpectedly (status %d).\n' \
            "$capture_status" >&2
        exit "$capture_status"
    fi

    if [[ ! -f $destination ]]; then
        printf 'Error: capture did not create %s for band %d-%d nm.\n' \
            "$destination" \
            "$n" "$upper" >&2
        exit 1
    fi

    # Allow the GigE/GenTL stack a brief settling period before reopening the
    # same device for the next wavelength band.
    sleep 1
done

printf 'Finished capturing all bands.\n'
