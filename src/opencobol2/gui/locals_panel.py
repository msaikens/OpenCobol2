"""A table view of the active debug session's local COBOL variables."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.debugger.models import Variable


_COLUMN_HEADERS = (
    "Name",
    "Value",
    "Type",
)


class LocalsWidget(QTableWidget):
    """Lists every decoded local COBOL variable at the current stop."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty, read-only locals table."""

        super().__init__(0, len(_COLUMN_HEADERS), parent)

        self.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(False)

    def set_variables(self, variables: Sequence[Variable]) -> None:
        """Replace the table's contents with a new set of variables."""

        self.setRowCount(len(variables))

        for row, variable in enumerate(variables):
            self.setItem(
                row, 0, QTableWidgetItem(variable.name),
            )
            self.setItem(
                row, 1, QTableWidgetItem(variable.value),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(variable.type_name or ""),
            )

    def clear_variables(self) -> None:
        """Remove every variable from the locals table."""

        self.setRowCount(0)
