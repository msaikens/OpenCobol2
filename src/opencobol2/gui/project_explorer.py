"""Renders an OpenCobol2 project as a real file/organization tree widget."""

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
        """Build the project explorer, optionally already showing a project."""

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
        """Return the project currently displayed, if any."""

        return self._project

    def set_project(
        self,
        project: Project | None,
    ) -> None:
        """Display a project's tree, or clear back to the empty state."""

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
        """Emit `file_double_clicked` when a physical file item is opened."""

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
        """Show Properties... when the project's own root item is right-clicked."""

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
        """Request that the project's properties be edited."""

        self.project_properties_requested.emit()


def populate_project_tree(
    tree: QTreeWidget,
    project: Project,
) -> None:
    """Populate a tree widget with one project's files and organization."""

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
            linked_root.addChild(
                QTreeWidgetItem(
                    [
                        linked_file.display_name,
                    ]
                )
            )

    tree.expandItem(
        root_item,
    )


def _add_physical_entries(
    parent_item: QTreeWidgetItem,
    directory: Path,
    excluded_patterns: Sequence[str],
) -> None:
    """Recursively add a directory's real entries, honoring exclusions."""

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
    """Return whether a file or directory name matches an exclusion pattern."""

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
    """Recursively add one virtual folder and its members."""

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
        folder_item.addChild(
            QTreeWidgetItem(
                [
                    member_path,
                ]
            )
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
            folder_item.addChild(
                QTreeWidgetItem(
                    [
                        linked_file.display_name,
                    ]
                )
            )


def _collect_referenced_linked_file_ids(
    virtual_folders: Sequence[VirtualFolder],
) -> set:
    """Collect every linked file ID referenced anywhere in a virtual folder tree."""

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
