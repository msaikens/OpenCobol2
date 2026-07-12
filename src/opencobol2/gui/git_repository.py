"""Renders a repository's branches, tags, remotes, and commit history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from opencobol2.git import (
    GitBranch,
    GitCommitLogEntry,
    GitRemote,
    GitTag,
)
from opencobol2.services.git import (
    GitBranchNotFoundError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitExecutableUnavailableError,
    GitRepositoryNotFoundError,
    GitService,
)


_NAME_DATA_ROLE = Qt.ItemDataRole.UserRole


class GitRepositoryWidget(QWidget):
    """Shows branches, tags, remotes, and history for one Git repository."""

    def __init__(
        self,
        *,
        git_service: GitService,
        repository_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the Git Repository panel, optionally already showing a repository."""

        super().__init__(
            parent,
        )

        if not isinstance(
            git_service,
            GitService,
        ):
            raise TypeError(
                "Git Repository widget service must be GitService."
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

        self._tabs = QTabWidget()

        self._branches_list = QListWidget()
        self._branches_list.itemDoubleClicked.connect(
            self._switch_to_item,
        )
        self._tabs.addTab(
            self._branches_list,
            "Branches",
        )

        self._tags_list = QListWidget()
        self._tabs.addTab(
            self._tags_list,
            "Tags",
        )

        self._remotes_list = QListWidget()
        self._tabs.addTab(
            self._remotes_list,
            "Remotes",
        )

        self._history_list = QListWidget()
        self._tabs.addTab(
            self._history_list,
            "History",
        )

        self._stack = QStackedWidget()
        self._stack.addWidget(
            self._empty_label,
        )
        self._stack.addWidget(
            self._tabs,
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
        """Return the repository path currently displayed, if any."""

        return self._repository_path

    def set_repository_path(
        self,
        path: Path | None,
    ) -> None:
        """Display a repository's branches/tags/remotes/history, or clear it."""

        self._repository_path = path
        self.refresh()

    def refresh(
        self,
    ) -> None:
        """Re-fetch and redisplay every tab from the current repository."""

        if self._repository_path is None:
            self._stack.setCurrentWidget(
                self._empty_label,
            )
            return

        try:
            branches = self._git_service.list_branches(
                self._repository_path,
            )
            tags = self._git_service.list_tags(
                self._repository_path,
            )
            remotes = self._git_service.get_remotes(
                self._repository_path,
            )
            history = self._git_service.get_history(
                self._repository_path,
                max_count=100,
            )
        except GitRepositoryNotFoundError:
            self._stack.setCurrentWidget(
                self._empty_label,
            )
            return

        self._render_branches(
            branches,
        )
        self._render_tags(
            tags,
        )
        self._render_remotes(
            remotes,
        )
        self._render_history(
            history,
        )
        self._stack.setCurrentWidget(
            self._tabs,
        )

    def _render_branches(
        self,
        branches: tuple[GitBranch, ...],
    ) -> None:
        """Populate the Branches tab, marking the current branch."""

        self._branches_list.clear()

        for branch in branches:
            prefix = (
                "* "
                if branch.is_current
                else "  "
            )
            item = QListWidgetItem(
                f"{prefix}{branch.name}",
            )
            item.setData(
                _NAME_DATA_ROLE,
                branch.name,
            )
            self._branches_list.addItem(
                item,
            )

    def _render_tags(
        self,
        tags: tuple[GitTag, ...],
    ) -> None:
        """Populate the Tags tab."""

        self._tags_list.clear()

        for tag in tags:
            self._tags_list.addItem(
                f"{tag.name} ({tag.target_oid[:7]})",
            )

    def _render_remotes(
        self,
        remotes: tuple[GitRemote, ...],
    ) -> None:
        """Populate the Remotes tab."""

        self._remotes_list.clear()

        for remote in remotes:
            self._remotes_list.addItem(
                f"{remote.name} ({remote.fetch_url})",
            )

    def _render_history(
        self,
        history: tuple[GitCommitLogEntry, ...],
    ) -> None:
        """Populate the History tab."""

        self._history_list.clear()

        for entry in history:
            self._history_list.addItem(
                f"{entry.commit_oid[:7]} "
                f"{entry.subject} "
                f"({entry.author_name})",
            )

    def _switch_to_item(
        self,
        item: QListWidgetItem,
    ) -> None:
        """Switch to the branch represented by one double-clicked item."""

        if self._repository_path is None:
            return

        branch_name = item.data(
            _NAME_DATA_ROLE,
        )

        try:
            self._git_service.switch_branch(
                self._repository_path,
                branch_name,
            )
        except (
            GitBranchNotFoundError,
            GitExecutableUnavailableError,
            GitCommandFailedError,
            GitCommandTimedOutError,
        ) as error:
            QMessageBox.critical(
                self,
                "Switch Branch Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()
