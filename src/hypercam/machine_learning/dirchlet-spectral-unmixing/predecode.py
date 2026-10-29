# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-27
# Notice:        This file was authored or modified with the assistance of
#                Kilo (openrouter/qwen/qwen3.8-flash).
# ==============================================================================

"""Populate the EVT3 event cache for every manifest recording, in parallel.

EVT3 decoding is CPU-bound (Rust reader + numpy rasterization) and is the
pipeline bottleneck. It is also fully independent of the GPU, so it is done
ONCE here across all cores: each recording is decoded to flat event columns
(idx/t/p) under outputs/cache, from which clips at ANY frame density are
assembled at training time without re-decoding.

The cache key is shared with ``evt3.load_or_decode_events`` (recording
identity + OpenEVT build), so re-running is cheap: cached recordings are
skipped.
"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

import evt3

PROJECT_ROOT = Path(__file__).resolve().parent


def load_decode_settings() -> dict:
    """Read the exact decode parameters the trainer will use (cache-key match)."""
    config = yaml.safe_load((PROJECT_ROOT / "configs/config.yaml").read_text())
    data = yaml.safe_load(
        (PROJECT_ROOT / "configs/data/default.yaml").read_text()
    )
    library_dir = Path(config["evt3"]["library_dir"])
    if not library_dir.is_absolute():
        library_dir = PROJECT_ROOT / library_dir
    return {
        "library_dir": library_dir,
        "cache_dir": PROJECT_ROOT / data["cache_dir"],
    }


def decode_one(recording: str, settings: dict) -> tuple[str, int, str]:
    """Fill the event cache for one recording; returns a status line."""
    path = Path(recording)
    try:
        cache_dir, meta = evt3.load_or_decode_events(
            path,
            settings["cache_dir"],
            library_dir=settings["library_dir"],
        )
        return (path.name, int(meta["num_events"]), "ok")
    except Exception as error:  # noqa: BLE001 - report per-file, keep the pool alive
        return (path.name, 0, f"ERROR: {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "outputs/manifests/manifest.csv")
    parser.add_argument("--jobs", type=int, default=None, help="parallel workers (default: all cores)")
    args = parser.parse_args(argv)
    # Workers decode in parallel; keep them quiet and let the parent's
    # every-20 progress lines (below) be the signal.
    logging.basicConfig(level=logging.WARNING, force=True)

    import csv

    with args.manifest.open(newline="") as handle:
        recordings = sorted({row["recording"] for row in csv.DictReader(handle)})
    settings = load_decode_settings()
    print(f"{len(recordings)} recordings, {args.jobs or 'all'} workers, "
          f"cache={settings['cache_dir']}")

    done = failed = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(decode_one, r, settings): r for r in recordings}
        for future in as_completed(futures):
            name, windows, status = future.result()
            if status == "ok":
                done += 1
            else:
                failed += 1
                print(f"  {name}: {status}")
            if (done + failed) % 20 == 0:
                print(f"  {done + failed}/{len(recordings)} recordings decoded")
    print(f"predecode complete: {done} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
