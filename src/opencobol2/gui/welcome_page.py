"""A welcome overlay shown in the editor area when no documents are open."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomePageWidget(QWidget):
    """A quick-start page: New/Open Project actions and recent projects.

    Purely presentational: it never touches `SettingsService` or any
    command registry itself. Callers wire `new_project_requested` /
    `open_project_requested` / `open_recent_project_requested` to real
    handlers, and feed the recent-projects list in via
    `set_recent_projects()` -- the same signal-out, wire-it-up-externally
    pattern already used by `ProjectExplorerWidget`.
    """

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_recent_project_requested = Signal(Path)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build the welcome page, initially with an empty recent list."""

        super().__init__(
            parent,
        )

        layout = QVBoxLayout(
            self,
        )
        layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop,
        )

        title_label = QLabel(
            "OpenCobol2",
        )
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter,
        )
        title_font = title_label.font()
        title_font.setPointSize(
            title_font.pointSize() + 12,
        )
        title_font.setBold(
            True,
        )
        title_label.setFont(
            title_font,
        )
        layout.addWidget(
            title_label,
        )

        subtitle_label = QLabel(
            "A modern COBOL development environment",
        )
        subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(
            subtitle_label,
        )

        layout.addSpacing(
            24,
        )

        button_row = QHBoxLayout()
        button_row.addStretch()

        new_project_button = QPushButton(
            "New Project...",
        )
        new_project_button.clicked.connect(
            self.new_project_requested.emit,
        )
        button_row.addWidget(
            new_project_button,
        )

        open_project_button = QPushButton(
            "Open Project...",
        )
        open_project_button.clicked.connect(
            self.open_project_requested.emit,
        )
        button_row.addWidget(
            open_project_button,
        )

        button_row.addStretch()
        layout.addLayout(
            button_row,
        )

        layout.addSpacing(
            24,
        )

        recent_label = QLabel(
            "Recent Projects",
        )
        recent_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(
            recent_label,
        )

        self._recent_list = QListWidget()
        self._recent_list.setMaximumWidth(
            480,
        )
        self._recent_list.itemDoubleClicked.connect(
            self._handle_recent_item_double_clicked,
        )
        layout.addWidget(
            self._recent_list,
        )

        self._empty_recent_label = QLabel(
            "No recent projects yet.",
        )
        self._empty_recent_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(
            self._empty_recent_label,
        )

        self.set_recent_projects(
            (),
        )

    def set_recent_projects(
        self,
        paths: Sequence[Path],
    ) -> None:
        """Replace the displayed recent-projects list."""

        self._recent_list.clear()

        for path in paths:
            item = QListWidgetItem(
                str(
                    path,
                ),
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                Path(
                    path,
                ),
            )
            self._recent_list.addItem(
                item,
            )

        has_recent_projects = bool(
            paths,
        )
        self._recent_list.setVisible(
            has_recent_projects,
        )
        self._empty_recent_label.setVisible(
            not has_recent_projects,
        )

    def _handle_recent_item_double_clicked(
        self,
        item: QListWidgetItem,
    ) -> None:
        path = item.data(
            Qt.ItemDataRole.UserRole,
        )

        if isinstance(
            path,
            Path,
        ):
            self.open_recent_project_requested.emit(
                path,
            )
