# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-26
# Notice:        This file was authored or modified with the assistance of
#                Kilo (Qwen, qwen/qwen3.8-flash) and Kilo (GLM,
#                z-ai/glm-5.3-flash).
# ==============================================================================

"""Connection to the lakeFS server and the raw transfer primitives.

This module wraps the official ``lakefs`` Python client (itself a layer
over ``lakefs_sdk``) with the small set of operations the data-versioning
commands need:

- resolve/create the repository and branch,
- list every object under the synced prefixes at a given reference,
- upload a local file (two-phase presigned staging upload where possible,
  so the file's modification time and size travel with the object and make
  the cheap size+mtime change detection reliable; files above the multipart
  threshold travel as a presigned multipart upload so a single flaky
  connection can never strand a tens-of-gigabytes transfer; the transports
  degrade to a shared-filesystem staging copy and finally to the upload API
  itself when the block store cannot serve presigned URLs),
- download an object in bounded chunks to a temporary file and atomically
  move it into place with the remote modification time restored,
- batch-delete objects and create commits with metadata.

All network errors are converted into :class:`RemoteError` with the server's
message attached, so the CLI can print one actionable diagnostic.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import strftime

import urllib3.exceptions

import lakefs
import lakefs_sdk
from lakefs.branch import Branch
from lakefs.client import Client
from lakefs.exceptions import LakeFSException, NotFoundException
from lakefs.models import ObjectInfo
from lakefs.repository import Repository
from lakefs_sdk.exceptions import ApiException as SdkApiException

from hypercam.data_versioning.config import Settings
from hypercam.data_versioning.errors import RemoteError

#: Every error the lakeFS layers can raise around a network call.  The
#: high-level package wraps API errors into ``LakeFSException`` subclasses,
#: but calls made through ``sdk_client`` directly raise the SDK's own
#: ``ApiException`` hierarchy — both must be caught (and converted into
#: :class:`RemoteError`) for consistent diagnostics.
LAKEFS_ERRORS = (LakeFSException, SdkApiException)

#: Bytes fetched per ranged request while downloading an object.  Bounded so
#: multi-hundred-megabyte recordings never have to fit in memory at once.
_DOWNLOAD_CHUNK_BYTES = 8 * 1024 * 1024

#: Files at least this large travel as a presigned *multipart* upload.  A
#: single PUT of a tens-of-gigabytes recording is one long-lived connection:
#: any middlebox or proxy that drops it (as the s3.rbaird.me hairpin did to
#: a 74 GB PUT) strands the whole transfer.  Split into parts, each part is
#: a short PUT that can be retried on its own.
_MULTIPART_THRESHOLD_BYTES = 256 * 1024 * 1024

#: Target part size for multipart uploads.  74.5 GB / 128 MiB is ~553 parts,
#: far below the S3 limit of 10,000 parts per upload.
_MULTIPART_PART_BYTES = 128 * 1024 * 1024

#: Attempts per part before giving up on the whole upload.
_MULTIPART_PART_ATTEMPTS = 3

#: Maximum number of object paths sent per batch-delete request.
_DELETE_BATCH_SIZE = 1000


@dataclass(frozen=True)
class RemoteStamp:
    """The subset of an object's stat that matters for change detection.

    :param size_bytes: object size; ``None`` if the server did not report it.
    :param mtime: object modification time as recorded at upload; ``None``
        means "unknown" and forces the object to be treated as changed, so a
        snapshot is never silently skipped.
    """

    size_bytes: int | None
    mtime: int | None


@dataclass(frozen=True)
class RemoteListing:
    """Every object of interest at a given reference, grouped by prefix."""

    objects_by_prefix: dict[str, dict[str, RemoteStamp]]

    def all_paths(self) -> set[str]:
        """Union of object names across every synced prefix."""
        return {path for objects in self.objects_by_prefix.values() for path in objects}


class LakeFSSession:
    """A lazily-connected session against one lakeFS repository/branch pair.

    The connection is established on first use, so commands that never touch
    the server (e.g. reporting an unrecorded pointer) work without one.

    :param settings: resolved endpoint, credentials, repository and branch.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Client | None = None

    # ------------------------------------------------------------------ #
    # Connection and repository management
    # ------------------------------------------------------------------ #

    @property
    def client(self) -> Client:
        """The configured lakeFS client, connected on first access.

        :raise RemoteError: when the server is unreachable, the endpoint is
            malformed or the credentials are rejected.
        """
        if self._client is None:
            try:
                self._client = lakefs.Client(
                    host=self.settings.endpoint,
                    username=self.settings.access_key_id,
                    password=self.settings.secret_access_key,
                )
                # Force one trivial request so connection problems surface
                # here, with context, instead of deep inside a later call.
                _ = self._client.version
            except LAKEFS_ERRORS as error:
                raise RemoteError(
                    f"lakeFS at {self.settings.endpoint} rejected the request: {error}"
                ) from error
            except Exception as error:
                raise RemoteError(
                    f"cannot reach lakeFS at {self.settings.endpoint}: {error}\n"
                    "Is the server running? Start one with `lakefs run` (or the "
                    "project's docker compose) and retry."
                ) from error
        return self._client

    def repository(self) -> Repository:
        """Return the configured repository.

        :raise RemoteError: when the repository does not exist, with a hint
            to create it via ``hypercam-data-commit --create``.
        """
        repository = lakefs.Repository(self.settings.repository, client=self.client)
        try:
            _ = repository.properties
        except LAKEFS_ERRORS as error:
            raise RemoteError(
                f"lakeFS repository {self.settings.repository!r} is missing "
                f"({error}); create it with `hypercam-data-commit --create "
                "--storage-namespace <namespace>`."
            ) from error
        return repository

    def ensure_repository(self, storage_namespace: str) -> Repository:
        """Return the repository, creating it if it does not exist yet.

        :param storage_namespace: physical namespace for a new repository
            (e.g. ``s3://bucket/hypercam-data`` or ``local://path``).
        :raise RemoteError: when creation fails for a reason other than the
            repository already existing.
        """
        repository = lakefs.Repository(self.settings.repository, client=self.client)
        try:
            return repository.create(
                storage_namespace=storage_namespace,
                default_branch=self.settings.branch,
                exist_ok=True,
            )
        except LAKEFS_ERRORS as error:
            raise RemoteError(
                f"cannot create lakeFS repository {self.settings.repository!r} "
                f"in namespace {storage_namespace!r}: {error}"
            ) from error

    def branch(self, repository: Repository) -> Branch:
        """Return the configured branch of *repository*, ensuring it exists."""
        branch = repository.branch(self.settings.branch)
        try:
            _ = branch.head
        except NotFoundException as error:
            raise RemoteError(
                f"branch {self.settings.branch!r} does not exist in repository "
                f"{self.settings.repository!r}; create it first (lakectl branch "
                f"create) or commit to the default branch."
            ) from error
        except LAKEFS_ERRORS as error:
            raise RemoteError(
                f"cannot inspect branch {self.settings.branch!r}: {error}"
            ) from error
        return branch

    def reference(self, reference_id: str):
        """Return a :class:`~lakefs.reference.Reference` for a commit/branch/tag id."""
        return self.repository().ref(reference_id)

    # ------------------------------------------------------------------ #
    # Listing
    # ------------------------------------------------------------------ #

    def list_objects(self, reference_id: str) -> RemoteListing:
        """List all objects under the synced prefixes at *reference_id*.

        :param reference_id: branch name, commit hash or tag.
        :return: mapping of remote prefix to that prefix's objects.
        """
        listing: dict[str, dict[str, RemoteStamp]] = {}
        reference = self.reference(reference_id)
        for remote_prefix in self.settings.remote_prefixes():
            objects: dict[str, RemoteStamp] = {}
            for info in reference.objects(prefix=remote_prefix):
                # Without a delimiter only real objects come back, but stay
                # defensive: CommonPrefix entries carry no size and are skipped.
                if not isinstance(info, ObjectInfo):
                    continue
                objects[info.path] = RemoteStamp(
                    size_bytes=info.size_bytes,
                    mtime=info.mtime,
                )
            listing[remote_prefix] = objects
        return RemoteListing(objects_by_prefix=listing)

    # ------------------------------------------------------------------ #
    # Transfers
    # ------------------------------------------------------------------ #

    def upload_file(self, branch: Branch, local_path: Path, remote_path: str) -> None:
        """Upload *local_path* to *remote_path* on *branch*.

        The upload records the file's modification time and an MD5 checksum,
        which is what makes the cheap size+mtime change detection exact (and
        repeat runs converge to a no-op).  Three transports cover the block
        stores and network topologies lakeFS is deployed with, tried in
        order until one works:

        - presigned PUT (S3/GCS/Azure): bytes go straight to storage; files
          of :data:`_MULTIPART_THRESHOLD_BYTES` or larger travel instead as a
          presigned *multipart* upload, one short retryable PUT per part;
        - shared-filesystem staging (local block store): the server hands
          out a ``local://`` physical address the client can write directly;
        - the upload API itself: the server pulls the bytes from the request
          body, for deployments where neither presigned URLs are served nor
          the staging area is reachable from this machine.

        The last transport cannot carry staging metadata, so the server
        stamps the object with its own clock; the local file's mtime is then
        aligned to the object's (mirroring :meth:`download_file`) to keep
        repeated runs converged.

        :param branch: target branch.
        :param local_path: file to read.
        :param remote_path: destination object name.
        :raise RemoteError: on any transfer or link failure, when no
            transport is available, or when the stored size does not match
            the local file.
        """
        stat_result = local_path.stat()
        file_size = stat_result.st_size
        file_mtime = int(stat_result.st_mtime)
        sdk_client = self.client.sdk_client

        try:
            staging_location = sdk_client.staging_api.get_physical_address(
                branch.repo_id, branch.id, remote_path, True
            )
        except LAKEFS_ERRORS:
            # Some block stores (e.g. the local adapter) do not support
            # presigned URLs at all; fall back to the shared-filesystem path.
            staging_location = None

        if staging_location is not None and staging_location.presigned_url:
            if file_size >= _MULTIPART_THRESHOLD_BYTES:
                self._upload_via_presigned_multipart(
                    branch, staging_location, local_path, remote_path, file_size
                )
                return
            checksum = _transfer_to_presigned_url(
                self.client, staging_location.presigned_url, local_path, file_size
            )
        else:
            try:
                if staging_location is None:
                    try:
                        staging_location = sdk_client.staging_api.get_physical_address(
                            branch.repo_id, branch.id, remote_path, False
                        )
                    except LAKEFS_ERRORS as error:
                        raise RemoteError(
                            f"cannot obtain a staging address for {remote_path!r}: {error}"
                        ) from error
                checksum = _copy_to_local_staging_path(
                    staging_location.physical_address, local_path
                )
            except (RemoteError, OSError) as staging_error:
                # The storage serves neither presigned URLs nor a staging
                # area this machine can write to.  Last resort: hand the
                # bytes to the server through its own upload API, which
                # resolves the block store on the server's side.
                self._upload_via_server_api(
                    branch, local_path, remote_path, file_size, staging_error
                )
                return

        staging_metadata = lakefs_sdk.StagingMetadata(
            staging=staging_location,
            size_bytes=file_size,
            checksum=checksum,
            mtime=file_mtime,
            content_type=None,
            user_metadata=None,
        )
        try:
            object_stats = sdk_client.staging_api.link_physical_address(
                branch.repo_id,
                branch.id,
                remote_path,
                staging_metadata=staging_metadata,
            )
        except LAKEFS_ERRORS as error:
            raise RemoteError(
                f"cannot link staged object {remote_path!r}: {error}"
            ) from error
        stored_size = object_stats.size_bytes
        if stored_size is not None and stored_size != file_size:
            raise RemoteError(
                f"server stored {stored_size} bytes for {remote_path!r} but the "
                f"local file holds {file_size}; refusing to continue on a "
                "corrupted transfer."
            )

    def _upload_via_presigned_multipart(
        self,
        branch: Branch,
        staging_location: lakefs_sdk.StagingLocation,
        local_path: Path,
        remote_path: str,
        file_size: int,
    ) -> None:
        """Stream *local_path* to the block store as a presigned multipart upload.

        The transport for files of :data:`_MULTIPART_THRESHOLD_BYTES` and
        above.  lakeFS's experimental presign-multipart API hands out one
        short-lived presigned PUT per part (S3 multipart semantics): a
        connection that dies costs only the retry of its current part, not
        the whole transfer — which for a 74 GB recording is the difference
        between an upload and an afternoon of lost work.  Each part's ETag
        (an MD5 of the part bytes, as S3 computes it) is collected and
        handed to ``complete_presign_multipart_upload``, which assembles and
        links the object server-side.

        The complete payload carries no mtime field (unlike the single-PUT
        staging link), so the server stamps the object with its own clock;
        the local file's mtime is then aligned to the object's, exactly as
        :meth:`_upload_via_server_api` does, to keep repeated runs converged.

        :param branch: target branch.
        :param staging_location: the presigned staging address from
            :meth:`upload_file` (its physical address seeds the multipart
            session).
        :param local_path: file to read.
        :param remote_path: destination object name.
        :param file_size: size of *local_path*.
        :raise RemoteError: when initiation, a part, or completion fails, or
            when the stored size does not match the local file.
        """
        sdk_client = self.client.sdk_client
        try:
            initiation = sdk_client.experimental_api.create_presign_multipart_upload(
                branch.repo_id,
                branch.id,
                remote_path,
                math.ceil(file_size / _MULTIPART_PART_BYTES),
            )
        except LAKEFS_ERRORS as error:
            raise RemoteError(
                f"cannot start a multipart upload for {remote_path!r}: {error}"
            ) from error

        presigned_urls = initiation.presigned_urls or []
        if not presigned_urls:
            raise RemoteError(
                f"the server issued no presigned part URLs for {remote_path!r}"
            )
        # Part boundaries follow from the number of URLs the server chose to
        # issue; the request above only hints at the desired count.
        part_size = math.ceil(file_size / len(presigned_urls))
        pool_manager = (
            sdk_client.objects_api.api_client.rest_client.pool_manager
        )
        upload_parts: list[lakefs_sdk.UploadPart] = []
        print(
            f"beginning multipart upload ({len(presigned_urls)} parts of "
            f"~{part_size // (1024 * 1024)} MiB): "
            f"{strftime('%d-%H-%M')}"
        )
        try:
            with local_path.open("rb") as source:
                for part_number, part_url in enumerate(presigned_urls, start=1):
                    offset = (part_number - 1) * part_size
                    length = min(part_size, file_size - offset)
                    if length <= 0:
                        raise RemoteError(
                            f"the server issued more parts than {file_size} bytes "
                            f"can fill for {remote_path!r}"
                        )
                    etag = _put_part_to_presigned_url(
                        pool_manager, part_url, source, offset, length, part_number
                    )
                    upload_parts.append(
                        lakefs_sdk.UploadPart(part_number=part_number, etag=etag)
                    )
                    print(
                        f"  part {part_number}/{len(presigned_urls)} done "
                        f"({strftime('%d-%H-%M')})"
                    )
            object_stats = sdk_client.experimental_api.complete_presign_multipart_upload(
                branch.repo_id,
                branch.id,
                initiation.upload_id,
                remote_path,
                complete_presign_multipart_upload=(
                    lakefs_sdk.CompletePresignMultipartUpload(
                        physical_address=initiation.physical_address,
                        parts=upload_parts,
                    )
                ),
            )
        except LAKEFS_ERRORS as error:
            _abort_presigned_multipart(sdk_client, branch, initiation, remote_path)
            raise RemoteError(
                f"multipart upload of {remote_path!r} failed: {error}"
            ) from error
        except RemoteError:
            _abort_presigned_multipart(sdk_client, branch, initiation, remote_path)
            raise
        except (urllib3.exceptions.HTTPError, OSError) as error:
            _abort_presigned_multipart(sdk_client, branch, initiation, remote_path)
            raise RemoteError(
                f"multipart upload of {remote_path!r} failed: {error}"
            ) from error
        print(f"upload completed: {strftime('%d-%H-%M')}")

        stored_size = object_stats.size_bytes
        if stored_size is not None and stored_size != file_size:
            raise RemoteError(
                f"server stored {stored_size} bytes for {remote_path!r} but the "
                f"local file holds {file_size}; refusing to continue on a "
                "corrupted transfer."
            )
        if object_stats.mtime is not None:
            os.utime(local_path, times=(object_stats.mtime, object_stats.mtime))

    def _upload_via_server_api(
        self,
        branch: Branch,
        local_path: Path,
        remote_path: str,
        file_size: int,
        staging_error: Exception,
    ) -> None:
        """Last-resort upload through the lakeFS upload API itself.

        :param branch: target branch.
        :param local_path: file to read.
        :param remote_path: destination object name.
        :param file_size: size of *local_path* (sent as Content-Length).
        :param staging_error: the failure of the staging transports, carried
            so the final diagnostic lists every attempt that was made.
        :raise RemoteError: when the upload API also fails, or when the
            stored size does not match the local file.
        """
        try:
            object_stats = _upload_via_lakefs_api(
                self.client,
                branch.repo_id,
                branch.id,
                remote_path,
                local_path,
                file_size,
            )
        except Exception as api_error:  # every failure is reported below
            raise RemoteError(
                f"cannot upload {remote_path!r}: neither the staging transports "
                f"({staging_error}) nor the lakeFS upload API ({api_error}) "
                "could transfer the file."
            ) from api_error
        stored_size = object_stats.size_bytes
        if stored_size is not None and stored_size != file_size:
            raise RemoteError(
                f"server stored {stored_size} bytes for {remote_path!r} but the "
                f"local file holds {file_size}; refusing to continue on a "
                "corrupted transfer."
            )
        if object_stats.mtime is not None:
            # The upload API carries no staging metadata, so the server
            # stamped the object with its own clock.  Aligning the local
            # mtime to the object's (as download_file does in the opposite
            # direction) keeps repeated runs converged instead of treating
            # the file as changed forever.
            os.utime(local_path, times=(object_stats.mtime, object_stats.mtime))

    def download_file(
        self, reference_id: str, remote_path: str, local_path: Path
    ) -> None:
        """Download object *remote_path* at *reference_id* to *local_path*.

        The file is fetched in bounded chunks to a sibling ``.part`` file and
        atomically renamed into place, leaving the previous content intact on
        failure; the remote modification time is restored afterwards so
        repeated checkouts are no-ops.

        :param reference_id: commit hash (or any reference) to read from.
        :param remote_path: object name inside the repository.
        :param local_path: destination file path.
        :raise RemoteError: on any fetch or write failure.
        """
        object_stats = self.reference(reference_id).object(remote_path).stat()
        temporary_path = local_path.with_name(f"{local_path.name}.{os.getpid()}.part")
        try:
            # A fresh clone carries only the pointer file: every directory on
            # the way to the object has to be created on first checkout.
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with (
                self.reference(reference_id)
                .object(remote_path)
                .reader(mode="rb", pre_sign=False) as reader,
                temporary_path.open("wb") as output,
            ):
                while True:
                    chunk = reader.read(_DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    output.write(chunk)
            os.replace(temporary_path, local_path)
        except LAKEFS_ERRORS as error:
            temporary_path.unlink(missing_ok=True)
            raise RemoteError(f"cannot download {remote_path!r}: {error}") from error
        except OSError as error:
            temporary_path.unlink(missing_ok=True)
            raise RemoteError(f"cannot write {local_path}: {error}") from error

        remote_mtime = object_stats.mtime
        if remote_mtime is not None:
            # Restoring the source mtime makes "downloaded == unchanged" hold,
            # so the next status/commit run does not consider the file stale.
            os.utime(local_path, times=(remote_mtime, remote_mtime))

    def delete_objects(self, branch: Branch, remote_paths: list[str]) -> None:
        """Batch-delete objects from *branch*.

        Deletions are recoverable: the objects remain reachable through
        previous commits, mirroring how git keeps removed files in history.

        :param branch: branch to mutate.
        :param remote_paths: object names to remove.
        """
        for start in range(0, len(remote_paths), _DELETE_BATCH_SIZE):
            batch = remote_paths[start : start + _DELETE_BATCH_SIZE]
            try:
                branch.delete_objects(batch)
            except LAKEFS_ERRORS as error:
                raise RemoteError(
                    f"cannot delete {len(batch)} object(s): {error}"
                ) from error

    def commit_branch(
        self, branch: Branch, message: str, metadata: dict[str, str]
    ) -> str | None:
        """Commit the branch's pending changes and return the new commit hash.

        :param branch: branch to commit.
        :param message: commit message.
        :param metadata: key/value metadata stored alongside the commit
            (used to record the parent git commit for cross-referencing).
        :return: the new lakeFS commit hash, or ``None`` when the branch had
            no pending changes (nothing to snapshot).
        """
        try:
            if not any(branch.uncommitted(max_amount=1)):
                return None
            reference = branch.commit(message=message, metadata=metadata)
        except LAKEFS_ERRORS as error:
            raise RemoteError(f"cannot commit to {branch.id!r}: {error}") from error
        return reference.id

    def branch_head(self) -> str | None:
        """Current head commit of the configured branch, or ``None`` if unknown."""
        try:
            return self.branch(self.repository()).head.id
        except RemoteError:
            return None


class _HashingReader(io.RawIOBase):
    """File-like wrapper computing the MD5 digest of everything read.

    ``urllib3``/``http.client`` pull file-like bodies with ``read(n)``; this
    class hashes while streaming so the checksum comes for free and no file
    is ever read twice.
    """

    def __init__(self, path: Path) -> None:
        self._stream = path.open("rb")
        self._hasher = hashlib.md5()
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def read(self, amount: int = -1) -> bytes:
        chunk = self._stream.read(amount if amount and amount > 0 else 1024 * 1024)
        self._hasher.update(chunk)
        self.bytes_read += len(chunk)
        return chunk

    def hexdigest(self) -> str:
        """MD5 hex digest of everything read so far."""
        return self._hasher.hexdigest()

    def close(self) -> None:
        if not self.closed:
            self._stream.close()
        super().close()


class _BoundedFileReader(io.RawIOBase):
    """A read-only view of at most *length* bytes of an already-open file.

    urllib3 streams a body until ``read()`` returns empty; handing it the
    raw file would send everything past the part boundary.  This wrapper
    stops exactly at the boundary so each part PUT carries precisely its
    own slice with a correct Content-Length.

    :param source: the open binary file positioned anywhere (it is seeked
        by the caller before each part).
    :param length: maximum bytes to expose.
    """

    def __init__(self, source, length: int) -> None:
        self._source = source
        self._remaining = length

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        amount = self._remaining if size is None or size < 0 else min(size, self._remaining)
        chunk = self._source.read(amount)
        self._remaining -= len(chunk)
        return chunk


def _put_part_to_presigned_url(
    pool_manager,
    url: str,
    source,
    offset: int,
    length: int,
    part_number: int,
) -> str:
    """PUT one part slice to its presigned URL and return the storage ETag.

    Each attempt re-seeks the shared file, so a retried part re-sends the
    same bytes.  Connection-level failures (TLS resets, protocol errors)
    and server-side 5xx/429 answers are retried
    :data:`_MULTIPART_PART_ATTEMPTS` times with exponential backoff; a
    client-side rejection (an expired presigned URL, a bad signature) is
    final and reported immediately.

    :param pool_manager: the lakeFS client's urllib3 pool manager.
    :param url: presigned PUT URL for this part.
    :param source: the open binary file holding the whole upload.
    :param offset: byte offset of the part inside *source*.
    :param length: byte length of the part.
    :param part_number: 1-based part index (for diagnostics).
    :return: the ETag header the storage returned for the part.
    :raise RemoteError: after the retry budget is exhausted, or on a
        non-retryable rejection.
    """
    last_error: Exception | None = None
    for attempt in range(1, _MULTIPART_PART_ATTEMPTS + 1):
        source.seek(offset)
        try:
            response = pool_manager.request(
                method="PUT",
                url=url,
                body=_BoundedFileReader(source, length),
                headers={
                    "Content-Length": str(length),
                    "Content-Type": "application/octet-stream",
                },
                retries=False,
            )
        except (urllib3.exceptions.HTTPError, OSError) as error:
            last_error = error
            print(
                f"  part {part_number} attempt {attempt} failed: {error}; "
                f"retrying in {2 ** attempt}s"
            )
            time.sleep(2 ** attempt)
            continue
        if response.status < 400:
            etag = response.getheader("ETag")
            if not etag:
                raise RemoteError(
                    f"storage returned no ETag for part {part_number} of a "
                    "multipart upload; cannot complete it."
                )
            return etag.strip('"')
        body = response.data.decode("utf-8", errors="replace")
        response.close()
        if response.status in (429, 500, 502, 503, 504):
            last_error = RemoteError(
                f"part {part_number}: HTTP {response.status} {body}"
            )
            print(
                f"  part {part_number} attempt {attempt} got HTTP "
                f"{response.status}; retrying in {2 ** attempt}s"
            )
            time.sleep(2 ** attempt)
            continue
        raise RemoteError(
            f"multipart part {part_number} rejected with HTTP "
            f"{response.status}: {body}"
        )
    raise RemoteError(
        f"multipart part {part_number} failed after "
        f"{_MULTIPART_PART_ATTEMPTS} attempts: {last_error}"
    )


def _abort_presigned_multipart(
    sdk_client,
    branch: Branch,
    initiation: lakefs_sdk.PresignMultipartUpload,
    remote_path: str,
) -> None:
    """Best-effort cleanup of a failed multipart session on the block store.

    :param sdk_client: the raw lakeFS SDK client.
    :param branch: branch the upload was started on.
    :param initiation: the ``create`` response naming the session.
    :param remote_path: object name (for diagnostics only; the abort is
        attempted regardless — orphaned parts otherwise bill and clutter).
    """
    try:
        sdk_client.experimental_api.abort_presign_multipart_upload(
            branch.repo_id,
            branch.id,
            initiation.upload_id,
            remote_path,
            abort_presign_multipart_upload=lakefs_sdk.AbortPresignMultipartUpload(
                physical_address=initiation.physical_address
            ),
        )
    except LAKEFS_ERRORS as error:
        print(
            f"  warning: could not abort multipart upload "
            f"{initiation.upload_id!r} for {remote_path!r}: {error}"
        )


def _transfer_to_presigned_url(
    client: Client,
    url: str,
    local_path: Path,
    file_size: int,
) -> str:
    """PUT *local_path* to the presigned *url* and return the MD5 hex digest.

    This is the transport for S3/GCS/Azure block stores: the server issues a
    time-limited upload URL and the bytes flow straight to storage, exactly
    like the official client's presign upload path.

    :param client: connected lakeFS client (for its urllib3 pool).
    :param url: the presigned URL returned by the staging API.
    :param local_path: file to upload.
    :param file_size: size of *local_path* (sent as Content-Length).
    :return: the MD5 hex digest of everything that was sent.
    :raise RemoteError: when the storage rejects the PUT.
    """
    hasher = hashlib.md5()
    with local_path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    checksum = hasher.hexdigest()
    pool_manager = client.sdk_client.objects_api.api_client.rest_client.pool_manager
    print(f"beginning upload: {datetime.now().strftime('%d-%H-%M')}")
    with local_path.open("rb") as body_stream:
        response = pool_manager.request(
            method="PUT",
            url=url,
            body=body_stream,
            headers={
                "Content-Length": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            retries=False,
        )
        if response.status >= 400:
            raise RemoteError(
                f"presigned upload to {url} failed with HTTP {response.status}"
            )

    print(f"upload completed: {datetime.now().strftime('%d-%H-%M')}")
    return checksum


def _upload_via_lakefs_api(
    client: Client,
    repository_id: str,
    branch_id: str,
    remote_path: str,
    local_path: Path,
    file_size: int,
) -> lakefs_sdk.ObjectStats:
    """POST *local_path* through the lakeFS upload API and return the stats.

    The transport of last resort for deployments where the server neither
    serves presigned URLs nor exposes a staging area this machine can write
    to: the server itself copies the request body into its block store.
    This mirrors the official client's raw-upload path
    (``lakefs.object.ObjectWriter._upload_raw``), bypassing the generated
    SDK's whole-file multipart validation so the body streams from disk
    instead of having to fit into memory.

    :param client: connected lakeFS client.
    :param repository_id: repository name.
    :param branch_id: branch name.
    :param remote_path: destination object name.
    :param local_path: file to upload.
    :param file_size: size of *local_path* (sent as Content-Length).
    :return: the server's :class:`~lakefs_sdk.ObjectStats` for the object.
    :raise RemoteError: when the server rejects the upload.
    """
    resource_path = urllib.parse.quote(
        f"/repositories/{repository_id}/branches/{branch_id}/objects"
    )
    url = f"{client.config.host}{resource_path}?{urllib.parse.urlencode({'path': remote_path})}"
    api_client = client.sdk_client.objects_api.api_client
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file_size),
    }
    with local_path.open("rb") as body_stream:
        # The raw pool manager sends no credentials of its own; inject the
        # client's configured authentication the same way the official
        # client's raw upload does.
        api_client.update_params_for_auth(
            headers,
            None,
            ["basic_auth", "cookie_auth", "oidc_auth", "saml_auth", "jwt_token"],
            resource_path,
            "POST",
            body_stream,
        )
        response = api_client.rest_client.pool_manager.request(
            method="POST", url=url, body=body_stream, headers=headers
        )
    if response.status >= 400:
        raise RemoteError(
            f"direct upload of {remote_path!r} failed with HTTP {response.status}"
        )
    return lakefs_sdk.ObjectStats(**json.loads(response.data))


def _copy_to_local_staging_path(physical_address: str, local_path: Path) -> str:
    """Write *local_path* onto a shared-filesystem staging address.

    Block stores such as lakeFS's local adapter address objects with a
    ``local://`` (or ``file://``) URI that resolves to a path both the
    server and this client can reach.  The bytes are copied there and then
    linked to the branch, keeping the mtime/checksum metadata intact.

    :param physical_address: the staging address (e.g. ``local:///var/...``).
    :param local_path: file to copy from.
    :return: the MD5 hex digest of everything that was copied.
    :raise RemoteError: when the address is not a writable filesystem path.
    """
    parsed = urllib.parse.urlparse(physical_address)
    if parsed.scheme not in ("local", "file"):
        raise RemoteError(
            f"storage at {physical_address!r} supports neither presigned "
            "uploads nor a client-reachable filesystem path. Use S3/GCS/Azure "
            "(presigned) or run lakeFS with a local block store reachable "
            "from this machine."
        )
    destination = Path(parsed.path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    hasher_stream = _HashingReader(local_path)
    try:
        with destination.open("wb") as target:
            shutil.copyfileobj(hasher_stream, target, length=1024 * 1024)
    finally:
        hasher_stream.close()
    return hasher_stream.hexdigest()
