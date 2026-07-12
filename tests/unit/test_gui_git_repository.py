"""Unit tests for the Git Repository panel, against a real Git repository."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.services.git import GitService


def _run(
    args: list[str],
    cwd: Path,
) -> None:
    """Run one Git subprocess command for test repository setup."""

    subprocess.run(
        [
            "git",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _init_repository_with_history(
    path: Path,
) -> None:
    """Initialize a real Git repository with one commit, a branch, a tag, and a remote."""

    _run(
        [
            "init",
            "-q",
        ],
        path,
    )
    _run(
        [
            "config",
            "user.email",
            "test@example.com",
        ],
        path,
    )
    _run(
        [
            "config",
            "user.name",
            "Test User",
        ],
        path,
    )
    (
        path / "main.cbl"
    ).write_text(
        "x",
    )
    _run(
        [
            "add",
            ".",
        ],
        path,
    )
    _run(
        [
            "commit",
            "-q",
            "-m",
            "Initial commit",
        ],
        path,
    )
    _run(
        [
            "branch",
            "feature-x",
        ],
        path,
    )
    _run(
        [
            "tag",
            "-a",
            "v1.0",
            "-m",
            "release",
        ],
        path,
    )
    _run(
        [
            "remote",
            "add",
            "origin",
            "https://example.com/repo.git",
        ],
        path,
    )


def test_widget_shows_empty_state_with_no_repository(
    qapp,
) -> None:
    widget = GitRepositoryWidget(
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
    widget = GitRepositoryWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_widget_lists_branches_tags_remotes_and_history(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository_with_history(
        tmp_path,
    )

    widget = GitRepositoryWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    assert (
        widget._stack.currentWidget()
        is widget._tabs
    )

    branch_labels = [
        widget._branches_list.item(
            index,
        ).text()
        for index in range(
            widget._branches_list.count(),
        )
    ]
    assert any(
        "feature-x" in label
        for label in branch_labels
    )

    current_branch_labels = [
        label
        for label in branch_labels
        if label.startswith(
            "* ",
        )
    ]
    assert len(current_branch_labels) == 1
    assert (
        "master" in current_branch_labels[0]
        or "main" in current_branch_labels[0]
    )

    assert widget._tags_list.count() == 1
    assert (
        "v1.0"
        in widget._tags_list.item(
            0,
        ).text()
    )

    assert widget._remotes_list.count() == 1
    assert (
        "origin"
        in widget._remotes_list.item(
            0,
        ).text()
    )
    assert (
        "https://example.com/repo.git"
        in widget._remotes_list.item(
            0,
        ).text()
    )

    assert widget._history_list.count() == 1
    assert (
        "Initial commit"
        in widget._history_list.item(
            0,
        ).text()
    )


def test_double_click_switches_branch(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository_with_history(
        tmp_path,
    )

    widget = GitRepositoryWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    feature_item = next(
        widget._branches_list.item(
            index,
        )
        for index in range(
            widget._branches_list.count(),
        )
        if "feature-x"
        in widget._branches_list.item(
            index,
        ).text()
    )

    widget._switch_to_item(
        feature_item,
    )

    current_branch_label = next(
        widget._branches_list.item(
            index,
        ).text()
        for index in range(
            widget._branches_list.count(),
        )
        if widget._branches_list.item(
            index,
        ).text().startswith(
            "* ",
        )
    )
    assert "feature-x" in current_branch_label


def test_switch_to_unknown_branch_shows_critical_error(
    qapp,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repository_with_history(
        tmp_path,
    )

    widget = GitRepositoryWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt

    bogus_item = QListWidgetItem(
        "  does-not-exist",
    )
    bogus_item.setData(
        Qt.ItemDataRole.UserRole,
        "does-not-exist",
    )

    shown = []
    monkeypatch.setattr(
        "opencobol2.gui.git_repository.QMessageBox.critical",
        lambda *args, **kwargs: shown.append(
            args,
        ),
    )

    widget._switch_to_item(
        bogus_item,
    )

    assert len(shown) == 1


def test_set_repository_path_switches_and_clears(
    qapp,
    tmp_path: Path,
) -> None:
    _init_repository_with_history(
        tmp_path,
    )

    widget = GitRepositoryWidget(
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
    assert widget._branches_list.count() == 2

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
        match=(
            "Git Repository widget service must be GitService"
        ),
    ):
        GitRepositoryWidget(
            git_service=object(),  # type: ignore[arg-type]
        )
