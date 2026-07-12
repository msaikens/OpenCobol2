"""A table view of parsed compiler diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.compiler import CompilerDiagnostic


_COLUMN_HEADERS = (
    "Severity",
    "File",
    "Line",
    "Column",
    "Message",
)


class ProblemsWidget(QTableWidget):
    """Shows parsed compiler diagnostics from the most recent build."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only diagnostics table."""

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

    def set_diagnostics(
        self,
        diagnostics: Sequence[CompilerDiagnostic],
    ) -> None:
        """Replace the table's contents with a new set of diagnostics."""

        self.setRowCount(
            len(
                diagnostics,
            ),
        )

        for row, diagnostic in enumerate(
            diagnostics,
        ):
            self.setItem(
                row,
                0,
                QTableWidgetItem(
                    diagnostic.severity.value.upper(),
                ),
            )
            self.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(
                        diagnostic.source_path,
                    )
                    if diagnostic.source_path is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(
                        diagnostic.line,
                    )
                    if diagnostic.line is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                3,
                QTableWidgetItem(
                    str(
                        diagnostic.column,
                    )
                    if diagnostic.column is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                4,
                QTableWidgetItem(
                    diagnostic.message,
                ),
            )

    def clear_diagnostics(
        self,
    ) -> None:
        """Remove every row from the diagnostics table."""

        self.setRowCount(
            0,
        )
