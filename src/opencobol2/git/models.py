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


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitCommitResult:
    """Result of creating one commit from staged index content."""

    commit_oid: str
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate committed repository state."""

        commit_oid = _require_non_empty_string(
            self.commit_oid,
            "Git commit OID",
        )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git commit repository status must be "
                "GitRepositoryStatus."
            )

        if (
            self.repository_status.head_oid
            != commit_oid
        ):
            raise ValueError(
                "Git commit OID must match the refreshed repository "
                "HEAD OID."
            )

        object.__setattr__(
            self,
            "commit_oid",
            commit_oid,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRepositoryCreateResult:
    """Result of creating one new local Git repository."""

    repository_root: Path
    branch_name: str | None
    head_oid: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate created repository state."""

        repository_root = Path(
            self.repository_root,
        )
        branch_name = _normalize_optional_string(
            self.branch_name,
            "Git repository create branch name",
        )
        head_oid = _normalize_optional_string(
            self.head_oid,
            "Git repository create HEAD OID",
        )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git repository create status must be "
                "GitRepositoryStatus."
            )

        if (
            self.repository_status.repository_root
            != repository_root
        ):
            raise ValueError(
                "Git repository create root must match the refreshed "
                "repository status root."
            )

        if (
            self.repository_status.branch_name
            != branch_name
        ):
            raise ValueError(
                "Git repository create branch name must match the "
                "refreshed repository status branch name."
            )

        if (
            self.repository_status.head_oid
            != head_oid
        ):
            raise ValueError(
                "Git repository create HEAD OID must match the "
                "refreshed repository status HEAD OID."
            )

        object.__setattr__(
            self,
            "repository_root",
            repository_root,
        )
        object.__setattr__(
            self,
            "branch_name",
            branch_name,
        )
        object.__setattr__(
            self,
            "head_oid",
            head_oid,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRepositoryCloneResult:
    """Result of cloning one local Git repository from a source."""

    repository_root: Path
    default_branch: str | None
    head_oid: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate cloned repository state."""

        repository_root = Path(
            self.repository_root,
        )
        default_branch = _normalize_optional_string(
            self.default_branch,
            "Git repository clone default branch",
        )
        head_oid = _normalize_optional_string(
            self.head_oid,
            "Git repository clone HEAD OID",
        )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git repository clone status must be "
                "GitRepositoryStatus."
            )

        if (
            self.repository_status.repository_root
            != repository_root
        ):
            raise ValueError(
                "Git repository clone root must match the refreshed "
                "repository status root."
            )

        if (
            self.repository_status.branch_name
            != default_branch
        ):
            raise ValueError(
                "Git repository clone default branch must match the "
                "refreshed repository status branch name."
            )

        if (
            self.repository_status.head_oid
            != head_oid
        ):
            raise ValueError(
                "Git repository clone HEAD OID must match the "
                "refreshed repository status HEAD OID."
            )

        object.__setattr__(
            self,
            "repository_root",
            repository_root,
        )
        object.__setattr__(
            self,
            "default_branch",
            default_branch,
        )
        object.__setattr__(
            self,
            "head_oid",
            head_oid,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRemote:
    """One configured Git remote and its fetch/push URLs."""

    name: str
    fetch_url: str
    push_url: str

    def __post_init__(self) -> None:
        """Normalize and validate remote configuration."""

        name = _require_non_empty_string(
            self.name,
            "Git remote name",
        )
        fetch_url = _require_non_empty_string(
            self.fetch_url,
            "Git remote fetch URL",
        )
        push_url = _require_non_empty_string(
            self.push_url,
            "Git remote push URL",
        )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "fetch_url",
            fetch_url,
        )
        object.__setattr__(
            self,
            "push_url",
            push_url,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRemoteAddResult:
    """Result of adding one new Git remote."""

    remote: GitRemote
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate added remote state."""

        if not isinstance(
            self.remote,
            GitRemote,
        ):
            raise TypeError(
                "Git remote add result remote must be GitRemote."
            )

        remotes = _require_remote_tuple(
            self.remotes,
            "Git remote add result remotes",
        )

        if not any(
            remote == self.remote
            for remote in remotes
        ):
            raise ValueError(
                "Git remote add result must appear in the refreshed "
                "remote list."
            )

        object.__setattr__(
            self,
            "remotes",
            remotes,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRemoteRemoveResult:
    """Result of removing one Git remote."""

    removed_name: str
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate removed remote state."""

        removed_name = _require_non_empty_string(
            self.removed_name,
            "Git remote removed name",
        )
        remotes = _require_remote_tuple(
            self.remotes,
            "Git remote remove result remotes",
        )

        if any(
            remote.name == removed_name
            for remote in remotes
        ):
            raise ValueError(
                "Git remote remove result must not include the "
                "removed remote in the refreshed remote list."
            )

        object.__setattr__(
            self,
            "removed_name",
            removed_name,
        )
        object.__setattr__(
            self,
            "remotes",
            remotes,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRemoteRenameResult:
    """Result of renaming one Git remote."""

    remote: GitRemote
    previous_name: str
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate renamed remote state."""

        if not isinstance(
            self.remote,
            GitRemote,
        ):
            raise TypeError(
                "Git remote rename result remote must be GitRemote."
            )

        previous_name = _require_non_empty_string(
            self.previous_name,
            "Git remote previous name",
        )
        remotes = _require_remote_tuple(
            self.remotes,
            "Git remote rename result remotes",
        )

        if not any(
            remote == self.remote
            for remote in remotes
        ):
            raise ValueError(
                "Git remote rename result must appear in the "
                "refreshed remote list."
            )

        if (
            previous_name != self.remote.name
            and any(
                remote.name == previous_name
                for remote in remotes
            )
        ):
            raise ValueError(
                "Git remote rename result must not include the "
                "previous remote name in the refreshed remote list."
            )

        object.__setattr__(
            self,
            "previous_name",
            previous_name,
        )
        object.__setattr__(
            self,
            "remotes",
            remotes,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitFetchResult:
    """Result of fetching from one Git remote."""

    remote: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate fetched repository state."""

        remote = _normalize_optional_string(
            self.remote,
            "Git fetch remote",
        )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git fetch repository status must be "
                "GitRepositoryStatus."
            )

        object.__setattr__(
            self,
            "remote",
            remote,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitPullResult:
    """Result of pulling from one Git remote branch."""

    remote: str | None
    branch: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate pulled repository state."""

        remote = _normalize_optional_string(
            self.remote,
            "Git pull remote",
        )
        branch = _normalize_optional_string(
            self.branch,
            "Git pull branch",
        )

        if (
            branch is not None
            and remote is None
        ):
            raise ValueError(
                "Git pull result branch requires a remote."
            )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git pull repository status must be "
                "GitRepositoryStatus."
            )

        object.__setattr__(
            self,
            "remote",
            remote,
        )
        object.__setattr__(
            self,
            "branch",
            branch,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitPushResult:
    """Result of pushing to one Git remote branch."""

    remote: str | None
    branch: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate pushed repository state."""

        remote = _normalize_optional_string(
            self.remote,
            "Git push remote",
        )
        branch = _normalize_optional_string(
            self.branch,
            "Git push branch",
        )

        if (
            branch is not None
            and remote is None
        ):
            raise ValueError(
                "Git push result branch requires a remote."
            )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git push repository status must be "
                "GitRepositoryStatus."
            )

        object.__setattr__(
            self,
            "remote",
            remote,
        )
        object.__setattr__(
            self,
            "branch",
            branch,
        )


def _require_remote_tuple(
    remotes: tuple[GitRemote, ...],
    name: str,
) -> tuple[GitRemote, ...]:
    """Require a tuple of GitRemote instances."""

    normalized_remotes = tuple(
        remotes,
    )

    if not all(
        isinstance(
            remote,
            GitRemote,
        )
        for remote in normalized_remotes
    ):
        raise TypeError(
            f"{name} must contain GitRemote instances."
        )

    return normalized_remotes


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitBranch:
    """One local Git branch reference."""

    name: str
    head_oid: str
    is_current: bool
    upstream: str | None

    def __post_init__(self) -> None:
        """Normalize and validate branch reference state."""

        name = _require_non_empty_string(
            self.name,
            "Git branch name",
        )
        head_oid = _require_non_empty_string(
            self.head_oid,
            "Git branch HEAD OID",
        )
        upstream = _normalize_optional_string(
            self.upstream,
            "Git branch upstream",
        )

        if not isinstance(
            self.is_current,
            bool,
        ):
            raise TypeError(
                "Git branch current flag must be a boolean."
            )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "head_oid",
            head_oid,
        )
        object.__setattr__(
            self,
            "upstream",
            upstream,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitBranchCreateResult:
    """Result of creating one new local Git branch."""

    branch: GitBranch
    branches: tuple[GitBranch, ...]

    def __post_init__(self) -> None:
        """Normalize and validate created branch state."""

        if not isinstance(
            self.branch,
            GitBranch,
        ):
            raise TypeError(
                "Git branch create result branch must be GitBranch."
            )

        branches = _require_branch_tuple(
            self.branches,
            "Git branch create result branches",
        )

        if not any(
            branch == self.branch
            for branch in branches
        ):
            raise ValueError(
                "Git branch create result must appear in the "
                "refreshed branch list."
            )

        object.__setattr__(
            self,
            "branches",
            branches,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitBranchDeleteResult:
    """Result of deleting one local Git branch."""

    deleted_name: str
    branches: tuple[GitBranch, ...]

    def __post_init__(self) -> None:
        """Normalize and validate deleted branch state."""

        deleted_name = _require_non_empty_string(
            self.deleted_name,
            "Git branch deleted name",
        )
        branches = _require_branch_tuple(
            self.branches,
            "Git branch delete result branches",
        )

        if any(
            branch.name == deleted_name
            for branch in branches
        ):
            raise ValueError(
                "Git branch delete result must not include the "
                "deleted branch in the refreshed branch list."
            )

        object.__setattr__(
            self,
            "deleted_name",
            deleted_name,
        )
        object.__setattr__(
            self,
            "branches",
            branches,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitBranchSwitchResult:
    """Result of switching the current local Git branch."""

    branch: GitBranch
    branches: tuple[GitBranch, ...]
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate switched branch state."""

        if not isinstance(
            self.branch,
            GitBranch,
        ):
            raise TypeError(
                "Git branch switch result branch must be GitBranch."
            )

        branches = _require_branch_tuple(
            self.branches,
            "Git branch switch result branches",
        )

        if not any(
            branch == self.branch
            for branch in branches
        ):
            raise ValueError(
                "Git branch switch result must appear in the "
                "refreshed branch list."
            )

        if not self.branch.is_current:
            raise ValueError(
                "Git branch switch result branch must be the "
                "current branch."
            )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git branch switch repository status must be "
                "GitRepositoryStatus."
            )

        if (
            self.repository_status.branch_name
            != self.branch.name
        ):
            raise ValueError(
                "Git branch switch result must match the refreshed "
                "repository status branch name."
            )

        if (
            self.repository_status.head_oid
            != self.branch.head_oid
        ):
            raise ValueError(
                "Git branch switch result must match the refreshed "
                "repository status HEAD OID."
            )


def _require_branch_tuple(
    branches: tuple[GitBranch, ...],
    name: str,
) -> tuple[GitBranch, ...]:
    """Require a tuple of GitBranch instances."""

    normalized_branches = tuple(
        branches,
    )

    if not all(
        isinstance(
            branch,
            GitBranch,
        )
        for branch in normalized_branches
    ):
        raise TypeError(
            f"{name} must contain GitBranch instances."
        )

    return normalized_branches


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitTag:
    """One local Git tag reference."""

    name: str
    target_oid: str
    annotated: bool

    def __post_init__(self) -> None:
        """Normalize and validate tag reference state."""

        name = _require_non_empty_string(
            self.name,
            "Git tag name",
        )
        target_oid = _require_non_empty_string(
            self.target_oid,
            "Git tag target OID",
        )

        if not isinstance(
            self.annotated,
            bool,
        ):
            raise TypeError(
                "Git tag annotated flag must be a boolean."
            )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "target_oid",
            target_oid,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitTagCreateResult:
    """Result of creating one new local Git tag."""

    tag: GitTag
    tags: tuple[GitTag, ...]

    def __post_init__(self) -> None:
        """Normalize and validate created tag state."""

        if not isinstance(
            self.tag,
            GitTag,
        ):
            raise TypeError(
                "Git tag create result tag must be GitTag."
            )

        tags = _require_tag_tuple(
            self.tags,
            "Git tag create result tags",
        )

        if not any(
            tag == self.tag
            for tag in tags
        ):
            raise ValueError(
                "Git tag create result must appear in the refreshed "
                "tag list."
            )

        object.__setattr__(
            self,
            "tags",
            tags,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitTagDeleteResult:
    """Result of deleting one local Git tag."""

    deleted_name: str
    tags: tuple[GitTag, ...]

    def __post_init__(self) -> None:
        """Normalize and validate deleted tag state."""

        deleted_name = _require_non_empty_string(
            self.deleted_name,
            "Git tag deleted name",
        )
        tags = _require_tag_tuple(
            self.tags,
            "Git tag delete result tags",
        )

        if any(
            tag.name == deleted_name
            for tag in tags
        ):
            raise ValueError(
                "Git tag delete result must not include the "
                "deleted tag in the refreshed tag list."
            )

        object.__setattr__(
            self,
            "deleted_name",
            deleted_name,
        )
        object.__setattr__(
            self,
            "tags",
            tags,
        )


def _require_tag_tuple(
    tags: tuple[GitTag, ...],
    name: str,
) -> tuple[GitTag, ...]:
    """Require a tuple of GitTag instances."""

    normalized_tags = tuple(
        tags,
    )

    if not all(
        isinstance(
            tag,
            GitTag,
        )
        for tag in normalized_tags
    ):
        raise TypeError(
            f"{name} must contain GitTag instances."
        )

    return normalized_tags


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitCommitLogEntry:
    """One entry in a Git commit history log."""

    commit_oid: str
    parent_oids: tuple[str, ...]
    author_name: str
    author_email: str
    authored_at: str
    committer_name: str
    committer_email: str
    committed_at: str
    subject: str
    body: str

    def __post_init__(self) -> None:
        """Normalize and validate commit log entry state."""

        commit_oid = _require_non_empty_string(
            self.commit_oid,
            "Git commit log OID",
        )

        parent_oids = tuple(
            self.parent_oids,
        )

        if not all(
            isinstance(
                parent_oid,
                str,
            )
            and parent_oid.strip()
            for parent_oid in parent_oids
        ):
            raise ValueError(
                "Git commit log parent OIDs must be non-empty "
                "strings."
            )

        for field_label, field_value in (
            (
                "author name",
                self.author_name,
            ),
            (
                "author email",
                self.author_email,
            ),
            (
                "authored date",
                self.authored_at,
            ),
            (
                "committer name",
                self.committer_name,
            ),
            (
                "committer email",
                self.committer_email,
            ),
            (
                "committed date",
                self.committed_at,
            ),
            (
                "subject",
                self.subject,
            ),
            (
                "body",
                self.body,
            ),
        ):
            if not isinstance(
                field_value,
                str,
            ):
                raise TypeError(
                    f"Git commit log {field_label} must be a string."
                )

        object.__setattr__(
            self,
            "commit_oid",
            commit_oid,
        )
        object.__setattr__(
            self,
            "parent_oids",
            parent_oids,
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


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize one non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

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