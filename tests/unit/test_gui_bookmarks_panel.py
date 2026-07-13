"""Unit tests for the Bookmarks panel widget."""

from __future__ import annotations

from uuid import uuid4

from opencobol2.gui.bookmarks_panel import (
    BookmarkEntry,
    BookmarksWidget,
)


def test_set_bookmarks_populates_every_column(
    qapp,
) -> None:
    widget = BookmarksWidget()
    document_id = uuid4()

    widget.set_bookmarks(
        (
            BookmarkEntry(
                document_id=document_id,
                display_name="main.cbl",
                line=5,
                text="MOVE X TO Y",
            ),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == "main.cbl"
    assert widget.item(0, 1).text() == "5"
    assert widget.item(0, 2).text() == "MOVE X TO Y"


def test_clear_bookmarks_empties_the_table(
    qapp,
) -> None:
    widget = BookmarksWidget()
    widget.set_bookmarks(
        (
            BookmarkEntry(
                document_id=uuid4(),
                display_name="main.cbl",
                line=1,
                text="x",
            ),
        )
    )

    widget.clear_bookmarks()

    assert widget.rowCount() == 0


def test_double_clicking_a_row_emits_entry_activated(
    qapp,
) -> None:
    widget = BookmarksWidget()
    document_id = uuid4()
    widget.set_bookmarks(
        (
            BookmarkEntry(
                document_id=document_id,
                display_name="main.cbl",
                line=7,
                text="DISPLAY X",
            ),
        )
    )
    received = []
    widget.entry_activated.connect(
        lambda activated_document_id, line: received.append(
            (
                activated_document_id,
                line,
            )
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == [
        (
            document_id,
            7,
        )
    ]


def test_double_clicking_an_out_of_range_row_does_nothing(
    qapp,
) -> None:
    widget = BookmarksWidget()
    received = []
    widget.entry_activated.connect(
        lambda *args: received.append(
            args,
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == []
