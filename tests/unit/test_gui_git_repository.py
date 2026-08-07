"""Unit tests for the Git Repository panel, against a real Git repository."""

from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

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


def test_new_branch_creates_branch(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QInputDialog.getText",
        return_value=(
            "feature-y",
            True,
        ),
    ):
        widget._new_branch()

    labels = [
        widget._branches_list.item(
            index,
        ).text()
        for index in range(
            widget._branches_list.count(),
        )
    ]
    assert any(
        "feature-y" in label
        for label in labels
    )


def test_new_branch_cancelled_does_nothing(
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
    original_count = (
        widget._branches_list.count()
    )

    with patch(
        "opencobol2.gui.git_repository."
        "QInputDialog.getText",
        return_value=(
            "",
            False,
        ),
    ):
        widget._new_branch()

    assert (
        widget._branches_list.count()
        == original_count
    )


def test_new_branch_with_a_dash_prefixed_name_shows_an_error_instead_of_crashing(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §GitPanels-1: `GitService.create_branch` correctly rejects
    # a dash-prefixed ref name via a bare `ValueError`, but
    # `_COMMON_GIT_ERRORS` never included it, so the error propagated
    # all the way out of this handler uncaught.
    _init_repository_with_history(
        tmp_path,
    )
    widget = GitRepositoryWidget(
        git_service=GitService(),
        repository_path=tmp_path,
    )

    with (
        patch(
            "opencobol2.gui.git_repository."
            "QInputDialog.getText",
            return_value=(
                "-weird",
                True,
            ),
        ),
        patch(
            "opencobol2.gui.git_repository."
            "QMessageBox.critical",
        ) as mock_critical,
    ):
        widget._new_branch()

    mock_critical.assert_called_once()


def test_new_tag_with_a_dash_prefixed_name_shows_an_error_instead_of_crashing(
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

    with (
        patch(
            "opencobol2.gui.git_repository."
            "QInputDialog.getText",
            side_effect=[
                (
                    "-weird-tag",
                    True,
                ),
                (
                    "",
                    True,
                ),
            ],
        ),
        patch(
            "opencobol2.gui.git_repository."
            "QMessageBox.critical",
        ) as mock_critical,
    ):
        widget._new_tag()

    mock_critical.assert_called_once()


def test_refresh_falls_back_to_empty_state_when_the_repository_directory_vanishes(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §GitPanels-2: only `GitRepositoryNotFoundError` was
    # caught here -- if the directory itself (not just `.git`)
    # vanishes out from under a still-open panel, the
    # missing-executable-shaped `GitExecutableUnavailableError`
    # propagated uncaught on the very next refresh.
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

    import os
    import shutil
    import stat

    def _force_remove(
        func,
        path,
        _exc_info,
    ) -> None:
        # Git marks its own object files read-only on Windows.
        os.chmod(
            path,
            stat.S_IWRITE,
        )
        func(
            path,
        )

    shutil.rmtree(
        tmp_path,
        onexc=_force_remove,
    )

    widget.refresh()

    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_delete_branch_removes_it_when_confirmed(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    ):
        widget._delete_branch(
            "feature-x",
        )

    labels = [
        widget._branches_list.item(
            index,
        ).text()
        for index in range(
            widget._branches_list.count(),
        )
    ]
    assert not any(
        "feature-x" in label
        for label in labels
    )


def test_delete_branch_kept_when_not_confirmed(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.No
        ),
    ):
        widget._delete_branch(
            "feature-x",
        )

    labels = [
        widget._branches_list.item(
            index,
        ).text()
        for index in range(
            widget._branches_list.count(),
        )
    ]
    assert any(
        "feature-x" in label
        for label in labels
    )


def test_delete_branch_reports_error_for_unknown_branch(
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

    with (
        patch(
            "opencobol2.gui.git_repository."
            "QMessageBox.question",
            return_value=(
                QMessageBox.StandardButton.Yes
            ),
        ),
        patch(
            "opencobol2.gui.git_repository."
            "QMessageBox.critical",
        ) as mock_critical,
    ):
        widget._delete_branch(
            "does-not-exist",
        )

    mock_critical.assert_called_once()


def test_new_tag_creates_lightweight_tag(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QInputDialog.getText",
        side_effect=[
            (
                "v2.0",
                True,
            ),
            (
                "",
                True,
            ),
        ],
    ):
        widget._new_tag()

    labels = [
        widget._tags_list.item(
            index,
        ).text()
        for index in range(
            widget._tags_list.count(),
        )
    ]
    assert any(
        "v2.0" in label
        for label in labels
    )


def test_delete_tag_removes_it_when_confirmed(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    ):
        widget._delete_tag(
            "v1.0",
        )

    assert widget._tags_list.count() == 0


def test_add_remote_creates_remote(
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
    # The fixture already adds an "origin" remote; use a different name.
    with patch(
        "opencobol2.gui.git_repository."
        "QInputDialog.getText",
        side_effect=[
            (
                "upstream",
                True,
            ),
            (
                "https://example.com/upstream.git",
                True,
            ),
        ],
    ):
        widget._add_remote()

    labels = [
        widget._remotes_list.item(
            index,
        ).text()
        for index in range(
            widget._remotes_list.count(),
        )
    ]
    assert any(
        "upstream" in label
        for label in labels
    )


def test_remove_remote_deletes_it_when_confirmed(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    ):
        widget._remove_remote(
            "origin",
        )

    assert widget._remotes_list.count() == 0


def test_rename_remote_renames_it(
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

    with patch(
        "opencobol2.gui.git_repository."
        "QInputDialog.getText",
        return_value=(
            "renamed",
            True,
        ),
    ):
        widget._rename_remote(
            "origin",
        )

    labels = [
        widget._remotes_list.item(
            index,
        ).text()
        for index in range(
            widget._remotes_list.count(),
        )
    ]
    assert any(
        "renamed" in label
        for label in labels
    )
    assert not any(
        label.startswith(
            "origin ",
        )
        for label in labels
    )
