"""Wires the Help menu's About and Keyboard Shortcuts commands.

Editor §UIBootstrap-1: neither had an application handler wired at
all previously.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from opencobol2.commands import CommandContext, CommandHandler
from opencobol2.services.commands import CommandService


_ABOUT_TEXT = (
    "<b>OpenCobol2</b><br><br>"
    "A COBOL IDE built on GnuCOBOL and PySide6."
)


def create_show_about_handler(
    *,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that shows the About dialog."""

    def handle_show_about(context: CommandContext) -> None:
        QMessageBox.about(
            parent_widget_provider(),
            "About OpenCobol2",
            _ABOUT_TEXT,
        )

    return handle_show_about


def _format_keyboard_shortcuts(
    command_service: CommandService,
) -> str:
    """Render every registered command's shortcut as one line of text."""

    rows = sorted(
        (
            (
                command.category or "",
                command.title,
                ", ".join(command.default_shortcuts),
            )
            for command in command_service.registry.commands
            if command.default_shortcuts
        ),
    )

    if not rows:
        return "No keyboard shortcuts are registered."

    category_width = max(len(row[0]) for row in rows) + 2
    title_width = max(len(row[1]) for row in rows) + 2

    return "\n".join(
        f"{category:<{category_width}}"
        f"{title:<{title_width}}"
        f"{shortcut}"
        for category, title, shortcut in rows
    )


def create_show_keyboard_shortcuts_handler(
    *,
    command_service_provider: Callable[[], CommandService | None],
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that lists every registered command's shortcut."""

    def handle_show_keyboard_shortcuts(context: CommandContext) -> None:
        command_service = command_service_provider()

        if command_service is None:
            return

        dialog = QDialog(
            parent_widget_provider(),
        )
        dialog.setWindowTitle(
            "Keyboard Shortcuts",
        )
        dialog.resize(520, 480)

        text = QPlainTextEdit(
            dialog,
        )
        text.setReadOnly(True)
        text.setPlainText(
            _format_keyboard_shortcuts(
                command_service,
            ),
        )

        layout = QVBoxLayout(
            dialog,
        )
        layout.addWidget(
            text,
        )

        dialog.exec()

    return handle_show_keyboard_shortcuts


def create_not_yet_available_handler(
    title: str,
    message: str,
    *,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that shows an honest "not yet available" message.

    For commands whose underlying feature genuinely doesn't exist yet
    (running a compiled program outside the debugger, repository-level
    Git settings, the not-yet-built plugin system, real user-facing
    documentation) -- this replaces a silent, unhandled
    `BuiltInCommandHandlerNotConfiguredError` with a clear message
    instead, without pretending the feature exists.
    """

    def handle_not_yet_available(context: CommandContext) -> None:
        QMessageBox.information(
            parent_widget_provider(),
            title,
            message,
        )

    return handle_not_yet_available
