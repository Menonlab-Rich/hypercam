# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Planning and execution of the data <-> git alignment flows.

Three flows live here, one per command:

- :func:`commit_data` — bring the lakeFS branch to the local data state,
  record the resulting commit hash in ``data/.lakefs-commit`` and stage it,
  optionally creating the git commit (with a ``Data-lakefs-commit:``
  trailer) so the two histories are aligned.
- :func:`checkout_data` — read the pointer recorded at a git ref and make
  the local data tree byte-identical to that lakeFS commit (downloading
  changed files, deleting files the snapshot does not contain).
- :func:`build_status` — compare pointer (git ref and working tree),
  branch head and local tree to report drift in both directions.

Change detection is deliberately cheap: a file counts as unchanged only
when both size and modification time match the remote object.  Uploads
record the local mtime on the object and downloads restore it, so
repeated runs converge to a no-op.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from hypercam.data_versioning.config import (
    EXCLUDED_REMOTE_PREFIXES,
    POINTER_RELATIVE_PATH,
    Settings,
)
from hypercam.data_versioning.errors import (
    ConfigurationError,
    LocalDataError,
    PointerError,
    RemoteError,
)
from hypercam.data_versioning.git_ops import (
    create_commit,
    current_branch,
    head_commit,
    read_file_at_ref,
    stage_paths,
)
from hypercam.data_versioning.pointer import (
    DataPointer,
    fresh_pointer,
    parse_pointer,
    read_pointer_file,
    with_commit,
    write_pointer_file,
)
from hypercam.data_versioning.remote import LakeFSSession, RemoteStamp


@dataclass(frozen=True)
class FileStamp:
    """What change detection needs to know about a local file."""

    size_bytes: int
    mtime: int


@dataclass
class TransferPlan:
    """The work needed to reconcile one direction of the sync.

    :param transfers: object paths that must be uploaded (commit flow) or
        downloaded (checkout flow).
    :param deletions: object paths that must be deleted remotely (files that
        vanished locally) or locally (files absent from the snapshot).
    :param unchanged: number of files already identical on both sides.
    """

    transfers: list[str] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    unchanged: int = 0

    @property
    def is_empty(self) -> bool:
        """True when nothing needs to move in this direction."""
        return not self.transfers and not self.deletions

    def summary(self, transfer_verb: str) -> str:
        """One-line human summary of the plan."""
        return (
            f"{len(self.transfers)} file(s) to {transfer_verb}, "
            f"{len(self.deletions)} to delete, {self.unchanged} already up to date"
        )


def _is_unchanged(local: FileStamp | None, remote: RemoteStamp | None) -> bool:
    """Decide whether a local file and a remote object are the same snapshot.

    Both sides must agree on size *and* modification time.  An object whose
    mtime the server never recorded (e.g. imported by foreign tooling) is
    always treated as changed: that forces exactly one extra transfer and is
    the safe direction to err in.
    """
    if local is None or remote is None:
        return False
    if remote.mtime is None:
        return False
    return local.size_bytes == (remote.size_bytes or 0) and local.mtime == remote.mtime


def plan_transfer(
    local: dict[str, FileStamp], remote: dict[str, RemoteStamp]
) -> tuple[TransferPlan, TransferPlan]:
    """Plan both sync directions over one prefix's listings.

    :param local: mapping of remote object path to local file stamp.
    :param remote: mapping of remote object path to remote stamp.
    :return: ``(upload_plan, download_plan)`` — the upload plan lists files
        to push and remote deletions; the download plan lists files to pull
        and local deletions.
    """
    unchanged = sum(1 for path in local if _is_unchanged(local[path], remote.get(path)))
    upload_plan = TransferPlan(
        transfers=sorted(
            path for path, stamp in local.items() if not _is_unchanged(stamp, remote.get(path))
        ),
        deletions=sorted(path for path in remote if path not in local),
        unchanged=unchanged,
    )
    download_plan = TransferPlan(
        transfers=sorted(
            path for path, stamp in remote.items() if not _is_unchanged(local.get(path), stamp)
        ),
        deletions=sorted(path for path in local if path not in remote),
        unchanged=unchanged,
    )
    return upload_plan, download_plan


def _local_paths_under_prefix(
    local_inventory: dict[str, FileStamp], remote_prefix: str
) -> dict[str, FileStamp]:
    """Slice the local inventory down to one remote prefix."""
    return {
        path: stamp
        for path, stamp in local_inventory.items()
        if path.startswith(remote_prefix)
    }


def _plan_merged(
    local_inventory: dict[str, FileStamp],
    remote_by_prefix: dict[str, dict[str, RemoteStamp]],
    keep_local_deletions: bool,
) -> TransferPlan:
    """Merge per-prefix plans into one whole-tree plan.

    :param local_inventory: full local inventory (all prefixes).
    :param remote_by_prefix: remote listing grouped by prefix.
    :param keep_local_deletions: when True, local files absent from the
        snapshot are reported as deletions (checkout semantics); when False
        the local side is authoritative and only remote deletions are
        reported (commit semantics).
    :return: the merged plan (uploads or downloads in :attr:`transfers`,
        depending on direction, plus the deletions applicable to it).
    """
    merged_transfers: list[str] = []
    merged_local_deletions: list[str] = []
    merged_remote_deletions: list[str] = []
    unchanged = 0
    for remote_prefix, remote_objects in remote_by_prefix.items():
        prefix_local = _local_paths_under_prefix(local_inventory, remote_prefix)
        uploads, downloads = plan_transfer(prefix_local, remote_objects)
        if keep_local_deletions:
            merged_transfers += downloads.transfers
            merged_local_deletions += downloads.deletions
        else:
            merged_transfers += uploads.transfers
            merged_remote_deletions += uploads.deletions
        unchanged += uploads.unchanged
    deletions = merged_local_deletions if keep_local_deletions else merged_remote_deletions
    return TransferPlan(
        transfers=sorted(merged_transfers), deletions=sorted(deletions), unchanged=unchanged
    )


def scan_local_tree(settings: Settings) -> dict[str, FileStamp]:
    """Inventory every file that belongs in the lakeFS repository.

    Walks ``raw/``, ``cad_models/`` and ``results/`` (relative to the
    resolved data/results roots) and maps each file onto its remote object
    name.  ``results/archive/`` is skipped on both sides, matching the data
    image build; symbolic links are never followed (the data image mount
    works through symlinks and must not be traversed — see
    :func:`ensure_local_roots_mountable`).

    :param settings: resolved settings.
    :return: mapping of remote object path to local file stamp.
    """
    inventory: dict[str, FileStamp] = {}
    for content_root in settings.content_roots:
        root = content_root.local_path
        if not root.is_dir():
            continue
        for directory, subdirectories, file_names in os.walk(root):
            # Do not descend into symlinked directories: podman image mounts
            # expose read-only trees that must never be written into.
            subdirectories[:] = [
                name for name in subdirectories if not (Path(directory) / name).is_symlink()
            ]
            for file_name in file_names:
                file_path = Path(directory) / file_name
                if file_path.is_symlink():
                    continue  # mount artefact or loose link: not a snapshot member
                remote_path = content_root.remote_path_for(file_path)
                if any(remote_path.startswith(prefix) for prefix in EXCLUDED_REMOTE_PREFIXES):
                    continue
                stat_result = file_path.stat()
                inventory[remote_path] = FileStamp(
                    size_bytes=stat_result.st_size,
                    mtime=int(stat_result.st_mtime),
                )
    return inventory


def ensure_local_roots_mountable(settings: Settings, for_writing: bool) -> None:
    """Refuse to operate when a data root is a symlink or otherwise not a plain directory.

    A symlinked root almost always means ``scripts/data_image_mount.sh`` has
    mounted a read-only image over the tree; writing there would fail or,
    worse, mislead change detection.

    :param settings: resolved settings.
    :param for_writing: True for the commit flow (which also rejects missing
        directories, since an empty source would otherwise prune everything
        from the remote snapshot).
    :raise LocalDataError: describing the offending root and how to fix it.
    """
    for content_root in settings.content_roots:
        root = content_root.local_path
        if root.is_symlink():
            raise LocalDataError(
                f"{root} is a symlink; it looks like a data-image mount. Run "
                "`scripts/data_image_mount.sh --unmount` (and re-run the "
                "command) before syncing with lakeFS."
            )
        if root.exists() and not root.is_dir():
            raise LocalDataError(f"{root} exists but is not a directory.")
        if for_writing and not root.is_dir():
            raise LocalDataError(
                f"{root} does not exist on this machine, so this checkout "
                "does not hold the experiment data. Run the sync from the lab "
                "workstation or point --data-dir (env HYPERCAM_DATA_DIR) at the "
                "directory holding raw/ and cad_models/."
            )


def _require_non_empty_snapshot(
    settings: Settings, inventory: dict[str, FileStamp], force: bool
) -> None:
    """Guard against publishing a data-less snapshot.

    Mirrors the byte-size guard in ``scripts/data_image_build.sh``: if the
    recording roots contain no file at all, the caller is probably on a
    machine without the data, and committing would *delete* the entire
    remote snapshot (pruning everything that is not local).
    """
    if force:
        return
    recording_paths = sorted(
        path for path in inventory if path.startswith(("raw/", "cad_models/"))
    )
    if not recording_paths:
        raise LocalDataError(
            "No recordings or CAD models were found under "
            f"{settings.data_dir}; refusing to commit a snapshot that would "
            "prune the remote data. Run from the lab workstation, fix "
            "--data-dir, or pass --force if an empty recording set is intended."
        )


def _progress_printer(quiet: bool):
    """Return a progress callback; silent in quiet mode, printing otherwise."""
    return (lambda message: None) if quiet else print


# --------------------------------------------------------------------------- #
# Flow: commit
# --------------------------------------------------------------------------- #


@dataclass
class CommitOutcome:
    """Result of :func:`commit_data`."""

    lakefs_commit: str | None
    branch_head_before: str | None
    upload_plan: TransferPlan
    git_commit: str | None = None
    pointer_written: bool = False
    dry_run: bool = False


def commit_data(
    settings: Settings,
    session: LakeFSSession,
    message: str | None = None,
    make_git_commit: bool = False,
    create_repository: bool = False,
    storage_namespace: str | None = None,
    prune: bool = True,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
) -> CommitOutcome:
    """Snapshot the local data into lakeFS and record the hash for git.

    :param settings: resolved settings.
    :param session: connected lakeFS session.
    :param message: commit message; used for both the lakeFS commit and
        (when *make_git_commit*) the git commit.  Defaults to a descriptive
        one-liner for the data side.
    :param make_git_commit: also create the git commit carrying the staged
        pointer plus a ``Data-lakefs-commit:`` trailer; requires *message*.
    :param create_repository: create the lakeFS repository if it is missing.
    :param storage_namespace: physical namespace for repository creation
        (required for a genuinely new repository, e.g.
        ``s3://bucket/hypercam-data`` or ``local:///path``).
    :param prune: delete remote objects that no longer exist locally
        (default True; recoverable through lakeFS history).
    :param force: skip the empty-snapshot safety guard.
    :param dry_run: compute and report the plan without transferring,
        committing or writing the pointer.
    :param quiet: suppress per-file progress output.
    :return: a :class:`CommitOutcome` describing what was (or would be) done.
    :raise ConfigurationError: inconsistent options (``--git-commit`` without
        ``--message``, ``--create`` without a namespace for a new repository).
    :raise LocalDataError: the local tree cannot be a snapshot source.
    :raise RemoteError: the server refused an operation.
    """
    if make_git_commit and not message:
        raise ConfigurationError("--git-commit requires --message.")

    if create_repository:
        if storage_namespace is None and not _repository_exists(session):
            raise ConfigurationError(
                "--create needs --storage-namespace (e.g. s3://bucket/hypercam-data "
                "or local:///var/lib/lakefs/blocks/hypercam-data) the first time "
                "the repository is created."
            )
        if storage_namespace is not None:
            session.ensure_repository(storage_namespace)

    repository = session.repository()
    branch = session.branch(repository)
    branch_head_before = branch.head.id

    ensure_local_roots_mountable(settings, for_writing=True)
    local_inventory = scan_local_tree(settings)
    _require_non_empty_snapshot(settings, local_inventory, force)
    remote_by_prefix = session.list_objects(branch.id).objects_by_prefix

    # The local side is authoritative: push what differs and prune what
    # vanished, so the branch head becomes an exact snapshot of the machine.
    plan = _plan_merged(
        local_inventory, remote_by_prefix, keep_local_deletions=False
    )
    if not prune:
        plan.deletions = []

    outcome = CommitOutcome(
        lakefs_commit=None,
        branch_head_before=branch_head_before,
        upload_plan=plan,
        dry_run=dry_run,
    )
    if dry_run:
        return outcome

    progress = _progress_printer(quiet)
    for remote_path in plan.transfers:
        content_root = _content_root_for_path(settings, remote_path)
        local_file = content_root.local_path_for(remote_path)
        progress(f"upload  {remote_path}  ({local_file.stat().st_size} bytes)")
        session.upload_file(branch, local_file, remote_path)
    if plan.deletions:
        progress(f"pruning {len(plan.deletions)} remote object(s) absent locally")
        session.delete_objects(branch, plan.deletions)

    git_head = head_commit(settings.repo_root)
    commit_metadata = {
        "git-commit-parent": git_head or "none",
        "git-branch": current_branch(settings.repo_root),
        "tool": "hypercam-data-commit",
    }
    data_message = message or "Experiment data snapshot (hypercam-data-commit)"
    new_commit = session.commit_branch(branch, data_message, commit_metadata)
    if new_commit is None:
        new_commit = branch.head.id  # nothing pending: point at the current head
    outcome.lakefs_commit = new_commit

    pointer = with_commit(
        fresh_pointer(
            repository=settings.repository,
            branch=settings.branch,
            parent_git_commit=git_head,
        ),
        new_commit,
    )
    write_pointer_file(settings.pointer_path, pointer)
    stage_paths(settings.repo_root, [POINTER_RELATIVE_PATH])
    outcome.pointer_written = True
    progress(f"pointer staged: {POINTER_RELATIVE_PATH} -> lakeFS {new_commit}")

    if make_git_commit:
        outcome.git_commit = create_commit(
            settings.repo_root,
            [message, f"Data-lakefs-commit: {new_commit}"],
        )
        progress(
            f"git {outcome.git_commit} <-> lakeFS {new_commit} "
            f"(pointer: {POINTER_RELATIVE_PATH})"
        )
    return outcome


def _repository_exists(session: LakeFSSession) -> bool:
    """True when the configured repository already exists on the server."""
    try:
        _ = session.repository()
    except RemoteError:
        return False
    return True


def _content_root_for_path(settings: Settings, remote_path: str):
    """Find the content root owning a remote object path."""
    for content_root in settings.content_roots:
        if remote_path.startswith(content_root.remote_prefix):
            return content_root
    raise ConfigurationError(f"{remote_path!r} does not belong to any synced prefix.")


# --------------------------------------------------------------------------- #
# Flow: checkout
# --------------------------------------------------------------------------- #


@dataclass
class CheckoutOutcome:
    """Result of :func:`checkout_data`."""

    lakefs_commit: str
    git_ref: str
    download_plan: TransferPlan
    dry_run: bool


def read_pointer_at_ref(settings: Settings, git_ref: str) -> DataPointer:
    """Load the data pointer recorded in git at *git_ref*.

    :param settings: resolved settings (only the repo root is used).
    :param git_ref: commit-ish expression to read the pointer from.
    :return: the parsed pointer.
    :raise PointerError: when the ref carries no pointer, or the pointer
        does not name a data snapshot yet.
    """
    text = read_file_at_ref(settings.repo_root, git_ref, POINTER_RELATIVE_PATH)
    if text is None:
        raise PointerError(
            f"{POINTER_RELATIVE_PATH} does not exist at git ref {git_ref!r}; the "
            "history before the lakeFS integration has no data snapshots."
        )
    pointer = parse_pointer(text)
    if not pointer.is_recorded:
        raise PointerError(
            f"the git commit at {git_ref!r} has no data snapshot recorded yet "
            f"({POINTER_RELATIVE_PATH} still says commit: none). Run "
            "`hypercam-data-commit` on the machine holding the data."
        )
    return pointer


def checkout_data(
    settings: Settings,
    session: LakeFSSession,
    git_ref: str = "HEAD",
    keep_deleted: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
) -> CheckoutOutcome:
    """Materialise the data snapshot recorded at git ref *git_ref*.

    The pointer file is authoritative: its repository and commit are used
    even when the configured defaults differ, so checking out an old commit
    reproduces exactly the data that commit pinned.

    :param settings: resolved settings.
    :param session: connected lakeFS session.
    :param git_ref: git commit-ish to take the pointer from (default HEAD).
    :param keep_deleted: keep local files that the snapshot does not contain
        (default: delete them, for an exact checkout).
    :param dry_run: report the plan without touching anything.
    :param quiet: suppress per-file progress output.
    :return: a :class:`CheckoutOutcome` describing what was (or would be) done.
    :raise PointerError: no usable pointer at *git_ref*.
    :raise LocalDataError: the local roots cannot be written.
    :raise RemoteError: the server refused an operation.
    """
    pointer = read_pointer_at_ref(settings, git_ref)
    snapshot_commit = pointer.commit
    if snapshot_commit is None:  # defensive: read_pointer_at_ref guarantees this
        raise PointerError(f"pointer at {git_ref!r} records no snapshot commit.")

    # The pointer's repository/branch take precedence over configured defaults.
    authoritative = Settings(
        endpoint=settings.endpoint,
        access_key_id=settings.access_key_id,
        secret_access_key=settings.secret_access_key,
        repository=pointer.repository,
        branch=pointer.branch,
        repo_root=settings.repo_root,
        data_dir=settings.data_dir,
        results_dir=settings.results_dir,
    )

    ensure_local_roots_mountable(authoritative, for_writing=False)
    local_inventory = scan_local_tree(authoritative)
    remote_by_prefix = session.list_objects(snapshot_commit).objects_by_prefix

    # The snapshot is authoritative: pull what differs and remove local files
    # the snapshot does not contain, so the tree matches the commit exactly.
    plan = _plan_merged(local_inventory, remote_by_prefix, keep_local_deletions=True)
    if keep_deleted:
        plan.deletions = []

    outcome = CheckoutOutcome(
        lakefs_commit=snapshot_commit,
        git_ref=git_ref,
        download_plan=plan,
        dry_run=dry_run,
    )
    if dry_run:
        return outcome

    progress = _progress_printer(quiet)
    for remote_path in plan.transfers:
        content_root = _content_root_for_path(authoritative, remote_path)
        local_file = content_root.local_path_for(remote_path)
        progress(f"download  {remote_path}")
        session.download_file(snapshot_commit, remote_path, local_file)
    for remote_path in plan.deletions:
        content_root = _content_root_for_path(authoritative, remote_path)
        local_file = content_root.local_path_for(remote_path)
        progress(f"delete    {remote_path}")
        local_file.unlink(missing_ok=True)
    return outcome


# --------------------------------------------------------------------------- #
# Flow: status
# --------------------------------------------------------------------------- #


@dataclass
class StatusReport:
    """Everything :func:`build_status` learned, for the CLI to render."""

    git_head: str | None
    git_branch: str
    pointer_at_ref: DataPointer | None
    pointer_error: str | None
    pointer_on_disk: DataPointer | None
    endpoint: str
    repository: str
    branch: str
    remote_reachable: bool
    remote_error: str | None
    branch_head: str | None
    commit_plan: TransferPlan | None
    checkout_plan: TransferPlan | None
    checkout_lakefs_commit: str | None


def build_status(
    settings: Settings, session: LakeFSSession, git_ref: str = "HEAD"
) -> StatusReport:
    """Collect drift between the git history, the pointer and the lakeFS branch.

    A reachable server is optional: everything that needs it degrades to
    ``None`` and its absence is reported through :attr:`remote_error`.  A
    missing pointer is reported through :attr:`pointer_error` without
    hiding the remote state.

    :param settings: resolved settings.
    :param session: lakeFS session (connection is attempted lazily).
    :param git_ref: git ref to read the pointer from (default HEAD).
    :return: a :class:`StatusReport`.
    """
    local_inventory = scan_local_tree(settings)
    report = StatusReport(
        git_head=head_commit(settings.repo_root),
        git_branch=current_branch(settings.repo_root),
        pointer_at_ref=None,
        pointer_error=None,
        pointer_on_disk=read_pointer_file(settings.pointer_path),
        endpoint=settings.endpoint,
        repository=settings.repository,
        branch=settings.branch,
        remote_reachable=False,
        remote_error=None,
        branch_head=None,
        commit_plan=None,
        checkout_plan=None,
        checkout_lakefs_commit=None,
    )
    try:
        report.pointer_at_ref = read_pointer_at_ref(settings, git_ref)
    except PointerError as error:
        report.pointer_error = str(error)

    try:
        branch = session.branch(session.repository())
        branch_head = branch.head.id
        working_by_prefix = session.list_objects(session.settings.branch).objects_by_prefix
    except Exception as error:  # noqa: BLE001  (any failure degrades status)
        report.remote_error = f"lakeFS at {settings.endpoint}: {error}"
        return report
    report.remote_reachable = True
    report.branch_head = branch_head

    # Commit direction: local tree against the branch's working state.
    report.commit_plan = _plan_merged(
        local_inventory, working_by_prefix, keep_local_deletions=False
    )
    # Checkout direction: local tree against the snapshot pinned by the
    # pointer at the requested ref (not the branch head).
    pointer = report.pointer_at_ref
    if pointer is not None and pointer.commit:
        try:
            snapshot_by_prefix = session.list_objects(pointer.commit).objects_by_prefix
            report.checkout_plan = _plan_merged(
                local_inventory, snapshot_by_prefix, keep_local_deletions=True
            )
            report.checkout_lakefs_commit = pointer.commit
        except Exception as error:  # noqa: BLE001
            report.remote_error = f"snapshot {pointer.commit}: {error}"
    return report
