"""Renders a repository's branches, tags, remotes, and commit history.

Every mutating action in this panel (switching branches, creating or
deleting a branch or tag, adding/removing/renaming a remote) shares one
common tuple of real Git failures it can catch alongside its own
domain-specific already-exists/not-found error: a missing repository
mid-operation, a missing `git` executable, a failed command, a timeout,
or a plain `ValueError` raised by the service layer's own argument
validation (for example, a dash-prefixed branch or tag name). That
shared tuple has to be kept in sync by hand with the service layer: the
dash-prefixed-name validation was added correctly there, but the tuple
was not updated at the same time to include its `ValueError` exception
type.
"""

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

_COMMON_GIT_ERRORS = (
    GitRepositoryNotFoundError,
    GitExecutableUnavailableError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    ValueError,
)


class GitRepositoryWidget(QWidget):
    """Shows branches, tags, remotes, and history for one Git repository.

    :ivar _git_service: The service used to query and mutate the
        displayed repository.
    :ivar _repository_path: The repository currently displayed, or
        None if no repository is open.
    :ivar _empty_label: The placeholder shown in `_stack` when there is
        no repository to display.
    :ivar _tabs: The tab widget holding the Branches, Tags, Remotes,
        and History pages, shown in `_stack` once a repository is open.
    :ivar _branches_list: The list widget showing every local branch,
        with the current branch marked.
    :ivar _tags_list: The list widget showing every tag.
    :ivar _remotes_list: The list widget showing every configured
        remote.
    :ivar _history_list: The list widget showing the recent commit log.
    :ivar _stack: The stacked widget that switches between
        `_empty_label` and `_tabs` depending on whether a repository is
        open.
    """

    def __init__(
        self,
        *,
        git_service: GitService,
        repository_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the Git Repository panel, optionally already showing a repository.

        :param git_service: The service used to query and mutate the
            displayed repository.
        :param repository_path: The repository to display immediately,
            or None to start in the empty state.
        :param parent: The optional parent widget, forwarded to
            :class:`QWidget`.
        :returns: None.
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
        """Return the repository path currently displayed, if any.

        :returns: The repository path currently displayed, or None if
            the panel is in its empty state.
        """

        return self._repository_path

    def set_repository_path(
        self,
        path: Path | None,
    ) -> None:
        """Display a repository's branches/tags/remotes/history, or clear it.

        :param path: The repository to display, or None to clear the
            panel back to its empty state.
        :returns: None. `_repository_path` is updated and every tab is
            refreshed from it.
        """

        self._repository_path = path
        self.refresh()

    def show_branches_tab(
        self,
    ) -> None:
        """Switch to the Branches tab (a no-op with no repository open).

        :returns: None. The visible tab is changed as a side effect.
        """

        if self._repository_path is None:
            return

        self._tabs.setCurrentIndex(
            0,
        )

    def refresh(
        self,
    ) -> None:
        """Re-fetch and redisplay every tab from the current repository.

        Both `GitRepositoryNotFoundError` (the directory exists but is
        not a Git worktree) and `GitExecutableUnavailableError` are
        caught below and treated the same way, falling back to the
        empty-repository placeholder. Previously only
        `GitRepositoryNotFoundError` was handled here: if the
        repository directory itself vanished out from under a
        still-open panel, the missing-executable-shaped
        `GitExecutableUnavailableError` propagated uncaught on the very
        next refresh instead of falling back to this same empty state.

        :returns: None. The panel's tabs (or the empty-state
            placeholder) are updated in place.
        """

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
        """Populate the Branches tab, marking the current branch.

        :param branches: Every local branch to display.
        :returns: None. `_branches_list` is repopulated in place.
        """

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
        """Populate the Tags tab.

        :param tags: Every tag to display.
        :returns: None. `_tags_list` is repopulated in place.
        """

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
        """Populate the Remotes tab.

        :param remotes: Every remote to display.
        :returns: None. `_remotes_list` is repopulated in place.
        """

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
        """Populate the History tab.

        :param history: The recent commit log entries to display.
        :returns: None. `_history_list` is repopulated in place.
        """

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
        """Switch to the branch represented by one double-clicked item.

        :param item: The double-clicked item from `_branches_list`.
        :returns: None. The repository's checked-out branch and the
            panel's tabs are updated as a side effect, or an error
            dialog is shown on failure.
        """

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
        """Prompt for a name and create a new local branch.

        :returns: None. A new branch is created and the panel's tabs
            are refreshed, or an error dialog is shown on failure. Does
            nothing if the user cancels or enters a blank name.
        """

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
        """Show a context menu with a delete action for one branch item.

        :param position: The position, relative to `_branches_list`,
            that the context menu was requested at.
        :returns: None. A branch may be deleted as a side effect,
            depending on the user's choice.
        """

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
        """Delete one branch after confirmation.

        :param branch_name: The name of the branch to delete.
        :returns: None. The branch is deleted and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user declines the confirmation.
        """

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
        """Prompt for a name (and optional message) and create a new tag.

        :returns: None. A new tag is created and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user cancels or enters a blank name.
        """

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
        """Show a context menu with a delete action for one tag item.

        :param position: The position, relative to `_tags_list`, that
            the context menu was requested at.
        :returns: None. A tag may be deleted as a side effect,
            depending on the user's choice.
        """

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
        """Delete one tag after confirmation.

        :param tag_name: The name of the tag to delete.
        :returns: None. The tag is deleted and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user declines the confirmation.
        """

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
        """Prompt for a name and URL and add a new remote.

        :returns: None. A new remote is added and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user cancels or enters a blank name or URL.
        """

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
        """Show a context menu with remove/rename actions for one remote item.

        :param position: The position, relative to `_remotes_list`,
            that the context menu was requested at.
        :returns: None. A remote may be removed or renamed as a side
            effect, depending on the user's choice.
        """

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
        """Remove one remote after confirmation.

        :param remote_name: The name of the remote to remove.
        :returns: None. The remote is removed and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user declines the confirmation.
        """

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
        """Rename one remote to a new, user-provided name.

        :param remote_name: The current name of the remote to rename.
        :returns: None. The remote is renamed and the panel's tabs are
            refreshed, or an error dialog is shown on failure. Does
            nothing if the user cancels or enters a blank name.
        """

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
    """Build one tab page: an action button above a context-menu-enabled list.

    :param list_widget: The list to place below the action button and
        wire up with the context-menu policy.
    :param add_button_label: The label text for the action button.
    :param add_button_handler: The slot connected to the action
        button's `clicked` signal.
    :param context_menu_handler: The slot connected to `list_widget`'s
        `customContextMenuRequested` signal.
    :returns: The assembled tab page widget.
    """

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
