# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Resolution of the lakeFS endpoint, credentials and data-directory layout.

Settings are gathered from (highest precedence first):

1. Explicit command-line options,
2. ``HYPERCAM_LAKEFS_*`` environment variables (project-specific override),
3. the generic lakeFS environment variables used by ``lakectl``
   (``LAKECTL_SERVER_ENDPOINT_URL``, ``LAKECTL_CREDENTIALS_ACCESS_KEY_ID``,
   ``LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY``),
4. ``~/.lakectl.yaml`` (so a workstation that already runs ``lakectl``
   needs no further configuration),
5. built-in defaults (endpoint ``http://localhost:8000``, repository
   ``hypercam-data``, branch ``main``).

No server needs to be reachable to *build* the settings — the commands that
need one will fail with an actionable message at connection time instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml  # guaranteed available: the lakefs package depends on PyYAML

from hypercam.data_versioning.errors import ConfigurationError
from hypercam.data_versioning.git_ops import repository_root

#: The git-tracked file that binds each git commit to its lakeFS commit hash.
POINTER_RELATIVE_PATH = "data/.lakefs-commit"

#: Local directory holding the heavy recordings, relative to the repo root.
DEFAULT_DATA_DIRNAME = "data"

#: Local directory holding the analysis outputs.
RESULTS_DIRNAME = "results"

#: Remote trees synced into the lakeFS repository, mirrored after the GHCR
#: data image: (local sub-path relative to the data/results roots, remote
#: object-name prefix). results/archive/ is deliberately excluded on both
#: sides, matching scripts/data_image_build.sh.
CONTENT_ROOTS: tuple[tuple[str, str], ...] = (
    ("raw", "raw/"),
    ("cad_models", "cad_models/"),
    (RESULTS_DIRNAME, f"{RESULTS_DIRNAME}/"),
)

#: Sub-trees never pushed to lakeFS nor pulled from it (provenance-only data).
EXCLUDED_REMOTE_PREFIXES: tuple[str, ...] = (f"{RESULTS_DIRNAME}/archive/",)


@dataclass(frozen=True)
class ContentRoot:
    """One synced directory and where it lives in the lakeFS namespace.

    :param local_path: directory on this machine.
    :param remote_prefix: object-name prefix inside the lakeFS repository
        (always ends with ``/``).
    """

    local_path: Path
    remote_prefix: str

    def remote_path_for(self, file_path: Path) -> str:
        """Map a local file onto its object name inside the lakeFS repository.

        :param file_path: absolute path inside :attr:`local_path`.
        :return: object name such as ``raw/evt3_raw/spectral_425.raw``.
        """
        return self.remote_prefix + file_path.relative_to(self.local_path).as_posix()

    def local_path_for(self, remote_path: str) -> Path:
        """Map a lakeFS object name back onto its local file.

        :param remote_path: object name starting with :attr:`remote_prefix`.
        :return: the corresponding absolute local path.
        """
        relative = remote_path[len(self.remote_prefix):]
        return self.local_path / relative


@dataclass(frozen=True)
class Settings:
    """Everything the data-versioning commands need to operate.

    :param endpoint: base URL of the lakeFS server.
    :param access_key_id: lakeFS access key (also used as basic-auth user).
    :param secret_access_key: lakeFS secret key.
    :param repository: lakeFS repository holding the experiment data.
    :param branch: lakeFS branch that ``hypercam-data-commit`` snapshots onto.
    :param repo_root: top of the git checkout (anchor for the pointer file).
    :param data_dir: directory holding ``raw/`` and ``cad_models/``.
    :param results_dir: directory holding the analysis outputs.
    """

    endpoint: str
    access_key_id: str
    secret_access_key: str
    repository: str
    branch: str
    repo_root: Path
    data_dir: Path
    results_dir: Path

    @property
    def pointer_path(self) -> Path:
        """Absolute path of the git-tracked pointer file."""
        return self.repo_root / POINTER_RELATIVE_PATH

    @property
    def content_roots(self) -> tuple[ContentRoot, ...]:
        """The synced (directory, prefix) pairs, resolved against local paths.

        ``results/`` is always taken from the repository root (it is a
        product of the checkout), while the data directory may live
        elsewhere on the machine (override via ``--data-dir`` or
        ``HYPERCAM_DATA_DIR``), mirroring ``scripts/data_image_build.sh``.
        """
        return tuple(
            ContentRoot(
                local_path=self._local_root_for(local_name),
                remote_prefix=remote_prefix,
            )
            for local_name, remote_prefix in CONTENT_ROOTS
        )

    def _local_root_for(self, local_name: str) -> Path:
        if local_name == RESULTS_DIRNAME:
            return self.repo_root / RESULTS_DIRNAME
        return self.data_dir / local_name

    def local_root_for_prefix(self, remote_prefix: str) -> Path:
        """Map a remote object prefix back to its local directory.

        :param remote_prefix: object prefix such as ``raw/``.
        :return: the absolute local directory holding that subtree.
        """
        for local_name, prefix in CONTENT_ROOTS:
            if prefix == remote_prefix:
                return self._local_root_for(local_name)
        raise ConfigurationError(f"no local root is mapped to the remote prefix {remote_prefix!r}")

    def remote_prefixes(self) -> tuple[str, ...]:
        """All object-name prefixes owned by this integration."""
        return tuple(remote_prefix for _, remote_prefix in CONTENT_ROOTS)


def _first_environment_value(names: tuple[str, ...]) -> str | None:
    """Return the value of the first environment variable in *names* that is set and non-empty."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _read_lakectl_yaml() -> dict:
    """Load ``~/.lakectl.yaml`` (or ``$LAKECTL_CONFIG_FILE``) as a plain dict.

    Missing or unreadable files yield an empty dict; the lakeFS Python
    client honours the same file, so behaviour stays consistent with
    ``lakectl``.
    """
    config_path = Path(
        os.environ.get("LAKECTL_CONFIG_FILE", str(Path.home() / ".lakectl.yaml"))
    )
    try:
        with config_path.open(encoding="utf-8") as file_descriptor:
            loaded = yaml.safe_load(file_descriptor)
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise ConfigurationError(f"cannot read {config_path}: {error}") from error
    return loaded if isinstance(loaded, dict) else {}


def _lakectl_yaml_server_endpoint() -> str | None:
    """Extract ``server.endpoint_url`` from ``~/.lakectl.yaml``, if present."""
    server_block = _read_lakectl_yaml().get("server")
    if isinstance(server_block, dict):
        endpoint = server_block.get("endpoint_url")
        if isinstance(endpoint, str) and endpoint.strip():
            return endpoint.strip()
    return None


def _lakectl_yaml_credentials() -> tuple[str, str] | None:
    """Extract ``credentials.access_key_id`` / ``secret_access_key`` from ``~/.lakectl.yaml``."""
    credentials_block = _read_lakectl_yaml().get("credentials")
    if isinstance(credentials_block, dict):
        key = credentials_block.get("access_key_id")
        secret = credentials_block.get("secret_access_key")
        if isinstance(key, str) and key.strip() and isinstance(secret, str) and secret.strip():
            return key.strip(), secret.strip()
    return None


def load_settings(
    repo_root: Path,
    repository: str | None = None,
    branch: str | None = None,
    data_dir: Path | None = None,
) -> Settings:
    """Resolve every setting for the data-versioning commands.

    :param repo_root: top of the git checkout (see :func:`git_ops.repository_root`).
    :param repository: explicit lakeFS repository override.
    :param branch: explicit lakeFS branch override.
    :param data_dir: explicit data-directory override (still contains ``raw/``
        and ``cad_models/``).
    :return: fully resolved :class:`Settings`.
    :raise ConfigurationError: when the lakeFS credentials cannot be found
        anywhere in the precedence chain.
    """
    endpoint = (
        _first_environment_value(("HYPERCAM_LAKEFS_ENDPOINT", "LAKECTL_SERVER_ENDPOINT_URL"))
        or _lakectl_yaml_server_endpoint()
        or "http://localhost:8000"
    )

    key_from_env = _first_environment_value(
        ("HYPERCAM_LAKEFS_ACCESS_KEY_ID", "LAKECTL_CREDENTIALS_ACCESS_KEY_ID")
    )
    secret_from_env = _first_environment_value(
        ("HYPERCAM_LAKEFS_SECRET_ACCESS_KEY", "LAKECTL_CREDENTIALS_SECRET_ACCESS_KEY")
    )
    key_from_yaml, secret_from_yaml = _lakectl_yaml_credentials() or (None, None)
    access_key_id = key_from_env or key_from_yaml
    secret_access_key = secret_from_env or secret_from_yaml
    if not access_key_id or not secret_access_key:
        raise ConfigurationError(
            "No lakeFS credentials found. Either run `lakectl config` once "
            "(creates ~/.lakectl.yaml) or export "
            "HYPERCAM_LAKEFS_ACCESS_KEY_ID / HYPERCAM_LAKEFS_SECRET_ACCESS_KEY."
        )

    resolved_data_dir = (
        data_dir
        or (Path(os.environ["HYPERCAM_DATA_DIR"]) if os.environ.get("HYPERCAM_DATA_DIR") else None)
        or repo_root / DEFAULT_DATA_DIRNAME
    )

    return Settings(
        endpoint=endpoint.rstrip("/"),
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        repository=repository or os.environ.get("HYPERCAM_LAKEFS_REPOSITORY", "hypercam-data"),
        branch=branch or os.environ.get("HYPERCAM_LAKEFS_BRANCH", "main"),
        repo_root=repo_root,
        data_dir=resolved_data_dir,
        results_dir=repo_root / RESULTS_DIRNAME,
    )
