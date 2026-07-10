"""Local Git repository services."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path

from opencobol2.git.models import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitRepositoryStatus,
)
from opencobol2.git.process import (
    invoke_git_process,
)
from opencobol2.git.status import (
    parse_git_status_porcelain_v2,
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


class GitService:
    """Reads local Git repository state."""

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