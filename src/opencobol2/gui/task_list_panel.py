"""A table view of TODO/FIXME-style task markers found across a project."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectTaskEntry:
    """One task-tagged comment found in one project source file."""

    path: Path
    tag: str
    line: int
    column: int
    text: str


_COLUMN_HEADERS = (
    "Tag",
    "File",
    "Line",
    "Text",
)


class TaskListWidget(QWidget):
    """Lists TODO/FIXME-style task markers; double-click opens one.

    Scanning is on demand rather than automatic (no filesystem watcher):
    a Refresh button re-scans immediately, and the caller wires whatever
    other moments (e.g. opening a project) should also trigger a rescan.
    """

    refresh_requested = Signal()
    entry_activated = Signal(
        Path,
        int,
        int,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty task list with its Refresh control."""

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

        refresh_button = QPushButton(
            "Refresh",
        )
        refresh_button.clicked.connect(
            self.refresh_requested.emit,
        )
        layout.addWidget(
            refresh_button,
        )

        self._table = QTableWidget(
            0,
            len(
                _COLUMN_HEADERS,
            ),
        )
        self._table.setHorizontalHeaderLabels(
            _COLUMN_HEADERS,
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.verticalHeader().setVisible(
            False,
        )
        self._table.cellDoubleClicked.connect(
            self._handle_cell_double_clicked,
        )
        layout.addWidget(
            self._table,
        )

        self._entries: tuple[
            ProjectTaskEntry,
            ...,
        ] = ()

    @property
    def row_count(
        self,
    ) -> int:
        """Return the number of listed task entries."""

        return self._table.rowCount()

    def set_tasks(
        self,
        entries: Sequence[ProjectTaskEntry],
    ) -> None:
        """Replace the table's contents with a new set of task entries."""

        self._entries = tuple(
            entries,
        )
        self._table.setRowCount(
            len(
                self._entries,
            )
        )

        for row, entry in enumerate(
            self._entries,
        ):
            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    entry.tag,
                ),
            )
            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(
                        entry.path,
                    )
                ),
            )
            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(
                        entry.line,
                    )
                ),
            )
            self._table.setItem(
                row,
                3,
                QTableWidgetItem(
                    entry.text,
                ),
            )

    def clear_tasks(
        self,
    ) -> None:
        """Remove every entry from the task list."""

        self._entries = ()
        self._table.setRowCount(
            0,
        )

    def _handle_cell_double_clicked(
        self,
        row: int,
        _column: int,
    ) -> None:
        if not (
            0
            <= row
            < len(
                self._entries,
            )
        ):
            return

        entry = self._entries[row]
        self.entry_activated.emit(
            entry.path,
            entry.line,
            entry.column,
        )
