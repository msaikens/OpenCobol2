"""Unit tests for the Watch panel widget."""

from __future__ import annotations

from opencobol2.debugger.models import WatchExpression
from opencobol2.gui.watch_panel import WatchWidget


def test_typing_and_pressing_enter_adds_an_expression(qapp) -> None:
    widget = WatchWidget()
    received = []
    widget.expressions_changed.connect(lambda: received.append(True))

    widget._input.setText("WS-SUM")
    widget._input.returnPressed.emit()

    assert widget.expressions() == ("WS-SUM",)
    assert widget._input.text() == ""
    assert received == [True]


def test_adding_an_empty_expression_is_a_no_op(qapp) -> None:
    widget = WatchWidget()
    received = []
    widget.expressions_changed.connect(lambda: received.append(True))

    widget._input.setText("   ")
    widget._handle_add()

    assert widget.expressions() == ()
    assert received == []


def test_adding_a_duplicate_expression_is_a_no_op(qapp) -> None:
    widget = WatchWidget()
    widget._input.setText("WS-SUM")
    widget._handle_add()
    received = []
    widget.expressions_changed.connect(lambda: received.append(True))

    widget._input.setText("WS-SUM")
    widget._handle_add()

    assert widget.expressions() == ("WS-SUM",)
    assert received == []


def test_set_watches_shows_value_or_error(qapp) -> None:
    widget = WatchWidget()
    widget._input.setText("WS-SUM")
    widget._handle_add()
    widget._input.setText("1 + 1")
    widget._handle_add()

    widget.set_watches(
        (
            WatchExpression(expression="WS-SUM", value="0030"),
            WatchExpression(
                expression="1 + 1",
                error="No active debug session.",
            ),
        )
    )

    assert widget._table.rowCount() == 2
    assert widget._table.item(0, 0).text() == "WS-SUM"
    assert widget._table.item(0, 1).text() == "0030"
    assert widget._table.item(1, 0).text() == "1 + 1"
    assert (
        widget._table.item(1, 1).text() == "No active debug session."
    )


def test_remove_selected_removes_the_expression(qapp) -> None:
    widget = WatchWidget()
    widget._input.setText("WS-A")
    widget._handle_add()
    widget._input.setText("WS-B")
    widget._handle_add()
    widget.set_watches(
        (
            WatchExpression(expression="WS-A", value="0010"),
            WatchExpression(expression="WS-B", value="0020"),
        )
    )
    widget._table.selectRow(0)
    received = []
    widget.expressions_changed.connect(lambda: received.append(True))

    widget._handle_remove_selected()

    assert widget.expressions() == ("WS-B",)
    assert received == [True]


def test_remove_selected_with_no_selection_is_a_no_op(qapp) -> None:
    widget = WatchWidget()
    widget._input.setText("WS-A")
    widget._handle_add()
    received = []
    widget.expressions_changed.connect(lambda: received.append(True))

    widget._handle_remove_selected()

    assert widget.expressions() == ("WS-A",)
    assert received == []


def test_clear_watches_blanks_values_but_keeps_expressions(qapp) -> None:
    widget = WatchWidget()
    widget._input.setText("WS-A")
    widget._handle_add()
    widget.set_watches(
        (WatchExpression(expression="WS-A", value="0010"),)
    )

    widget.clear_watches()

    assert widget.expressions() == ("WS-A",)
    assert widget._table.rowCount() == 1
    assert widget._table.item(0, 1).text() == ""
