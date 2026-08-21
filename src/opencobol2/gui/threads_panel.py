"""A table view of the active debug session's threads.

Renders one row per thread reported by the debugger, showing its ID,
run state, and current stack frame location.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.debugger.models import ThreadInfo


_COLUMN_HEADERS = (
    "ID",
    "State",
    "Function",
    "Line",
)


class ThreadsWidget(QTableWidget):
    """Lists every thread in the debugged process.

    Read-only for now -- switching the active thread (`-thread-select`)
    is left for a later pass; this only shows where each thread is
    currently stopped.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty, read-only threads table.

        :param parent: The optional parent widget.
        :returns: None.
        """

        super().__init__(0, len(_COLUMN_HEADERS), parent)

        self.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(False)

    def set_threads(self, threads: Sequence[ThreadInfo]) -> None:
        """Replace the table's contents with a new set of threads."""

        self.setRowCount(len(threads))

        for row, thread in enumerate(threads):
            self.setItem(
                row, 0, QTableWidgetItem(str(thread.thread_id)),
            )
            self.setItem(
                row, 1, QTableWidgetItem(thread.state),
            )
            frame = thread.frame
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    frame.function_name if frame is not None else "",
                ),
            )
            self.setItem(
                row,
                3,
                QTableWidgetItem(
                    str(frame.line)
                    if frame is not None and frame.line is not None
                    else "",
                ),
            )

    def clear_threads(self) -> None:
        """Remove every thread from the threads table."""

        self.setRowCount(0)
