"""Unit tests for the Git Changes panel, against a real Git repository."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.services.git import GitService


def _init_repository(
    path: Path,
) -> None:
    """Initialize a real, minimally-configured Git repository for testing."""

    subprocess.run(
        [
            "git",
            "init",
            "-q",
        ],
        cwd=path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "test@example.com",
        ],
        cwd=path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.name",
            "Test User",
        ],
        cwd=path,
        check=True,
    )


def test_widget_shows_empty_state_with_no_repository(
    qapp,
) -> None:
    widget = GitChangesWidget(
        git_service=GitService(),
    )

    assert widget.repository_path is None
    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_widget_shows_empty_state_for_non_repository_path(
    qapp,
    tmp_path: Path,
) -> None:
    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_widget_shows_branch_and_untracked_file(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "x",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    assert (
        "master" in widget._branch_label.text()
        or "main" in widget._branch_label.text()
    )
    assert widget._unstaged_list.count() == 1
    assert (
        widget._unstaged_list.item(
            0,
        ).text()
        == "[?] main.cbl"
    )
    assert widget._staged_list.count() == 0
    assert (
        widget._stack.currentWidget()
        is widget._content
    )


def test_double_click_stages_and_unstages_a_file(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "x",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    widget._stage_item(
        widget._unstaged_list.item(
            0,
        )
    )

    assert widget._unstaged_list.count() == 0
    assert widget._staged_list.count() == 1
    assert (
        widget._staged_list.item(
            0,
        ).text()
        == "[A] main.cbl"
    )

    widget._unstage_item(
        widget._staged_list.item(
            0,
        )
    )

    assert widget._staged_list.count() == 0
    assert widget._unstaged_list.count() == 1


def test_stage_all_and_unstage_all_buttons(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "a.cbl"
    ).write_text(
        "a",
    )
    (
        tmp_path / "b.cbl"
    ).write_text(
        "b",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    assert widget._unstaged_list.count() == 2

    widget._stage_all()

    assert widget._staged_list.count() == 2
    assert widget._unstaged_list.count() == 0

    widget._unstage_all()

    assert widget._staged_list.count() == 0
    assert widget._unstaged_list.count() == 2


def test_commit_with_message_clears_staged_changes(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "x",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )
    widget._stage_all()
    widget._message_edit.setText(
        "Initial commit",
    )

    widget._commit()

    assert widget._staged_list.count() == 0
    assert (
        widget._message_edit.text()
        == ""
    )

    log = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Initial commit" in log.stdout


def test_commit_without_message_shows_information_and_does_not_commit(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "x",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )
    widget._stage_all()

    shown = []
    monkeypatch.setattr(
        "opencobol2.gui.git_changes.QMessageBox.information",
        lambda *args, **kwargs: shown.append(
            args,
        ),
    )

    widget._commit()

    assert len(shown) == 1
    assert widget._staged_list.count() == 1


def test_commit_with_nothing_staged_shows_critical_error(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repository(
        tmp_path,
    )

    widget = GitChangesWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )
    widget._message_edit.setText(
        "Nothing to commit",
    )

    shown = []
    monkeypatch.setattr(
        "opencobol2.gui.git_changes.QMessageBox.critical",
        lambda *args, **kwargs: shown.append(
            args,
        ),
    )

    widget._commit()

    assert len(shown) == 1


def test_set_repository_path_switches_and_clears(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository(
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "x",
    )

    widget = GitChangesWidget(
        git_service=GitService(),
    )

    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )

    widget.set_repository_path(
        tmp_path,
    )

    assert widget.repository_path == tmp_path
    assert widget._unstaged_list.count() == 1

    widget.set_repository_path(
        None,
    )

    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_widget_rejects_non_git_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match="Git Changes widget service must be GitService",
    ):
        GitChangesWidget(
            git_service=object(),  # type: ignore[arg-type]
        )
