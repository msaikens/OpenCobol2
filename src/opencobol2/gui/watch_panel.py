"""A user-managed list of watch expressions, evaluated on every debug stop."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opencobol2.debugger.models import WatchExpression


_COLUMN_HEADERS = (
    "Expression",
    "Value",
)


class WatchWidget(QWidget):
    """Lets the user add/remove watch expressions and shows their values.

    Owns only the list of expression *strings* the user asked to watch
    -- evaluating them against a live session (a COBOL data name via
    `DebugSessionController.read_variable`, falling back to a raw GDB
    expression) is the caller's job; `set_watches()` just renders
    whatever results it's given.
    """

    expressions_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty watch list with an expression input row."""

        super().__init__(parent)

        self._expressions: list[str] = []

        self._input = QLineEdit(self)
        self._input.setPlaceholderText(
            "Add a data name or expression to watch...",
        )
        self._input.returnPressed.connect(self._handle_add)

        add_button = QPushButton("Add", self)
        add_button.clicked.connect(self._handle_add)

        remove_button = QPushButton("Remove Selected", self)
        remove_button.clicked.connect(self._handle_remove_selected)

        self._table = QTableWidget(0, len(_COLUMN_HEADERS), self)
        self._table.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.verticalHeader().setVisible(False)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(add_button)

        layout = QVBoxLayout(self)
        layout.addLayout(input_row)
        layout.addWidget(self._table)
        layout.addWidget(remove_button)

    def expressions(self) -> tuple[str, ...]:
        """Return every expression currently being watched, in order."""

        return tuple(self._expressions)

    def set_watches(self, watches: Sequence[WatchExpression]) -> None:
        """Replace the table's contents with newly evaluated watch results."""

        self._table.setRowCount(len(watches))

        for row, watch in enumerate(watches):
            self._table.setItem(
                row, 0, QTableWidgetItem(watch.expression),
            )
            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    watch.value if watch.error is None else watch.error,
                ),
            )

    def clear_watches(self) -> None:
        """Blank every value cell without forgetting which expressions exist."""

        self._table.setRowCount(len(self._expressions))

        for row in range(len(self._expressions)):
            self._table.setItem(row, 1, QTableWidgetItem(""))

    def _handle_add(self) -> None:
        text = self._input.text().strip()
        self._input.clear()

        if not text or text in self._expressions:
            return

        self._expressions.append(text)
        self.expressions_changed.emit()

    def _handle_remove_selected(self) -> None:
        rows = sorted(
            {index.row() for index in self._table.selectedIndexes()},
            reverse=True,
        )

        if not rows:
            return

        for row in rows:
            del self._expressions[row]

        self.expressions_changed.emit()
