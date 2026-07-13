"""Unit tests for the COBOL structure outline tree widget."""

from __future__ import annotations

from opencobol2.gui.outline_panel import OutlineWidget
from opencobol2.language import OutlineNode


def test_set_outline_populates_top_level_and_nested_items(
    qapp,
) -> None:
    widget = OutlineWidget()

    widget.set_outline(
        (
            OutlineNode(
                name="DATA DIVISION",
                kind="division",
                line=4,
                children=(
                    OutlineNode(
                        name="WORKING-STORAGE SECTION",
                        kind="section",
                        line=5,
                    ),
                ),
            ),
            OutlineNode(
                name="PROCEDURE DIVISION",
                kind="division",
                line=7,
                children=(
                    OutlineNode(
                        name="MAIN-PARA",
                        kind="paragraph",
                        line=8,
                    ),
                ),
            ),
        )
    )

    assert widget.topLevelItemCount() == 2
    data_item = widget.topLevelItem(0)
    assert data_item.text(0) == "DATA DIVISION"
    assert data_item.childCount() == 1
    assert (
        data_item.child(0).text(0)
        == "WORKING-STORAGE SECTION"
    )

    procedure_item = widget.topLevelItem(1)
    assert procedure_item.child(0).text(0) == "MAIN-PARA"


def test_clear_outline_empties_the_tree(
    qapp,
) -> None:
    widget = OutlineWidget()
    widget.set_outline(
        (
            OutlineNode(
                name="IDENTIFICATION DIVISION (DEMO)",
                kind="division",
                line=1,
            ),
        )
    )

    widget.clear_outline()

    assert widget.topLevelItemCount() == 0


def test_set_outline_replaces_previous_contents(
    qapp,
) -> None:
    widget = OutlineWidget()
    widget.set_outline(
        (
            OutlineNode(
                name="OLD",
                kind="division",
                line=1,
            ),
        )
    )

    widget.set_outline(
        (
            OutlineNode(
                name="NEW",
                kind="division",
                line=2,
            ),
        )
    )

    assert widget.topLevelItemCount() == 1
    assert widget.topLevelItem(0).text(0) == "NEW"


def test_double_clicking_an_item_emits_line_activated(
    qapp,
) -> None:
    widget = OutlineWidget()
    widget.set_outline(
        (
            OutlineNode(
                name="MAIN-PARA",
                kind="paragraph",
                line=8,
            ),
        )
    )
    received = []
    widget.line_activated.connect(
        lambda line: received.append(
            line,
        )
    )

    widget._handle_item_double_clicked(
        widget.topLevelItem(0),
        0,
    )

    assert received == [8]


def test_double_clicking_a_nested_item_emits_its_own_line(
    qapp,
) -> None:
    widget = OutlineWidget()
    widget.set_outline(
        (
            OutlineNode(
                name="PROCEDURE DIVISION",
                kind="division",
                line=7,
                children=(
                    OutlineNode(
                        name="MAIN-PARA",
                        kind="paragraph",
                        line=8,
                    ),
                ),
            ),
        )
    )
    received = []
    widget.line_activated.connect(
        lambda line: received.append(
            line,
        )
    )

    child_item = widget.topLevelItem(
        0,
    ).child(
        0,
    )
    widget._handle_item_double_clicked(
        child_item,
        0,
    )

    assert received == [8]
