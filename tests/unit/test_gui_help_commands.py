"""Unit tests for the Help menu commands and the shared "not yet available" handler."""

from __future__ import annotations

from unittest.mock import patch

from opencobol2.commands import Command, CommandRegistry
from opencobol2.gui.help_commands import (
    _format_keyboard_shortcuts,
    create_not_yet_available_handler,
    create_show_about_handler,
    create_show_keyboard_shortcuts_handler,
)
from opencobol2.services.commands import CommandService


def _registry_with(*commands: Command) -> CommandRegistry:
    registry = CommandRegistry()

    for command in commands:
        registry.register(command)

    return registry


def test_show_about_handler_shows_the_about_dialog(qapp) -> None:
    handler = create_show_about_handler()

    with patch(
        "opencobol2.gui.help_commands.QMessageBox.about",
    ) as mock_about:
        handler(None)

    mock_about.assert_called_once()
    assert mock_about.call_args[0][1] == "About OpenCobol2"


def test_format_keyboard_shortcuts_reports_no_shortcuts_for_an_empty_registry() -> None:
    service = CommandService(registry=CommandRegistry())

    assert (
        _format_keyboard_shortcuts(service)
        == "No keyboard shortcuts are registered."
    )


def test_format_keyboard_shortcuts_skips_commands_without_shortcuts() -> None:
    service = CommandService(
        registry=_registry_with(
            Command(
                command_id="edit.undo",
                title="Undo",
                handler=lambda context: None,
                category="Edit",
                default_shortcuts=("Ctrl+Z",),
            ),
            Command(
                command_id="edit.rename",
                title="Rename Symbol",
                handler=lambda context: None,
                category="Edit",
            ),
        ),
    )

    formatted = _format_keyboard_shortcuts(service)

    assert "Undo" in formatted
    assert "Ctrl+Z" in formatted
    assert "Rename Symbol" not in formatted


def test_format_keyboard_shortcuts_sorts_by_category_then_title() -> None:
    service = CommandService(
        registry=_registry_with(
            Command(
                command_id="file.save",
                title="Save",
                handler=lambda context: None,
                category="File",
                default_shortcuts=("Ctrl+S",),
            ),
            Command(
                command_id="edit.undo",
                title="Undo",
                handler=lambda context: None,
                category="Edit",
                default_shortcuts=("Ctrl+Z",),
            ),
        ),
    )

    formatted = _format_keyboard_shortcuts(service)
    lines = formatted.splitlines()

    assert lines[0].startswith("Edit")
    assert lines[1].startswith("File")


def test_show_keyboard_shortcuts_handler_does_nothing_without_a_command_service(
    qapp,
) -> None:
    handler = create_show_keyboard_shortcuts_handler(
        command_service_provider=lambda: None,
    )

    with patch(
        "opencobol2.gui.help_commands.QDialog.exec",
    ) as mock_exec:
        handler(None)

    assert not mock_exec.called


def test_show_keyboard_shortcuts_handler_opens_a_dialog_listing_shortcuts(
    qapp,
) -> None:
    from PySide6.QtWidgets import QPlainTextEdit

    service = CommandService(
        registry=_registry_with(
            Command(
                command_id="edit.undo",
                title="Undo",
                handler=lambda context: None,
                category="Edit",
                default_shortcuts=("Ctrl+Z",),
            ),
        ),
    )
    handler = create_show_keyboard_shortcuts_handler(
        command_service_provider=lambda: service,
    )
    created_dialogs = []

    def _capture_dialog(self) -> int:
        created_dialogs.append(self)
        return 0

    with patch(
        "opencobol2.gui.help_commands.QDialog.exec",
        _capture_dialog,
    ):
        handler(None)

    assert len(created_dialogs) == 1
    text_widget = created_dialogs[0].findChild(QPlainTextEdit)
    assert "Undo" in text_widget.toPlainText()
    assert "Ctrl+Z" in text_widget.toPlainText()


def test_not_yet_available_handler_shows_the_given_title_and_message(qapp) -> None:
    handler = create_not_yet_available_handler(
        "Plugins",
        "The extension/plugin system isn't implemented yet.",
    )

    with patch(
        "opencobol2.gui.help_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert mock_information.call_args[0][1] == "Plugins"
    assert (
        mock_information.call_args[0][2]
        == "The extension/plugin system isn't implemented yet."
    )


def test_not_yet_available_handler_passes_the_provided_parent_widget(qapp) -> None:
    sentinel_parent = object()
    handler = create_not_yet_available_handler(
        "Documentation",
        "There is no user documentation yet.",
        parent_widget_provider=lambda: sentinel_parent,
    )

    with patch(
        "opencobol2.gui.help_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    assert mock_information.call_args[0][0] is sentinel_parent
