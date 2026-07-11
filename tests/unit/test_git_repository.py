"""Unit tests for Git repository creation and cloning."""

from pathlib import Path

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitRepositoryCloneResult,
    GitRepositoryCreateResult,
    GitRepositoryStatus,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCloneDestinationNotEmptyError,
    GitCloneSourceError,
    GitCommandFailedError,
    GitExecutableUnavailableError,
    GitRepositoryAlreadyExistsError,
    GitRepositoryPathError,
    GitService,
)


def _completed_result(
    command: tuple[str, ...],
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> GitCommandResult:
    """Create one completed Git process result."""

    return GitCommandResult(
        command=command,
        status=GitCommandExecutionStatus.COMPLETED,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
    )


def _unborn_status_output(
    repository_root: Path,
    branch_name: str = "main",
) -> str:
    """Build porcelain-v2 output for a freshly initialized repository."""

    return (
        "# branch.oid (initial)\0"
        f"# branch.head {branch_name}\0"
    )


def _cloned_status_output(
    head_oid: str,
    branch_name: str = "main",
) -> str:
    """Build porcelain-v2 output for a freshly cloned repository."""

    return (
        f"# branch.oid {head_oid}\0"
        f"# branch.head {branch_name}\0"
    )


# --- Model validation -------------------------------------------------


def test_repository_create_result_requires_root_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/other",
        head_oid=None,
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="root must match",
    ):
        GitRepositoryCreateResult(
            repository_root="/source/project",
            branch_name="main",
            head_oid=None,
            repository_status=status,
        )


def test_repository_create_result_requires_branch_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid=None,
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="branch name must match",
    ):
        GitRepositoryCreateResult(
            repository_root="/source/project",
            branch_name="develop",
            head_oid=None,
            repository_status=status,
        )


def test_repository_create_result_requires_head_oid_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="HEAD OID must match",
    ):
        GitRepositoryCreateResult(
            repository_root="/source/project",
            branch_name="main",
            head_oid=None,
            repository_status=status,
        )


def test_repository_clone_result_requires_root_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/other",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="root must match",
    ):
        GitRepositoryCloneResult(
            repository_root="/source/project",
            default_branch="main",
            head_oid="abc123",
            repository_status=status,
        )


def test_repository_clone_result_requires_branch_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="default branch must match",
    ):
        GitRepositoryCloneResult(
            repository_root="/source/project",
            default_branch="release",
            head_oid="abc123",
            repository_status=status,
        )


def test_repository_clone_result_requires_head_oid_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="HEAD OID must match",
    ):
        GitRepositoryCloneResult(
            repository_root="/source/project",
            default_branch="main",
            head_oid="def456",
            repository_status=status,
        )


# --- create_repository --------------------------------------------------


def test_create_repository_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    commands: list[tuple[str, ...]] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if command[1] == "init":
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        return _completed_result(
            command,
            stdout=_unborn_status_output(destination),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.create_repository(destination)

    assert result.repository_root == destination
    assert result.branch_name == "main"
    assert result.head_oid is None
    assert result.repository_status.clean is True

    assert commands[0] == (
        "git",
        "init",
        "--",
        str(destination),
    )


def test_create_repository_with_explicit_initial_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    captured_init_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_init_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if command[1] == "init":
            captured_init_command = command
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        return _completed_result(
            command,
            stdout=_unborn_status_output(
                destination,
                branch_name="trunk",
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.create_repository(
        destination,
        initial_branch="trunk",
    )

    assert result.branch_name == "trunk"
    assert captured_init_command == (
        "git",
        "init",
        "--initial-branch",
        "trunk",
        "--",
        str(destination),
    )


def test_create_repository_into_existing_empty_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    destination.mkdir()

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if command[1] == "init":
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        return _completed_result(
            command,
            stdout=_unborn_status_output(destination),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.create_repository(destination)

    assert result.repository_root == destination


def test_create_repository_rejects_existing_non_empty_directory(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "repo"
    destination.mkdir()
    (destination / "existing.txt").write_text("data")

    service = GitService()

    with pytest.raises(
        GitRepositoryAlreadyExistsError,
        match="not empty",
    ):
        service.create_repository(destination)


def test_create_repository_rejects_existing_file_at_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "repo"
    destination.write_text("data")

    service = GitService()

    with pytest.raises(
        GitRepositoryAlreadyExistsError,
        match="not a directory",
    ):
        service.create_repository(destination)


def test_create_repository_rejects_nonexistent_parent(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "missing" / "repo"

    service = GitService()

    with pytest.raises(
        GitRepositoryPathError,
        match="parent directory does not exist",
    ):
        service.create_repository(destination)


def test_create_repository_rejects_blank_initial_branch(
    tmp_path: Path,
) -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.create_repository(
            tmp_path / "repo",
            initial_branch="   ",
        )


def test_create_repository_rejects_non_string_initial_branch(
    tmp_path: Path,
) -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        service.create_repository(
            tmp_path / "repo",
            initial_branch=42,  # type: ignore[arg-type]
        )


def test_create_repository_refreshes_status_after_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal status_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if command[1] == "init":
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        status_reads += 1
        return _completed_result(
            command,
            stdout=_unborn_status_output(destination),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.create_repository(destination)

    assert status_reads == 1


def test_create_repository_propagates_git_executable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: not found",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(GitExecutableUnavailableError):
        service.create_repository(tmp_path / "repo")


def test_create_repository_propagates_git_command_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: permission denied",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="permission denied",
    ) as error:
        service.create_repository(tmp_path / "repo")

    assert error.value.result.return_code == 128


# --- clone_repository -----------------------------------------------------


def test_clone_repository_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    commands: list[tuple[str, ...]] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if command[1] == "clone":
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        return _completed_result(
            command,
            stdout=_cloned_status_output("abc123"),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.clone_repository(
        "https://example.invalid/project.git",
        destination,
    )

    assert result.repository_root == destination
    assert result.default_branch == "main"
    assert result.head_oid == "abc123"

    assert commands[0] == (
        "git",
        "clone",
        "--",
        "https://example.invalid/project.git",
        str(destination),
    )


def test_clone_repository_with_specific_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    captured_clone_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_clone_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if command[1] == "clone":
            captured_clone_command = command
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        return _completed_result(
            command,
            stdout=_cloned_status_output(
                "def456",
                branch_name="release",
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.clone_repository(
        "git@example.invalid:project.git",
        destination,
        branch="release",
    )

    assert result.default_branch == "release"
    assert captured_clone_command == (
        "git",
        "clone",
        "--branch",
        "release",
        "--",
        "git@example.invalid:project.git",
        str(destination),
    )


def test_clone_repository_rejects_existing_non_empty_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "repo"
    destination.mkdir()
    (destination / "existing.txt").write_text("data")

    service = GitService()

    with pytest.raises(
        GitCloneDestinationNotEmptyError,
        match="not empty",
    ):
        service.clone_repository(
            "https://example.invalid/project.git",
            destination,
        )


def test_clone_repository_rejects_existing_file_at_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "repo"
    destination.write_text("data")

    service = GitService()

    with pytest.raises(
        GitCloneDestinationNotEmptyError,
        match="not a directory",
    ):
        service.clone_repository(
            "https://example.invalid/project.git",
            destination,
        )


def test_clone_repository_rejects_nonexistent_parent(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "missing" / "repo"

    service = GitService()

    with pytest.raises(
        GitRepositoryPathError,
        match="parent directory does not exist",
    ):
        service.clone_repository(
            "https://example.invalid/project.git",
            destination,
        )


def test_clone_repository_rejects_blank_source(
    tmp_path: Path,
) -> None:
    service = GitService()

    with pytest.raises(
        GitCloneSourceError,
        match="must not be empty",
    ):
        service.clone_repository(
            "   ",
            tmp_path / "repo",
        )


def test_clone_repository_rejects_non_string_source(
    tmp_path: Path,
) -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        service.clone_repository(
            42,  # type: ignore[arg-type]
            tmp_path / "repo",
        )


def test_clone_repository_refreshes_status_after_clone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "repo"
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal status_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if command[1] == "clone":
            return _completed_result(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout=f"{destination}\n",
            )

        status_reads += 1
        return _completed_result(
            command,
            stdout=_cloned_status_output("abc123"),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.clone_repository(
        "https://example.invalid/project.git",
        destination,
    )

    assert status_reads == 1


def test_clone_repository_translates_source_not_found_stderr_to_source_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return _completed_result(
            command,
            return_code=128,
            stderr=(
                "fatal: repository "
                "'https://example.invalid/missing.git' not found"
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCloneSourceError,
        match="not found",
    ):
        service.clone_repository(
            "https://example.invalid/missing.git",
            tmp_path / "repo",
        )


def test_clone_repository_propagates_generic_git_command_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: disk full",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="disk full",
    ) as error:
        service.clone_repository(
            "https://example.invalid/project.git",
            tmp_path / "repo",
        )

    assert error.value.result.return_code == 128


def test_clone_repository_propagates_git_executable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: not found",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(GitExecutableUnavailableError):
        service.clone_repository(
            "https://example.invalid/project.git",
            tmp_path / "repo",
        )
