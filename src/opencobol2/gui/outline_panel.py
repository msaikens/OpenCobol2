"""A tree view of the active document's COBOL structure."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from opencobol2.language import OutlineNode


class OutlineWidget(QTreeWidget):
    """Shows the active editor's division/section/paragraph structure.

    Double-clicking any entry emits `line_activated` with its 1-based
    source line, for the caller to move the active editor's cursor there.
    """

    line_activated = Signal(
        int,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty outline tree."""

        super().__init__(
            parent,
        )

        self.setHeaderHidden(
            True,
        )
        self.itemDoubleClicked.connect(
            self._handle_item_double_clicked,
        )

    def set_outline(
        self,
        nodes: Sequence[OutlineNode],
    ) -> None:
        """Replace the tree's contents with a new outline."""

        self.clear()

        for node in nodes:
            self.addTopLevelItem(
                _build_item(
                    node,
                ),
            )

        self.expandAll()

    def clear_outline(
        self,
    ) -> None:
        """Remove every entry from the outline tree."""

        self.clear()

    def _handle_item_double_clicked(
        self,
        item: QTreeWidgetItem,
        _column: int,
    ) -> None:
        line = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        if isinstance(
            line,
            int,
        ):
            self.line_activated.emit(
                line,
            )


def _build_item(
    node: OutlineNode,
) -> QTreeWidgetItem:
    item = QTreeWidgetItem(
        [
            node.name,
        ]
    )
    item.setData(
        0,
        Qt.ItemDataRole.UserRole,
        node.line,
    )

    for child in node.children:
        item.addChild(
            _build_item(
                child,
            ),
        )

    return item
