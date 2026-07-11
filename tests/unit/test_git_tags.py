"""Unit tests for Git local tag management."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitTag,
    GitTagCreateResult,
    GitTagDeleteResult,
    parse_git_tag_for_each_ref_output,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitService,
    GitTagAlreadyExistsError,
    GitTagNotFoundError,
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


def _tag_output(
    entries: list[tuple[str, str, bool]],
) -> str:
    """Build `git for-each-ref` style output for given tags."""

    lines: list[str] = []

    for name, target_oid, annotated in entries:
        object_type = "tag" if annotated else "commit"
        lines.append(
            f"{object_type}\t{name}\t{target_oid}"
        )

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


# --- parse_git_tag_for_each_ref_output ------------------------------------


def test_parse_git_tag_for_each_ref_output_parses_annotated_and_lightweight() -> (
    None
):
    output = _tag_output(
        [
            ("v1.0.0", "abc123", True),
            ("legacy", "def456", False),
        ],
    )

    tags = parse_git_tag_for_each_ref_output(output)

    assert tags == (
        GitTag(
            name="v1.0.0",
            target_oid="abc123",
            annotated=True,
        ),
        GitTag(
            name="legacy",
            target_oid="def456",
            annotated=False,
        ),
    )


def test_parse_git_tag_for_each_ref_output_returns_empty_tuple_for_blank_output() -> (
    None
):
    assert parse_git_tag_for_each_ref_output("") == ()
    assert parse_git_tag_for_each_ref_output("\n\n") == ()


def test_parse_git_tag_for_each_ref_output_rejects_invalid_line() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid Git tag status line",
    ):
        parse_git_tag_for_each_ref_output("only\tonefield\n")


# --- Model validation -----------------------------------------------------


def test_tag_requires_non_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitTag(
            name="   ",
            target_oid="abc123",
            annotated=False,
        )


def test_tag_requires_non_empty_target_oid() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitTag(
            name="v1.0.0",
            target_oid="",
            annotated=False,
        )


def test_tag_create_result_requires_tag_in_refreshed_list() -> None:
    tag = GitTag(
        name="v1.0.0",
        target_oid="abc123",
        annotated=False,
    )

    with pytest.raises(
        ValueError,
        match="must appear in the refreshed",
    ):
        GitTagCreateResult(
            tag=tag,
            tags=(),
        )


def test_tag_delete_result_rejects_deleted_tag_still_present() -> None:
    tag = GitTag(
        name="v1.0.0",
        target_oid="abc123",
        annotated=False,
    )

    with pytest.raises(
        ValueError,
        match="must not include the deleted tag",
    ):
        GitTagDeleteResult(
            deleted_name="v1.0.0",
            tags=(tag,),
        )


# --- list_tags ------------------------------------------------------------


def test_list_tags_returns_parsed_tags(
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
            stdout=_tag_output(
                [
                    ("v1.0.0", "abc123", True),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    tags = service.list_tags("/source/project")

    assert tags == (
        GitTag(
            name="v1.0.0",
            target_oid="abc123",
            annotated=True,
        ),
    )


# --- create_tag -------------------------------------------------------------


def test_create_tag_lightweight_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    tag_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal tag_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            tag_reads += 1

            if tag_reads == 1:
                return _completed_result(command, stdout="")

            return _completed_result(
                command,
                stdout=_tag_output(
                    [
                        ("v1.0.0", "abc123", False),
                    ],
                ),
            )

        if command[1] == "tag":
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.create_tag(
        "/source/project",
        "v1.0.0",
    )

    assert result.tag.name == "v1.0.0"
    assert result.tag.annotated is False

    assert commands[2] == (
        "git",
        "tag",
        "--",
        "v1.0.0",
    )


def test_create_tag_annotated_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_tag_command: tuple[str, ...] | None = None
    tag_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_tag_command
        nonlocal tag_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            tag_reads += 1

            if tag_reads == 1:
                return _completed_result(command, stdout="")

            return _completed_result(
                command,
                stdout=_tag_output(
                    [
                        ("v1.0.0", "abc123", True),
                    ],
                ),
            )

        if command[1] == "tag":
            captured_tag_command = command
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.create_tag(
        "/source/project",
        "v1.0.0",
        message="Release 1.0.0",
    )

    assert captured_tag_command == (
        "git",
        "tag",
        "--annotate",
        "--message",
        "Release 1.0.0",
        "--",
        "v1.0.0",
    )


def test_create_tag_with_target_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_tag_command: tuple[str, ...] | None = None
    tag_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_tag_command
        nonlocal tag_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            tag_reads += 1

            if tag_reads == 1:
                return _completed_result(command, stdout="")

            return _completed_result(
                command,
                stdout=_tag_output(
                    [
                        ("v1.0.0", "abc123", False),
                    ],
                ),
            )

        if command[1] == "tag":
            captured_tag_command = command
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.create_tag(
        "/source/project",
        "v1.0.0",
        target="abc123",
    )

    assert captured_tag_command == (
        "git",
        "tag",
        "--",
        "v1.0.0",
        "abc123",
    )


def test_create_tag_rejects_existing_name(
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
            stdout=_tag_output(
                [
                    ("v1.0.0", "abc123", False),
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
        GitTagAlreadyExistsError,
        match="already exists",
    ):
        service.create_tag(
            "/source/project",
            "v1.0.0",
        )


def test_create_tag_rejects_blank_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.create_tag(
            "/source/project",
            "   ",
        )


def test_create_tag_propagates_git_command_failure(
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
            return _completed_result(command, stdout="")

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: tag create failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="tag create failed",
    ):
        service.create_tag(
            "/source/project",
            "v1.0.0",
        )


# --- delete_tag ---------------------------------------------------------


def test_delete_tag_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    tag_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal tag_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "for-each-ref":
            tag_reads += 1

            if tag_reads == 1:
                return _completed_result(
                    command,
                    stdout=_tag_output(
                        [
                            ("v1.0.0", "abc123", False),
                        ],
                    ),
                )

            return _completed_result(command, stdout="")

        if command[1] == "tag":
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.delete_tag(
        "/source/project",
        "v1.0.0",
    )

    assert result.deleted_name == "v1.0.0"
    assert result.tags == ()

    assert commands[2] == (
        "git",
        "tag",
        "--delete",
        "--",
        "v1.0.0",
    )


def test_delete_tag_rejects_unknown_name(
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

        return _completed_result(command, stdout="")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitTagNotFoundError,
        match="does not exist",
    ):
        service.delete_tag(
            "/source/project",
            "v1.0.0",
        )


def test_delete_tag_propagates_git_command_failure(
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
                stdout=_tag_output(
                    [
                        ("v1.0.0", "abc123", False),
                    ],
                ),
            )

        return _completed_result(
            command,
            return_code=1,
            stderr="error: tag delete failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="tag delete failed",
    ):
        service.delete_tag(
            "/source/project",
            "v1.0.0",
        )
