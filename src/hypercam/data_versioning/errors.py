# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-10-08
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

"""Exception hierarchy for the data-versioning integration.

Every exception raised on purpose by this package derives from
:class:`DataVersioningError`, so the command-line entry points can print a
single, human-readable diagnostic instead of a traceback for all
foreseeable failure modes (bad configuration, unreadable pointer, git
plumbing failure, lakeFS server problems).
"""


class DataVersioningError(Exception):
    """Base class for all recoverable data-versioning failures."""


class ConfigurationError(DataVersioningError):
    """The lakeFS endpoint, credentials or repository settings are missing or contradictory."""


class PointerError(DataVersioningError):
    """The ``data/.lakefs-commit`` pointer file is missing, malformed or unresolvable."""


class GitError(DataVersioningError):
    """A git plumbing call failed or returned an unusable result."""


class LocalDataError(DataVersioningError):
    """The local data tree is in a state the commands refuse to act on
    (missing directories, read-only mounts, suspicious emptiness)."""


class RemoteError(DataVersioningError):
    """The lakeFS server rejected or could not complete a request."""
