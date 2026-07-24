"""A table view of the active debug session's CPU registers."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.debugger.models import RegisterValue


_COLUMN_HEADERS = (
    "Register",
    "Value",
)


class RegistersWidget(QTableWidget):
    """Lists every named CPU register's current value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty, read-only registers table."""

        super().__init__(0, len(_COLUMN_HEADERS), parent)

        self.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(False)

    def set_registers(self, registers: Sequence[RegisterValue]) -> None:
        """Replace the table's contents with a new set of registers."""

        self.setRowCount(len(registers))

        for row, register in enumerate(registers):
            self.setItem(
                row, 0, QTableWidgetItem(register.name),
            )
            self.setItem(
                row, 1, QTableWidgetItem(register.value),
            )

    def clear_registers(self) -> None:
        """Remove every register from the registers table."""

        self.setRowCount(0)
