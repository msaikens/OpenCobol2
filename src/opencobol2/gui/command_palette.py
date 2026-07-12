"""A searchable dialog for finding and executing registered commands."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.services.commands import CommandService


class CommandPaletteDialog(QDialog):
    """Lets a user search registered commands by title and run one."""

    def __init__(
        self,
        *,
        command_service: CommandService,
        parent: QWidget | None = None,
    ) -> None:
        """Build the command palette against a command service."""

        super().__init__(
            parent,
        )

        if not isinstance(
            command_service,
            CommandService,
        ):
            raise TypeError(
                "Command palette command service must be "
                "CommandService."
            )

        self._command_service = command_service

        self.setWindowTitle(
            "Command Palette",
        )

        layout = QVBoxLayout(
            self,
        )

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(
            "Type a command name...",
        )
        layout.addWidget(
            self._search_box,
        )

        self._list = QListWidget()
        layout.addWidget(
            self._list,
        )

        self._search_box.textChanged.connect(
            self._refresh_list,
        )
        self._list.itemActivated.connect(
            self._execute_item,
        )

        self._refresh_list(
            "",
        )
        self._search_box.setFocus()

    def keyPressEvent(
        self,
        event,
    ) -> None:
        """Route arrow/enter keys to list navigation and execution."""

        if event.key() == Qt.Key.Key_Down:
            self._move_selection(
                1,
            )
            return

        if event.key() == Qt.Key.Key_Up:
            self._move_selection(
                -1,
            )
            return

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            item = self._list.currentItem()

            if item is not None:
                self._execute_item(
                    item,
                )

            return

        super().keyPressEvent(
            event,
        )

    def _move_selection(
        self,
        delta: int,
    ) -> None:
        """Move the list selection by one row in either direction."""

        count = self._list.count()

        if count == 0:
            return

        current_row = self._list.currentRow()
        new_row = max(
            0,
            min(
                count - 1,
                max(
                    current_row,
                    0,
                )
                + delta,
            ),
        )
        self._list.setCurrentRow(
            new_row,
        )

    def _refresh_list(
        self,
        query: str,
    ) -> None:
        """Rebuild the command list from the current search text."""

        self._list.clear()
        normalized_query = query.strip().lower()

        for command in (
            self._command_service.registry.commands
        ):
            state = command.state(
                CommandContext(),
            )

            if not state.visible:
                continue

            label = (
                f"{command.category}: {command.title}"
                if command.category
                else command.title
            )

            if (
                normalized_query
                and normalized_query
                not in label.lower()
            ):
                continue

            item = QListWidgetItem(
                label,
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                command.command_id,
            )

            if not state.enabled:
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEnabled
                )

            self._list.addItem(
                item,
            )

        if self._list.count() > 0:
            self._list.setCurrentRow(
                0,
            )

    def _execute_item(
        self,
        item: QListWidgetItem,
    ) -> None:
        """Execute one command list item's command, if it is enabled."""

        command_id = item.data(
            Qt.ItemDataRole.UserRole,
        )
        state = self._command_service.get_state(
            command_id,
        )

        if not state.enabled:
            return

        self._command_service.execute(
            command_id,
        )
        self.accept()


def create_show_command_palette_handler(
    *,
    command_service_provider: Callable[
        [],
        CommandService,
    ],
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that opens the command palette dialog.

    `command_service_provider` is resolved lazily, not at handler-creation
    time: the palette command is itself registered as part of building the
    command registry that its own CommandService wraps, so that service
    does not exist yet when this factory runs.
    """

    def handle_show_command_palette(
        context: CommandContext,
    ) -> None:
        dialog = CommandPaletteDialog(
            command_service=command_service_provider(),
            parent=parent_widget_provider(),
        )
        dialog.exec()

    return handle_show_command_palette
