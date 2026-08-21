"""Renders an OpenCobol2 project as a real file/organization tree widget.

The tree combines the project's physical files on disk with its
virtual organization: real directory entries first, then a "Virtual
Folders" branch for any virtual folders the project defines, then a
"Linked Files" branch for any linked file not already referenced by a
virtual folder.
"""

from __future__ import annotations

from collections.abc import Sequence
import fnmatch
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opencobol2.project import (
    Project,
    VirtualFolder,
)


class ProjectExplorerWidget(QWidget):
    """Displays the currently open project's files and organization."""

    project_changed = Signal(object)
    """Emitted with the new `Project | None` whenever `set_project` runs."""

    file_double_clicked = Signal(Path)
    """Emitted with a physical file's path when its tree item is double-clicked."""

    project_properties_requested = Signal()
    """Emitted when the user chooses Properties... on the project's root item."""

    def __init__(
        self,
        project: Project | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the project explorer, optionally already showing a project.

        :param project: The project to display immediately, or `None`
            to start in the empty state.
        :param parent: The owning Qt widget, if any.
        :returns: None.
        """

        super().__init__(
            parent,
        )

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
            "No project is open.",
        )
        self._empty_label.setMargin(
            8,
        )

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(
            True,
        )
        self._tree.itemDoubleClicked.connect(
            self._handle_item_double_clicked,
        )
        self._tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self._tree.customContextMenuRequested.connect(
            self._show_context_menu,
        )

        self._stack = QStackedWidget()
        self._stack.addWidget(
            self._empty_label,
        )
        self._stack.addWidget(
            self._tree,
        )

        layout.addWidget(
            self._stack,
        )

        self._project: Project | None = None
        self.set_project(
            project,
        )

    @property
    def project(
        self,
    ) -> Project | None:
        """Return the project currently displayed, if any.

        :returns: The currently displayed project, or `None` if the
            explorer is in its empty state.
        """

        return self._project

    def set_project(
        self,
        project: Project | None,
    ) -> None:
        """Display a project's tree, or clear back to the empty state.

        :param project: The project to display, or `None` to clear
            back to the empty state.
        :returns: None. The tree widget is rebuilt (or cleared) and
            `project_changed` is emitted with the new project.
        :raises TypeError: If `project` is neither a :class:`Project`
            nor `None`.
        """

        if (
            project is not None
            and not isinstance(
                project,
                Project,
            )
        ):
            raise TypeError(
                "Project explorer project must be Project or None."
            )

        self._project = project
        self._tree.clear()

        if project is None:
            self._stack.setCurrentWidget(
                self._empty_label,
            )
            self.project_changed.emit(
                None,
            )
            return

        populate_project_tree(
            self._tree,
            project,
        )
        self._stack.setCurrentWidget(
            self._tree,
        )
        self.project_changed.emit(
            project,
        )

    def _handle_item_double_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        """Emit `file_double_clicked` when a physical file item is opened.

        :param item: The tree item that was double-clicked.
        :param column: The column that was double-clicked (unused;
            the tree has only one column).
        :returns: None. `file_double_clicked` is emitted only if
            `item` carries a physical file path; a virtual-folder or
            organizational item carries none and is silently ignored.
        """

        path = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        if isinstance(
            path,
            Path,
        ):
            self.file_double_clicked.emit(
                path,
            )

    def _show_context_menu(
        self,
        position,
    ) -> None:
        """Show Properties... when the project's own root item is right-clicked.

        :param position: The right-click position, in the tree
            widget's own coordinates.
        :returns: None. A context menu is shown only when the
            right-clicked item is the tree's top-level (project root)
            item; any other item, or empty space, is ignored.
        """

        item = self._tree.itemAt(
            position,
        )

        if (
            item is None
            or item is not self._tree.topLevelItem(
                0,
            )
        ):
            return

        menu = QMenu(
            self,
        )
        properties_action = menu.addAction(
            "Properties...",
        )
        chosen_action = menu.exec(
            self._tree.mapToGlobal(
                position,
            )
        )

        if chosen_action is properties_action:
            self._show_project_properties()

    def _show_project_properties(
        self,
    ) -> None:
        """Request that the project's properties be edited.

        :returns: None. `project_properties_requested` is emitted.
        """

        self.project_properties_requested.emit()


def populate_project_tree(
    tree: QTreeWidget,
    project: Project,
) -> None:
    """Populate a tree widget with one project's files and organization.

    :param tree: The tree widget to populate. Any existing content is
        cleared first.
    :param project: The project whose files and organization to
        display.
    :returns: None. `tree` is populated in place and its root item is
        expanded.
    """

    tree.clear()

    root_item = QTreeWidgetItem(
        [
            project.name,
        ]
    )
    tree.addTopLevelItem(
        root_item,
    )

    _add_physical_entries(
        root_item,
        project.root_path,
        project.excluded_patterns,
    )

    if project.virtual_folders:
        virtual_root = QTreeWidgetItem(
            [
                "Virtual Folders",
            ]
        )
        root_item.addChild(
            virtual_root,
        )

        for folder in project.virtual_folders:
            _add_virtual_folder(
                virtual_root,
                folder,
                project,
            )

    referenced_linked_file_ids = (
        _collect_referenced_linked_file_ids(
            project.virtual_folders,
        )
    )
    unreferenced_linked_files = [
        linked_file
        for linked_file in project.linked_files
        if (
            linked_file.linked_file_id
            not in referenced_linked_file_ids
        )
    ]

    if unreferenced_linked_files:
        linked_root = QTreeWidgetItem(
            [
                "Linked Files",
            ]
        )
        root_item.addChild(
            linked_root,
        )

        for linked_file in unreferenced_linked_files:
            item = QTreeWidgetItem(
                [
                    linked_file.display_name,
                ]
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                linked_file.target_path,
            )
            linked_root.addChild(
                item,
            )

    tree.expandItem(
        root_item,
    )


def _add_physical_entries(
    parent_item: QTreeWidgetItem,
    directory: Path,
    excluded_patterns: Sequence[str],
) -> None:
    """Recursively add a directory's real entries, honoring exclusions.

    :param parent_item: The tree item to add this directory's entries
        under.
    :param directory: The directory to list and recurse into.
    :param excluded_patterns: Glob patterns; an entry whose name
        matches any of them is skipped entirely (and, for a directory,
        never recursed into).
    :returns: None. Child items are appended to `parent_item` in
        place. Entries are sorted directories-first, then
        case-insensitively by name. A file item carries its
        :class:`~pathlib.Path` in `Qt.ItemDataRole.UserRole`; a
        directory item does not, since it is a container rather than
        something that can be opened. If `directory` cannot be listed
        (e.g. a permissions error) or is not actually a directory, no
        entries are added.
    """

    if not directory.is_dir():
        return

    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda entry: (
                entry.is_file(),
                entry.name.lower(),
            ),
        )
    except OSError:
        return

    for entry in entries:
        if _is_excluded(
            entry.name,
            excluded_patterns,
        ):
            continue

        item = QTreeWidgetItem(
            [
                entry.name,
            ]
        )
        parent_item.addChild(
            item,
        )

        if entry.is_dir():
            _add_physical_entries(
                item,
                entry,
                excluded_patterns,
            )
        else:
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                entry,
            )


def _is_excluded(
    name: str,
    excluded_patterns: Sequence[str],
) -> bool:
    """Return whether a file or directory name matches an exclusion pattern.

    :param name: The file or directory name to test.
    :param excluded_patterns: Glob patterns to test `name` against.
    :returns: True if `name` matches any pattern in
        `excluded_patterns`, False otherwise.
    """

    return any(
        fnmatch.fnmatch(
            name,
            pattern,
        )
        for pattern in excluded_patterns
    )


def _add_virtual_folder(
    parent_item: QTreeWidgetItem,
    folder: VirtualFolder,
    project: Project,
) -> None:
    """Recursively add one virtual folder and its members.

    :param parent_item: The tree item to add this virtual folder
        under.
    :param folder: The virtual folder to render, including its nested
        virtual folders and its member paths and linked files.
    :param project: The owning project, used to resolve member paths
        to absolute locations and linked-file IDs to their targets.
    :returns: None. Child items are appended to `parent_item` in
        place.

    Each of a virtual folder's own member paths gets
    `setData(0, UserRole, entry)` set on its tree item, exactly like a
    physical tree entry, so that the double-click handler's
    `isinstance(path, Path)` check finds it; before this was added,
    virtual-folder members never carried that data, so double-clicking
    one always silently failed that check, unlike an ordinary file
    row.
    """

    folder_item = QTreeWidgetItem(
        [
            folder.name,
        ]
    )
    parent_item.addChild(
        folder_item,
    )

    for nested_folder in folder.virtual_folders:
        _add_virtual_folder(
            folder_item,
            nested_folder,
            project,
        )

    for member_path in folder.member_paths:
        item = QTreeWidgetItem(
            [
                member_path,
            ]
        )
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            project.root_path / member_path,
        )
        folder_item.addChild(
            item,
        )

    linked_files_by_id = {
        linked_file.linked_file_id: linked_file
        for linked_file in project.linked_files
    }

    for linked_file_id in folder.linked_file_ids:
        linked_file = linked_files_by_id.get(
            linked_file_id,
        )

        if linked_file is not None:
            item = QTreeWidgetItem(
                [
                    linked_file.display_name,
                ]
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                linked_file.target_path,
            )
            folder_item.addChild(
                item,
            )


def _collect_referenced_linked_file_ids(
    virtual_folders: Sequence[VirtualFolder],
) -> set:
    """Collect every linked file ID referenced anywhere in a virtual folder tree.

    :param virtual_folders: The top-level virtual folders to walk,
        including their nested virtual folders recursively.
    :returns: The set of every linked file ID referenced by any of
        `virtual_folders` or their descendants.
    """

    referenced_ids: set = set()

    for folder in virtual_folders:
        referenced_ids.update(
            folder.linked_file_ids,
        )
        referenced_ids.update(
            _collect_referenced_linked_file_ids(
                folder.virtual_folders,
            )
        )

    return referenced_ids
