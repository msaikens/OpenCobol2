"""Renders a repository's branches, tags, remotes, and commit history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
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
    GitBranchAlreadyExistsError,
    GitBranchNotFoundError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitExecutableUnavailableError,
    GitRemoteAlreadyExistsError,
    GitRemoteNameError,
    GitRemoteNotFoundError,
    GitRemoteUrlError,
    GitRepositoryNotFoundError,
    GitService,
    GitTagAlreadyExistsError,
    GitTagNotFoundError,
)


_NAME_DATA_ROLE = Qt.ItemDataRole.UserRole

# Every real Git failure this panel's mutating actions can trigger, besides
# the domain-specific already-exists/not-found errors each action also
# catches: a missing repository mid-operation, a missing `git` executable,
# a failed command, a timeout, or a plain `ValueError` from the service
# layer's own argument validation (e.g. a dash-prefixed branch/tag name --
# Editor §GitPanels-1: that validation was added correctly at the service
# layer, but this tuple was never updated for its exception type).
_COMMON_GIT_ERRORS = (
    GitRepositoryNotFoundError,
    GitExecutableUnavailableError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    ValueError,
)


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
            _build_tab(
                self._branches_list,
                "New Branch...",
                self._new_branch,
                self._show_branch_context_menu,
            ),
            "Branches",
        )

        self._tags_list = QListWidget()
        self._tabs.addTab(
            _build_tab(
                self._tags_list,
                "New Tag...",
                self._new_tag,
                self._show_tag_context_menu,
            ),
            "Tags",
        )

        self._remotes_list = QListWidget()
        self._tabs.addTab(
            _build_tab(
                self._remotes_list,
                "Add Remote...",
                self._add_remote,
                self._show_remote_context_menu,
            ),
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

    def show_branches_tab(
        self,
    ) -> None:
        """Switch to the Branches tab (a no-op with no repository open)."""

        if self._repository_path is None:
            return

        self._tabs.setCurrentIndex(
            0,
        )

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
        except (
            GitRepositoryNotFoundError,
            GitExecutableUnavailableError,
        ):
            # Editor §GitPanels-2: only `GitRepositoryNotFoundError`
            # (directory exists but isn't a Git worktree) was caught
            # here -- if the directory itself vanishes out from under
            # a still-open panel, the missing-executable-shaped
            # `GitExecutableUnavailableError` propagated uncaught on
            # the very next refresh instead of falling back to this
            # same empty state.
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
            item = QListWidgetItem(
                f"{tag.name} ({tag.target_oid[:7]})",
            )
            item.setData(
                _NAME_DATA_ROLE,
                tag.name,
            )
            self._tags_list.addItem(
                item,
            )

    def _render_remotes(
        self,
        remotes: tuple[GitRemote, ...],
    ) -> None:
        """Populate the Remotes tab."""

        self._remotes_list.clear()

        for remote in remotes:
            item = QListWidgetItem(
                f"{remote.name} ({remote.fetch_url})",
            )
            item.setData(
                _NAME_DATA_ROLE,
                remote.name,
            )
            self._remotes_list.addItem(
                item,
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
            *_COMMON_GIT_ERRORS,
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

    def _new_branch(
        self,
    ) -> None:
        """Prompt for a name and create a new local branch."""

        if self._repository_path is None:
            return

        name, ok = QInputDialog.getText(
            self,
            "New Branch",
            "Branch name:",
        )

        if not ok or not name.strip():
            return

        try:
            self._git_service.create_branch(
                self._repository_path,
                name,
            )
        except (
            GitBranchAlreadyExistsError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "New Branch Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _show_branch_context_menu(
        self,
        position,
    ) -> None:
        """Show a context menu with a delete action for one branch item."""

        item = self._branches_list.itemAt(
            position,
        )

        if item is None:
            return

        branch_name = item.data(
            _NAME_DATA_ROLE,
        )
        menu = QMenu(
            self,
        )
        delete_action = menu.addAction(
            "Delete Branch",
        )
        chosen_action = menu.exec(
            self._branches_list.mapToGlobal(
                position,
            ),
        )

        if chosen_action is delete_action:
            self._delete_branch(
                branch_name,
            )

    def _delete_branch(
        self,
        branch_name: str,
    ) -> None:
        """Delete one branch after confirmation."""

        if not _confirm(
            self,
            "Delete Branch",
            f"Delete branch {branch_name!r}?",
        ):
            return

        try:
            self._git_service.delete_branch(
                self._repository_path,
                branch_name,
            )
        except (
            GitBranchNotFoundError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "Delete Branch Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _new_tag(
        self,
    ) -> None:
        """Prompt for a name (and optional message) and create a new tag."""

        if self._repository_path is None:
            return

        name, ok = QInputDialog.getText(
            self,
            "New Tag",
            "Tag name:",
        )

        if not ok or not name.strip():
            return

        message, _ = QInputDialog.getText(
            self,
            "New Tag",
            "Annotation message (leave blank for a lightweight tag):",
        )

        try:
            self._git_service.create_tag(
                self._repository_path,
                name,
                message=(
                    message.strip()
                    if message.strip()
                    else None
                ),
            )
        except (
            GitTagAlreadyExistsError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "New Tag Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _show_tag_context_menu(
        self,
        position,
    ) -> None:
        """Show a context menu with a delete action for one tag item."""

        item = self._tags_list.itemAt(
            position,
        )

        if item is None:
            return

        tag_name = item.data(
            _NAME_DATA_ROLE,
        )
        menu = QMenu(
            self,
        )
        delete_action = menu.addAction(
            "Delete Tag",
        )
        chosen_action = menu.exec(
            self._tags_list.mapToGlobal(
                position,
            ),
        )

        if chosen_action is delete_action:
            self._delete_tag(
                tag_name,
            )

    def _delete_tag(
        self,
        tag_name: str,
    ) -> None:
        """Delete one tag after confirmation."""

        if not _confirm(
            self,
            "Delete Tag",
            f"Delete tag {tag_name!r}?",
        ):
            return

        try:
            self._git_service.delete_tag(
                self._repository_path,
                tag_name,
            )
        except (
            GitTagNotFoundError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "Delete Tag Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _add_remote(
        self,
    ) -> None:
        """Prompt for a name and URL and add a new remote."""

        if self._repository_path is None:
            return

        name, ok = QInputDialog.getText(
            self,
            "Add Remote",
            "Remote name:",
        )

        if not ok or not name.strip():
            return

        url, ok = QInputDialog.getText(
            self,
            "Add Remote",
            "Remote URL:",
        )

        if not ok or not url.strip():
            return

        try:
            self._git_service.add_remote(
                self._repository_path,
                name,
                url,
            )
        except (
            GitRemoteAlreadyExistsError,
            GitRemoteNameError,
            GitRemoteUrlError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "Add Remote Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _show_remote_context_menu(
        self,
        position,
    ) -> None:
        """Show a context menu with remove/rename actions for one remote item."""

        item = self._remotes_list.itemAt(
            position,
        )

        if item is None:
            return

        remote_name = item.data(
            _NAME_DATA_ROLE,
        )
        menu = QMenu(
            self,
        )
        rename_action = menu.addAction(
            "Rename Remote...",
        )
        remove_action = menu.addAction(
            "Remove Remote",
        )
        chosen_action = menu.exec(
            self._remotes_list.mapToGlobal(
                position,
            ),
        )

        if chosen_action is remove_action:
            self._remove_remote(
                remote_name,
            )
        elif chosen_action is rename_action:
            self._rename_remote(
                remote_name,
            )

    def _remove_remote(
        self,
        remote_name: str,
    ) -> None:
        """Remove one remote after confirmation."""

        if not _confirm(
            self,
            "Remove Remote",
            f"Remove remote {remote_name!r}?",
        ):
            return

        try:
            self._git_service.remove_remote(
                self._repository_path,
                remote_name,
            )
        except (
            GitRemoteNotFoundError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "Remove Remote Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()

    def _rename_remote(
        self,
        remote_name: str,
    ) -> None:
        """Rename one remote to a new, user-provided name."""

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Remote",
            "New remote name:",
            text=remote_name,
        )

        if not ok or not new_name.strip():
            return

        try:
            self._git_service.rename_remote(
                self._repository_path,
                remote_name,
                new_name,
            )
        except (
            GitRemoteNotFoundError,
            GitRemoteAlreadyExistsError,
            GitRemoteNameError,
            *_COMMON_GIT_ERRORS,
        ) as error:
            QMessageBox.critical(
                self,
                "Rename Remote Failed",
                str(
                    error,
                ),
            )
            return

        self.refresh()


def _build_tab(
    list_widget: QListWidget,
    add_button_label: str,
    add_button_handler,
    context_menu_handler,
) -> QWidget:
    """Build one tab page: an action button above a context-menu-enabled list."""

    tab = QWidget()
    layout = QVBoxLayout(
        tab,
    )
    layout.setContentsMargins(
        0,
        0,
        0,
        0,
    )

    button_row = QHBoxLayout()
    add_button = QPushButton(
        add_button_label,
    )
    add_button.clicked.connect(
        add_button_handler,
    )
    button_row.addWidget(
        add_button,
    )
    button_row.addStretch()
    layout.addLayout(
        button_row,
    )

    list_widget.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu,
    )
    list_widget.customContextMenuRequested.connect(
        context_menu_handler,
    )
    layout.addWidget(
        list_widget,
    )

    return tab


def _confirm(
    parent: QWidget,
    title: str,
    message: str,
) -> bool:
    """Ask a yes/no confirmation question before a destructive Git action."""

    return (
        QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )
