# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Live integration tests against a real lakeFS server.

These tests are skipped unless a server is provided via environment
variables::

    export HYPERCAM_LAKEFS_ENDPOINT=http://localhost:8000
    export HYPERCAM_LAKEFS_ACCESS_KEY_ID=<access key>
    export HYPERCAM_LAKEFS_SECRET_ACCESS_KEY=<secret key>
    export HYPERCAM_LAKEFS_REPOSITORY=hypercam-data-tests   # optional

They then exercise the full alignment story on a throwaway git checkout and
fixture data: commit -> pointer -> git commit with trailer -> clone ->
checkout at HEAD and at a historical ref, verifying the data trees land
byte-identical.  See the README's "Data version control" section for how to
start a suitable server (``lakefs run`` with a local block store is enough).

Note on change detection: file identity is decided by size + modification
time in whole seconds (what lakeFS records per object).  The fixtures
therefore shift file mtimes explicitly, mirroring how real recordings are
written minutes apart; rewrites inside the same second as a previous sync
are not detected — the same trade-off git's own index makes.
"""

import os
import subprocess
from pathlib import Path

import pytest

from hypercam.data_versioning.config import POINTER_RELATIVE_PATH, load_settings
from hypercam.data_versioning.git_ops import read_file_at_ref
from hypercam.data_versioning.pointer import read_pointer_file
from hypercam.data_versioning.remote import LakeFSSession
from hypercam.data_versioning.sync import checkout_data, commit_data

_ENDPOINT = os.environ.get("HYPERCAM_LAKEFS_ENDPOINT")
_ACCESS_KEY = os.environ.get("HYPERCAM_LAKEFS_ACCESS_KEY_ID")
_SECRET_KEY = os.environ.get("HYPERCAM_LAKEFS_SECRET_ACCESS_KEY")
_REPOSITORY = os.environ.get("HYPERCAM_LAKEFS_REPOSITORY", "hypercam-data-tests")
_STORAGE_NAMESPACE = os.environ.get(
    "HYPERCAM_LAKEFS_TEST_STORAGE_NAMESPACE", "local:///tmp/kilo/lakefs-test-blocks"
)

pytestmark = pytest.mark.skipif(
    not (_ENDPOINT and _ACCESS_KEY and _SECRET_KEY),
    reason="set HYPERCAM_LAKEFS_ENDPOINT/_ACCESS_KEY_ID/_SECRET_ACCESS_KEY to run live tests",
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command in *repo* and return stdout."""
    completed = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def _fresh_mtime(path: Path, seconds: int) -> None:
    """Set an unmistakably distinct mtime so the size+seconds comparison sees the change."""
    os.utime(path, times=(seconds, seconds))


@pytest.fixture()
def producer_checkout(tmp_path: Path, monkeypatch, request) -> Path:
    """A git checkout with fixture data, configured against the live server.

    The checkout starts with one code commit (any real repository has one),
    which keeps ``HEAD~1`` meaningful once the aligned data commits arrive.
    A unique per-run lakeFS repository is used and deleted afterwards, so
    reruns never trip over snapshots left by earlier (failed) executions.
    """
    repo = tmp_path / "producer"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "data" / "raw").mkdir(parents=True)
    (repo / "data" / "cad_models").mkdir(parents=True)
    (repo / "results" / "spectral_correlation").mkdir(parents=True)
    recording = repo / "data" / "raw" / "spectral_425.raw"
    recording.write_bytes(b"recording-v1")
    matrix = repo / "results" / "spectral_correlation" / "matrix.npy"
    matrix.write_bytes(b"matrix-v1")
    readme = repo / "results" / "README.md"
    readme.write_text("results\n")
    _fresh_mtime(recording, 1_000_000)
    _fresh_mtime(matrix, 1_000_001)

    _git(repo, "add", "results/README.md")
    _git(repo, "commit", "-q", "-m", "bootstrap code")

    # lakeFS repository names are lowercase [a-z0-9-] only (3..63 chars).
    safe_node = request.node.name.replace("_", "-").replace("[", "").replace("]", "")[:20]
    repository_name = f"hypercam-data-tests-{os.getpid()}-{safe_node}".lower()
    # The storage namespace must be unique per repository as well; nesting
    # under the shared base keeps the block store tidy.
    storage_namespace = f"{_STORAGE_NAMESPACE.rstrip('/')}/{repository_name}"
    monkeypatch.setenv("HYPERCAM_LAKEFS_ENDPOINT", _ENDPOINT)
    monkeypatch.setenv("HYPERCAM_LAKEFS_ACCESS_KEY_ID", _ACCESS_KEY)
    monkeypatch.setenv("HYPERCAM_LAKEFS_SECRET_ACCESS_KEY", _SECRET_KEY)
    monkeypatch.setenv("HYPERCAM_LAKEFS_REPOSITORY", repository_name)

    settings = load_settings(repo)
    session = LakeFSSession(settings)
    session.ensure_repository(storage_namespace)

    yield repo

    try:
        session.repository().delete()
    except Exception:  # noqa: BLE001  (teardown must never mask the test result)
        pass


def test_commit_pointer_and_checkout_round_trip(producer_checkout: Path):
    """The full alignment loop: commit, clone, checkout, historical checkout."""
    producer = producer_checkout

    # --- data commit #1: stage the pointer, commit the git side --------- #
    settings = load_settings(producer)
    session = LakeFSSession(settings)
    outcome = commit_data(settings, session, message="first snapshot", make_git_commit=True)
    assert outcome.lakefs_commit is not None

    pointer = read_pointer_file(settings.pointer_path)
    assert pointer is not None and pointer.commit == outcome.lakefs_commit

    # The pointer must carry into the git history.
    staged = _git(producer, "show", f":{POINTER_RELATIVE_PATH}")
    assert outcome.lakefs_commit in staged
    trailer = _git(producer, "log", "-1", "--format=%B")
    assert f"Data-lakefs-commit: {outcome.lakefs_commit}" in trailer
    first_git_sha = _git(producer, "rev-parse", "HEAD").strip()

    # --- data change + second aligned git commit ------------------------ #
    second_recording = producer / "data" / "raw" / "spectral_500.raw"
    second_recording.write_bytes(b"recording-two")
    matrix = producer / "results" / "spectral_correlation" / "matrix.npy"
    matrix.write_bytes(b"matrix-v2")
    _fresh_mtime(second_recording, 2_000_000)
    _fresh_mtime(matrix, 2_000_001)

    outcome2 = commit_data(
        load_settings(producer),
        LakeFSSession(load_settings(producer)),
        message="second snapshot",
        make_git_commit=True,
    )
    assert outcome2.lakefs_commit != outcome.lakefs_commit
    trailer = _git(producer, "log", "-1", "--format=%B")
    assert f"Data-lakefs-commit: {outcome2.lakefs_commit}" in trailer

    # The FIRST git commit still points at the first lakeFS snapshot.
    assert outcome.lakefs_commit in read_file_at_ref(
        producer, first_git_sha, POINTER_RELATIVE_PATH
    )

    # --- collaborator machine: clone + checkout ------------------------- #
    consumer = producer.parent / "consumer"
    _git(producer.parent, "clone", "-q", str(producer), str(consumer))

    consumer_settings = load_settings(consumer)
    checkout_data(consumer_settings, LakeFSSession(consumer_settings))
    assert (consumer / "data" / "raw" / "spectral_425.raw").read_bytes() == b"recording-v1"
    assert (consumer / "data" / "raw" / "spectral_500.raw").read_bytes() == b"recording-two"
    assert (consumer / "results" / "spectral_correlation" / "matrix.npy").read_bytes() == b"matrix-v2"

    # --- historical checkout: data as of the FIRST git commit ----------- #
    checkout_data(
        consumer_settings, LakeFSSession(consumer_settings), git_ref=first_git_sha
    )
    assert (consumer / "data" / "raw" / "spectral_425.raw").read_bytes() == b"recording-v1"
    assert not (consumer / "data" / "raw" / "spectral_500.raw").exists()
    assert (consumer / "results" / "spectral_correlation" / "matrix.npy").read_bytes() == b"matrix-v1"


def test_commit_is_idempotent_when_nothing_changed(producer_checkout: Path):
    """A second commit with no data changes must not create a new snapshot."""
    producer = producer_checkout
    settings = load_settings(producer)
    session = LakeFSSession(settings)
    first = commit_data(settings, session, message="snapshot")
    second = commit_data(load_settings(producer), LakeFSSession(load_settings(producer)))
    assert second.lakefs_commit == first.lakefs_commit
    assert second.upload_plan.is_empty
