"""A table view of Find-in-Files search results."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class FindResult:
    """One source line matching a Find-in-Files search."""

    path: Path
    line: int
    column: int
    line_text: str


_COLUMN_HEADERS = (
    "File",
    "Line",
    "Column",
    "Text",
)


class FindResultsWidget(QTableWidget):
    """Shows Find-in-Files results; double-clicking a row opens it."""

    result_activated = Signal(
        Path,
        int,
        int,
    )
    """Emitted with (path, line, column) when a result row is activated."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only search-results table."""

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

        self._results: tuple[FindResult, ...] = ()

    def set_results(
        self,
        results: Sequence[FindResult],
    ) -> None:
        """Replace the table's contents with a new set of search results."""

        self._results = tuple(
            results,
        )
        self.setRowCount(
            len(
                self._results,
            )
        )

        for row, result in enumerate(
            self._results,
        ):
            self.setItem(
                row,
                0,
                QTableWidgetItem(
                    str(
                        result.path,
                    )
                ),
            )
            self.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(
                        result.line,
                    )
                ),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(
                        result.column,
                    )
                ),
            )
            self.setItem(
                row,
                3,
                QTableWidgetItem(
                    result.line_text,
                ),
            )

    def clear_results(
        self,
    ) -> None:
        """Remove every row from the results table."""

        self._results = ()
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
                self._results,
            )
        ):
            return

        result = self._results[row]
        self.result_activated.emit(
            result.path,
            result.line,
            result.column,
        )
