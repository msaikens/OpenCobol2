"""Unit tests for the Registers panel widget."""

from __future__ import annotations

from opencobol2.debugger.models import RegisterValue
from opencobol2.gui.registers_panel import RegistersWidget


def test_set_registers_populates_every_column(qapp) -> None:
    widget = RegistersWidget()

    widget.set_registers((RegisterValue(name="rip", value="0x1234"),))

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == "rip"
    assert widget.item(0, 1).text() == "0x1234"


def test_clear_registers_empties_the_table(qapp) -> None:
    widget = RegistersWidget()
    widget.set_registers((RegisterValue(name="rip", value="0x1234"),))

    widget.clear_registers()

    assert widget.rowCount() == 0
