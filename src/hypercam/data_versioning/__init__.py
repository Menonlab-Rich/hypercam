# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Aligned version control of experiment data and source code.

The heavy experiment data (``data/raw``, ``data/cad_models``) and the
analysis outputs (``results/``) are too large for git, so they are
versioned in a parallel `lakeFS <https://lakefs.io>`_ repository — a
Git-like versioning layer on top of object storage.  This package keeps
the two histories *aligned*:

- ``hypercam-data-commit``  snapshots the local data tree into a lakeFS
  commit and records that commit's hash in the git-tracked pointer file
  ``data/.lakefs-commit`` (staged, so the *next* git commit carries it).
  With ``--git-commit`` it also creates the git commit, embedding the
  hash a second time as a ``Data-lakefs-commit:`` message trailer.
- ``hypercam-data-checkout`` reads the pointer from any git ref and
  materialises the exact data snapshot that commit refers to — the
  one-command answer to "give me the data for the latest updates".
- ``hypercam-data-status`` reports how far the local data, the lakeFS
  branch head and the recorded pointer have drifted apart.

Directory contents mirror the GHCR data image (``raw/``, ``cad_models/``,
``results/`` without ``results/archive/``), so both versioning mechanisms
carry byte-identical trees.
"""

from hypercam.data_versioning.errors import (
    ConfigurationError,
    DataVersioningError,
    GitError,
    LocalDataError,
    PointerError,
    RemoteError,
)

__all__ = [
    "ConfigurationError",
    "DataVersioningError",
    "GitError",
    "LocalDataError",
    "PointerError",
    "RemoteError",
]
