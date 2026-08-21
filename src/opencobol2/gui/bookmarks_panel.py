"""A table view of bookmarks across every open editor tab.

Presents a flat, read-only table of every bookmark known to the
application regardless of which tab it lives in, and emits a signal
when the user double-clicks a row so the host window can jump to it.
"""

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
class BookmarkEntry:
    """One bookmarked line in one open document.

    Keyed by `document_id` rather than a filesystem path, since untitled
    (never-saved) documents can be bookmarked too.

    :ivar document_id: The unique identifier of the document the
        bookmark belongs to, used instead of a filesystem path so
        never-saved documents can be bookmarked too.
    :ivar display_name: The human-readable label to show for the
        document in the "File" column.
    :ivar line: The 1-based line number the bookmark points to.
    :ivar text: The source text of the bookmarked line, shown in the
        "Text" column.
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


class BookmarksWidget(QTableWidget):
    """Lists every bookmark across open tabs; double-click jumps to one.

    :ivar entry_activated: Qt signal emitted with a bookmark's
        ``document_id`` and ``line`` when the user double-clicks its
        row.
    """

    entry_activated = Signal(
        UUID,
        int,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only bookmarks table.

        :param parent: The optional parent widget, passed through to
            :class:`QTableWidget`.
        :returns: None. The table is initialized with its column
            headers, read-only/row-selection behavior, and an empty
            entry list.
        """

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
            BookmarkEntry,
            ...,
        ] = ()

    def set_bookmarks(
        self,
        entries: Sequence[BookmarkEntry],
    ) -> None:
        """Replace the table's contents with a new set of bookmarks.

        :param entries: The complete new set of bookmarks to display,
            replacing whatever was previously shown.
        :returns: None. The table's rows are rebuilt from `entries`
            and the stored entry list is replaced.
        """

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

    def clear_bookmarks(
        self,
    ) -> None:
        """Remove every entry from the bookmarks table.

        :returns: None. The stored entry list and every table row are
            cleared.
        """

        self._entries = ()
        self.setRowCount(
            0,
        )

    def _handle_cell_double_clicked(
        self,
        row: int,
        _column: int,
    ) -> None:
        """Emit `entry_activated` for the bookmark on a double-clicked row.

        :param row: The 0-based row index that was double-clicked.
        :param _column: The 0-based column index that was
            double-clicked; unused since every column in a row maps
            to the same bookmark.
        :returns: None. Emits `entry_activated` unless `row` is out
            of range for the current entry list.
        """

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
