"""A read-only log view for compiler/build process output."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QWidget,
)


class OutputWidget(QPlainTextEdit):
    """Append-only log of build and compiler process output."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only output log."""

        super().__init__(
            parent,
        )

        self.setReadOnly(
            True,
        )
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap,
        )

    def append_line(
        self,
        text: str,
    ) -> None:
        """Append one line of output text to the log."""

        self.appendPlainText(
            text,
        )
