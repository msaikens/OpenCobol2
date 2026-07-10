"""Domain models for local Git repository state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class GitCommandExecutionStatus(StrEnum):
    """Outcome of invoking one local Git process."""

    COMPLETED = "completed"
    TIMED_OUT = "timed-out"
    FAILED_TO_START = "failed-to-start"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitCommandResult:
    """Captured result from one local Git process invocation."""

    command: tuple[str, ...]
    status: GitCommandExecutionStatus
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate captured Git process state."""

        command = tuple(
            str(argument)
            for argument in self.command
        )

        if not command:
            raise ValueError(
                "Git command must not be empty."
            )

        if not isinstance(
            self.status,
            GitCommandExecutionStatus,
        ):
            raise TypeError(
                "Git command status must be "
                "GitCommandExecutionStatus."
            )

        if (
            self.return_code is not None
            and (
                not isinstance(
                    self.return_code,
                    int,
                )
                or isinstance(
                    self.return_code,
                    bool,
                )
            )
        ):
            raise TypeError(
                "Git command return code must be an integer or None."
            )

        if not isinstance(
            self.stdout,
            str,
        ):
            raise TypeError(
                "Git command stdout must be a string."
            )

        if not isinstance(
            self.stderr,
            str,
        ):
            raise TypeError(
                "Git command stderr must be a string."
            )

        if (
            not isinstance(
                self.elapsed_seconds,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                self.elapsed_seconds,
                bool,
            )
        ):
            raise TypeError(
                "Git command elapsed seconds must be numeric."
            )

        if self.elapsed_seconds < 0:
            raise ValueError(
                "Git command elapsed seconds must not be negative."
            )

        error_message = _normalize_optional_string(
            self.error_message,
            "Git command error message",
        )

        object.__setattr__(
            self,
            "command",
            command,
        )
        object.__setattr__(
            self,
            "elapsed_seconds",
            float(
                self.elapsed_seconds,
            ),
        )
        object.__setattr__(
            self,
            "error_message",
            error_message,
        )

    @property
    def completed(
        self,
    ) -> bool:
        """Return whether the Git process completed."""

        return (
            self.status
            is GitCommandExecutionStatus.COMPLETED
        )

    @property
    def succeeded(
        self,
    ) -> bool:
        """Return whether Git completed with return code zero."""

        return (
            self.completed
            and self.return_code == 0
        )


class GitChangeStatus(StrEnum):
    """Normalized Git index or worktree change state."""

    UNMODIFIED = "unmodified"
    MODIFIED = "modified"
    TYPE_CHANGED = "type-changed"
    ADDED = "added"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNMERGED = "unmerged"
    UNTRACKED = "untracked"
    IGNORED = "ignored"
    UNKNOWN = "unknown"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitChange:
    """One changed repository path."""

    path: Path
    index_status: GitChangeStatus
    worktree_status: GitChangeStatus
    original_path: Path | None = None

    def __post_init__(self) -> None:
        """Normalize and validate changed-path state."""

        path = Path(
            self.path,
        )

        if not str(
            path,
        ):
            raise ValueError(
                "Git change path must not be empty."
            )

        if not isinstance(
            self.index_status,
            GitChangeStatus,
        ):
            raise TypeError(
                "Git change index status must be GitChangeStatus."
            )

        if not isinstance(
            self.worktree_status,
            GitChangeStatus,
        ):
            raise TypeError(
                "Git change worktree status must be GitChangeStatus."
            )

        original_path = (
            None
            if self.original_path is None
            else Path(
                self.original_path,
            )
        )

        object.__setattr__(
            self,
            "path",
            path,
        )
        object.__setattr__(
            self,
            "original_path",
            original_path,
        )

    @property
    def staged(
        self,
    ) -> bool:
        """Return whether the path has staged index changes."""

        return self.index_status not in {
            GitChangeStatus.UNMODIFIED,
            GitChangeStatus.UNTRACKED,
            GitChangeStatus.IGNORED,
        }

    @property
    def unstaged(
        self,
    ) -> bool:
        """Return whether the path has worktree changes."""

        return self.worktree_status not in {
            GitChangeStatus.UNMODIFIED,
            GitChangeStatus.IGNORED,
        }


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRepositoryStatus:
    """Current branch and changed-path state for one Git repository."""

    repository_root: Path
    head_oid: str | None
    branch_name: str | None
    detached: bool
    upstream: str | None
    ahead: int
    behind: int
    changes: tuple[GitChange, ...]

    def __post_init__(self) -> None:
        """Normalize and validate repository status."""

        repository_root = Path(
            self.repository_root,
        )

        head_oid = _normalize_optional_string(
            self.head_oid,
            "Git repository HEAD OID",
        )
        branch_name = _normalize_optional_string(
            self.branch_name,
            "Git repository branch name",
        )
        upstream = _normalize_optional_string(
            self.upstream,
            "Git repository upstream",
        )

        if not isinstance(
            self.detached,
            bool,
        ):
            raise TypeError(
                "Git repository detached state must be a boolean."
            )

        _require_non_negative_integer(
            self.ahead,
            "Git repository ahead count",
        )
        _require_non_negative_integer(
            self.behind,
            "Git repository behind count",
        )

        changes = tuple(
            self.changes,
        )

        if not all(
            isinstance(
                change,
                GitChange,
            )
            for change in changes
        ):
            raise TypeError(
                "Git repository changes must contain GitChange "
                "instances."
            )

        if (
            self.detached
            and branch_name is not None
        ):
            raise ValueError(
                "Detached Git repository status must not have a "
                "branch name."
            )

        object.__setattr__(
            self,
            "repository_root",
            repository_root,
        )
        object.__setattr__(
            self,
            "head_oid",
            head_oid,
        )
        object.__setattr__(
            self,
            "branch_name",
            branch_name,
        )
        object.__setattr__(
            self,
            "upstream",
            upstream,
        )
        object.__setattr__(
            self,
            "changes",
            changes,
        )

    @property
    def clean(
        self,
    ) -> bool:
        """Return whether the repository has no reported changes."""

        return not self.changes

    @property
    def has_staged_changes(
        self,
    ) -> bool:
        """Return whether any changed path has staged changes."""

        return any(
            change.staged
            for change in self.changes
        )

    @property
    def has_unstaged_changes(
        self,
    ) -> bool:
        """Return whether any changed path has worktree changes."""

        return any(
            change.unstaged
            for change in self.changes
        )


def _normalize_optional_string(
    value: str | None,
    name: str,
) -> str | None:
    """Normalize an optional non-empty string."""

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string or None."
        )

    normalized_value = value.strip()

    if not normalized_value:
        return None

    return normalized_value


def _require_non_negative_integer(
    value: int,
    name: str,
) -> None:
    """Require a non-negative non-boolean integer."""

    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    if value < 0:
        raise ValueError(
            f"{name} must not be negative."
        )