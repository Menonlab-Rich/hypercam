# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Thin, subprocess-based helpers for the handful of git plumbing calls.

The data-versioning workflow must interoperate with git from the command
line (stage the pointer file, read it back out of an arbitrary commit,
create a commit with a trailer).  Rather than pulling in a git library,
these helpers shell out to the ``git`` binary that git users already have,
keep output parsing explicit, and raise :class:`GitError` with the raw
stderr attached so failures are diagnosable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from hypercam.data_versioning.errors import GitError

# Exit code git uses for "path/ref does not exist"; treated as a normal,
# expected outcome by callers probing for a pointer that is not recorded yet.
_GIT_NOT_FOUND_EXIT = 128


def _run_git(args: list[str], repo_root: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command inside *repo_root* and return the completed process.

    :param args: git arguments (everything after the ``git`` keyword).
    :param repo_root: working directory for the command.
    :param check: when True (default), raise :class:`GitError` on a non-zero exit.
    :return: the completed process with ``stdout``/``stderr`` as text.
    """
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed (exit {completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return completed


def repository_root(start: Path | None = None) -> Path:
    """Return the top level of the git checkout containing *start*.

    :param start: directory to search from (default: the current directory).
    :raise GitError: if *start* is not inside a git work tree.
    """
    start = start or Path.cwd()
    completed = _run_git(["rev-parse", "--show-toplevel"], start, check=False)
    if completed.returncode != 0:
        raise GitError(
            f"{start} is not inside a git checkout; the data-versioning "
            "commands anchor everything to the repository root."
        )
    return Path(completed.stdout.strip())


def head_commit(repo_root: Path) -> str | None:
    """Return the full SHA of the current HEAD commit, or ``None`` before the first commit."""
    completed = _run_git(["rev-parse", "--verify", "HEAD"], repo_root, check=False)
    if completed.returncode != 0:
        return None  # unborn branch: no commit exists yet
    return completed.stdout.strip()


def current_branch(repo_root: Path) -> str:
    """Return the checked-out branch name, or ``"HEAD"`` on a detached HEAD."""
    completed = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "HEAD"


def read_file_at_ref(repo_root: Path, ref: str, relative_path: str) -> str | None:
    """Read a file's contents as recorded in *ref*.

    :param repo_root: git checkout to query.
    :param ref: any commit-ish expression (``HEAD``, ``HEAD~3``, a SHA, a tag).
    :param relative_path: path of the file relative to the repository root.
    :return: the file contents, or ``None`` when the file does not exist in
        that commit (e.g. before the pointer was first recorded).
    :raise GitError: if the ref itself cannot be resolved.
    """
    # Resolve the ref first and explicitly: git's own error message for a
    # bad ref combined with a missing path is ambiguous, and callers must be
    # able to distinguish "pointer not recorded yet" from "typo in the ref".
    _run_git(["cat-file", "-e", f"{ref}^{{commit}}"], repo_root)
    completed = _run_git(
        ["show", f"{ref}:{relative_path}"], repo_root, check=False
    )
    if completed.returncode == 0:
        return completed.stdout
    return None


def stage_paths(repo_root: Path, relative_paths: list[str]) -> None:
    """Stage files so they belong to the next commit.

    ``git add --force`` is used because ``data/.lakefs-commit`` lives under
    the blanket ``data/**`` ignore rule; the tracked-exception entry in
    ``.gitignore`` makes the force flag a no-op for contributors who run
    plain ``git add`` themselves.
    """
    _run_git(["add", "--force", *relative_paths], repo_root)


def create_commit(repo_root: Path, messages: list[str]) -> str:
    """Create a commit from the current index and return its full SHA.

    :param repo_root: git checkout to commit in.
    :param messages: one or more ``-m`` message paragraphs; the data-versioning
        workflow passes the user message first and the ``Data-lakefs-commit``
        trailer last.
    :raise GitError: if there is nothing staged to commit.
    """
    args = ["commit"]
    for message in messages:
        args += ["--message", message]
    _run_git(args, repo_root)
    return head_commit(repo_root) or ""
