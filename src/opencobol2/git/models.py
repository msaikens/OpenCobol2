"""Domain models for local Git repository state.

Every model here is a frozen, slotted, keyword-only dataclass that
represents either a piece of observed repository state (a change, a
branch, a tag, a commit log entry, ...) or the outcome of running one
Git operation (a commit, a fetch, a branch switch, ...). Each
dataclass validates and normalizes its own fields in `__post_init__`,
raising `TypeError`/`ValueError` for malformed input so that
downstream code can trust the shape of any instance it receives
without re-checking it. Several "operation result" dataclasses go
further and cross-check their fields against an embedded, freshly
refreshed :class:`GitRepositoryStatus` (or list of branches/remotes/
tags), so a result object can never claim an outcome that the
refreshed state contradicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class GitCommandExecutionStatus(StrEnum):
    """Outcome of invoking one local Git process.

    :cvar COMPLETED: The process ran to completion and produced a
        return code, whether or not that return code indicates
        success.
    :cvar TIMED_OUT: The process was still running when its allotted
        run time elapsed and was killed.
    :cvar FAILED_TO_START: The process could not be started at all,
        for example because the Git executable was not found.
    """

    COMPLETED = "completed"
    TIMED_OUT = "timed-out"
    FAILED_TO_START = "failed-to-start"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitCommandResult:
    """Captured result from one local Git process invocation.

    :ivar command: The argument vector that was executed, normalized
        to a tuple of strings.
    :ivar status: The high-level outcome of the invocation.
    :ivar return_code: The process's exit code, or None if it never
        produced one because it timed out or failed to start.
    :ivar stdout: The captured standard output.
    :ivar stderr: The captured standard error.
    :ivar elapsed_seconds: How long the invocation took, normalized
        to a non-negative float.
    :ivar error_message: A human-readable description of why the
        process failed to start or timed out, normalized to None if
        blank or not applicable.
    """

    command: tuple[str, ...]
    status: GitCommandExecutionStatus
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the captured Git process state.

        :returns: None. `command` is normalized to a tuple of
            strings, `elapsed_seconds` is coerced to a float, and
            `error_message` is normalized to None if blank.
        :raises ValueError: If `command` is empty, or
            `elapsed_seconds` is negative.
        :raises TypeError: If `status` is not a
            :class:`GitCommandExecutionStatus`, `return_code` is
            neither an int nor None, `stdout` or `stderr` is not a
            string, or `elapsed_seconds` is not numeric.
        """

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
        """Report whether the Git process completed.

        :returns: True if `status` is
            :attr:`GitCommandExecutionStatus.COMPLETED`, False if it
            timed out or failed to start.
        """

        return (
            self.status
            is GitCommandExecutionStatus.COMPLETED
        )

    @property
    def succeeded(
        self,
    ) -> bool:
        """Report whether Git completed with return code zero.

        :returns: True if the process completed and `return_code`
            is 0, False otherwise.
        """

        return (
            self.completed
            and self.return_code == 0
        )


class GitChangeStatus(StrEnum):
    """Normalized Git index or worktree change state.

    :cvar UNMODIFIED: No change relative to the compared state.
    :cvar MODIFIED: The path's content was modified.
    :cvar TYPE_CHANGED: The path's type changed, for example between
        a regular file and a symlink.
    :cvar ADDED: The path was added.
    :cvar DELETED: The path was deleted.
    :cvar RENAMED: The path was renamed from `original_path`.
    :cvar COPIED: The path was copied from `original_path`.
    :cvar UNMERGED: The path has an unresolved merge conflict.
    :cvar UNTRACKED: The path is not tracked by Git.
    :cvar IGNORED: The path is excluded by `.gitignore` or similar.
    :cvar UNKNOWN: The path's status could not be classified into
        any of the above.
    """

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
    """One changed repository path.

    :ivar path: The repository-relative path of the changed entry,
        normalized to a :class:`Path`.
    :ivar index_status: The path's staged (index) change state.
    :ivar worktree_status: The path's unstaged (worktree) change
        state.
    :ivar original_path: The path's previous location if it was
        renamed or copied, normalized to a :class:`Path`, or None
        otherwise.
    """

    path: Path
    index_status: GitChangeStatus
    worktree_status: GitChangeStatus
    original_path: Path | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the changed-path state.

        :returns: None. `path` and `original_path` are normalized
            to :class:`Path` instances.
        :raises ValueError: If `path` is empty.
        :raises TypeError: If `index_status` or `worktree_status` is
            not a :class:`GitChangeStatus`.
        """

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
        """Report whether the path has staged index changes.

        :returns: True if `index_status` is anything other than
            unmodified, untracked, or ignored.
        """

        return self.index_status not in {
            GitChangeStatus.UNMODIFIED,
            GitChangeStatus.UNTRACKED,
            GitChangeStatus.IGNORED,
        }

    @property
    def unstaged(
        self,
    ) -> bool:
        """Report whether the path has worktree changes.

        :returns: True if `worktree_status` is anything other than
            unmodified or ignored.
        """

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
    """Current branch and changed-path state for one Git repository.

    :ivar repository_root: The repository's working tree root,
        normalized to a :class:`Path`.
    :ivar head_oid: The object ID that HEAD points to, or None if
        HEAD is unborn (no commits yet).
    :ivar branch_name: The current branch's name, or None if HEAD is
        detached or unborn.
    :ivar detached: Whether HEAD points directly at a commit rather
        than a branch.
    :ivar upstream: The current branch's configured upstream
        reference, or None if it has none.
    :ivar ahead: How many commits the current branch is ahead of its
        upstream.
    :ivar behind: How many commits the current branch is behind its
        upstream.
    :ivar changes: Every changed path reported for the repository.
    """

    repository_root: Path
    head_oid: str | None
    branch_name: str | None
    detached: bool
    upstream: str | None
    ahead: int
    behind: int
    changes: tuple[GitChange, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the repository status.

        :returns: None. `repository_root` is normalized to a
            :class:`Path`, `head_oid`/`branch_name`/`upstream` are
            normalized to None if blank, and `changes` is normalized
            to a tuple.
        :raises ValueError: If `ahead` or `behind` is negative, or if
            `detached` is True while `branch_name` is not None.
        :raises TypeError: If `detached` is not a bool, `ahead` or
            `behind` is not a non-boolean int, or `changes` contains
            anything other than :class:`GitChange` instances.
        """

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
        """Report whether the repository has no reported changes.

        :returns: True if `changes` is empty.
        """

        return not self.changes

    @property
    def has_staged_changes(
        self,
    ) -> bool:
        """Report whether any changed path has staged changes.

        :returns: True if any entry in `changes` has
            :attr:`GitChange.staged` set.
        """

        return any(
            change.staged
            for change in self.changes
        )

    @property
    def has_unstaged_changes(
        self,
    ) -> bool:
        """Report whether any changed path has worktree changes.

        :returns: True if any entry in `changes` has
            :attr:`GitChange.unstaged` set.
        """

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
    """Result of creating one commit from staged index content.

    :ivar commit_oid: The newly created commit's object ID.
    :ivar repository_status: The repository status refreshed after
        the commit was created.
    """

    commit_oid: str
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the committed repository state.

        :returns: None. `commit_oid` is normalized by stripping
            surrounding whitespace.
        :raises ValueError: If `commit_oid` is empty, or does not
            match `repository_status.head_oid`.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """Result of creating one new local Git repository.

    :ivar repository_root: The new repository's working tree root.
    :ivar branch_name: The new repository's initial branch name, or
        None if it has none yet.
    :ivar head_oid: The new repository's HEAD object ID, or None if
        it is unborn (no commits yet).
    :ivar repository_status: The repository status refreshed after
        creation.
    """

    repository_root: Path
    branch_name: str | None
    head_oid: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the created repository state.

        :returns: None. `repository_root` is normalized to a
            :class:`Path`, and `branch_name`/`head_oid` are
            normalized to None if blank.
        :raises ValueError: If `repository_status` does not match
            `repository_root`, `branch_name`, or `head_oid`.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """Result of cloning one local Git repository from a source.

    :ivar repository_root: The cloned repository's working tree
        root.
    :ivar default_branch: The cloned repository's checked-out
        default branch name, or None if it has none.
    :ivar head_oid: The cloned repository's HEAD object ID, or None
        if it is unborn (no commits yet).
    :ivar repository_status: The repository status refreshed after
        cloning.
    """

    repository_root: Path
    default_branch: str | None
    head_oid: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the cloned repository state.

        :returns: None. `repository_root` is normalized to a
            :class:`Path`, and `default_branch`/`head_oid` are
            normalized to None if blank.
        :raises ValueError: If `repository_status` does not match
            `repository_root`, `default_branch`, or `head_oid`.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """One configured Git remote and its fetch/push URLs.

    :ivar name: The remote's configured name.
    :ivar fetch_url: The URL Git fetches from for this remote.
    :ivar push_url: The URL Git pushes to for this remote.
    """

    name: str
    fetch_url: str
    push_url: str

    def __post_init__(self) -> None:
        """Normalize and validate the remote configuration.

        :returns: None. `name`, `fetch_url`, and `push_url` are
            normalized by stripping surrounding whitespace.
        :raises ValueError: If `name`, `fetch_url`, or `push_url` is
            empty.
        :raises TypeError: If `name`, `fetch_url`, or `push_url` is
            not a string.
        """

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
    """Result of adding one new Git remote.

    :ivar remote: The newly added remote.
    :ivar remotes: Every remote configured for the repository after
        the addition.
    """

    remote: GitRemote
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the added remote state.

        :returns: None. `remotes` is normalized to a tuple.
        :raises ValueError: If `remote` does not appear in
            `remotes`.
        :raises TypeError: If `remote` is not a :class:`GitRemote`,
            or `remotes` contains anything other than
            :class:`GitRemote` instances.
        """

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
    """Result of removing one Git remote.

    :ivar removed_name: The name of the remote that was removed.
    :ivar remotes: Every remote configured for the repository after
        the removal.
    """

    removed_name: str
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the removed remote state.

        :returns: None. `removed_name` is normalized by stripping
            surrounding whitespace, and `remotes` is normalized to a
            tuple.
        :raises ValueError: If `removed_name` is empty, or a remote
            named `removed_name` still appears in `remotes`.
        :raises TypeError: If `removed_name` is not a string, or
            `remotes` contains anything other than
            :class:`GitRemote` instances.
        """

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
    """Result of renaming one Git remote.

    :ivar remote: The remote under its new name.
    :ivar previous_name: The remote's name before the rename.
    :ivar remotes: Every remote configured for the repository after
        the rename.
    """

    remote: GitRemote
    previous_name: str
    remotes: tuple[GitRemote, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the renamed remote state.

        :returns: None. `previous_name` is normalized by stripping
            surrounding whitespace, and `remotes` is normalized to a
            tuple.
        :raises ValueError: If `previous_name` is empty, `remote`
            does not appear in `remotes`, or (when the name actually
            changed) a remote named `previous_name` still appears in
            `remotes`.
        :raises TypeError: If `remote` is not a :class:`GitRemote`,
            or `remotes` contains anything other than
            :class:`GitRemote` instances.
        """

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
    """Result of fetching from one Git remote.

    :ivar remote: The name of the remote that was fetched from, or
        None if Git's configured default was used.
    :ivar repository_status: The repository status refreshed after
        the fetch.
    """

    remote: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the fetched repository state.

        :returns: None. `remote` is normalized to None if blank.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """Result of pulling from one Git remote branch.

    :ivar remote: The name of the remote that was pulled from, or
        None if Git's configured default was used.
    :ivar branch: The name of the remote branch that was pulled, or
        None if Git's configured default was used. Only meaningful
        together with `remote`.
    :ivar repository_status: The repository status refreshed after
        the pull.
    """

    remote: str | None
    branch: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the pulled repository state.

        :returns: None. `remote` and `branch` are normalized to
            None if blank.
        :raises ValueError: If `branch` is set while `remote` is
            None.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """Result of pushing to one Git remote branch.

    :ivar remote: The name of the remote that was pushed to, or None
        if Git's configured default was used.
    :ivar branch: The name of the remote branch that was pushed to,
        or None if Git's configured default was used. Only
        meaningful together with `remote`.
    :ivar repository_status: The repository status refreshed after
        the push.
    """

    remote: str | None
    branch: str | None
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Normalize and validate the pushed repository state.

        :returns: None. `remote` and `branch` are normalized to
            None if blank.
        :raises ValueError: If `branch` is set while `remote` is
            None.
        :raises TypeError: If `repository_status` is not a
            :class:`GitRepositoryStatus`.
        """

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
    """Normalize and validate a sequence of remotes.

    :param remotes: The sequence of remotes to normalize.
    :param name: A human-readable label for `remotes`, used in any
        raised error message.
    :returns: `remotes` normalized to a tuple.
    :raises TypeError: If `remotes` contains anything other than
        :class:`GitRemote` instances.
    """

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
    """One local Git branch reference.

    :ivar name: The branch's name.
    :ivar head_oid: The object ID the branch points to.
    :ivar is_current: Whether this branch is the repository's
        currently checked-out branch.
    :ivar upstream: The branch's configured upstream reference, or
        None if it has none.
    """

    name: str
    head_oid: str
    is_current: bool
    upstream: str | None

    def __post_init__(self) -> None:
        """Normalize and validate the branch reference state.

        :returns: None. `name` and `head_oid` are normalized by
            stripping surrounding whitespace, and `upstream` is
            normalized to None if blank.
        :raises ValueError: If `name` or `head_oid` is empty.
        :raises TypeError: If `name` or `head_oid` is not a string,
            or `is_current` is not a bool.
        """

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
    """Result of creating one new local Git branch.

    :ivar branch: The newly created branch.
    :ivar branches: Every local branch in the repository after the
        creation.
    """

    branch: GitBranch
    branches: tuple[GitBranch, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the created branch state.

        :returns: None. `branches` is normalized to a tuple.
        :raises ValueError: If `branch` does not appear in
            `branches`.
        :raises TypeError: If `branch` is not a :class:`GitBranch`,
            or `branches` contains anything other than
            :class:`GitBranch` instances.
        """

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
    """Result of deleting one local Git branch.

    :ivar deleted_name: The name of the branch that was deleted.
    :ivar branches: Every local branch in the repository after the
        deletion.
    """

    deleted_name: str
    branches: tuple[GitBranch, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the deleted branch state.

        :returns: None. `deleted_name` is normalized by stripping
            surrounding whitespace, and `branches` is normalized to
            a tuple.
        :raises ValueError: If `deleted_name` is empty, or a branch
            named `deleted_name` still appears in `branches`.
        :raises TypeError: If `deleted_name` is not a string, or
            `branches` contains anything other than
            :class:`GitBranch` instances.
        """

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
    """Result of switching the current local Git branch.

    :ivar branch: The branch that is now checked out.
    :ivar branches: Every local branch in the repository after the
        switch.
    :ivar repository_status: The repository status refreshed after
        the switch.
    """

    branch: GitBranch
    branches: tuple[GitBranch, ...]
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Validate the switched branch state.

        :returns: None. Nothing is normalized; this only validates.
        :raises ValueError: If `branch` does not appear in
            `branches`, `branch.is_current` is False, or
            `repository_status`'s branch name or HEAD OID does not
            match `branch`.
        :raises TypeError: If `branch` is not a :class:`GitBranch`,
            `branches` contains anything other than
            :class:`GitBranch` instances, or `repository_status` is
            not a :class:`GitRepositoryStatus`.
        """

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
    """Normalize and validate a sequence of branches.

    :param branches: The sequence of branches to normalize.
    :param name: A human-readable label for `branches`, used in any
        raised error message.
    :returns: `branches` normalized to a tuple.
    :raises TypeError: If `branches` contains anything other than
        :class:`GitBranch` instances.
    """

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


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitStashEntry:
    """One entry in the local Git stash list."""

    index: int
    commit_oid: str
    message: str

    def __post_init__(self) -> None:
        """Normalize and validate stash entry state."""

        _require_non_negative_integer(
            self.index,
            "Git stash index",
        )
        commit_oid = _require_non_empty_string(
            self.commit_oid,
            "Git stash commit OID",
        )

        if not isinstance(
            self.message,
            str,
        ):
            raise TypeError(
                "Git stash message must be a string."
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
class GitStashPushResult:
    """Result of creating one new stash entry."""

    entry: GitStashEntry
    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Validate created stash entry state."""

        if not isinstance(
            self.entry,
            GitStashEntry,
        ):
            raise TypeError(
                "Git stash push result entry must be GitStashEntry."
            )

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git stash push repository status must be "
                "GitRepositoryStatus."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitStashApplyResult:
    """Result of applying or popping one stash entry."""

    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Validate applied stash repository state."""

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git stash apply repository status must be "
                "GitRepositoryStatus."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitStashDropResult:
    """Result of dropping one stash entry."""

    dropped_index: int
    remaining: tuple[GitStashEntry, ...]

    def __post_init__(self) -> None:
        """Normalize and validate dropped stash state."""

        _require_non_negative_integer(
            self.dropped_index,
            "Git stash dropped index",
        )

        remaining = tuple(
            self.remaining,
        )

        if not all(
            isinstance(
                entry,
                GitStashEntry,
            )
            for entry in remaining
        ):
            raise TypeError(
                "Git stash drop result remaining entries must "
                "contain GitStashEntry instances."
            )

        object.__setattr__(
            self,
            "remaining",
            remaining,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitRevertResult:
    """Result of reverting one commit."""

    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Validate reverted repository state."""

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git revert repository status must be "
                "GitRepositoryStatus."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GitCherryPickResult:
    """Result of cherry-picking one commit."""

    repository_status: GitRepositoryStatus

    def __post_init__(self) -> None:
        """Validate cherry-picked repository state."""

        if not isinstance(
            self.repository_status,
            GitRepositoryStatus,
        ):
            raise TypeError(
                "Git cherry-pick repository status must be "
                "GitRepositoryStatus."
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