"""Unit tests for the Find-in-Files results table widget."""

from __future__ import annotations

from pathlib import Path

from opencobol2.gui.find_results_panel import (
    FindResult,
    FindResultsWidget,
)


def test_set_results_populates_every_column(
    qapp,
    tmp_path: Path,
) -> None:
    widget = FindResultsWidget()
    path = tmp_path / "main.cbl"

    widget.set_results(
        (
            FindResult(
                path=path,
                line=5,
                column=12,
                line_text="MOVE X TO Y",
            ),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == str(path)
    assert widget.item(0, 1).text() == "5"
    assert widget.item(0, 2).text() == "12"
    assert widget.item(0, 3).text() == "MOVE X TO Y"


def test_clear_results_empties_the_table(
    qapp,
    tmp_path: Path,
) -> None:
    widget = FindResultsWidget()
    widget.set_results(
        (
            FindResult(
                path=tmp_path / "main.cbl",
                line=1,
                column=1,
                line_text="x",
            ),
        )
    )

    widget.clear_results()

    assert widget.rowCount() == 0


def test_double_clicking_a_row_emits_result_activated(
    qapp,
    tmp_path: Path,
) -> None:
    widget = FindResultsWidget()
    path = tmp_path / "main.cbl"
    widget.set_results(
        (
            FindResult(
                path=path,
                line=7,
                column=3,
                line_text="DISPLAY X",
            ),
        )
    )
    received = []
    widget.result_activated.connect(
        lambda activated_path, line, column: received.append(
            (
                activated_path,
                line,
                column,
            )
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == [
        (
            path,
            7,
            3,
        )
    ]


def test_double_clicking_an_out_of_range_row_does_nothing(
    qapp,
) -> None:
    widget = FindResultsWidget()
    received = []
    widget.result_activated.connect(
        lambda *args: received.append(
            args,
        )
    )

    widget._handle_cell_double_clicked(
        0,
        0,
    )

    assert received == []
