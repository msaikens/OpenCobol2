"""Unit tests for Git local branch management."""

import pytest

from opencobol2.git import (
    GitBranch,
    GitBranchCreateResult,
    GitBranchDeleteResult,
    GitBranchSwitchResult,
    GitCommandExecutionStatus,
    GitCommandResult,
    GitRepositoryStatus,
    parse_git_branch_for_each_ref_output,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitBranchAlreadyExistsError,
    GitBranchNotFoundError,
    GitCannotDeleteCurrentBranchError,
    GitCommandFailedError,
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


def _branch_output(
    entries: list[tuple[bool, str, str, str | None]],
) -> str:
    """Build `git for-each-ref` style output for given branches."""

    lines: list[str] = []

    for is_current, name, head_oid, upstream in entries:
        marker = "*" if is_current else " "
        lines.append(
            f"{marker}\t{name}\t{head_oid}\t{upstream or ''}"
        )

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


# --- parse_git_branch_for_each_ref_output --------------------------------


def test_parse_git_branch_for_each_ref_output_parses_current_and_other_branch() -> (
    None
):
    output = _branch_output(
        [
            (True, "main", "abc123", "origin/main"),
            (False, "feature", "def456", None),
        ],
    )

    branches = parse_git_branch_for_each_ref_output(output)

    assert branches == (
        GitBranch(
            name="main",
            head_oid="abc123",
            is_current=True,
            upstream="origin/main",
        ),
        GitBranch(
            name="feature",
            head_oid="def456",
            is_current=False,
            upstream=None,
        ),
    )


def test_parse_git_branch_for_each_ref_output_returns_empty_tuple_for_blank_output() -> (
    None
):
    assert parse_git_branch_for_each_ref_output("") == ()
    assert parse_git_branch_for_each_ref_output("\n\n") == ()


def test_parse_git_branch_for_each_ref_output_rejects_invalid_line() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid Git branch status line",
    ):
        parse_git_branch_for_each_ref_output("only\ttwo\tfields\n")


# --- Model validation -----------------------------------------------------


def test_branch_requires_non_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitBranch(
            name="   ",
            head_oid="abc123",
            is_current=False,
            upstream=None,
        )


def test_branch_requires_non_empty_head_oid() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitBranch(
            name="main",
            head_oid="",
            is_current=False,
            upstream=None,
        )


def test_branch_create_result_requires_branch_in_refreshed_list() -> None:
    branch = GitBranch(
        name="feature",
        head_oid="def456",
        is_current=False,
        upstream=None,
    )

    with pytest.raises(
        ValueError,
        match="must appear in the refreshed",
    ):
        GitBranchCreateResult(
            branch=branch,
            branches=(),
        )


def test_branch_delete_result_rejects_deleted_branch_still_present() -> None:
    branch = GitBranch(
        name="feature",
        head_oid="def456",
        is_current=False,
        upstream=None,
    )

    with pytest.raises(
        ValueError,
        match="must not include the deleted branch",
    ):
        GitBranchDeleteResult(
            deleted_name="feature",
            branches=(branch,),
        )


def test_branch_switch_result_requires_current_flag() -> None:
    branch = GitBranch(
        name="feature",
        head_oid="def456",
        is_current=False,
        upstream=None,
    )
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="def456",
        branch_name="feature",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="must be the current branch",
    ):
        GitBranchSwitchResult(
            branch=branch,
            branches=(branch,),
            repository_status=status,
        )


def test_branch_switch_result_requires_status_branch_name_match() -> None:
    branch = GitBranch(
        name="feature",
        head_oid="def456",
        is_current=True,
        upstream=None,
    )
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="def456",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="must match the refreshed repository status branch",
    ):
        GitBranchSwitchResult(
            branch=branch,
            branches=(branch,),
            repository_status=status,
        )


def test_branch_switch_result_requires_status_head_oid_match() -> None:
    branch = GitBranch(
        name="feature",
        head_oid="def456",
        is_current=True,
        upstream=None,
    )
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="feature",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="must match the refreshed repository status HEAD OID",
    ):
        GitBranchSwitchResult(
            branch=branch,
            branches=(branch,),
            repository_status=status,
        )


# --- list_branches ----------------------------------------------------------


def test_list_branches_returns_parsed_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", "origin/main"),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    branches = service.list_branches("/source/project")

    assert branches == (
        GitBranch(
            name="main",
            head_oid="abc123",
            is_current=True,
            upstream="origin/main",
        ),
    )


# --- create_branch ------------------------------------------------------


def test_create_branch_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    branch_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal branch_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                        (False, "feature", "abc123", None),
                    ],
                ),
            )

        if command[1] == "branch":
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.create_branch(
        "/source/project",
        "feature",
    )

    assert result.branch.name == "feature"
    assert len(result.branches) == 2

    assert commands[2] == (
        "git",
        "branch",
        "--",
        "feature",
    )


def test_create_branch_with_start_point_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_branch_command: tuple[str, ...] | None = None
    branch_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_branch_command
        nonlocal branch_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                        (False, "release", "abc123", None),
                    ],
                ),
            )

        if command[1] == "branch":
            captured_branch_command = command
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.create_branch(
        "/source/project",
        "release",
        start_point="main",
    )

    assert captured_branch_command == (
        "git",
        "branch",
        "--",
        "release",
        "main",
    )


def test_create_branch_rejects_existing_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", None),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitBranchAlreadyExistsError,
        match="already exists",
    ):
        service.create_branch(
            "/source/project",
            "main",
        )


def test_create_branch_rejects_blank_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.create_branch(
            "/source/project",
            "   ",
        )


def test_create_branch_propagates_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                    ],
                ),
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: branch create failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="branch create failed",
    ):
        service.create_branch(
            "/source/project",
            "feature",
        )


# --- delete_branch -----------------------------------------------------


def test_delete_branch_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    branch_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal branch_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                            (False, "feature", "abc123", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                    ],
                ),
            )

        if command[1] == "branch":
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.delete_branch(
        "/source/project",
        "feature",
    )

    assert result.deleted_name == "feature"
    assert len(result.branches) == 1

    assert commands[2] == (
        "git",
        "branch",
        "--delete",
        "--",
        "feature",
    )


def test_delete_branch_force_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_branch_command: tuple[str, ...] | None = None
    branch_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_branch_command
        nonlocal branch_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                            (False, "feature", "abc123", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                    ],
                ),
            )

        if command[1] == "branch":
            captured_branch_command = command
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.delete_branch(
        "/source/project",
        "feature",
        force=True,
    )

    assert captured_branch_command == (
        "git",
        "branch",
        "--delete",
        "--force",
        "--",
        "feature",
    )


def test_delete_branch_rejects_unknown_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", None),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitBranchNotFoundError,
        match="does not exist",
    ):
        service.delete_branch(
            "/source/project",
            "feature",
        )


def test_delete_branch_rejects_current_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", None),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCannotDeleteCurrentBranchError,
        match="currently checked out",
    ):
        service.delete_branch(
            "/source/project",
            "main",
        )


def test_delete_branch_propagates_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                        (False, "feature", "abc123", None),
                    ],
                ),
            )

        return _completed_result(
            command,
            return_code=1,
            stderr="error: branch delete failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="branch delete failed",
    ):
        service.delete_branch(
            "/source/project",
            "feature",
        )


# --- switch_branch -----------------------------------------------------


def test_switch_branch_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    branch_reads = 0
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal branch_reads
        nonlocal status_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                            (False, "feature", "def456", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (False, "main", "abc123", None),
                        (True, "feature", "def456", None),
                    ],
                ),
            )

        if command[1] == "switch":
            return _completed_result(command)

        if "status" in command:
            status_reads += 1
            return _completed_result(
                command,
                stdout=(
                    "# branch.oid def456\0"
                    "# branch.head feature\0"
                ),
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.switch_branch(
        "/source/project",
        "feature",
    )

    assert result.branch.name == "feature"
    assert result.branch.is_current is True
    assert result.repository_status.head_oid == "def456"
    assert status_reads == 1

    assert commands[2] == (
        "git",
        "switch",
        "--",
        "feature",
    )


def test_switch_branch_with_create_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_switch_command: tuple[str, ...] | None = None
    branch_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_switch_command
        nonlocal branch_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            branch_reads += 1

            if branch_reads == 1:
                return _completed_result(
                    command,
                    stdout=_branch_output(
                        [
                            (True, "main", "abc123", None),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (False, "main", "abc123", None),
                        (True, "feature", "abc123", None),
                    ],
                ),
            )

        if command[1] == "switch":
            captured_switch_command = command
            return _completed_result(command)

        if "status" in command:
            return _completed_result(
                command,
                stdout=(
                    "# branch.oid abc123\0"
                    "# branch.head feature\0"
                ),
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.switch_branch(
        "/source/project",
        "feature",
        create=True,
    )

    assert captured_switch_command == (
        "git",
        "switch",
        "--create",
        "--",
        "feature",
    )


def test_switch_branch_rejects_unknown_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", None),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitBranchNotFoundError,
        match="does not exist",
    ):
        service.switch_branch(
            "/source/project",
            "feature",
        )


def test_switch_branch_rejects_create_when_already_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            stdout=_branch_output(
                [
                    (True, "main", "abc123", None),
                    (False, "feature", "abc123", None),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitBranchAlreadyExistsError,
        match="already exists",
    ):
        service.switch_branch(
            "/source/project",
            "feature",
            create=True,
        )


def test_switch_branch_propagates_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            return _completed_result(
                command,
                stdout=_branch_output(
                    [
                        (True, "main", "abc123", None),
                        (False, "feature", "def456", None),
                    ],
                ),
            )

        return _completed_result(
            command,
            return_code=1,
            stderr="error: Your local changes would be overwritten",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="local changes would be overwritten",
    ):
        service.switch_branch(
            "/source/project",
            "feature",
        )
