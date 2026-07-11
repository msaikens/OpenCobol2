"""Unit tests for Git remote configuration management."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitRemote,
    GitRemoteAddResult,
    GitRemoteRemoveResult,
    GitRemoteRenameResult,
    parse_git_remote_v_output,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitRemoteAlreadyExistsError,
    GitRemoteNameError,
    GitRemoteNotFoundError,
    GitRemoteUrlError,
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


def _remote_v_output(
    entries: list[tuple[str, str, str]],
) -> str:
    """Build `git remote -v` style output for given remotes."""

    lines: list[str] = []

    for name, fetch_url, push_url in entries:
        lines.append(f"{name}\t{fetch_url} (fetch)")
        lines.append(f"{name}\t{push_url} (push)")

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


# --- parse_git_remote_v_output ------------------------------------------


def test_parse_git_remote_v_output_groups_fetch_and_push() -> None:
    output = _remote_v_output(
        [
            (
                "origin",
                "https://example.invalid/project.git",
                "https://example.invalid/project.git",
            ),
        ],
    )

    remotes = parse_git_remote_v_output(output)

    assert remotes == (
        GitRemote(
            name="origin",
            fetch_url="https://example.invalid/project.git",
            push_url="https://example.invalid/project.git",
        ),
    )


def test_parse_git_remote_v_output_handles_multiple_remotes_in_order() -> None:
    output = _remote_v_output(
        [
            (
                "origin",
                "https://example.invalid/project.git",
                "https://example.invalid/project.git",
            ),
            (
                "upstream",
                "https://example.invalid/upstream.git",
                "https://example.invalid/upstream-push.git",
            ),
        ],
    )

    remotes = parse_git_remote_v_output(output)

    assert [remote.name for remote in remotes] == [
        "origin",
        "upstream",
    ]
    assert remotes[1].fetch_url == "https://example.invalid/upstream.git"
    assert remotes[1].push_url == "https://example.invalid/upstream-push.git"


def test_parse_git_remote_v_output_returns_empty_tuple_for_blank_output() -> None:
    assert parse_git_remote_v_output("") == ()
    assert parse_git_remote_v_output("\n\n") == ()


def test_parse_git_remote_v_output_rejects_invalid_line() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid Git remote status line",
    ):
        parse_git_remote_v_output("origin only-one-column\n")


# --- Model validation -----------------------------------------------------


def test_remote_requires_non_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitRemote(
            name="   ",
            fetch_url="https://example.invalid/project.git",
            push_url="https://example.invalid/project.git",
        )


def test_remote_requires_non_empty_fetch_url() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitRemote(
            name="origin",
            fetch_url="",
            push_url="https://example.invalid/project.git",
        )


def test_remote_requires_non_empty_push_url() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitRemote(
            name="origin",
            fetch_url="https://example.invalid/project.git",
            push_url="",
        )


def test_remote_add_result_requires_remote_in_refreshed_list() -> None:
    remote = GitRemote(
        name="origin",
        fetch_url="https://example.invalid/project.git",
        push_url="https://example.invalid/project.git",
    )

    with pytest.raises(
        ValueError,
        match="must appear in the refreshed",
    ):
        GitRemoteAddResult(
            remote=remote,
            remotes=(),
        )


def test_remote_remove_result_rejects_removed_remote_still_present() -> None:
    remote = GitRemote(
        name="origin",
        fetch_url="https://example.invalid/project.git",
        push_url="https://example.invalid/project.git",
    )

    with pytest.raises(
        ValueError,
        match="must not include the removed remote",
    ):
        GitRemoteRemoveResult(
            removed_name="origin",
            remotes=(remote,),
        )


def test_remote_rename_result_requires_remote_in_refreshed_list() -> None:
    remote = GitRemote(
        name="upstream",
        fetch_url="https://example.invalid/project.git",
        push_url="https://example.invalid/project.git",
    )

    with pytest.raises(
        ValueError,
        match="must appear in the refreshed",
    ):
        GitRemoteRenameResult(
            remote=remote,
            previous_name="origin",
            remotes=(),
        )


def test_remote_rename_result_rejects_previous_name_still_present() -> None:
    renamed = GitRemote(
        name="upstream",
        fetch_url="https://example.invalid/project.git",
        push_url="https://example.invalid/project.git",
    )
    stale = GitRemote(
        name="origin",
        fetch_url="https://example.invalid/project.git",
        push_url="https://example.invalid/project.git",
    )

    with pytest.raises(
        ValueError,
        match="must not include the previous remote name",
    ):
        GitRemoteRenameResult(
            remote=renamed,
            previous_name="origin",
            remotes=(
                renamed,
                stale,
            ),
        )


# --- get_remotes ------------------------------------------------------------


def test_get_remotes_returns_parsed_remotes(
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
            stdout=_remote_v_output(
                [
                    (
                        "origin",
                        "https://example.invalid/project.git",
                        "https://example.invalid/project.git",
                    ),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    remotes = service.get_remotes("/source/project")

    assert remotes == (
        GitRemote(
            name="origin",
            fetch_url="https://example.invalid/project.git",
            push_url="https://example.invalid/project.git",
        ),
    )


# --- add_remote -------------------------------------------------------------


def test_add_remote_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    remote_v_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal remote_v_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1:3] == ("remote", "-v"):
            remote_v_reads += 1

            if remote_v_reads == 1:
                return _completed_result(command, stdout="")

            return _completed_result(
                command,
                stdout=_remote_v_output(
                    [
                        (
                            "origin",
                            "https://example.invalid/project.git",
                            "https://example.invalid/project.git",
                        ),
                    ],
                ),
            )

        if command[1:3] == ("remote", "add"):
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.add_remote(
        "/source/project",
        "origin",
        "https://example.invalid/project.git",
    )

    assert result.remote.name == "origin"
    assert result.remote.fetch_url == "https://example.invalid/project.git"
    assert len(result.remotes) == 1

    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
        (
            "git",
            "remote",
            "add",
            "--",
            "origin",
            "https://example.invalid/project.git",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
    ]


def test_add_remote_rejects_existing_name(
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
            stdout=_remote_v_output(
                [
                    (
                        "origin",
                        "https://example.invalid/project.git",
                        "https://example.invalid/project.git",
                    ),
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
        GitRemoteAlreadyExistsError,
        match="already exists",
    ):
        service.add_remote(
            "/source/project",
            "origin",
            "https://example.invalid/other.git",
        )


def test_add_remote_rejects_blank_name() -> None:
    service = GitService()

    with pytest.raises(
        GitRemoteNameError,
        match="must not be empty",
    ):
        service.add_remote(
            "/source/project",
            "   ",
            "https://example.invalid/project.git",
        )


def test_add_remote_rejects_blank_url() -> None:
    service = GitService()

    with pytest.raises(
        GitRemoteUrlError,
        match="must not be empty",
    ):
        service.add_remote(
            "/source/project",
            "origin",
            "   ",
        )


def test_add_remote_rejects_name_with_whitespace() -> None:
    service = GitService()

    with pytest.raises(
        GitRemoteNameError,
        match="must not contain whitespace",
    ):
        service.add_remote(
            "/source/project",
            "origin upstream",
            "https://example.invalid/project.git",
        )


def test_add_remote_rejects_non_string_name() -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        service.add_remote(
            "/source/project",
            42,  # type: ignore[arg-type]
            "https://example.invalid/project.git",
        )


def test_add_remote_propagates_git_command_failure(
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

        if command[1:3] == ("remote", "-v"):
            return _completed_result(command, stdout="")

        if command[1:3] == ("remote", "add"):
            return _completed_result(
                command,
                return_code=128,
                stderr="fatal: remote add failed",
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="remote add failed",
    ):
        service.add_remote(
            "/source/project",
            "origin",
            "https://example.invalid/project.git",
        )


# --- remove_remote -----------------------------------------------------------


def test_remove_remote_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    remote_v_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal remote_v_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1:3] == ("remote", "-v"):
            remote_v_reads += 1

            if remote_v_reads == 1:
                return _completed_result(
                    command,
                    stdout=_remote_v_output(
                        [
                            (
                                "origin",
                                "https://example.invalid/project.git",
                                "https://example.invalid/project.git",
                            ),
                        ],
                    ),
                )

            return _completed_result(command, stdout="")

        if command[1:3] == ("remote", "remove"):
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.remove_remote(
        "/source/project",
        "origin",
    )

    assert result.removed_name == "origin"
    assert result.remotes == ()

    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
        (
            "git",
            "remote",
            "remove",
            "--",
            "origin",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
    ]


def test_remove_remote_rejects_unknown_name(
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
        GitRemoteNotFoundError,
        match="does not exist",
    ):
        service.remove_remote(
            "/source/project",
            "origin",
        )


def test_remove_remote_rejects_blank_name() -> None:
    service = GitService()

    with pytest.raises(
        GitRemoteNameError,
        match="must not be empty",
    ):
        service.remove_remote(
            "/source/project",
            "",
        )


def test_remove_remote_propagates_git_command_failure(
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

        if command[1:3] == ("remote", "-v"):
            return _completed_result(
                command,
                stdout=_remote_v_output(
                    [
                        (
                            "origin",
                            "https://example.invalid/project.git",
                            "https://example.invalid/project.git",
                        ),
                    ],
                ),
            )

        if command[1:3] == ("remote", "remove"):
            return _completed_result(
                command,
                return_code=128,
                stderr="fatal: remote remove failed",
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="remote remove failed",
    ):
        service.remove_remote(
            "/source/project",
            "origin",
        )


# --- rename_remote -----------------------------------------------------------


def test_rename_remote_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    remote_v_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal remote_v_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1:3] == ("remote", "-v"):
            remote_v_reads += 1

            if remote_v_reads == 1:
                return _completed_result(
                    command,
                    stdout=_remote_v_output(
                        [
                            (
                                "origin",
                                "https://example.invalid/project.git",
                                "https://example.invalid/project.git",
                            ),
                        ],
                    ),
                )

            return _completed_result(
                command,
                stdout=_remote_v_output(
                    [
                        (
                            "upstream",
                            "https://example.invalid/project.git",
                            "https://example.invalid/project.git",
                        ),
                    ],
                ),
            )

        if command[1:3] == ("remote", "rename"):
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.rename_remote(
        "/source/project",
        "origin",
        "upstream",
    )

    assert result.previous_name == "origin"
    assert result.remote.name == "upstream"
    assert len(result.remotes) == 1

    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
        (
            "git",
            "remote",
            "rename",
            "--",
            "origin",
            "upstream",
        ),
        (
            "git",
            "remote",
            "-v",
        ),
    ]


def test_rename_remote_rejects_unknown_name(
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
        GitRemoteNotFoundError,
        match="does not exist",
    ):
        service.rename_remote(
            "/source/project",
            "origin",
            "upstream",
        )


def test_rename_remote_rejects_existing_new_name(
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
            stdout=_remote_v_output(
                [
                    (
                        "origin",
                        "https://example.invalid/project.git",
                        "https://example.invalid/project.git",
                    ),
                    (
                        "upstream",
                        "https://example.invalid/upstream.git",
                        "https://example.invalid/upstream.git",
                    ),
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
        GitRemoteAlreadyExistsError,
        match="already exists",
    ):
        service.rename_remote(
            "/source/project",
            "origin",
            "upstream",
        )


def test_rename_remote_allows_same_name_no_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_rename_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_rename_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1:3] == ("remote", "-v"):
            return _completed_result(
                command,
                stdout=_remote_v_output(
                    [
                        (
                            "origin",
                            "https://example.invalid/project.git",
                            "https://example.invalid/project.git",
                        ),
                    ],
                ),
            )

        if command[1:3] == ("remote", "rename"):
            captured_rename_command = command
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.rename_remote(
        "/source/project",
        "origin",
        "origin",
    )

    assert result.remote.name == "origin"
    assert captured_rename_command == (
        "git",
        "remote",
        "rename",
        "--",
        "origin",
        "origin",
    )


def test_rename_remote_propagates_git_command_failure(
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

        if command[1:3] == ("remote", "-v"):
            return _completed_result(
                command,
                stdout=_remote_v_output(
                    [
                        (
                            "origin",
                            "https://example.invalid/project.git",
                            "https://example.invalid/project.git",
                        ),
                    ],
                ),
            )

        if command[1:3] == ("remote", "rename"):
            return _completed_result(
                command,
                return_code=128,
                stderr="fatal: remote rename failed",
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="remote rename failed",
    ):
        service.rename_remote(
            "/source/project",
            "origin",
            "upstream",
        )
