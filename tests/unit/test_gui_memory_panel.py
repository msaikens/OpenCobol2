"""Unit tests for the Memory panel widget and its hex-dump formatting."""

from __future__ import annotations

from opencobol2.debugger.models import MemoryBytes
from opencobol2.gui.memory_panel import format_hex_dump, MemoryWidget


def test_format_hex_dump_renders_offset_hex_and_ascii() -> None:
    memory = MemoryBytes(
        address=0x1000,
        data=b"HELLO, WORLD!\x00\x01\x02",
    )

    dump = format_hex_dump(memory)

    assert dump.startswith("00001000  ")
    assert "48 45 4c 4c 4f" in dump
    assert "|HELLO, WORLD!" in dump
    # Non-printable bytes render as a dot, not raw control characters.
    assert dump.count("|") == 2


def test_format_hex_dump_wraps_at_sixteen_bytes_per_row() -> None:
    memory = MemoryBytes(address=0, data=bytes(range(20)))

    dump = format_hex_dump(memory)
    lines = dump.splitlines()

    assert len(lines) == 2
    assert lines[0].startswith("00000000  ")
    assert lines[1].startswith("00000010  ")


def test_format_hex_dump_of_empty_data_is_empty() -> None:
    assert format_hex_dump(MemoryBytes(address=0, data=b"")) == ""


def test_read_button_emits_address_and_length(qapp) -> None:
    widget = MemoryWidget()
    received = []
    widget.read_requested.connect(
        lambda address, length: received.append((address, length))
    )

    widget._address_input.setText("&b_19")
    widget._length_input.setValue(8)
    widget._handle_read()

    assert received == [("&b_19", 8)]


def test_read_with_empty_address_does_nothing(qapp) -> None:
    widget = MemoryWidget()
    received = []
    widget.read_requested.connect(lambda *args: received.append(args))

    widget._handle_read()

    assert received == []


def test_set_memory_renders_the_hex_dump(qapp) -> None:
    widget = MemoryWidget()

    widget.set_memory(MemoryBytes(address=0, data=b"HI"))

    assert "48 49" in widget._output.toPlainText()


def test_clear_memory_blanks_the_output(qapp) -> None:
    widget = MemoryWidget()
    widget.set_memory(MemoryBytes(address=0, data=b"HI"))

    widget.clear_memory()

    assert widget._output.toPlainText() == ""
