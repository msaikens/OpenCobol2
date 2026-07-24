"""An address/length-driven raw memory hex-dump viewer."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from opencobol2.debugger.models import MemoryBytes


_BYTES_PER_ROW = 16


def format_hex_dump(memory: MemoryBytes) -> str:
    """Render a classic `offset  hex bytes  |ascii|` hex dump."""

    lines: list[str] = []

    for row_start in range(0, len(memory.data), _BYTES_PER_ROW):
        row_bytes = memory.data[row_start : row_start + _BYTES_PER_ROW]
        hex_part = " ".join(f"{byte:02x}" for byte in row_bytes)
        ascii_part = "".join(
            chr(byte) if 0x20 <= byte < 0x7F else "."
            for byte in row_bytes
        )
        lines.append(
            f"{memory.address + row_start:08x}  "
            f"{hex_part:<{_BYTES_PER_ROW * 3 - 1}}  |{ascii_part}|",
        )

    return "\n".join(lines)


class MemoryWidget(QWidget):
    """Prompts for an address/length and shows the resulting hex dump."""

    read_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an empty memory viewer with an address/length input row."""

        super().__init__(parent)

        self._address_input = QLineEdit(self)
        self._address_input.setPlaceholderText(
            "Address or expression (e.g. &b_19, 0x1000)",
        )
        self._address_input.returnPressed.connect(self._handle_read)

        self._length_input = QSpinBox(self)
        self._length_input.setRange(1, 4096)
        self._length_input.setValue(64)

        read_button = QPushButton("Read", self)
        read_button.clicked.connect(self._handle_read)

        self._output = QPlainTextEdit(self)
        self._output.setReadOnly(True)
        self._output.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap,
        )

        input_row = QHBoxLayout()
        input_row.addWidget(self._address_input)
        input_row.addWidget(QLabel("Length:", self))
        input_row.addWidget(self._length_input)
        input_row.addWidget(read_button)

        layout = QVBoxLayout(self)
        layout.addLayout(input_row)
        layout.addWidget(self._output)

    def set_memory(self, memory: MemoryBytes) -> None:
        """Show a hex dump of a freshly read block of memory."""

        self._output.setPlainText(format_hex_dump(memory))

    def clear_memory(self) -> None:
        """Blank the hex-dump output."""

        self._output.clear()

    def _handle_read(self) -> None:
        address = self._address_input.text().strip()

        if not address:
            return

        self.read_requested.emit(address, self._length_input.value())
