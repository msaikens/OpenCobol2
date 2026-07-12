"""Unit tests for the Project Explorer tree widget."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.gui.project_explorer import (
    populate_project_tree,
    ProjectExplorerWidget,
)
from opencobol2.project import (
    create_project,
    LinkedFile,
    VirtualFolder,
)


def _dump(item) -> list:
    """Recursively collect an item's text and its children's text."""

    return [
        item.text(0),
        [
            _dump(
                item.child(index),
            )
            for index in range(
                item.childCount(),
            )
        ],
    ]


def test_widget_shows_empty_state_with_no_project(
    qapp,
) -> None:
    widget = ProjectExplorerWidget()

    assert widget.project is None
    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_set_project_emits_project_changed_signal(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    widget = ProjectExplorerWidget()
    received = []
    widget.project_changed.connect(
        received.append,
    )

    widget.set_project(
        project,
    )

    assert received == [project]

    widget.set_project(
        None,
    )

    assert received == [
        project,
        None,
    ]


def test_widget_shows_tree_when_project_set(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text(
        "x",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    widget = ProjectExplorerWidget()

    widget.set_project(
        project,
    )

    assert widget.project is project
    assert (
        widget._stack.currentWidget()
        is widget._tree
    )
    assert (
        widget._tree.topLevelItem(
            0,
        ).text(0)
        == "Demo"
    )


def test_widget_clears_back_to_empty_state(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    widget = ProjectExplorerWidget(
        project,
    )

    widget.set_project(
        None,
    )

    assert widget.project is None
    assert (
        widget._stack.currentWidget()
        is widget._empty_label
    )


def test_widget_rejects_non_project(
    qapp,
) -> None:
    widget = ProjectExplorerWidget()

    with pytest.raises(
        TypeError,
        match=(
            "Project explorer project must be Project or None"
        ),
    ):
        widget.set_project(
            object(),  # type: ignore[arg-type]
        )


def test_populate_tree_lists_physical_files_and_directories(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.cbl").write_text(
        "x",
    )
    (tmp_path / "README.MD").write_text(
        "x",
    )

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    from PySide6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    populate_project_tree(
        tree,
        project,
    )

    root_item = tree.topLevelItem(
        0,
    )
    children = [
        _dump(
            root_item.child(
                index,
            )
        )
        for index in range(
            root_item.childCount(),
        )
    ]

    assert [
        "src",
        [
            [
                "main.cbl",
                [],
            ],
        ],
    ] in children
    assert [
        "README.MD",
        [],
    ] in children


def test_populate_tree_honors_excluded_patterns(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text(
        "x",
    )
    (tmp_path / "keep.cbl").write_text(
        "x",
    )

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        excluded_patterns=(
            "__pycache__",
        ),
    )

    from PySide6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    populate_project_tree(
        tree,
        project,
    )

    root_item = tree.topLevelItem(
        0,
    )
    names = [
        root_item.child(
            index,
        ).text(
            0,
        )
        for index in range(
            root_item.childCount(),
        )
    ]

    assert "__pycache__" not in names
    assert "keep.cbl" in names


def test_populate_tree_shows_virtual_folders_and_nested_members(
    qapp,
    tmp_path: Path,
) -> None:
    linked_file = LinkedFile(
        linked_file_id=uuid4(),
        display_name="shared.cpy",
        target_path=(
            tmp_path
            / ".."
            / "shared.cpy"
        ),
    )
    nested_folder = VirtualFolder(
        folder_id=uuid4(),
        name="Nested",
        member_paths=(
            "src/nested.cbl",
        ),
    )
    virtual_folder = VirtualFolder(
        folder_id=uuid4(),
        name="Sources",
        virtual_folders=(
            nested_folder,
        ),
        member_paths=(
            "src/main.cbl",
        ),
        linked_file_ids=(
            linked_file.linked_file_id,
        ),
    )

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        virtual_folders=(
            virtual_folder,
        ),
        linked_files=(
            linked_file,
        ),
    )

    from PySide6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    populate_project_tree(
        tree,
        project,
    )

    root_item = tree.topLevelItem(
        0,
    )
    top_level_labels = [
        root_item.child(
            index,
        ).text(
            0,
        )
        for index in range(
            root_item.childCount(),
        )
    ]

    assert "Virtual Folders" in top_level_labels
    # The linked file is referenced by the virtual folder, so it must
    # not also appear in a separate top-level "Linked Files" branch.
    assert "Linked Files" not in top_level_labels

    virtual_root = next(
        root_item.child(
            index,
        )
        for index in range(
            root_item.childCount(),
        )
        if root_item.child(
            index,
        ).text(
            0,
        )
        == "Virtual Folders"
    )
    sources_item = virtual_root.child(
        0,
    )
    member_labels = [
        sources_item.child(
            index,
        ).text(
            0,
        )
        for index in range(
            sources_item.childCount(),
        )
    ]

    assert sources_item.text(
        0,
    ) == "Sources"
    assert "Nested" in member_labels
    assert "src/main.cbl" in member_labels
    assert "shared.cpy" in member_labels


def test_populate_tree_shows_unreferenced_linked_files(
    qapp,
    tmp_path: Path,
) -> None:
    linked_file = LinkedFile(
        linked_file_id=uuid4(),
        display_name="standalone.cpy",
        target_path=(
            tmp_path
            / ".."
            / "standalone.cpy"
        ),
    )

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        linked_files=(
            linked_file,
        ),
    )

    from PySide6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    populate_project_tree(
        tree,
        project,
    )

    root_item = tree.topLevelItem(
        0,
    )
    linked_root = next(
        root_item.child(
            index,
        )
        for index in range(
            root_item.childCount(),
        )
        if root_item.child(
            index,
        ).text(
            0,
        )
        == "Linked Files"
    )

    assert (
        linked_root.child(
            0,
        ).text(
            0,
        )
        == "standalone.cpy"
    )


def test_double_clicking_a_file_emits_its_path(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text(
        "x",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    widget = ProjectExplorerWidget(
        project,
    )
    received = []
    widget.file_double_clicked.connect(
        received.append,
    )

    root_item = widget._tree.topLevelItem(
        0,
    )
    file_item = root_item.child(
        0,
    )

    widget._handle_item_double_clicked(
        file_item,
        0,
    )

    assert received == [
        tmp_path / "main.cbl",
    ]


def test_double_clicking_a_directory_emits_nothing(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.cbl").write_text(
        "x",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    widget = ProjectExplorerWidget(
        project,
    )
    received = []
    widget.file_double_clicked.connect(
        received.append,
    )

    root_item = widget._tree.topLevelItem(
        0,
    )
    directory_item = root_item.child(
        0,
    )
    assert directory_item.text(
        0,
    ) == "src"

    widget._handle_item_double_clicked(
        directory_item,
        0,
    )

    assert received == []
