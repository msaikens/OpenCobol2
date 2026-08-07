"""Wires the Git menu's Fetch/Pull/Push/Sync/Clone/Create/Manage Branches
commands to the real `GitService`.

Editor §UIBootstrap-1: these commands (plus several others in the Edit,
Build, and Help menus) previously had no application handler wired at
all, and raised `BuiltInCommandHandlerNotConfiguredError` when
triggered -- silently swallowed by PySide6's own slot-exception
reporter, so the user saw nothing happen. Fetch/Pull/Push/Create/Clone
were already fully implemented at the `GitService` layer (this exact
functionality is what the Git Repository panel's own buttons already
call) -- only the menu-level wiring was missing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from opencobol2.commands import CommandContext, CommandHandler
from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.services.git import (
    GitCloneDestinationNotEmptyError,
    GitCloneSourceError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitExecutableUnavailableError,
    GitPullConflictError,
    GitRepositoryAlreadyExistsError,
    GitRepositoryNotFoundError,
    GitService,
)


# Every real Git failure a menu-triggered command can hit: a missing
# repository, a missing `git` executable, a failed command, a timeout,
# or a plain `ValueError` from the service layer's own argument
# validation (e.g. a malformed remote/branch name).
_COMMON_GIT_ERRORS = (
    GitRepositoryNotFoundError,
    GitExecutableUnavailableError,
    GitCommandFailedError,
    GitCommandTimedOutError,
    ValueError,
)


def _discover_open_repository(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    title: str,
    parent_widget: QWidget | None,
) -> Path | None:
    """Return the open project's Git repository root, or `None` with a message."""

    project = project_explorer.project

    if project is None:
        QMessageBox.information(
            parent_widget,
            title,
            "No project is open.",
        )
        return None

    try:
        return git_service.discover_repository(
            project.root_path,
        )
    except _COMMON_GIT_ERRORS as error:
        QMessageBox.warning(
            parent_widget,
            title,
            f"No Git repository found: {error}",
        )
        return None


def create_fetch_handler(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    git_changes_widget: GitChangesWidget,
    git_repository_widget: GitRepositoryWidget,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that fetches the open project's default remote."""

    def handle_fetch(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()
        repository_path = _discover_open_repository(
            git_service=git_service,
            project_explorer=project_explorer,
            title="Fetch",
            parent_widget=parent_widget,
        )

        if repository_path is None:
            return

        try:
            git_service.fetch(repository_path)
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(parent_widget, "Fetch", str(error))
            return

        git_changes_widget.refresh()
        git_repository_widget.refresh()
        QMessageBox.information(
            parent_widget,
            "Fetch",
            "Fetch completed.",
        )

    return handle_fetch


def create_pull_handler(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    git_changes_widget: GitChangesWidget,
    git_repository_widget: GitRepositoryWidget,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that pulls the open project's default remote/branch."""

    def handle_pull(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()
        repository_path = _discover_open_repository(
            git_service=git_service,
            project_explorer=project_explorer,
            title="Pull",
            parent_widget=parent_widget,
        )

        if repository_path is None:
            return

        try:
            git_service.pull(repository_path)
        except GitPullConflictError as error:
            QMessageBox.warning(
                parent_widget,
                "Pull",
                f"Pull resulted in merge conflicts: {error}",
            )
            git_changes_widget.refresh()
            git_repository_widget.refresh()
            return
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(parent_widget, "Pull", str(error))
            return

        git_changes_widget.refresh()
        git_repository_widget.refresh()
        QMessageBox.information(
            parent_widget,
            "Pull",
            "Pull completed.",
        )

    return handle_pull


def create_push_handler(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    git_changes_widget: GitChangesWidget,
    git_repository_widget: GitRepositoryWidget,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that pushes the open project's current branch."""

    def handle_push(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()
        repository_path = _discover_open_repository(
            git_service=git_service,
            project_explorer=project_explorer,
            title="Push",
            parent_widget=parent_widget,
        )

        if repository_path is None:
            return

        try:
            git_service.push(repository_path)
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(parent_widget, "Push", str(error))
            return

        git_changes_widget.refresh()
        git_repository_widget.refresh()
        QMessageBox.information(
            parent_widget,
            "Push",
            "Push completed.",
        )

    return handle_push


def create_sync_handler(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    git_changes_widget: GitChangesWidget,
    git_repository_widget: GitRepositoryWidget,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that pulls then pushes the open project's repository."""

    def handle_sync(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()
        repository_path = _discover_open_repository(
            git_service=git_service,
            project_explorer=project_explorer,
            title="Sync",
            parent_widget=parent_widget,
        )

        if repository_path is None:
            return

        try:
            git_service.pull(repository_path)
        except GitPullConflictError as error:
            QMessageBox.warning(
                parent_widget,
                "Sync",
                f"Pull resulted in merge conflicts: {error}",
            )
            git_changes_widget.refresh()
            git_repository_widget.refresh()
            return
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(parent_widget, "Sync", f"Pull failed: {error}")
            return

        try:
            git_service.push(repository_path)
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(parent_widget, "Sync", f"Push failed: {error}")
            git_changes_widget.refresh()
            git_repository_widget.refresh()
            return

        git_changes_widget.refresh()
        git_repository_widget.refresh()
        QMessageBox.information(
            parent_widget,
            "Sync",
            "Sync completed (pulled, then pushed).",
        )

    return handle_sync


def create_manage_branches_handler(
    *,
    git_repository_widget: GitRepositoryWidget,
    reveal_git_repository_panel: Callable[[], None],
) -> CommandHandler:
    """Create a handler that reveals the Git Repository panel's Branches tab."""

    def handle_manage_branches(context: CommandContext) -> None:
        reveal_git_repository_panel()
        git_repository_widget.show_branches_tab()

    return handle_manage_branches


def create_create_repository_handler(
    *,
    git_service: GitService,
    project_explorer: ProjectExplorerWidget,
    git_changes_widget: GitChangesWidget,
    git_repository_widget: GitRepositoryWidget,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that initializes a Git repository at the open project's root."""

    def handle_create_repository(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()
        project = project_explorer.project

        if project is None:
            QMessageBox.information(
                parent_widget,
                "Create Repository",
                "Open a project first.",
            )
            return

        try:
            git_service.create_repository(project.root_path)
        except GitRepositoryAlreadyExistsError as error:
            QMessageBox.information(
                parent_widget,
                "Create Repository",
                f"A Git repository already exists here: {error}",
            )
            return
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(
                parent_widget,
                "Create Repository",
                str(error),
            )
            return

        repository_path = git_service.discover_repository(
            project.root_path,
        )
        git_changes_widget.set_repository_path(repository_path)
        git_repository_widget.set_repository_path(repository_path)
        QMessageBox.information(
            parent_widget,
            "Create Repository",
            "Git repository created.",
        )

    return handle_create_repository


def create_clone_repository_handler(
    *,
    git_service: GitService,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that clones a remote repository into a chosen folder.

    Deliberately does not open the cloned repository as the current
    project -- cloning a repository and opening an OpenCobol2 project
    are different concepts (a project is a `.json` project file, not
    bare a directory), and conflating them would be a scope increase
    beyond this command's own literal purpose.
    """

    def handle_clone_repository(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()

        source, confirmed = QInputDialog.getText(
            parent_widget,
            "Clone Repository",
            "Repository URL or path:",
        )

        if not confirmed or not source.strip():
            return

        destination_text = QFileDialog.getExistingDirectory(
            parent_widget,
            "Clone Repository — choose an empty destination folder",
        )

        if not destination_text:
            return

        try:
            git_service.clone_repository(
                source.strip(),
                Path(destination_text),
            )
        except GitCloneDestinationNotEmptyError as error:
            QMessageBox.warning(
                parent_widget,
                "Clone Repository",
                f"That folder isn't empty: {error}",
            )
            return
        except GitCloneSourceError as error:
            QMessageBox.warning(
                parent_widget,
                "Clone Repository",
                f"Unable to clone that repository: {error}",
            )
            return
        except _COMMON_GIT_ERRORS as error:
            QMessageBox.warning(
                parent_widget,
                "Clone Repository",
                str(error),
            )
            return

        QMessageBox.information(
            parent_widget,
            "Clone Repository",
            f"Cloned into {destination_text}.",
        )

    return handle_clone_repository
