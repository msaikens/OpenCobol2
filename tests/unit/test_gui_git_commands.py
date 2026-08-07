"""Unit tests for the Git menu commands (Fetch/Pull/Push/Sync/Clone/Create/Manage Branches).

Fetch/Pull/Push/Sync mock at the same `invoke_git_process` boundary as
`test_git_sync.py` -- these tests exist to prove each handler calls the
right `GitService` method and reacts correctly to its result/error, not
to re-verify the underlying Git command construction (already covered
there). Create/Clone Repository instead run a real, local-only `git`
subprocess (no network involved), matching `_init_repository`'s existing
convention elsewhere in the test suite.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

from opencobol2.git import GitCommandExecutionStatus, GitCommandResult
from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.gui.git_commands import (
    create_clone_repository_handler,
    create_create_repository_handler,
    create_fetch_handler,
    create_manage_branches_handler,
    create_pull_handler,
    create_push_handler,
    create_sync_handler,
)
from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import create_project
from opencobol2.services import git as git_service_module
from opencobol2.services.git import GitService


def _init_repository(
    path: Path,
) -> None:
    """Initialize a real, minimally-configured Git repository for testing."""

    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
    )


def _completed_result(
    command: tuple[str, ...],
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> GitCommandResult:
    return GitCommandResult(
        command=command,
        status=GitCommandExecutionStatus.COMPLETED,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
    )


def _project_explorer_for(
    tmp_path: Path,
) -> ProjectExplorerWidget:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    return ProjectExplorerWidget(project)


def _rev_parse_ok(
    tmp_path: Path,
    command: tuple[str, ...],
) -> GitCommandResult | None:
    """Return a successful `rev-parse --show-toplevel` result, or `None`."""

    if "rev-parse" in command:
        return _completed_result(
            command,
            stdout=f"{tmp_path}\n",
        )

    return None


def _status_output() -> str:
    """Build porcelain-v2 output for a clean, tracked repository.

    Every real fetch/pull/push additionally issues a follow-up `git
    status` to build its result's `repository_status` -- any fake
    `invoke_git_process` below must answer that third call too, not
    just the leading `rev-parse` and the operation itself.
    """

    return (
        "# branch.oid abc123\0"
        "# branch.head main\0"
        "# branch.upstream origin/main\0"
        "# branch.ab +0 -0\0"
    )


# --- Fetch --------------------------------------------------------------


def test_fetch_handler_shows_message_when_no_project_is_open(
    qapp,
) -> None:
    git_service = GitService()
    handler = create_fetch_handler(
        git_service=git_service,
        project_explorer=ProjectExplorerWidget(None),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert mock_information.call_args[0][1] == "Fetch"


def test_fetch_handler_warns_when_project_root_is_not_a_repository(
    qapp,
    tmp_path: Path,
) -> None:
    git_service = GitService()
    handler = create_fetch_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "No Git repository found" in mock_warning.call_args[0][2]


def test_fetch_handler_completes_successfully(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        if "fetch" in command:
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_fetch_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert "Fetch completed" in mock_information.call_args[0][2]


def test_fetch_handler_warns_on_a_git_command_failure(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: could not read from remote repository",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_fetch_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "could not read from remote repository" in (
        mock_warning.call_args[0][2]
    )


# --- Pull -----------------------------------------------------------------


def test_pull_handler_completes_successfully(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        if "pull" in command:
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_pull_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert "Pull completed" in mock_information.call_args[0][2]


def test_pull_handler_warns_on_merge_conflict_and_still_refreshes_panels(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        return _completed_result(
            command,
            return_code=1,
            stdout=(
                "CONFLICT (content): Merge conflict in PAYROLL.cob\n"
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    git_changes_widget = GitChangesWidget(git_service=git_service)
    handler = create_pull_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=git_changes_widget,
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with (
        patch(
            "opencobol2.gui.git_commands.QMessageBox.warning",
        ) as mock_warning,
        patch.object(
            GitChangesWidget,
            "refresh",
        ) as mock_refresh,
    ):
        handler(None)

    mock_warning.assert_called_once()
    assert "merge conflicts" in mock_warning.call_args[0][2]
    mock_refresh.assert_called_once()


# --- Push -------------------------------------------------------------------


def test_push_handler_completes_successfully(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        if "push" in command:
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_push_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert "Push completed" in mock_information.call_args[0][2]


def test_push_handler_warns_on_a_git_command_failure(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: authentication failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_push_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "authentication failed" in mock_warning.call_args[0][2]


# --- Sync -------------------------------------------------------------------


def test_sync_handler_pulls_then_pushes_on_success(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen_subcommands: list[str] = []

    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        if "pull" in command:
            seen_subcommands.append("pull")
            return _completed_result(command)

        if "push" in command:
            seen_subcommands.append("push")
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_sync_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    assert seen_subcommands == ["pull", "push"]
    mock_information.assert_called_once()
    assert "pulled, then pushed" in mock_information.call_args[0][2]


def test_sync_handler_stops_before_pushing_when_pull_fails(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen_subcommands: list[str] = []

    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        seen_subcommands.append(command[1])
        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: unable to access remote",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_sync_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    assert seen_subcommands == ["pull"]
    mock_warning.assert_called_once()
    assert "Pull failed" in mock_warning.call_args[0][2]


def test_sync_handler_reports_push_failure_after_a_successful_pull(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def invoke_git_process(**kwargs: object) -> GitCommandResult:
        command = kwargs["command"]
        rev_parse_result = _rev_parse_ok(tmp_path, command)

        if rev_parse_result is not None:
            return rev_parse_result

        if "pull" in command:
            return _completed_result(command)

        if "status" in command:
            return _completed_result(
                command,
                stdout=_status_output(),
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: authentication failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    git_service = GitService()
    handler = create_sync_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "Push failed" in mock_warning.call_args[0][2]


# --- Manage Branches ---------------------------------------------------------


def test_manage_branches_handler_reveals_panel_and_switches_to_branches_tab(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    git_service = GitService()
    git_repository_widget = GitRepositoryWidget(
        git_service=git_service,
        repository_path=tmp_path,
    )
    git_repository_widget._tabs.setCurrentIndex(2)
    reveal_mock = Mock()
    handler = create_manage_branches_handler(
        git_repository_widget=git_repository_widget,
        reveal_git_repository_panel=reveal_mock,
    )

    handler(None)

    reveal_mock.assert_called_once()
    assert git_repository_widget._tabs.currentIndex() == 0


def test_manage_branches_handler_is_a_no_op_without_a_repository(
    qapp,
) -> None:
    git_service = GitService()
    git_repository_widget = GitRepositoryWidget(git_service=git_service)
    git_repository_widget._tabs.setCurrentIndex(2)
    reveal_mock = Mock()
    handler = create_manage_branches_handler(
        git_repository_widget=git_repository_widget,
        reveal_git_repository_panel=reveal_mock,
    )

    handler(None)

    reveal_mock.assert_called_once()
    assert git_repository_widget._tabs.currentIndex() == 2


# --- Create Repository (real, local-only `git init`) -------------------------


def test_create_repository_handler_shows_message_when_no_project_is_open(
    qapp,
) -> None:
    git_service = GitService()
    handler = create_create_repository_handler(
        git_service=git_service,
        project_explorer=ProjectExplorerWidget(None),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()


def test_create_repository_handler_initializes_a_real_repository(
    qapp,
    tmp_path: Path,
) -> None:
    git_service = GitService()
    git_changes_widget = GitChangesWidget(git_service=git_service)
    git_repository_widget = GitRepositoryWidget(git_service=git_service)
    handler = create_create_repository_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=git_changes_widget,
        git_repository_widget=git_repository_widget,
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    assert (tmp_path / ".git").is_dir()
    assert git_changes_widget.repository_path == tmp_path
    assert git_repository_widget.repository_path == tmp_path
    mock_information.assert_called_once()
    assert "created" in mock_information.call_args[0][2]


def test_create_repository_handler_warns_when_one_already_exists(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    git_service = GitService()
    handler = create_create_repository_handler(
        git_service=git_service,
        project_explorer=_project_explorer_for(tmp_path),
        git_changes_widget=GitChangesWidget(git_service=git_service),
        git_repository_widget=GitRepositoryWidget(git_service=git_service),
    )

    with patch(
        "opencobol2.gui.git_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert "already exists" in mock_information.call_args[0][2]


# --- Clone Repository (real, local-only `git clone`) --------------------------


def test_clone_repository_handler_does_nothing_when_the_source_prompt_is_cancelled(
    qapp,
) -> None:
    git_service = GitService()
    handler = create_clone_repository_handler(
        git_service=git_service,
    )

    with (
        patch(
            "opencobol2.gui.git_commands.QInputDialog.getText",
            return_value=("", False),
        ),
        patch(
            "opencobol2.gui.git_commands.QFileDialog.getExistingDirectory",
        ) as mock_get_directory,
    ):
        handler(None)

    assert not mock_get_directory.called


def test_clone_repository_handler_clones_a_real_local_repository(
    qapp,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _init_repository(source)
    (source / "README.md").write_text("hello")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=source,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial commit"],
        cwd=source,
        check=True,
    )

    destination = tmp_path / "destination"
    git_service = GitService()
    handler = create_clone_repository_handler(
        git_service=git_service,
    )

    with (
        patch(
            "opencobol2.gui.git_commands.QInputDialog.getText",
            return_value=(str(source), True),
        ),
        patch(
            "opencobol2.gui.git_commands.QFileDialog.getExistingDirectory",
            return_value=str(destination),
        ),
        patch(
            "opencobol2.gui.git_commands.QMessageBox.information",
        ) as mock_information,
    ):
        handler(None)

    assert (destination / ".git").is_dir()
    assert (destination / "README.md").is_file()
    mock_information.assert_called_once()
    assert "Cloned into" in mock_information.call_args[0][2]
