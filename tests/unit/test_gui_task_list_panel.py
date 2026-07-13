"""Unit tests for the Task List panel widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton

from opencobol2.gui.task_list_panel import (
    ProjectTaskEntry,
    TaskListWidget,
)


def test_set_tasks_populates_every_column(
    qapp,
    tmp_path: Path,
) -> None:
    widget = TaskListWidget()
    path = tmp_path / "main.cbl"

    widget.set_tasks(
        (
            ProjectTaskEntry(
                path=path,
                tag="TODO",
                line=5,
                column=10,
                text="TODO clean this up",
            ),
        )
    )

    assert widget.row_count == 1
    assert widget._table.item(0, 0).text() == "TODO"
    assert widget._table.item(0, 1).text() == str(path)
    assert widget._table.item(0, 2).text() == "5"
    assert (
        widget._table.item(0, 3).text()
        == "TODO clean this up"
    )


def test_clear_tasks_empties_the_table(
    qapp,
    tmp_path: Path,
) -> None:
    widget = TaskListWidget()
    widget.set_tasks(
        (
            ProjectTaskEntry(
                path=tmp_path / "main.cbl",
                tag="TODO",
                line=1,
                column=1,
                text="x",
            ),
        )
    )

    widget.clear_tasks()

    assert widget.row_count == 0


def test_refresh_button_emits_refresh_requested(
    qapp,
) -> None:
    widget = TaskListWidget()
    received = []
    widget.refresh_requested.connect(
        lambda: received.append(
            True,
        )
    )

    refresh_button = next(
        button
        for button in widget.findChildren(
            QPushButton,
        )
        if button.text() == "Refresh"
    )
    refresh_button.click()

    assert received == [True]


def test_double_clicking_a_row_emits_entry_activated(
    qapp,
    tmp_path: Path,
) -> None:
    widget = TaskListWidget()
    path = tmp_path / "main.cbl"
    widget.set_tasks(
        (
            ProjectTaskEntry(
                path=path,
                tag="FIXME",
                line=8,
                column=4,
                text="FIXME broken",
            ),
        )
    )
    received = []
    widget.entry_activated.connect(
        lambda activated_path, line, column: received.append(
            (
                activated_path,
                line,
                column,
            )
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == [
        (
            path,
            8,
            4,
        )
    ]


def test_double_clicking_an_out_of_range_row_does_nothing(
    qapp,
) -> None:
    widget = TaskListWidget()
    received = []
    widget.entry_activated.connect(
        lambda *args: received.append(
            args,
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == []
