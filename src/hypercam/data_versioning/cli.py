# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Command-line entry points for the data <-> git alignment workflow.

Three console scripts are installed:

- ``hypercam-data-commit``   — snapshot local data into lakeFS, stage the
  pointer (and optionally create the aligned git commit).
- ``hypercam-data-checkout`` — restore the data snapshot recorded at a git
  ref (HEAD by default, so "checkout the latest data" is one command).
- ``hypercam-data-status``   — show the drift between pointer, branch and
  local tree in both directions.

All three accept ``--help`` and share the same configuration surface
(options override ``HYPERCAM_LAKEFS_*``/``LAKECTL_*`` environment variables,
which override ``~/.lakectl.yaml``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hypercam.data_versioning.config import POINTER_RELATIVE_PATH, load_settings
from hypercam.data_versioning.errors import DataVersioningError
from hypercam.data_versioning.git_ops import repository_root
from hypercam.data_versioning.remote import LakeFSSession
from hypercam.data_versioning.sync import (
    build_status,
    checkout_data,
    commit_data,
)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach the options every subcommand understands."""
    parser.add_argument(
        "--repo",
        default=None,
        metavar="ID",
        help="lakeFS repository (default: %(default)s; env HYPERCAM_LAKEFS_REPOSITORY)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="directory holding raw/ and cad_models/ (default: <repo>/data; "
        "env HYPERCAM_DATA_DIR)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress per-file progress output",
    )


def _build_session(args: argparse.Namespace) -> tuple[object, object]:
    """Resolve settings and build a (not yet connected) lakeFS session.

    :return: ``(settings, session)``.
    """
    repo_root = repository_root()
    settings = load_settings(
        repo_root=repo_root,
        repository=args.repo,
        branch=getattr(args, "branch", None),
        data_dir=args.data_dir,
    )
    return settings, LakeFSSession(settings)


# --------------------------------------------------------------------------- #
# hypercam-data-commit
# --------------------------------------------------------------------------- #


def _commit_parser(subparsers: argparse.ArgumentParser) -> None:
    """Register the ``commit`` subcommand."""
    parser = subparsers.add_parser(
        "commit",
        help="snapshot local data/ + results/ into a lakeFS commit and stage "
        "the pointer for the next git commit",
        description=(
            "Upload changed files under data/{raw,cad_models} and results/ "
            "(minus results/archive) to the lakeFS branch, commit the branch, "
            f"write the returned commit hash into {POINTER_RELATIVE_PATH} and "
            "stage that file so the next git commit carries it. With "
            "--git-commit, also create that git commit with a "
            "Data-lakefs-commit trailer."
        ),
    )
    _add_shared_arguments(parser)
    parser.add_argument(
        "--branch",
        default=None,
        help="lakeFS branch to commit to (default: main; env HYPERCAM_LAKEFS_BRANCH)",
    )
    parser.add_argument(
        "-m",
        "--message",
        default=None,
        help="commit message for the lakeFS commit and (with --git-commit) the "
        "git commit",
    )
    parser.add_argument(
        "--git-commit",
        action="store_true",
        help="also run `git commit` on the staged pointer (requires --message) "
        "and append a Data-lakefs-commit trailer",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="create the lakeFS repository if it does not exist yet",
    )
    parser.add_argument(
        "--storage-namespace",
        default=None,
        metavar="URI",
        help="physical namespace for --create, e.g. s3://bucket/hypercam-data "
        "or local:///path/to/blocks",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="do not delete remote objects that no longer exist locally",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="skip the empty-snapshot safety guard",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be uploaded/deleted without changing anything",
    )
    parser.set_defaults(handler=_run_commit)


def _run_commit(args: argparse.Namespace) -> int:
    """Execute the commit flow."""
    settings, session = _build_session(args)
    outcome = commit_data(
        settings,
        session,
        message=args.message,
        make_git_commit=args.git_commit,
        create_repository=args.create,
        storage_namespace=args.storage_namespace,
        prune=not args.no_prune,
        force=args.force,
        dry_run=args.dry_run,
        quiet=args.quiet,
    )
    print(f"lakeFS repository : {settings.repository}")
    print(f"lakeFS branch     : {settings.branch}")
    print(f"plan              : {outcome.upload_plan.summary('upload')}")
    if outcome.dry_run:
        print("dry run: nothing was transferred, committed or written.")
        return 0
    if outcome.lakefs_commit:
        print(f"lakeFS commit     : {outcome.lakefs_commit}")
    if outcome.git_commit:
        print(f"git commit        : {outcome.git_commit}")
        print(
            "The two histories are aligned: the git commit carries the lakeFS "
            "hash in data/.lakefs-commit and in its message trailer."
        )
    else:
        print(
            "Next step: `git commit` (the staged pointer aligns it with the "
            "data snapshot above)."
        )
    return 0


# --------------------------------------------------------------------------- #
# hypercam-data-checkout
# --------------------------------------------------------------------------- #


def _checkout_parser(subparsers: argparse.ArgumentParser) -> None:
    """Register the ``checkout`` subcommand."""
    parser = subparsers.add_parser(
        "checkout",
        help="restore the data snapshot recorded at a git ref",
        description=(
            "Read data/.lakefs-commit from the given git ref and make the "
            "local data/ + results/ trees byte-identical to that lakeFS "
            "commit: download changed files, restore their timestamps and "
            "remove local files the snapshot does not contain."
        ),
    )
    _add_shared_arguments(parser)
    parser.add_argument(
        "--git-ref",
        default="HEAD",
        metavar="REF",
        help="git ref to read the pointer from (default: HEAD)",
    )
    parser.add_argument(
        "--keep-deleted",
        action="store_true",
        help="keep local files that the snapshot does not contain",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be downloaded/deleted without changing anything",
    )
    parser.set_defaults(handler=_run_checkout)


def _run_checkout(args: argparse.Namespace) -> int:
    """Execute the checkout flow."""
    settings, session = _build_session(args)
    outcome = checkout_data(
        settings,
        session,
        git_ref=args.git_ref,
        keep_deleted=args.keep_deleted,
        dry_run=args.dry_run,
        quiet=args.quiet,
    )
    print(f"git ref           : {outcome.git_ref}")
    print(f"lakeFS commit     : {outcome.lakefs_commit}")
    print(f"plan              : {outcome.download_plan.summary('download')}")
    if outcome.dry_run:
        print("dry run: nothing was downloaded, deleted or written.")
    else:
        print(f"data now matches lakeFS commit {outcome.lakefs_commit}.")
    return 0


# --------------------------------------------------------------------------- #
# hypercam-data-status
# --------------------------------------------------------------------------- #


def _status_parser(subparsers: argparse.ArgumentParser) -> None:
    """Register the ``status`` subcommand."""
    parser = subparsers.add_parser(
        "status",
        help="report drift between the pointer, the lakeFS branch and the local tree",
        description=(
            "Show which lakeFS commit the git history points at, how the "
            "branch head differs, and what commit/checkout would transfer. "
            "Works without a reachable server (the remote sections degrade "
            "gracefully)."
        ),
    )
    _add_shared_arguments(parser)
    parser.add_argument(
        "--git-ref",
        default="HEAD",
        metavar="REF",
        help="git ref to read the pointer from (default: HEAD)",
    )
    parser.set_defaults(handler=_run_status)


def _render_pointer_line(pointer) -> str:
    """Format one pointer for display."""
    if pointer is None:
        return "not recorded"
    commit = pointer.commit or "none (run hypercam-data-commit)"
    return f"{commit}  (repository {pointer.repository}, branch {pointer.branch})"


def _run_status(args: argparse.Namespace) -> int:
    """Execute the status flow."""
    settings, session = _build_session(args)
    report = build_status(settings, session, git_ref=args.git_ref)

    print(f"lakeFS endpoint   : {report.endpoint}")
    print(f"git HEAD          : {report.git_head or 'no commits yet'}")
    print(f"git branch        : {report.git_branch}")
    if report.pointer_error:
        print(f"pointer at ref    : not recorded ({report.pointer_error})")
    else:
        print(f"pointer at ref    : {_render_pointer_line(report.pointer_at_ref)}")
    if report.pointer_on_disk != report.pointer_at_ref:
        print(f"pointer on disk   : {_render_pointer_line(report.pointer_on_disk)}")
        print("                    (uncommitted changes to the pointer file)")
    if not report.remote_reachable:
        print(f"remote            : UNREACHABLE — {report.remote_error}")
        print(
            "  Start a lakeFS server or fix the endpoint/credentials; "
            "see README 'Data version control'."
        )
        return 1
    print(f"branch head       : {report.branch_head}")
    if report.commit_plan is not None:
        print(f"commit direction  : {report.commit_plan.summary('upload')}")
    if report.checkout_plan is not None:
        print(
            f"checkout direction: {report.checkout_plan.summary('download')} "
            f"(snapshot {report.checkout_lakefs_commit})"
        )
    elif report.pointer_error:
        print("checkout direction: n/a (no snapshot recorded at this ref)")
    aligned = (
        report.branch_head is not None
        and report.pointer_at_ref is not None
        and report.pointer_at_ref.commit == report.branch_head
        and report.commit_plan is not None
        and report.commit_plan.is_empty
    )
    print("histories         : " + ("ALIGNED" if aligned else "NOT ALIGNED"))
    return 0


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def data_main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested subcommand.

    :param argv: argument list (defaults to ``sys.argv[1:]``).
    :return: process exit code (0 success, 1 handled failure, 2 usage error).
    """
    parser = argparse.ArgumentParser(
        prog="hypercam-data",
        description=(
            "Keep the experiment data (lakeFS) and the source code (git) "
            "histories aligned."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _commit_parser(subparsers)
    _checkout_parser(subparsers)
    _status_parser(subparsers)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except DataVersioningError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def commit_main(argv: list[str] | None = None) -> int:
    """Console-script entry point: ``hypercam-data-commit`` (alias of data_main commit)."""
    return data_main(["commit", *(argv if argv is not None else sys.argv[1:])])


def checkout_main(argv: list[str] | None = None) -> int:
    """Console-script entry point: ``hypercam-data-checkout``."""
    return data_main(["checkout", *(argv if argv is not None else sys.argv[1:])])


def status_main(argv: list[str] | None = None) -> int:
    """Console-script entry point: ``hypercam-data-status``."""
    return data_main(["status", *(argv if argv is not None else sys.argv[1:])])


if __name__ == "__main__":
    raise SystemExit(data_main())
