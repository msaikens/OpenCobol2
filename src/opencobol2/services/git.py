"""Local Git repository services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from os import PathLike
from pathlib import Path

from opencobol2.git.branches import (
    BRANCH_FOR_EACH_REF_FORMAT,
    parse_git_branch_for_each_ref_output,
)
from opencobol2.git.history import (
    LOG_FORMAT,
    parse_git_log_output,
)
from opencobol2.git.models import (
    GitBranch,
    GitBranchCreateResult,
    GitBranchDeleteResult,
    GitBranchSwitchResult,
    GitCherryPickResult,
    GitCommandExecutionStatus,
    GitCommandResult,
    GitCommitLogEntry,
    GitCommitResult,
    GitFetchResult,
    GitPullResult,
    GitPushResult,
    GitRemote,
    GitRemoteAddResult,
    GitRemoteRemoveResult,
    GitRemoteRenameResult,
    GitRepositoryCloneResult,
    GitRepositoryCreateResult,
    GitRepositoryStatus,
    GitRevertResult,
    GitStashApplyResult,
    GitStashDropResult,
    GitStashEntry,
    GitStashPushResult,
    GitTag,
    GitTagCreateResult,
    GitTagDeleteResult,
)
from opencobol2.git.process import (
    invoke_git_process,
)
from opencobol2.git.remotes import (
    parse_git_remote_v_output,
)
from opencobol2.git.stash import (
    STASH_LIST_FORMAT,
    parse_git_stash_list_output,
)
from opencobol2.git.status import (
    parse_git_status_porcelain_v2,
)
from opencobol2.git.tags import (
    TAG_FOR_EACH_REF_FORMAT,
    parse_git_tag_for_each_ref_output,
)


class GitExecutableUnavailableError(RuntimeError):
    """Raised when the configured Git executable cannot be started."""


class GitCommandTimedOutError(TimeoutError):
    """Raised when a local Git command exceeds its timeout."""


class GitCommandFailedError(RuntimeError):
    """Raised when Git completes with a non-zero return code."""

    def __init__(
        self,
        *,
        result: GitCommandResult,
    ) -> None:
        """Initialize a failed Git command error."""

        if not isinstance(
            result,
            GitCommandResult,
        ):
            raise TypeError(
                "Failed Git command result must be GitCommandResult."
            )

        self.result = result

        detail = (
            result.error_message
            or result.stderr.strip()
            or result.stdout.strip()
            or "Git command failed."
        )

        super().__init__(
            detail,
        )


class GitRepositoryNotFoundError(LookupError):
    """Raised when a path is not inside a Git worktree."""


class GitRepositoryPathError(ValueError):
    """Raised when an invalid repository-relative path is requested."""


class GitCommitMessageError(ValueError):
    """Raised when a Git commit message is invalid."""


class GitNothingToCommitError(RuntimeError):
    """Raised when a staged commit is requested without staged changes."""


class GitRepositoryAlreadyExistsError(FileExistsError):
    """Raised when a new repository destination already has content."""


class GitCloneDestinationNotEmptyError(FileExistsError):
    """Raised when a Git clone destination already has content."""


class GitCloneSourceError(RuntimeError):
    """Raised when a Git clone source is blank or cannot be read."""


class GitRemoteNameError(ValueError):
    """Raised when a Git remote name is invalid."""


class GitRemoteUrlError(ValueError):
    """Raised when a Git remote URL is invalid."""


class GitRemoteNotFoundError(LookupError):
    """Raised when a referenced Git remote is not configured."""


class GitRemoteAlreadyExistsError(FileExistsError):
    """Raised when a Git remote name is already configured."""


class GitPullConflictError(RuntimeError):
    """Raised when a Git pull results in merge conflicts."""


class GitBranchNotFoundError(LookupError):
    """Raised when a referenced Git branch does not exist."""


class GitBranchAlreadyExistsError(FileExistsError):
    """Raised when a Git branch name is already configured."""


class GitCannotDeleteCurrentBranchError(RuntimeError):
    """Raised when deletion of the currently checked-out branch is requested."""


class GitTagNotFoundError(LookupError):
    """Raised when a referenced Git tag does not exist."""


class GitTagAlreadyExistsError(FileExistsError):
    """Raised when a Git tag name is already configured."""


class GitNothingToStashError(RuntimeError):
    """Raised when a stash is requested without any changes to stash."""


class GitStashNotFoundError(LookupError):
    """Raised when a referenced stash entry does not exist."""


class GitStashConflictError(RuntimeError):
    """Raised when applying or popping a stash results in conflicts."""


class GitRevertConflictError(RuntimeError):
    """Raised when reverting a commit results in conflicts."""


class GitCherryPickConflictError(RuntimeError):
    """Raised when cherry-picking a commit results in conflicts."""


class GitService:
    """Reads and updates local Git repository state."""

    def __init__(
        self,
        *,
        executable_path: Path | str = "git",
        environment_overrides: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize local Git repository services."""

        executable = str(
            executable_path,
        ).strip()

        if not executable:
            raise ValueError(
                "Git executable path must not be empty."
            )

        if (
            not isinstance(
                timeout_seconds,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                timeout_seconds,
                bool,
            )
        ):
            raise TypeError(
                "Git service timeout must be numeric."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Git service timeout must be greater than zero."
            )

        if (
            environment_overrides is not None
            and not isinstance(
                environment_overrides,
                Mapping,
            )
        ):
            raise TypeError(
                "Git environment overrides must be a mapping or None."
            )

        normalized_environment_overrides: dict[
            str,
            str,
        ] = {}

        if environment_overrides is not None:
            for name, value in environment_overrides.items():
                if not isinstance(
                    name,
                    str,
                ):
                    raise TypeError(
                        "Git environment variable names must be strings."
                    )

                normalized_name = name.strip()

                if not normalized_name:
                    raise ValueError(
                        "Git environment variable names must not be empty."
                    )

                if not isinstance(
                    value,
                    str,
                ):
                    raise TypeError(
                        "Git environment variable values must be strings."
                    )

                normalized_environment_overrides[
                    normalized_name
                ] = value

        self._executable_path = executable
        self._environment_overrides = (
            normalized_environment_overrides
        )
        self._timeout_seconds = float(
            timeout_seconds,
        )

    def set_executable_path(
        self,
        executable_path: Path | str,
    ) -> None:
        """Update the configured Git executable path."""

        executable = str(
            executable_path,
        ).strip()

        if not executable:
            raise ValueError(
                "Git executable path must not be empty."
            )

        self._executable_path = executable

    @property
    def executable_path(
        self,
    ) -> str:
        """Return the configured Git executable."""

        return self._executable_path

    @property
    def environment_overrides(
        self,
    ) -> Mapping[str, str]:
        """Return copied Git process environment overrides."""

        return dict(
            self._environment_overrides,
        )

    @property
    def timeout_seconds(
        self,
    ) -> float:
        """Return the local Git process timeout."""

        return self._timeout_seconds

    def discover_repository(
        self,
        path: Path | str,
    ) -> Path:
        """Resolve the Git worktree root containing a path."""

        working_directory = _resolve_working_directory(
            path,
        )

        result = self._invoke(
            arguments=(
                "--no-optional-locks",
                "rev-parse",
                "--show-toplevel",
            ),
            working_directory=working_directory,
        )

        if (
            result.completed
            and result.return_code != 0
        ):
            raise GitRepositoryNotFoundError(
                "Path is not inside a Git worktree: "
                f"{working_directory}"
            )

        _require_successful_result(
            result,
        )

        repository_root = result.stdout.strip()

        if not repository_root:
            raise GitCommandFailedError(
                result=GitCommandResult(
                    command=result.command,
                    status=result.status,
                    return_code=result.return_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_seconds=result.elapsed_seconds,
                    error_message=(
                        "Git did not return a repository root."
                    ),
                ),
            )

        return Path(
            repository_root,
        )

    def get_status(
        self,
        path: Path | str,
    ) -> GitRepositoryStatus:
        """Return current local status for a Git worktree."""

        repository_root = self.discover_repository(
            path,
        )

        return self._get_repository_status(
            repository_root,
        )

    def stage_paths(
        self,
        path: Path | str,
        repository_paths: Sequence[
            str | PathLike[str]
        ],
    ) -> GitRepositoryStatus:
        """Stage repository-relative paths and return refreshed status."""

        normalized_paths = _normalize_repository_paths(
            repository_paths,
        )
        repository_root = self.discover_repository(
            path,
        )

        result = self._invoke(
            arguments=(
                "add",
                "--",
                *normalized_paths,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return self._get_repository_status(
            repository_root,
        )

    def unstage_paths(
        self,
        path: Path | str,
        repository_paths: Sequence[
            str | PathLike[str]
        ],
    ) -> GitRepositoryStatus:
        """Unstage repository-relative paths and return refreshed status."""

        normalized_paths = _normalize_repository_paths(
            repository_paths,
        )
        repository_root = self.discover_repository(
            path,
        )
        status = self._get_repository_status(
            repository_root,
        )

        if status.head_oid is None:
            arguments = (
                "rm",
                "--cached",
                "--ignore-unmatch",
                "--",
                *normalized_paths,
            )
        else:
            arguments = (
                "restore",
                "--staged",
                "--",
                *normalized_paths,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return self._get_repository_status(
            repository_root,
        )

    def stage_all(
        self,
        path: Path | str,
    ) -> GitRepositoryStatus:
        """Stage all worktree changes and return refreshed status."""

        repository_root = self.discover_repository(
            path,
        )

        result = self._invoke(
            arguments=(
                "add",
                "--all",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return self._get_repository_status(
            repository_root,
        )

    def unstage_all(
        self,
        path: Path | str,
    ) -> GitRepositoryStatus:
        """Unstage all index changes and return refreshed status."""

        repository_root = self.discover_repository(
            path,
        )
        status = self._get_repository_status(
            repository_root,
        )

        if status.head_oid is None:
            arguments = (
                "rm",
                "--cached",
                "-r",
                "--ignore-unmatch",
                "--",
                ".",
            )
        else:
            arguments = (
                "restore",
                "--staged",
                "--",
                ".",
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return self._get_repository_status(
            repository_root,
        )

    def commit_staged(
        self,
        path: Path | str,
        message: str,
    ) -> GitCommitResult:
        """Commit current staged index content and return refreshed state."""

        normalized_message = _normalize_commit_message(
            message,
        )
        repository_root = self.discover_repository(
            path,
        )
        status = self._get_repository_status(
            repository_root,
        )

        if not status.has_staged_changes:
            raise GitNothingToCommitError(
                "Git repository has no staged changes to commit."
            )

        result = self._invoke(
            arguments=(
                "commit",
                "--message",
                normalized_message,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        commit_oid = self._resolve_head_oid(
            repository_root,
        )
        refreshed_status = self._get_repository_status(
            repository_root,
        )

        return GitCommitResult(
            commit_oid=commit_oid,
            repository_status=refreshed_status,
        )

    def create_repository(
        self,
        path: Path | str,
        *,
        initial_branch: str | None = None,
    ) -> GitRepositoryCreateResult:
        """Create a new local Git repository and return its state."""

        normalized_branch = _normalize_optional_ref_name(
            initial_branch,
            "Git initial branch name",
        )
        destination = _validate_new_repository_destination(
            path,
            occupied_error=GitRepositoryAlreadyExistsError,
        )

        arguments: tuple[str, ...] = (
            "init",
        )

        if normalized_branch is not None:
            arguments += (
                "--initial-branch",
                normalized_branch,
            )

        arguments += (
            "--",
            str(
                destination,
            ),
        )

        result = self._invoke(
            arguments=arguments,
            working_directory=Path.cwd(),
        )

        _require_successful_result(
            result,
        )

        repository_root = self.discover_repository(
            destination,
        )
        status = self._get_repository_status(
            repository_root,
        )

        return GitRepositoryCreateResult(
            repository_root=repository_root,
            branch_name=status.branch_name,
            head_oid=status.head_oid,
            repository_status=status,
        )

    def clone_repository(
        self,
        source: str,
        destination: Path | str,
        *,
        branch: str | None = None,
    ) -> GitRepositoryCloneResult:
        """Clone a Git repository into a new destination directory."""

        normalized_source = _require_clone_source(
            source,
        )
        normalized_branch = _normalize_optional_ref_name(
            branch,
            "Git clone branch name",
        )
        validated_destination = _validate_new_repository_destination(
            destination,
            occupied_error=GitCloneDestinationNotEmptyError,
        )

        arguments: tuple[str, ...] = (
            "clone",
        )

        if normalized_branch is not None:
            arguments += (
                "--branch",
                normalized_branch,
            )

        arguments += (
            "--",
            normalized_source,
            str(
                validated_destination,
            ),
        )

        result = self._invoke(
            arguments=arguments,
            working_directory=Path.cwd(),
        )

        _require_successful_clone_result(
            result,
        )

        repository_root = self.discover_repository(
            validated_destination,
        )
        status = self._get_repository_status(
            repository_root,
        )

        return GitRepositoryCloneResult(
            repository_root=repository_root,
            default_branch=status.branch_name,
            head_oid=status.head_oid,
            repository_status=status,
        )

    def get_remotes(
        self,
        path: Path | str,
    ) -> tuple[GitRemote, ...]:
        """Return configured remotes for a Git worktree."""

        repository_root = self.discover_repository(
            path,
        )

        return self._get_remotes(
            repository_root,
        )

    def add_remote(
        self,
        path: Path | str,
        name: str,
        url: str,
    ) -> GitRemoteAddResult:
        """Add a new Git remote and return the refreshed remote list."""

        normalized_name = _require_remote_name(
            name,
            "Git remote name",
        )
        normalized_url = _require_remote_url(
            url,
        )
        repository_root = self.discover_repository(
            path,
        )
        current_remotes = self._get_remotes(
            repository_root,
        )

        if any(
            remote.name == normalized_name
            for remote in current_remotes
        ):
            raise GitRemoteAlreadyExistsError(
                f"Git remote already exists: {normalized_name}"
            )

        result = self._invoke(
            arguments=(
                "remote",
                "add",
                "--",
                normalized_name,
                normalized_url,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_remotes = self._get_remotes(
            repository_root,
        )
        added_remote = _find_remote(
            refreshed_remotes,
            normalized_name,
            fallback_result=result,
        )

        return GitRemoteAddResult(
            remote=added_remote,
            remotes=refreshed_remotes,
        )

    def remove_remote(
        self,
        path: Path | str,
        name: str,
    ) -> GitRemoteRemoveResult:
        """Remove a Git remote and return the refreshed remote list."""

        normalized_name = _require_remote_name(
            name,
            "Git remote name",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_remotes = self._get_remotes(
            repository_root,
        )

        if not any(
            remote.name == normalized_name
            for remote in current_remotes
        ):
            raise GitRemoteNotFoundError(
                f"Git remote does not exist: {normalized_name}"
            )

        result = self._invoke(
            arguments=(
                "remote",
                "remove",
                "--",
                normalized_name,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_remotes = self._get_remotes(
            repository_root,
        )

        return GitRemoteRemoveResult(
            removed_name=normalized_name,
            remotes=refreshed_remotes,
        )

    def rename_remote(
        self,
        path: Path | str,
        name: str,
        new_name: str,
    ) -> GitRemoteRenameResult:
        """Rename a Git remote and return the refreshed remote list."""

        normalized_name = _require_remote_name(
            name,
            "Git remote name",
        )
        normalized_new_name = _require_remote_name(
            new_name,
            "Git remote new name",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_remotes = self._get_remotes(
            repository_root,
        )

        if not any(
            remote.name == normalized_name
            for remote in current_remotes
        ):
            raise GitRemoteNotFoundError(
                f"Git remote does not exist: {normalized_name}"
            )

        if (
            normalized_new_name != normalized_name
            and any(
                remote.name == normalized_new_name
                for remote in current_remotes
            )
        ):
            raise GitRemoteAlreadyExistsError(
                f"Git remote already exists: {normalized_new_name}"
            )

        result = self._invoke(
            arguments=(
                "remote",
                "rename",
                "--",
                normalized_name,
                normalized_new_name,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_remotes = self._get_remotes(
            repository_root,
        )
        renamed_remote = _find_remote(
            refreshed_remotes,
            normalized_new_name,
            fallback_result=result,
        )

        return GitRemoteRenameResult(
            remote=renamed_remote,
            previous_name=normalized_name,
            remotes=refreshed_remotes,
        )

    def fetch(
        self,
        path: Path | str,
        remote: str | None = None,
    ) -> GitFetchResult:
        """Fetch from a Git remote and return refreshed status."""

        normalized_remote = _normalize_optional_ref_name(
            remote,
            "Git fetch remote name",
        )
        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "fetch",
        )

        if normalized_remote is not None:
            arguments += (
                "--",
                normalized_remote,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        status = self._get_repository_status(
            repository_root,
        )

        return GitFetchResult(
            remote=normalized_remote,
            repository_status=status,
        )

    def pull(
        self,
        path: Path | str,
        remote: str | None = None,
        branch: str | None = None,
    ) -> GitPullResult:
        """Pull from a Git remote branch and return refreshed status."""

        normalized_remote = _normalize_optional_ref_name(
            remote,
            "Git pull remote name",
        )
        normalized_branch = _normalize_optional_ref_name(
            branch,
            "Git pull branch name",
        )

        if (
            normalized_branch is not None
            and normalized_remote is None
        ):
            raise ValueError(
                "Git pull branch requires an explicit remote."
            )

        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "pull",
        )

        if normalized_remote is not None:
            arguments += (
                "--",
                normalized_remote,
            )

            if normalized_branch is not None:
                arguments += (
                    normalized_branch,
                )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_conflict_aware_result(
            result,
            conflict_error_type=GitPullConflictError,
            default_message="Git pull resulted in merge conflicts.",
        )

        status = self._get_repository_status(
            repository_root,
        )

        return GitPullResult(
            remote=normalized_remote,
            branch=normalized_branch,
            repository_status=status,
        )

    def push(
        self,
        path: Path | str,
        remote: str | None = None,
        branch: str | None = None,
    ) -> GitPushResult:
        """Push to a Git remote branch and return refreshed status."""

        normalized_remote = _normalize_optional_ref_name(
            remote,
            "Git push remote name",
        )
        normalized_branch = _normalize_optional_ref_name(
            branch,
            "Git push branch name",
        )

        if (
            normalized_branch is not None
            and normalized_remote is None
        ):
            raise ValueError(
                "Git push branch requires an explicit remote."
            )

        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "push",
        )

        if normalized_remote is not None:
            arguments += (
                "--",
                normalized_remote,
            )

            if normalized_branch is not None:
                arguments += (
                    normalized_branch,
                )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        status = self._get_repository_status(
            repository_root,
        )

        return GitPushResult(
            remote=normalized_remote,
            branch=normalized_branch,
            repository_status=status,
        )

    def list_branches(
        self,
        path: Path | str,
    ) -> tuple[GitBranch, ...]:
        """Return local branches for a Git worktree."""

        repository_root = self.discover_repository(
            path,
        )

        return self._get_branches(
            repository_root,
        )

    def create_branch(
        self,
        path: Path | str,
        name: str,
        *,
        start_point: str | None = None,
    ) -> GitBranchCreateResult:
        """Create a new local branch and return the refreshed list."""

        normalized_name = _require_ref_name(
            name,
            "Git branch name",
        )
        normalized_start_point = _normalize_optional_ref_name(
            start_point,
            "Git branch start point",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_branches = self._get_branches(
            repository_root,
        )

        if any(
            branch.name == normalized_name
            for branch in current_branches
        ):
            raise GitBranchAlreadyExistsError(
                f"Git branch already exists: {normalized_name}"
            )

        arguments: tuple[str, ...] = (
            "branch",
            "--",
            normalized_name,
        )

        if normalized_start_point is not None:
            arguments += (
                normalized_start_point,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_branches = self._get_branches(
            repository_root,
        )
        created_branch = _find_branch(
            refreshed_branches,
            normalized_name,
            fallback_result=result,
        )

        return GitBranchCreateResult(
            branch=created_branch,
            branches=refreshed_branches,
        )

    def delete_branch(
        self,
        path: Path | str,
        name: str,
        *,
        force: bool = False,
    ) -> GitBranchDeleteResult:
        """Delete a local branch and return the refreshed list."""

        normalized_name = _require_ref_name(
            name,
            "Git branch name",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_branches = self._get_branches(
            repository_root,
        )
        matched_branch = next(
            (
                branch
                for branch in current_branches
                if branch.name == normalized_name
            ),
            None,
        )

        if matched_branch is None:
            raise GitBranchNotFoundError(
                f"Git branch does not exist: {normalized_name}"
            )

        if matched_branch.is_current:
            raise GitCannotDeleteCurrentBranchError(
                f"Git branch is currently checked out: {normalized_name}"
            )

        arguments: tuple[str, ...] = (
            (
                "branch",
                "--delete",
                "--force",
            )
            if force
            else (
                "branch",
                "--delete",
            )
        )
        arguments += (
            "--",
            normalized_name,
        )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_branches = self._get_branches(
            repository_root,
        )

        return GitBranchDeleteResult(
            deleted_name=normalized_name,
            branches=refreshed_branches,
        )

    def switch_branch(
        self,
        path: Path | str,
        name: str,
        *,
        create: bool = False,
    ) -> GitBranchSwitchResult:
        """Switch the current branch and return refreshed state."""

        normalized_name = _require_ref_name(
            name,
            "Git branch name",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_branches = self._get_branches(
            repository_root,
        )
        branch_exists = any(
            branch.name == normalized_name
            for branch in current_branches
        )

        if create:
            if branch_exists:
                raise GitBranchAlreadyExistsError(
                    f"Git branch already exists: {normalized_name}"
                )

            arguments = (
                "switch",
                "--create",
                "--",
                normalized_name,
            )
        else:
            if not branch_exists:
                raise GitBranchNotFoundError(
                    f"Git branch does not exist: {normalized_name}"
                )

            arguments = (
                "switch",
                "--",
                normalized_name,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_branches = self._get_branches(
            repository_root,
        )
        switched_branch = _find_branch(
            refreshed_branches,
            normalized_name,
            fallback_result=result,
        )
        refreshed_status = self._get_repository_status(
            repository_root,
        )

        return GitBranchSwitchResult(
            branch=switched_branch,
            branches=refreshed_branches,
            repository_status=refreshed_status,
        )

    def list_tags(
        self,
        path: Path | str,
    ) -> tuple[GitTag, ...]:
        """Return local tags for a Git worktree."""

        repository_root = self.discover_repository(
            path,
        )

        return self._get_tags(
            repository_root,
        )

    def create_tag(
        self,
        path: Path | str,
        name: str,
        *,
        target: str | None = None,
        message: str | None = None,
    ) -> GitTagCreateResult:
        """Create a new local tag and return the refreshed list."""

        normalized_name = _require_ref_name(
            name,
            "Git tag name",
        )
        normalized_target = _normalize_optional_ref_name(
            target,
            "Git tag target",
        )
        normalized_message = _normalize_optional_ref_name(
            message,
            "Git tag message",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_tags = self._get_tags(
            repository_root,
        )

        if any(
            tag.name == normalized_name
            for tag in current_tags
        ):
            raise GitTagAlreadyExistsError(
                f"Git tag already exists: {normalized_name}"
            )

        arguments: tuple[str, ...] = (
            "tag",
        )

        if normalized_message is not None:
            arguments += (
                "--annotate",
                "--message",
                normalized_message,
            )

        arguments += (
            "--",
            normalized_name,
        )

        if normalized_target is not None:
            arguments += (
                normalized_target,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_tags = self._get_tags(
            repository_root,
        )
        created_tag = _find_tag(
            refreshed_tags,
            normalized_name,
            fallback_result=result,
        )

        return GitTagCreateResult(
            tag=created_tag,
            tags=refreshed_tags,
        )

    def delete_tag(
        self,
        path: Path | str,
        name: str,
    ) -> GitTagDeleteResult:
        """Delete a local tag and return the refreshed list."""

        normalized_name = _require_ref_name(
            name,
            "Git tag name",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_tags = self._get_tags(
            repository_root,
        )

        if not any(
            tag.name == normalized_name
            for tag in current_tags
        ):
            raise GitTagNotFoundError(
                f"Git tag does not exist: {normalized_name}"
            )

        result = self._invoke(
            arguments=(
                "tag",
                "--delete",
                "--",
                normalized_name,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_tags = self._get_tags(
            repository_root,
        )

        return GitTagDeleteResult(
            deleted_name=normalized_name,
            tags=refreshed_tags,
        )

    def get_history(
        self,
        path: Path | str,
        *,
        ref: str | None = None,
        max_count: int | None = None,
    ) -> tuple[GitCommitLogEntry, ...]:
        """Return commit history for a Git worktree."""

        normalized_ref = _normalize_optional_ref_name(
            ref,
            "Git history ref",
        )
        normalized_max_count = _require_positive_optional_int(
            max_count,
            "Git history max count",
        )
        repository_root = self.discover_repository(
            path,
        )

        if normalized_ref is None:
            status = self._get_repository_status(
                repository_root,
            )

            if status.head_oid is None:
                return ()

        arguments: tuple[str, ...] = (
            "log",
            f"--format={LOG_FORMAT}",
        )

        if normalized_max_count is not None:
            arguments += (
                f"--max-count={normalized_max_count}",
            )

        if normalized_ref is not None:
            arguments += (
                normalized_ref,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_log_output(
            result.stdout,
        )

    def list_stashes(
        self,
        path: Path | str,
    ) -> tuple[GitStashEntry, ...]:
        """Return stash entries for a Git worktree."""

        repository_root = self.discover_repository(
            path,
        )

        return self._get_stashes(
            repository_root,
        )

    def stash_changes(
        self,
        path: Path | str,
        *,
        message: str | None = None,
        include_untracked: bool = False,
    ) -> GitStashPushResult:
        """Stash worktree changes and return the new stash entry."""

        normalized_message = _normalize_optional_ref_name(
            message,
            "Git stash message",
        )
        repository_root = self.discover_repository(
            path,
        )
        status = self._get_repository_status(
            repository_root,
        )

        if status.clean:
            raise GitNothingToStashError(
                "Git repository has no changes to stash."
            )

        arguments: tuple[str, ...] = (
            "stash",
            "push",
        )

        if include_untracked:
            arguments += (
                "--include-untracked",
            )

        if normalized_message is not None:
            arguments += (
                "--message",
                normalized_message,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        refreshed_stashes = self._get_stashes(
            repository_root,
        )

        if not refreshed_stashes:
            raise GitCommandFailedError(
                result=GitCommandResult(
                    command=result.command,
                    status=result.status,
                    return_code=result.return_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_seconds=result.elapsed_seconds,
                    error_message=(
                        "Git did not report the expected new stash "
                        "entry."
                    ),
                ),
            )

        refreshed_status = self._get_repository_status(
            repository_root,
        )

        return GitStashPushResult(
            entry=refreshed_stashes[0],
            repository_status=refreshed_status,
        )

    def apply_stash(
        self,
        path: Path | str,
        *,
        index: int = 0,
        pop: bool = False,
    ) -> GitStashApplyResult:
        """Apply or pop a stash entry and return refreshed status."""

        normalized_index = _require_non_negative_int(
            index,
            "Git stash index",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_stashes = self._get_stashes(
            repository_root,
        )

        if not any(
            entry.index == normalized_index
            for entry in current_stashes
        ):
            raise GitStashNotFoundError(
                f"Git stash entry does not exist: stash@{{{normalized_index}}}"
            )

        result = self._invoke(
            arguments=(
                "stash",
                "pop" if pop else "apply",
                f"stash@{{{normalized_index}}}",
            ),
            working_directory=repository_root,
        )

        _require_successful_conflict_aware_result(
            result,
            conflict_error_type=GitStashConflictError,
            default_message="Git stash apply resulted in merge conflicts.",
        )

        refreshed_status = self._get_repository_status(
            repository_root,
        )

        return GitStashApplyResult(
            repository_status=refreshed_status,
        )

    def drop_stash(
        self,
        path: Path | str,
        index: int = 0,
    ) -> GitStashDropResult:
        """Drop a stash entry and return the remaining entries."""

        normalized_index = _require_non_negative_int(
            index,
            "Git stash index",
        )
        repository_root = self.discover_repository(
            path,
        )
        current_stashes = self._get_stashes(
            repository_root,
        )

        if not any(
            entry.index == normalized_index
            for entry in current_stashes
        ):
            raise GitStashNotFoundError(
                f"Git stash entry does not exist: stash@{{{normalized_index}}}"
            )

        result = self._invoke(
            arguments=(
                "stash",
                "drop",
                f"stash@{{{normalized_index}}}",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        remaining = self._get_stashes(
            repository_root,
        )

        return GitStashDropResult(
            dropped_index=normalized_index,
            remaining=remaining,
        )

    def reset(
        self,
        path: Path | str,
        target: str = "HEAD",
        *,
        mode: str = "mixed",
    ) -> GitRepositoryStatus:
        """Reset the current branch to a target and return refreshed status."""

        normalized_target = _require_ref_name(
            target,
            "Git reset target",
        )

        if mode not in (
            "soft",
            "mixed",
            "hard",
        ):
            raise ValueError(
                "Git reset mode must be 'soft', 'mixed', or 'hard'."
            )

        repository_root = self.discover_repository(
            path,
        )

        result = self._invoke(
            arguments=(
                "reset",
                f"--{mode}",
                normalized_target,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return self._get_repository_status(
            repository_root,
        )

    def revert_commit(
        self,
        path: Path | str,
        commit: str,
        *,
        no_commit: bool = False,
    ) -> GitRevertResult:
        """Revert a commit and return refreshed status."""

        normalized_commit = _require_ref_name(
            commit,
            "Git revert commit",
        )
        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "revert",
        )

        if no_commit:
            arguments += (
                "--no-commit",
            )

        arguments += (
            normalized_commit,
        )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_conflict_aware_result(
            result,
            conflict_error_type=GitRevertConflictError,
            default_message="Git revert resulted in merge conflicts.",
        )

        return GitRevertResult(
            repository_status=self._get_repository_status(
                repository_root,
            ),
        )

    def cherry_pick_commit(
        self,
        path: Path | str,
        commit: str,
        *,
        no_commit: bool = False,
    ) -> GitCherryPickResult:
        """Cherry-pick a commit and return refreshed status."""

        normalized_commit = _require_ref_name(
            commit,
            "Git cherry-pick commit",
        )
        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "cherry-pick",
        )

        if no_commit:
            arguments += (
                "--no-commit",
            )

        arguments += (
            normalized_commit,
        )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_conflict_aware_result(
            result,
            conflict_error_type=GitCherryPickConflictError,
            default_message="Git cherry-pick resulted in merge conflicts.",
        )

        return GitCherryPickResult(
            repository_status=self._get_repository_status(
                repository_root,
            ),
        )

    def get_diff(
        self,
        path: Path | str,
        *,
        staged: bool = False,
        repository_paths: Sequence[str | PathLike[str]] | None = None,
    ) -> str:
        """Return raw unified diff text for worktree or staged changes."""

        repository_root = self.discover_repository(
            path,
        )

        arguments: tuple[str, ...] = (
            "diff",
        )

        if staged:
            arguments += (
                "--cached",
            )

        if repository_paths is not None:
            normalized_paths = _normalize_repository_paths(
                repository_paths,
            )
            arguments += (
                "--",
                *normalized_paths,
            )

        result = self._invoke(
            arguments=arguments,
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return result.stdout

    def get_commit_diff(
        self,
        path: Path | str,
        commit: str,
    ) -> str:
        """Return raw unified diff text introduced by one commit."""

        normalized_commit = _require_ref_name(
            commit,
            "Git commit",
        )
        repository_root = self.discover_repository(
            path,
        )

        result = self._invoke(
            arguments=(
                "show",
                "--format=",
                "--patch",
                normalized_commit,
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return result.stdout

    def _get_repository_status(
        self,
        repository_root: Path,
    ) -> GitRepositoryStatus:
        """Read status for an already-discovered repository root."""

        result = self._invoke(
            arguments=(
                "--no-optional-locks",
                "status",
                "--porcelain=v2",
                "--branch",
                "-z",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_status_porcelain_v2(
            repository_root=repository_root,
            output=result.stdout,
        )

    def _resolve_head_oid(
        self,
        repository_root: Path,
    ) -> str:
        """Resolve the current full HEAD object identifier."""

        result = self._invoke(
            arguments=(
                "--no-optional-locks",
                "rev-parse",
                "HEAD",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        commit_oid = result.stdout.strip()

        if not commit_oid:
            raise GitCommandFailedError(
                result=GitCommandResult(
                    command=result.command,
                    status=result.status,
                    return_code=result.return_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    elapsed_seconds=result.elapsed_seconds,
                    error_message=(
                        "Git did not return the current HEAD OID."
                    ),
                ),
            )

        return commit_oid

    def _get_remotes(
        self,
        repository_root: Path,
    ) -> tuple[GitRemote, ...]:
        """Read configured remotes for an already-discovered root."""

        result = self._invoke(
            arguments=(
                "remote",
                "-v",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_remote_v_output(
            result.stdout,
        )

    def _get_branches(
        self,
        repository_root: Path,
    ) -> tuple[GitBranch, ...]:
        """Read local branches for an already-discovered root."""

        result = self._invoke(
            arguments=(
                "for-each-ref",
                f"--format={BRANCH_FOR_EACH_REF_FORMAT}",
                "refs/heads",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_branch_for_each_ref_output(
            result.stdout,
        )

    def _get_tags(
        self,
        repository_root: Path,
    ) -> tuple[GitTag, ...]:
        """Read local tags for an already-discovered root."""

        result = self._invoke(
            arguments=(
                "for-each-ref",
                f"--format={TAG_FOR_EACH_REF_FORMAT}",
                "refs/tags",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_tag_for_each_ref_output(
            result.stdout,
        )

    def _get_stashes(
        self,
        repository_root: Path,
    ) -> tuple[GitStashEntry, ...]:
        """Read stash entries for an already-discovered root."""

        result = self._invoke(
            arguments=(
                "stash",
                "list",
                f"--format={STASH_LIST_FORMAT}",
            ),
            working_directory=repository_root,
        )

        _require_successful_result(
            result,
        )

        return parse_git_stash_list_output(
            result.stdout,
        )

    def _invoke(
        self,
        *,
        arguments: tuple[str, ...],
        working_directory: Path,
    ) -> GitCommandResult:
        """Invoke the configured local Git executable."""

        environment = dict(
            os.environ,
        )
        environment.update(
            self._environment_overrides,
        )

        return invoke_git_process(
            command=(
                self._executable_path,
                *arguments,
            ),
            timeout_seconds=self._timeout_seconds,
            working_directory=working_directory,
            environment=environment,
        )


def _resolve_working_directory(
    path: Path | str,
) -> Path:
    """Resolve a path to a candidate process working directory."""

    candidate = Path(
        path,
    )

    if candidate.is_file():
        return candidate.parent

    return candidate


def _normalize_repository_paths(
    repository_paths: Sequence[
        str | PathLike[str]
    ],
) -> tuple[str, ...]:
    """Validate repository-relative Git pathspec values."""

    if isinstance(
        repository_paths,
        (
            str,
            bytes,
            PathLike,
        ),
    ):
        raise TypeError(
            "Git repository paths must be a sequence of paths."
        )

    if not isinstance(
        repository_paths,
        Sequence,
    ):
        raise TypeError(
            "Git repository paths must be a sequence of paths."
        )

    normalized_paths: list[str] = []

    for repository_path in repository_paths:
        try:
            path_text = os.fspath(
                repository_path,
            )
        except TypeError as error:
            raise TypeError(
                "Git repository paths must contain string or "
                "path-like values."
            ) from error

        if not isinstance(
            path_text,
            str,
        ):
            raise TypeError(
                "Git repository paths must resolve to strings."
            )

        normalized_path = path_text.strip()

        if not normalized_path:
            raise GitRepositoryPathError(
                "Git repository path must not be empty."
            )

        path = Path(
            normalized_path,
        )

        if path.is_absolute():
            raise GitRepositoryPathError(
                "Git repository path must be relative."
            )

        if ".." in path.parts:
            raise GitRepositoryPathError(
                "Git repository path must not traverse outside "
                "the repository."
            )

        normalized_paths.append(
            normalized_path,
        )

    if not normalized_paths:
        raise GitRepositoryPathError(
            "At least one Git repository path is required."
        )

    return tuple(
        normalized_paths,
    )


def _normalize_commit_message(
    message: str,
) -> str:
    """Normalize and validate one Git commit message."""

    if not isinstance(
        message,
        str,
    ):
        raise TypeError(
            "Git commit message must be a string."
        )

    if "\0" in message:
        raise GitCommitMessageError(
            "Git commit message must not contain NUL characters."
        )

    normalized_message = message.strip()

    if not normalized_message:
        raise GitCommitMessageError(
            "Git commit message must not be empty."
        )

    return normalized_message


def _normalize_optional_ref_name(
    value: str | None,
    name: str,
) -> str | None:
    """Normalize an optional Git branch or ref name."""

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string or None."
        )

    if "\0" in value:
        raise ValueError(
            f"{name} must not contain NUL characters."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value


def _require_clone_source(
    source: str,
) -> str:
    """Validate and normalize a Git clone source."""

    if not isinstance(
        source,
        str,
    ):
        raise TypeError(
            "Git clone source must be a string."
        )

    if "\0" in source:
        raise GitCloneSourceError(
            "Git clone source must not contain NUL characters."
        )

    normalized_source = source.strip()

    if not normalized_source:
        raise GitCloneSourceError(
            "Git clone source must not be empty."
        )

    return normalized_source


def _validate_new_repository_destination(
    path: Path | str,
    *,
    occupied_error: type[Exception],
) -> Path:
    """Validate a filesystem destination for repository creation."""

    destination = Path(
        path,
    )

    if destination.exists():
        if destination.is_dir():
            if any(
                destination.iterdir(),
            ):
                raise occupied_error(
                    "Git repository destination already exists and "
                    f"is not empty: {destination}"
                )
        else:
            raise occupied_error(
                "Git repository destination already exists and is "
                f"not a directory: {destination}"
            )
    else:
        parent = destination.parent

        if (
            not parent.exists()
            or not parent.is_dir()
        ):
            raise GitRepositoryPathError(
                "Git repository destination parent directory does "
                f"not exist: {parent}"
            )

    return destination


_CLONE_SOURCE_FAILURE_MARKERS: tuple[str, ...] = (
    "does not appear to be a git repository",
    "could not read from remote repository",
    "not found",
    "unable to access",
    "does not exist",
)


def _looks_like_clone_source_failure(
    result: GitCommandResult,
) -> bool:
    """Return whether a failed clone result looks source-related."""

    combined_output = (
        f"{result.stderr}\n{result.stdout}"
    ).lower()

    return any(
        marker in combined_output
        for marker in _CLONE_SOURCE_FAILURE_MARKERS
    )


def _require_successful_clone_result(
    result: GitCommandResult,
) -> None:
    """Raise the appropriate service exception for clone failure."""

    if (
        result.status
        is GitCommandExecutionStatus.COMPLETED
        and not result.succeeded
        and _looks_like_clone_source_failure(
            result,
        )
    ):
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Git clone source is invalid or unreachable."
        )

        raise GitCloneSourceError(
            detail,
        )

    _require_successful_result(
        result,
    )


_MERGE_CONFLICT_MARKERS: tuple[str, ...] = (
    "conflict",
    "automatic merge failed",
    "could not revert",
    "could not apply",
)


def _looks_like_merge_conflict(
    result: GitCommandResult,
) -> bool:
    """Return whether a failed result looks conflict-related."""

    combined_output = (
        f"{result.stdout}\n{result.stderr}"
    ).lower()

    return any(
        marker in combined_output
        for marker in _MERGE_CONFLICT_MARKERS
    )


def _require_successful_conflict_aware_result(
    result: GitCommandResult,
    *,
    conflict_error_type: type[Exception],
    default_message: str,
) -> None:
    """Raise a conflict-specific error, else the usual Git failure error."""

    if (
        result.status
        is GitCommandExecutionStatus.COMPLETED
        and not result.succeeded
        and _looks_like_merge_conflict(
            result,
        )
    ):
        detail = (
            result.stdout.strip()
            or result.stderr.strip()
            or default_message
        )

        raise conflict_error_type(
            detail,
        )

    _require_successful_result(
        result,
    )


def _require_non_negative_int(
    value: int,
    name: str,
) -> int:
    """Validate a required non-negative integer."""

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

    return value


def _require_positive_optional_int(
    value: int | None,
    name: str,
) -> int | None:
    """Validate an optional positive integer."""

    if value is None:
        return None

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
            f"{name} must be an integer or None."
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return value


def _require_ref_name(
    value: str,
    name: str,
) -> str:
    """Validate and normalize a required Git ref name."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    if "\0" in value:
        raise ValueError(
            f"{name} must not contain NUL characters."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value


def _find_branch(
    branches: tuple[GitBranch, ...],
    name: str,
    *,
    fallback_result: GitCommandResult,
) -> GitBranch:
    """Find one branch by name after a successful Git operation."""

    for branch in branches:
        if branch.name == name:
            return branch

    raise GitCommandFailedError(
        result=GitCommandResult(
            command=fallback_result.command,
            status=fallback_result.status,
            return_code=fallback_result.return_code,
            stdout=fallback_result.stdout,
            stderr=fallback_result.stderr,
            elapsed_seconds=fallback_result.elapsed_seconds,
            error_message=(
                f"Git did not report the expected branch: {name}"
            ),
        ),
    )


def _find_tag(
    tags: tuple[GitTag, ...],
    name: str,
    *,
    fallback_result: GitCommandResult,
) -> GitTag:
    """Find one tag by name after a successful Git operation."""

    for tag in tags:
        if tag.name == name:
            return tag

    raise GitCommandFailedError(
        result=GitCommandResult(
            command=fallback_result.command,
            status=fallback_result.status,
            return_code=fallback_result.return_code,
            stdout=fallback_result.stdout,
            stderr=fallback_result.stderr,
            elapsed_seconds=fallback_result.elapsed_seconds,
            error_message=(
                f"Git did not report the expected tag: {name}"
            ),
        ),
    )


def _require_remote_name(
    value: str,
    name: str,
) -> str:
    """Validate and normalize a Git remote name."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    if "\0" in value:
        raise GitRemoteNameError(
            f"{name} must not contain NUL characters."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise GitRemoteNameError(
            f"{name} must not be empty."
        )

    if any(
        character.isspace()
        for character in normalized_value
    ):
        raise GitRemoteNameError(
            f"{name} must not contain whitespace."
        )

    return normalized_value


def _require_remote_url(
    value: str,
) -> str:
    """Validate and normalize a Git remote URL."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "Git remote URL must be a string."
        )

    if "\0" in value:
        raise GitRemoteUrlError(
            "Git remote URL must not contain NUL characters."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise GitRemoteUrlError(
            "Git remote URL must not be empty."
        )

    return normalized_value


def _find_remote(
    remotes: tuple[GitRemote, ...],
    name: str,
    *,
    fallback_result: GitCommandResult,
) -> GitRemote:
    """Find one remote by name after a successful Git operation."""

    for remote in remotes:
        if remote.name == name:
            return remote

    raise GitCommandFailedError(
        result=GitCommandResult(
            command=fallback_result.command,
            status=fallback_result.status,
            return_code=fallback_result.return_code,
            stdout=fallback_result.stdout,
            stderr=fallback_result.stderr,
            elapsed_seconds=fallback_result.elapsed_seconds,
            error_message=(
                f"Git did not report the expected remote: {name}"
            ),
        ),
    )


def _require_successful_result(
    result: GitCommandResult,
) -> None:
    """Raise the appropriate service exception for Git failure."""

    if (
        result.status
        is GitCommandExecutionStatus.FAILED_TO_START
    ):
        raise GitExecutableUnavailableError(
            result.error_message
            or "Unable to start Git."
        )

    if (
        result.status
        is GitCommandExecutionStatus.TIMED_OUT
    ):
        raise GitCommandTimedOutError(
            result.error_message
            or "Git command timed out."
        )

    if not result.succeeded:
        raise GitCommandFailedError(
            result=result,
        )