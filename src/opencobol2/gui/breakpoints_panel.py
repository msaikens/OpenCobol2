"""A table view of breakpoints across every open editor tab."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakpointEntry:
    """One breakpointed line in one open document.

    Keyed by `document_id` rather than a filesystem path, since untitled
    (never-saved) documents can carry breakpoints too. This is
    editor-side state; a `DebugSessionController` syncs it to a real
    GDB breakpoint while a debug session is active.
    """

    document_id: UUID
    display_name: str
    line: int
    text: str


_COLUMN_HEADERS = (
    "File",
    "Line",
    "Text",
)


class BreakpointsWidget(QTableWidget):
    """Lists every breakpoint across open tabs; double-click jumps to one."""

    entry_activated = Signal(
        UUID,
        int,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only breakpoints table."""

        super().__init__(
            0,
            len(
                _COLUMN_HEADERS,
            ),
            parent,
        )

        self.setHorizontalHeaderLabels(
            _COLUMN_HEADERS,
        )
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(
            False,
        )
        self.cellDoubleClicked.connect(
            self._handle_cell_double_clicked,
        )

        self._entries: tuple[
            BreakpointEntry,
            ...,
        ] = ()

    def set_breakpoints(
        self,
        entries: Sequence[BreakpointEntry],
    ) -> None:
        """Replace the table's contents with a new set of breakpoints."""

        self._entries = tuple(
            entries,
        )
        self.setRowCount(
            len(
                self._entries,
            )
        )

        for row, entry in enumerate(
            self._entries,
        ):
            self.setItem(
                row,
                0,
                QTableWidgetItem(
                    entry.display_name,
                ),
            )
            self.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(
                        entry.line,
                    )
                ),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    entry.text,
                ),
            )

    def clear_breakpoints(
        self,
    ) -> None:
        """Remove every entry from the breakpoints table."""

        self._entries = ()
        self.setRowCount(
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
            entry.document_id,
            entry.line,
        )
