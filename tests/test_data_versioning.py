# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-10
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Unit tests for the data <-> git alignment machinery.

These tests run without a lakeFS server: the pointer round-trip, the local
inventory scanner, the transfer planner, the upload transport fallback
chain, settings resolution and the git helpers are all exercised against
temporary directories, throwaway git repositories and stand-in clients.
Live-server coverage lives in ``test_data_versioning_integration.py``.
"""

import hashlib
import json
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from lakefs_sdk.exceptions import ApiException as SdkApiException
from lakefs_sdk.models.staging_location import StagingLocation

from hypercam.data_versioning.config import Settings, load_settings
from hypercam.data_versioning.errors import (
    ConfigurationError,
    GitError,
    PointerError,
    RemoteError,
)
from hypercam.data_versioning.git_ops import (
    create_commit,
    head_commit,
    read_file_at_ref,
    repository_root,
)
from hypercam.data_versioning.pointer import (
    DataPointer,
    fresh_pointer,
    parse_pointer,
    read_pointer_file,
    render_pointer,
    with_commit,
    write_pointer_file,
)
from hypercam.data_versioning.remote import LakeFSSession, RemoteStamp
from hypercam.data_versioning.sync import (
    FileStamp,
    ensure_local_roots_mountable,
    plan_transfer,
    scan_local_tree,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> str:
    """Run a git command in *repo* and return stdout."""
    completed = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repository with a configured identity."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    return tmp_path


def _settings_for(repo: Path, **overrides) -> Settings:
    """Build fully-resolved settings pointing at a temporary checkout."""
    values = dict(
        endpoint="http://localhost:8000",
        access_key_id="KEY",
        secret_access_key="SECRET",
        repository="hypercam-data",
        branch="main",
        repo_root=repo,
        data_dir=repo / "data",
        results_dir=repo / "results",
    )
    values.update(overrides)
    return Settings(**values)


# --------------------------------------------------------------------------- #
# Pointer file
# --------------------------------------------------------------------------- #


def test_pointer_round_trip_preserves_all_fields():
    pointer = DataPointer(
        repository="hypercam-data",
        branch="main",
        commit="a" * 64,
        parent_git_commit="9703eaf0a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
        recorded_at="2026-10-08T21:00:00Z",
    )
    parsed = parse_pointer(render_pointer(pointer))
    assert parsed == pointer
    assert parsed.is_recorded


def test_pointer_parses_placeholder_commit_as_unrecorded():
    text = (
        "# comment line\n"
        "repository: hypercam-data\n"
        "branch: main\n"
        "commit: none\n"
        "parent-git-commit: none\n"
        "recorded-at: none\n"
    )
    pointer = parse_pointer(text)
    assert pointer.commit is None
    assert not pointer.is_recorded


def test_pointer_rejects_duplicate_keys_and_malformed_lines():
    with pytest.raises(PointerError, match="more than once"):
        parse_pointer("repository: a\nrepository: b\nbranch: main\n")
    with pytest.raises(PointerError, match="key: value"):
        parse_pointer("repository: a\nbranch: main\njust-a-word\n")


def test_pointer_rejects_missing_required_keys():
    with pytest.raises(PointerError, match="required"):
        parse_pointer("# only a comment\n")


def test_pointer_file_round_trip_through_disk(tmp_path: Path):
    path = tmp_path / "data" / ".lakefs-commit"
    path.parent.mkdir()
    pointer = with_commit(fresh_pointer("hypercam-data", "main", None), "b" * 64)
    write_pointer_file(path, pointer)
    assert read_pointer_file(path) == pointer


def test_read_pointer_file_returns_none_when_absent(tmp_path: Path):
    assert read_pointer_file(tmp_path / "missing") is None


# --------------------------------------------------------------------------- #
# Git helpers
# --------------------------------------------------------------------------- #


def test_head_commit_is_none_before_first_commit(git_repo: Path):
    assert head_commit(git_repo) is None
    (git_repo / "file.txt").write_text("hello")
    _git(git_repo, "add", "file.txt")
    create_commit(git_repo, ["first"])
    assert head_commit(git_repo) is not None


def test_read_file_at_ref_returns_current_and_historical_content(git_repo: Path):
    tracked = git_repo / "pointer"
    tracked.write_text("version: 1\n")
    _git(git_repo, "add", "pointer")
    create_commit(git_repo, ["first"])
    first_sha = head_commit(git_repo)
    tracked.write_text("version: 2\n")
    _git(git_repo, "add", "pointer")
    create_commit(git_repo, ["second"])

    assert read_file_at_ref(git_repo, "HEAD", "pointer") == "version: 2\n"
    assert read_file_at_ref(git_repo, first_sha, "pointer") == "version: 1\n"


def test_read_file_at_ref_returns_none_for_missing_file(git_repo: Path):
    (git_repo / "file.txt").write_text("x")
    _git(git_repo, "add", "file.txt")
    create_commit(git_repo, ["first"])
    assert read_file_at_ref(git_repo, "HEAD", "no-such-file") is None


def test_read_file_at_ref_raises_for_bad_ref(git_repo: Path):
    with pytest.raises(GitError):
        read_file_at_ref(git_repo, "ffffffffffffffffffffffffffffffffffffffff", "pointer")


def test_repository_root_finds_parent(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    nested = tmp_path / "deep" / "inside"
    nested.mkdir(parents=True)
    assert repository_root(nested) == tmp_path.resolve()


# --------------------------------------------------------------------------- #
# Settings resolution
# --------------------------------------------------------------------------- #


def test_load_settings_prefers_environment_over_defaults(git_repo: Path, monkeypatch):
    monkeypatch.setenv("HYPERCAM_LAKEFS_ENDPOINT", "http://override:9000")
    monkeypatch.setenv("HYPERCAM_LAKEFS_ACCESS_KEY_ID", "env-key")
    monkeypatch.setenv("HYPERCAM_LAKEFS_SECRET_ACCESS_KEY", "env-secret")
    monkeypatch.setenv("HYPERCAM_LAKEFS_REPOSITORY", "other-data")
    monkeypatch.setenv("HYPERCAM_LAKEFS_BRANCH", "staging")
    settings = load_settings(git_repo)
    assert settings.endpoint == "http://override:9000"
    assert settings.access_key_id == "env-key"
    assert settings.secret_access_key == "env-secret"
    assert settings.repository == "other-data"
    assert settings.branch == "staging"
    assert settings.pointer_path == git_repo / "data" / ".lakefs-commit"


def test_load_settings_reads_lakectl_yaml(git_repo: Path, monkeypatch, tmp_path: Path):
    lakectl = tmp_path / "lakectl.yaml"
    lakectl.write_text(
        "server:\n"
        "  endpoint_url: http://from-yaml:8000\n"
        "credentials:\n"
        "  access_key_id: yaml-key\n"
        "  secret_access_key: yaml-secret\n"
    )
    monkeypatch.setenv("LAKECTL_CONFIG_FILE", str(lakectl))
    for name in (
        "HYPERCAM_LAKEFS_ENDPOINT",
        "LAKECTL_SERVER_ENDPOINT_URL",
        "HYPERCAM_LAKEFS_ACCESS_KEY_ID",
        "LAKECTL_CREDENTIALS_ACCESS_KEY_ID",
        "HYPERCAM_LAKEFS_SECRET_ACCESS_KEY",
        "LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings(git_repo)
    assert settings.endpoint == "http://from-yaml:8000"
    assert settings.access_key_id == "yaml-key"
    assert settings.secret_access_key == "yaml-secret"


def test_load_settings_fails_without_any_credentials(git_repo: Path, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LAKECTL_CONFIG_FILE", str(tmp_path / "absent.yaml"))
    for name in (
        "HYPERCAM_LAKEFS_ENDPOINT",
        "LAKECTL_SERVER_ENDPOINT_URL",
        "HYPERCAM_LAKEFS_ACCESS_KEY_ID",
        "LAKECTL_CREDENTIALS_ACCESS_KEY_ID",
        "HYPERCAM_LAKEFS_SECRET_ACCESS_KEY",
        "LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY",
        "HYPERCAM_DATA_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError, match="lakectl config"):
        load_settings(git_repo)


def test_content_roots_map_results_from_repo_root(git_repo: Path):
    settings = _settings_for(git_repo, data_dir=git_repo / "elsewhere")
    local_paths = {root.local_path for root in settings.content_roots}
    assert git_repo / "elsewhere" / "raw" in local_paths
    assert git_repo / "elsewhere" / "cad_models" in local_paths
    assert git_repo / "results" in local_paths


# --------------------------------------------------------------------------- #
# Local inventory
# --------------------------------------------------------------------------- #


def test_scan_local_tree_maps_files_and_skips_archive(tmp_path: Path):
    repo = tmp_path
    (repo / "data" / "raw" / "evt3_raw").mkdir(parents=True)
    (repo / "data" / "cad_models").mkdir(parents=True)
    (repo / "results" / "archive").mkdir(parents=True)
    (repo / "results" / "spectral_correlation").mkdir(parents=True)
    recording = repo / "data" / "raw" / "evt3_raw" / "spectral_425.raw"
    recording.write_bytes(b"0123456789")
    model = repo / "data" / "cad_models" / "wheel.step"
    model.write_bytes(b"model")
    live = repo / "results" / "spectral_correlation" / "matrix.npy"
    live.write_bytes(b"results")
    archived = repo / "results" / "archive" / "old.npy"
    archived.write_bytes(b"superseded")

    settings = _settings_for(repo)
    inventory = scan_local_tree(settings)

    stamp = FileStamp(size_bytes=10, mtime=int(recording.stat().st_mtime))
    assert inventory["raw/evt3_raw/spectral_425.raw"] == stamp
    assert "cad_models/wheel.step" in inventory
    assert "results/spectral_correlation/matrix.npy" in inventory
    assert "results/archive/old.npy" not in inventory


def test_scan_local_tree_ignores_symlinked_files(tmp_path: Path):
    repo = tmp_path
    (repo / "data" / "raw").mkdir(parents=True)
    target = tmp_path / "outside.txt"
    target.write_text("external")
    (repo / "data" / "raw" / "linked.txt").symlink_to(target)
    settings = _settings_for(repo)
    assert scan_local_tree(settings) == {}


def test_ensure_local_roots_rejects_symlink_mount(tmp_path: Path):
    repo = tmp_path
    (repo / "real_raw").mkdir()
    (repo / "data").mkdir()
    (repo / "data" / "raw").symlink_to(repo / "real_raw")
    settings = _settings_for(repo)
    with pytest.raises(Exception, match="data_image_mount"):
        ensure_local_roots_mountable(settings, for_writing=True)


def test_ensure_local_roots_rejects_missing_roots_when_writing(tmp_path: Path):
    repo = tmp_path
    settings = _settings_for(repo)
    with pytest.raises(Exception, match="does not hold the experiment data"):
        ensure_local_roots_mountable(settings, for_writing=True)


def test_ensure_local_roots_allows_missing_roots_for_reading(tmp_path: Path):
    repo = tmp_path
    settings = _settings_for(repo)
    ensure_local_roots_mountable(settings, for_writing=False)


# --------------------------------------------------------------------------- #
# Transfer planning
# --------------------------------------------------------------------------- #


def _remote(size: int, mtime: int | None) -> RemoteStamp:
    return RemoteStamp(size_bytes=size, mtime=mtime)


def test_plan_transfer_detects_new_changed_unchanged_and_deleted():
    local = {
        "raw/new.raw": FileStamp(10, 100),
        "raw/changed.raw": FileStamp(20, 200),
        "raw/same.raw": FileStamp(30, 300),
    }
    remote = {
        "raw/changed.raw": _remote(10, 200),  # size differs -> changed
        "raw/same.raw": _remote(30, 300),  # identical -> untouched
        "raw/gone.raw": _remote(40, 400),  # absent locally -> prune remotely
    }
    uploads, downloads = plan_transfer(local, remote)
    assert uploads.transfers == ["raw/changed.raw", "raw/new.raw"]
    assert uploads.deletions == ["raw/gone.raw"]
    assert uploads.unchanged == 1
    assert downloads.transfers == ["raw/changed.raw", "raw/gone.raw"]
    assert downloads.deletions == ["raw/new.raw"]


def test_plan_transfer_treats_unknown_remote_mtime_as_changed():
    local = {"raw/a.raw": FileStamp(10, 100)}
    remote = {"raw/a.raw": _remote(10, None)}
    uploads, downloads = plan_transfer(local, remote)
    assert uploads.transfers == ["raw/a.raw"]
    assert downloads.transfers == ["raw/a.raw"]
    assert uploads.unchanged == 0


def test_plan_transfer_is_symmetric_for_empty_sides():
    uploads, downloads = plan_transfer({}, {})
    assert uploads.is_empty and downloads.is_empty
    uploads, downloads = plan_transfer(
        {"raw/only.raw": FileStamp(1, 1)}, {"raw/only.raw": _remote(1, 1)}
    )
    assert uploads.is_empty and downloads.is_empty


# --------------------------------------------------------------------------- #
# Upload transports (presigned -> staging copy -> upload API)
# --------------------------------------------------------------------------- #


class _FakeRestResponse:
    """Minimal stand-in for a urllib3 ``HTTPResponse``."""

    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self.data = payload


class _FakePoolManager:
    """Records every raw request, replaying a canned response or error."""

    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.requests: list[dict] = []

    def request(self, method, url, body=None, headers=None):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "body": body.read() if body is not None else None,
                "headers": dict(headers),
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class _FakeStagingApi:
    """Staging endpoints whose presign requests are always refused.

    Real deployments hit this with block stores that cannot serve presigned
    URLs (or with presign disabled): the ``get_physical_address(presign=True)``
    call fails and the caller degrades to the plain staging address.
    """

    def __init__(self, plain_physical_address: str) -> None:
        self.plain_physical_address = plain_physical_address
        self.linked_metadata = None

    def get_physical_address(self, repo_id, branch_id, path, presign):
        if presign:
            raise SdkApiException(status=400, reason="presign not supported")
        # A real StagingLocation model, because upload_file feeds it back
        # into the StagingMetadata it links afterwards.
        return StagingLocation(
            physical_address=self.plain_physical_address, presigned_url=None
        )

    def link_physical_address(self, repo_id, branch_id, path, staging_metadata):
        self.linked_metadata = staging_metadata
        return SimpleNamespace(size_bytes=staging_metadata.size_bytes)


def _fake_session(tmp_path: Path, plain_physical_address: str, pool_manager) -> LakeFSSession:
    """A :class:`LakeFSSession` wired to stand-in lakeFS clients.

    The session's lazy client slot is filled with a ``SimpleNamespace`` twin
    of the real ``lakefs.Client`` exposing exactly the attributes the upload
    transports touch: ``config.host``, ``sdk_client.staging_api`` and the
    raw ``pool_manager`` behind ``sdk_client.objects_api.api_client``.
    """
    staging_api = _FakeStagingApi(plain_physical_address)
    api_client = SimpleNamespace(
        update_params_for_auth=lambda *args, **kwargs: None,
        rest_client=SimpleNamespace(pool_manager=pool_manager),
    )
    fake_client = SimpleNamespace(
        config=SimpleNamespace(host="http://localhost:8000"),
        sdk_client=SimpleNamespace(
            staging_api=staging_api,
            objects_api=SimpleNamespace(api_client=api_client),
        ),
    )
    session = LakeFSSession(_settings_for(tmp_path))
    session._client = fake_client
    return session


def _fake_branch() -> SimpleNamespace:
    return SimpleNamespace(repo_id="hypercam-data", id="main")


def _upload_api_response(size: int, mtime: int) -> _FakeRestResponse:
    """A success body in the shape of the lakeFS ``ObjectStats`` schema."""
    payload = {
        "path": "raw/file.raw",
        "path_type": "object",
        "physical_address": "s3://blocks/hypercam-data/objects",
        "checksum": "server-computed",
        "mtime": mtime,
        "size_bytes": size,
    }
    return _FakeRestResponse(200, json.dumps(payload).encode())


def test_upload_falls_back_to_lakefs_upload_api_when_staging_unreachable(tmp_path: Path):
    """A remote (non-file://) staging address degrades to the upload API."""
    local_file = tmp_path / "file.raw"
    local_file.write_bytes(b"recording-bytes")  # 15 bytes
    pool = _FakePoolManager(response=_upload_api_response(15, 4_242))
    session = _fake_session(tmp_path, "s3://blocks/hypercam-data/unreachable", pool)

    session.upload_file(_fake_branch(), local_file, "raw/file.raw")

    # The bytes travelled as the raw body of the upload API endpoint.
    assert len(pool.requests) == 1
    request = pool.requests[0]
    assert request["method"] == "POST"
    assert request["url"] == (
        "http://localhost:8000/repositories/hypercam-data/branches/main/objects"
        "?path=raw%2Ffile.raw"
    )
    assert request["body"] == b"recording-bytes"
    assert request["headers"]["Content-Length"] == "15"
    # The upload API created the object in one step: no staging link happened.
    assert session._client.sdk_client.staging_api.linked_metadata is None
    # The local mtime was aligned to the server's stamp, so the next run's
    # size+mtime comparison sees the file as unchanged.
    assert int(local_file.stat().st_mtime) == 4_242


def test_upload_falls_back_to_lakefs_upload_api_when_staging_copy_fails(tmp_path: Path):
    """A file:// staging address that cannot be written degrades too."""
    local_file = tmp_path / "file.raw"
    local_file.write_bytes(b"recording-bytes")
    # The staging parent exists but is a regular file, so creating the
    # destination directory fails with an OSError.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file, not a directory")
    pool = _FakePoolManager(response=_upload_api_response(15, 9_999))
    session = _fake_session(tmp_path, f"file://{blocker / 'child.bin'}", pool)

    session.upload_file(_fake_branch(), local_file, "raw/file.raw")

    assert len(pool.requests) == 1
    assert pool.requests[0]["body"] == b"recording-bytes"
    assert int(local_file.stat().st_mtime) == 9_999


def test_upload_reports_every_transport_when_all_of_them_fail(tmp_path: Path):
    """When the upload API also fails, the diagnostic names both attempts."""
    local_file = tmp_path / "file.raw"
    local_file.write_bytes(b"recording-bytes")
    pool = _FakePoolManager(error=ConnectionRefusedError("server unreachable"))
    session = _fake_session(tmp_path, "s3://blocks/hypercam-data/unreachable", pool)

    with pytest.raises(RemoteError) as excinfo:
        session.upload_file(_fake_branch(), local_file, "raw/file.raw")
    message = str(excinfo.value)
    assert "staging transports" in message
    assert "server unreachable" in message


def test_upload_through_writable_staging_still_links_metadata(tmp_path: Path):
    """The staging copy path keeps recording mtime/checksum via the link."""
    local_file = tmp_path / "file.raw"
    local_file.write_bytes(b"staging-bytes")
    pool = _FakePoolManager()  # must never see a request
    session = _fake_session(tmp_path, f"local://{tmp_path / 'blocks' / 'obj'}", pool)

    session.upload_file(_fake_branch(), local_file, "raw/file.raw")

    linked = session._client.sdk_client.staging_api.linked_metadata
    assert linked is not None
    assert linked.size_bytes == len(b"staging-bytes")
    assert linked.mtime == int(local_file.stat().st_mtime)
    hasher = hashlib.md5()
    hasher.update(b"staging-bytes")
    assert linked.checksum == hasher.hexdigest()
    assert pool.requests == []


# --------------------------------------------------------------------------- #
# prepare-commit-msg hook
# --------------------------------------------------------------------------- #


HOOK_RELATIVE = Path("scripts/git/hooks/prepare-commit-msg")


def _repo_hooks_path(repo_root: Path) -> Path:
    return repo_root


def _run_hook(repo_root: Path, message_text: str, source: str = "") -> tuple[int, str]:
    """Run the real hook script against *message_text* inside a git repo.

    The hook is executed with the message file inside the repo (as git does)
    and with the repository as working directory.
    """
    hook_source = Path(__file__).resolve().parent.parent / HOOK_RELATIVE
    message_file = repo_root / ".git" / "COMMIT_EDITMSG_TEST"
    message_file.write_text(message_text)
    completed = subprocess.run(
        [str(hook_source), str(message_file), source],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, message_file.read_text()


def test_hook_appends_trailer_from_pointer_file(tmp_path: Path):
    repo = _repo_hooks_path(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / ".lakefs-commit").write_text(
        "repository: hypercam-data\nbranch: main\ncommit: " + "c" * 64 + "\n"
    )
    _git(tmp_path, "init", "-q")
    code, message = _run_hook(tmp_path, "Add a feature\n")
    assert code == 0
    assert f"Data-lakefs-commit: {'c' * 64}" in message


def test_hook_skips_when_pointer_is_placeholder(tmp_path: Path):
    repo = _repo_hooks_path(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / ".lakefs-commit").write_text(
        "repository: hypercam-data\nbranch: main\ncommit: none\n"
    )
    _git(tmp_path, "init", "-q")
    code, message = _run_hook(tmp_path, "Initial commit\n")
    assert code == 0
    assert "Data-lakefs-commit" not in message


def test_hook_does_not_duplicate_existing_trailer(tmp_path: Path):
    repo = _repo_hooks_path(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / ".lakefs-commit").write_text(
        "repository: hypercam-data\nbranch: main\ncommit: " + "d" * 64 + "\n"
    )
    _git(tmp_path, "init", "-q")
    original = "message\n\nData-lakefs-commit: " + "d" * 64 + "\n"
    code, message = _run_hook(tmp_path, original)
    assert code == 0
    assert message.count("Data-lakefs-commit:") == 1


def test_hook_skips_merge_commits(tmp_path: Path):
    repo = _repo_hooks_path(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / ".lakefs-commit").write_text(
        "repository: hypercam-data\nbranch: main\ncommit: " + "e" * 64 + "\n"
    )
    _git(tmp_path, "init", "-q")
    code, message = _run_hook(tmp_path, "Merge branch 'x'\n", source="merge")
    assert code == 0
    assert "Data-lakefs-commit" not in message


# --------------------------------------------------------------------------- #
# Guard: the shipped hook script must stay executable
# --------------------------------------------------------------------------- #


def test_hook_script_is_executable():
    hook_path = Path(__file__).resolve().parent.parent / HOOK_RELATIVE
    mode = stat.S_IMODE(hook_path.stat().st_mode)
    assert mode & stat.S_IXUSR, "prepare-commit-msg must keep its executable bit"


# Import smoke test: the CLI module must wire every subcommand.
def test_cli_registers_all_subcommands():
    from hypercam.data_versioning.cli import data_main  # noqa: F401
    from hypercam.data_versioning.sync import CommitOutcome, CheckoutOutcome  # noqa: F401

    import argparse

    from hypercam.data_versioning import cli

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    cli._commit_parser(subparsers)
    cli._checkout_parser(subparsers)
    cli._status_parser(subparsers)
    parsed = parser.parse_args(["commit", "--dry-run"])
    assert parsed.handler is cli._run_commit
