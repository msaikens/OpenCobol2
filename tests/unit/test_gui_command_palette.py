"""Unit tests for the Command Palette dialog."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from opencobol2.commands import (
    Command,
    CommandRegistry,
    CommandState,
)
from opencobol2.gui.command_palette import (
    CommandPaletteDialog,
    create_show_command_palette_handler,
)
from opencobol2.services.commands import CommandService


def _build_service() -> CommandService:
    registry = CommandRegistry()
    registry.register(
        Command(
            command_id="test.new-file",
            title="New File",
            handler=lambda context: "new-file",
            category="File",
        )
    )
    registry.register(
        Command(
            command_id="test.save-file",
            title="Save File",
            handler=lambda context: "save-file",
            category="File",
        )
    )
    registry.register(
        Command(
            command_id="test.disabled",
            title="Disabled Thing",
            handler=lambda context: "disabled",
            state_provider=lambda context: CommandState(
                enabled=False,
            ),
        )
    )
    registry.register(
        Command(
            command_id="test.hidden",
            title="Hidden Thing",
            handler=lambda context: "hidden",
            state_provider=lambda context: CommandState(
                visible=False,
            ),
        )
    )

    return CommandService(
        registry=registry,
    )


def test_palette_lists_visible_commands_with_category_prefix(
    qapp,
) -> None:
    dialog = CommandPaletteDialog(
        command_service=_build_service(),
    )

    labels = [
        dialog._list.item(
            index,
        ).text()
        for index in range(
            dialog._list.count(),
        )
    ]

    assert "File: New File" in labels
    assert "File: Save File" in labels
    assert "Disabled Thing" in labels
    assert not any(
        "Hidden" in label
        for label in labels
    )


def test_palette_filters_by_typed_text(
    qapp,
) -> None:
    dialog = CommandPaletteDialog(
        command_service=_build_service(),
    )

    dialog._search_box.setText(
        "save",
    )

    labels = [
        dialog._list.item(
            index,
        ).text()
        for index in range(
            dialog._list.count(),
        )
    ]

    assert labels == ["File: Save File"]


def test_palette_filters_by_category(
    qapp,
) -> None:
    dialog = CommandPaletteDialog(
        command_service=_build_service(),
    )

    dialog._search_box.setText(
        "file:",
    )

    labels = {
        dialog._list.item(
            index,
        ).text()
        for index in range(
            dialog._list.count(),
        )
    }

    assert labels == {
        "File: New File",
        "File: Save File",
    }


def test_disabled_command_item_is_not_selectable_enabled(
    qapp,
) -> None:
    dialog = CommandPaletteDialog(
        command_service=_build_service(),
    )
    dialog._search_box.setText(
        "Disabled Thing",
    )
    item = dialog._list.item(
        0,
    )

    assert not bool(
        item.flags()
        & Qt.ItemFlag.ItemIsEnabled
    )


def test_executing_enabled_item_runs_command_and_accepts(
    qapp,
) -> None:
    service = _build_service()
    dialog = CommandPaletteDialog(
        command_service=service,
    )
    dialog._search_box.setText(
        "New File",
    )
    item = dialog._list.item(
        0,
    )

    dialog._execute_item(
        item,
    )

    assert dialog.result() == dialog.DialogCode.Accepted


def test_executing_disabled_item_does_nothing(
    qapp,
) -> None:
    service = _build_service()
    dialog = CommandPaletteDialog(
        command_service=service,
    )
    dialog._search_box.setText(
        "Disabled Thing",
    )
    item = dialog._list.item(
        0,
    )

    dialog._execute_item(
        item,
    )

    assert dialog.result() == 0


def test_move_selection_wraps_within_bounds(
    qapp,
) -> None:
    dialog = CommandPaletteDialog(
        command_service=_build_service(),
    )
    dialog._search_box.setText(
        "file",
    )

    assert dialog._list.currentRow() == 0

    dialog._move_selection(
        -1,
    )
    assert dialog._list.currentRow() == 0

    dialog._move_selection(
        1,
    )
    assert dialog._list.currentRow() == 1

    dialog._move_selection(
        1,
    )
    assert dialog._list.currentRow() == 1


def test_palette_rejects_non_command_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Command palette command service must be "
            "CommandService"
        ),
    ):
        CommandPaletteDialog(
            command_service=object(),  # type: ignore[arg-type]
        )


def test_show_command_palette_handler_opens_dialog(
    qapp,
) -> None:
    service = _build_service()
    handler = create_show_command_palette_handler(
        command_service_provider=lambda: service,
    )

    with patch(
        "opencobol2.gui.command_palette."
        "CommandPaletteDialog.exec",
        return_value=0,
    ) as mock_exec:
        handler(
            None,
        )

    mock_exec.assert_called_once()
