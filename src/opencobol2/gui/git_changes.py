"""Renders a repository's Git working tree status and staging controls.

The staging helpers (`_stage_paths`, `_unstage_paths`, `_stage_all`,
and `_unstage_all`) all share the same set of caught Git-service
errors. Unlike `_commit` in this same module, they previously had no
exception handling of their own at all: a real Git failure during any
of them -- a path deleted out from under a stale list, a vanished
repository directory, a timeout -- would have propagated completely
uncaught.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from opencobol2.git import (
    GitChange,
    GitChangeStatus,
    GitRepositoryStatus,
)
from opencobol2.services.git import (
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitCommitMessageError,
    GitExecutableUnavailableError,
    GitNothingToCommitError,
    GitRepositoryNotFoundError,
    GitService,
)


_STATUS_LABELS = {
    GitChangeStatus.MODIFIED: "M",
    GitChangeStatus.ADDED: "A",
    GitChangeStatus.DELETED: "D",
    GitChangeStatus.RENAMED: "R",
    GitChangeStatus.COPIED: "C",
    GitChangeStatus.TYPE_CHANGED: "T",
    GitChangeStatus.UNMERGED: "U",
    GitChangeStatus.UNTRACKED: "?",
}

_PATH_DATA_ROLE = Qt.ItemDataRole.UserRole

_COMMON_GIT_ERRORS = (
    GitRepositoryNotFoundError,
    GitExecutableUnavailableError,
    GitCommandFailedError,
    GitCommandTimedOutError,
)


class GitChangesWidget(QWidget):
    """Shows working tree status for one Git repository with staging controls."""

    def __init__(
        self,
        *,
        git_service: GitService,
        repository_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the Git Changes panel, optionally already showing a repository.

        :param git_service: The service used to query and mutate Git
            repository state.
        :param repository_path: An optional repository to display
            immediately; if None, the panel starts in its empty state.
        :param parent: The optional parent widget.
        :raises TypeError: If `git_service` is not a :class:`GitService`.
        """

        super().__init__(
            parent,
        )

        if not isinstance(
            git_service,
            GitService,
        ):
            raise TypeError(
                "Git Changes widget service must be GitService."
            )

        self._git_service = git_service
        self._repository_path: Path | None = None

        layout = QVBoxLayout(
            self,
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._empty_label = QLabel(
            "No Git repository.",
        )
        self._empty_label.setMargin(
            8,
        )

        self._content = QWidget()
        content_layout = QVBoxLayout(
            self._content,
        )

        self._branch_label = QLabel()
        content_layout.addWidget(
            self._branch_label,
        )

        content_layout.addWidget(
            QLabel(
                "Staged Changes",
            )
        )
        self._staged_list = QListWidget()
        self._staged_list.itemDoubleClicked.connect(
            self._unstage_item,
        )
        content_layout.addWidget(
            self._staged_list,
        )

        content_layout.addWidget(
            QLabel(
                "Changes",
            )
        )
        self._unstaged_list = QListWidget()
        self._unstaged_list.itemDoubleClicked.connect(
            self._stage_item,
        )
        content_layout.addWidget(
            self._unstaged_list,
        )

        button_row = QHBoxLayout()
        self._stage_all_button = QPushButton(
            "Stage All",
        )
        self._stage_all_button.clicked.connect(
            self._stage_all,
        )
        self._unstage_all_button = QPushButton(
            "Unstage All",
        )
        self._unstage_all_button.clicked.connect(
            self._unstage_all,
        )
        button_row.addWidget(
            self._stage_all_button,
        )
        button_row.addWidget(
            self._unstage_all_button,
        )
        content_layout.addLayout(
            button_row,
        )

        self._message_edit = QLineEdit()
        self._message_edit.setPlaceholderText(
            "Commit message",
        )
        content_layout.addWidget(
            self._message_edit,
        )

        self._commit_button = QPushButton(
            "Commit",
        )
        self._commit_button.clicked.connect(
            self._commit,
        )
        content_layout.addWidget(
            self._commit_button,
        )

        self._stack = QStackedWidget()
        self._stack.addWidget(
            self._empty_label,
        )
        self._stack.addWidget(
            self._content,
        )
        layout.addWidget(
            self._stack,
        )

        self.set_repository_path(
            repository_path,
        )

    @property
    def repository_path(
        self,
    ) -> Path | None:
        """Return the repository path currently displayed, if any.

        :returns: The currently displayed repository path, or None if
            the panel is showing its empty state.
        """

        return self._repository_path

    def set_repository_path(
        self,
        path: Path | None,
    ) -> None:
        """Display a repository's status, or clear back to the empty state.

        :param path: The repository to display, or None to clear back
            to the empty state.
        :returns: None. The panel is refreshed in place.
        """

        self._repository_path = path
        self.refresh()

    def refresh(
        self,
    ) -> None:
        """Re-fetch and redisplay the current repository's status.

        Both `GitRepositoryNotFoundError` and
        `GitExecutableUnavailableError` fall back to the same empty
        state here: if the repository's directory itself (not just
        `.git`) vanishes out from under a still-open panel, the
        missing-executable-shaped `GitExecutableUnavailableError` must
        be caught too, rather than propagating uncaught on the very
        next refresh.

        :returns: None. The panel's stacked widget and staged/unstaged
            lists are updated in place.
        """

        if self._repository_path is None:
            self._stack.setCurrentWidget(
                self._empty_label,
            )
            return

        try:
            status = self._git_service.get_status(
                self._repository_path,
            )
        except (
            GitRepositoryNotFoundError,
            GitExecutableUnavailableError,
        ):
            # Editor §GitPanels-2: only `GitRepositoryNotFoundError`
            # was caught here -- if the repository's directory itself
            # (not just `.git`) vanishes out from under a still-open
            # panel, the missing-executable-shaped
            # `GitExecutableUnavailableError` propagated uncaught on
            # the very next refresh instead of falling back to this
            # same empty state.
            self._stack.setCurrentWidget(
                self._empty_label,
            )
            return

        self._render_status(
            status,
        )
        self._stack.setCurrentWidget(
            self._content,
        )

    def _render_status(
        self,
        status: GitRepositoryStatus,
    ) -> None:
        """Populate the branch label and staged/unstaged lists."""

        if status.branch_name is not None:
            self._branch_label.setText(
                f"On branch: {status.branch_name}",
            )
        elif status.head_oid is not None:
            self._branch_label.setText(
                f"Detached at {status.head_oid[:7]}",
            )
        else:
            self._branch_label.setText(
                "No commits yet",
            )

        self._staged_list.clear()
        self._unstaged_list.clear()

        for change in status.changes:
            if change.staged:
                self._staged_list.addItem(
                    _create_change_item(
                        change,
                        change.index_status,
                    )
                )

            if change.unstaged:
                self._unstaged_list.addItem(
                    _create_change_item(
                        change,
                        change.worktree_status,
                    )
                )

    def _stage_item(
        self,
        item: QListWidgetItem,
    ) -> None:
        """Stage the path represented by one unstaged-list item."""

        self._stage_paths(
            [
                item.data(
                    _PATH_DATA_ROLE,
                ),
            ]
        )

    def _unstage_item(
        self,
        item: QListWidgetItem,
    ) -> None:
        """Unstage the path represented by one staged-list item."""

        self._unstage_paths(
            [
                item.data(
                    _PATH_DATA_ROLE,
                ),
            ]
        )

    def _stage_paths(
        self,
        paths: list[str],
    ) -> None:
        """Stage repository-relative paths and refresh the display."""

        if self._repository_path is None:
            return

        try:
            self._git_service.stage_paths(
                self._repository_path,
                paths,
            )
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.critical(
                self,
                "Stage Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _unstage_paths(
        self,
        paths: list[str],
    ) -> None:
        """Unstage repository-relative paths and refresh the display."""

        if self._repository_path is None:
            return

        try:
            self._git_service.unstage_paths(
                self._repository_path,
                paths,
            )
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.critical(
                self,
                "Unstage Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _stage_all(
        self,
    ) -> None:
        """Stage every worktree change."""

        if self._repository_path is None:
            return

        try:
            self._git_service.stage_all(
                self._repository_path,
            )
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.critical(
                self,
                "Stage Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _unstage_all(
        self,
    ) -> None:
        """Unstage every index change."""

        if self._repository_path is None:
            return

        try:
            self._git_service.unstage_all(
                self._repository_path,
            )
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.critical(
                self,
                "Unstage Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _commit(
        self,
    ) -> None:
        """Commit currently staged changes using the typed message."""

        if self._repository_path is None:
            return

        message = self._message_edit.text().strip()

        if not message:
            QMessageBox.information(
                self,
                "Commit",
                "Enter a commit message first.",
            )
            return

        try:
            self._git_service.commit_staged(
                self._repository_path,
                message,
            )
        except (
            GitCommitMessageError,
            GitNothingToCommitError,
            GitCommandFailedError,
        ) as error:
            QMessageBox.critical(
                self,
                "Commit Failed",
                str(
                    error,
                ),
            )
            return

        self._message_edit.clear()
        self.refresh()


def _create_change_item(
    change: GitChange,
    status: GitChangeStatus,
) -> QListWidgetItem:
    """Create one list item for a changed path with its status letter."""

    label = _STATUS_LABELS.get(
        status,
        "?",
    )
    item = QListWidgetItem(
        f"[{label}] {change.path}",
    )
    item.setData(
        _PATH_DATA_ROLE,
        str(
            change.path,
        ),
    )

    return item
