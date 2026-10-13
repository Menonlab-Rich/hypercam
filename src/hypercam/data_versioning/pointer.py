# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""The ``data/.lakefs-commit`` pointer: the record that binds git to lakeFS.

The file is tiny and *tracked by git*.  Each git commit therefore carries,
as first-class content, the hash of the lakeFS commit that holds the exact
data snapshot belonging to it::

    # Written by hypercam-data-commit; see README "Data version control".
    repository: hypercam-data
    branch: main
    commit: e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6
    parent-git-commit: 9703eaf0a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
    recorded-at: 2026-10-08T21:00:00Z

``commit: none`` is the placeholder for a checkout that has not recorded a
data snapshot yet (e.g. a fresh repository before the first
``hypercam-data-commit`` run).  ``parent-git-commit`` is advisory: it names
the git commit that was HEAD when the data snapshot was taken, which is the
*parent* of the git commit that ends up carrying the pointer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from hypercam.data_versioning.errors import PointerError

#: Marker written instead of a hash when nothing has been recorded yet.
_COMMIT_NONE = "none"

#: Keys understood in the pointer file, in canonical output order.
_KEYS_IN_ORDER = ("repository", "branch", "commit", "parent-git-commit", "recorded-at")


@dataclass(frozen=True)
class DataPointer:
    """A parsed ``data/.lakefs-commit`` record.

    :param repository: lakeFS repository the snapshot lives in.
    :param branch: lakeFS branch the snapshot was committed to.
    :param commit: lakeFS commit hash, or ``None`` when nothing has been
        recorded yet.
    :param parent_git_commit: git SHA that was HEAD when the snapshot was
        taken (advisory; ``None`` before the first git commit).
    :param recorded_at: ISO-8601 UTC timestamp of when the pointer was written.
    """

    repository: str
    branch: str
    commit: str | None = None
    parent_git_commit: str | None = None
    recorded_at: str | None = None

    @property
    def is_recorded(self) -> bool:
        """True once a real lakeFS commit hash has been recorded."""
        return bool(self.commit)


def parse_pointer(text: str) -> DataPointer:
    """Parse the pointer-file format into a :class:`DataPointer`.

    :param text: full file contents.
    :return: the parsed pointer.
    :raise PointerError: when required keys are missing or duplicated.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        key = key.strip()
        if not separator:
            raise PointerError(f"pointer line {raw_line!r} is not of the form 'key: value'")
        if key in values:
            raise PointerError(f"pointer key {key!r} appears more than once")
        values[key] = value.strip()

    missing = [key for key in ("repository", "branch") if not values.get(key)]
    if missing:
        raise PointerError(f"pointer file is missing required key(s): {', '.join(missing)}")

    def optional(key: str) -> str | None:
        value = values.get(key, "")
        return None if value in ("", _COMMIT_NONE) else value

    return DataPointer(
        repository=values["repository"],
        branch=values["branch"],
        commit=optional("commit"),
        parent_git_commit=optional("parent-git-commit"),
        recorded_at=optional("recorded-at"),
    )


def render_pointer(pointer: DataPointer) -> str:
    """Render a :class:`DataPointer` into the pointer-file text format.

    The output always starts with a short provenance comment so the file
    remains self-explanatory in ``git show`` and in diffs.
    """
    commit_value = pointer.commit or _COMMIT_NONE
    parent_value = pointer.parent_git_commit or _COMMIT_NONE
    recorded_value = pointer.recorded_at or _COMMIT_NONE
    lines = [
        "# Hypercam data <-> git alignment pointer (see README, 'Data version').",
        "# Tracked by git: the commit carrying this file names the lakeFS commit",
        "# holding the matching data snapshot (raw/, cad_models/, results/).",
    ]
    rendered_values = {
        "repository": pointer.repository,
        "branch": pointer.branch,
        "commit": commit_value,
        "parent-git-commit": parent_value,
        "recorded-at": recorded_value,
    }
    lines += [f"{key}: {rendered_values[key]}" for key in _KEYS_IN_ORDER]
    return "\n".join(lines) + "\n"


def read_pointer_file(path: Path) -> DataPointer | None:
    """Read and parse the pointer file from disk.

    :param path: location of ``data/.lakefs-commit``.
    :return: the parsed pointer, or ``None`` when the file does not exist yet.
    :raise PointerError: when the file exists but cannot be parsed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise PointerError(f"cannot read pointer file {path}: {error}") from error
    return parse_pointer(text)


def write_pointer_file(path: Path, pointer: DataPointer) -> None:
    """Atomically write the pointer file.

    A temporary file is written in the same directory and then renamed so a
    crash can never leave a half-written pointer behind.
    """
    temporary_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary_path.write_text(render_pointer(pointer), encoding="utf-8")
        os.replace(temporary_path, path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise PointerError(f"cannot write pointer file {path}: {error}") from error


def fresh_pointer(repository: str, branch: str, parent_git_commit: str | None) -> DataPointer:
    """Build a pointer for a just-created lakeFS commit.

    :param repository: lakeFS repository that received the snapshot.
    :param branch: lakeFS branch that received the snapshot.
    :param parent_git_commit: git SHA that was HEAD when the snapshot was taken.
    :return: a pointer stamped with the current UTC time.
    """
    return DataPointer(
        repository=repository,
        branch=branch,
        commit=None,  # filled in by the caller once the lakeFS commit exists
        parent_git_commit=parent_git_commit,
        recorded_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def with_commit(pointer: DataPointer, commit_id: str) -> DataPointer:
    """Return a copy of *pointer* bound to the lakeFS commit *commit_id*."""
    return replace(pointer, commit=commit_id)
