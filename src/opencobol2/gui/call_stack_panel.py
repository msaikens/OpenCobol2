"""A table view of the active debug session's call stack."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.debugger.models import StackFrame


_COLUMN_HEADERS = (
    "Level",
    "Function",
    "File",
    "Line",
)


class CallStackWidget(QTableWidget):
    """Lists every frame in the current thread's call stack, innermost first."""

    frame_activated = Signal(Path, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty, read-only call-stack table."""

        super().__init__(0, len(_COLUMN_HEADERS), parent)

        self.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(False)
        self.cellDoubleClicked.connect(
            self._handle_cell_double_clicked,
        )

        self._frames: tuple[StackFrame, ...] = ()

    def set_frames(self, frames: Sequence[StackFrame]) -> None:
        """Replace the table's contents with a new call stack."""

        self._frames = tuple(frames)
        self.setRowCount(len(self._frames))

        for row, frame in enumerate(self._frames):
            self.setItem(
                row, 0, QTableWidgetItem(str(frame.level)),
            )
            self.setItem(
                row, 1, QTableWidgetItem(frame.function_name),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    frame.source_path.name
                    if frame.source_path is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                3,
                QTableWidgetItem(
                    str(frame.line) if frame.line is not None else "",
                ),
            )

    def clear_frames(self) -> None:
        """Remove every frame from the call-stack table."""

        self._frames = ()
        self.setRowCount(0)

    def _handle_cell_double_clicked(
        self,
        row: int,
        _column: int,
    ) -> None:
        if not (0 <= row < len(self._frames)):
            return

        frame = self._frames[row]

        if frame.source_path is None or frame.line is None:
            return

        self.frame_activated.emit(frame.source_path, frame.line)
