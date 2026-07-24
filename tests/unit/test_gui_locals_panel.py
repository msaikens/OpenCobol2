"""Unit tests for the Locals panel widget."""

from __future__ import annotations

from opencobol2.debugger.models import Variable
from opencobol2.gui.locals_panel import LocalsWidget


def test_set_variables_populates_every_column(qapp) -> None:
    widget = LocalsWidget()

    widget.set_variables(
        (
            Variable(name="WS-SUM", value="0030", type_name="display"),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == "WS-SUM"
    assert widget.item(0, 1).text() == "0030"
    assert widget.item(0, 2).text() == "display"


def test_set_variables_handles_a_missing_type_name(qapp) -> None:
    widget = LocalsWidget()

    widget.set_variables((Variable(name="WS-A", value="0010"),))

    assert widget.item(0, 2).text() == ""


def test_clear_variables_empties_the_table(qapp) -> None:
    widget = LocalsWidget()
    widget.set_variables((Variable(name="WS-A", value="0010"),))

    widget.clear_variables()

    assert widget.rowCount() == 0
