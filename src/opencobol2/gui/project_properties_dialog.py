"""A dialog for editing per-project properties, such as the default compiler profile."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opencobol2.project import Project
from opencobol2.settings import SettingsService


_USE_GLOBAL_DEFAULT_LABEL = "(Use global default)"


class ProjectPropertiesDialog(QDialog):
    """Edits one project's build-related properties against real settings."""

    def __init__(
        self,
        *,
        project: Project,
        settings_service: SettingsService,
        parent: QWidget | None = None,
    ) -> None:
        """Build the dialog, preloaded from the given project's properties."""

        super().__init__(
            parent,
        )

        if not isinstance(
            project,
            Project,
        ):
            raise TypeError(
                "Project properties dialog project must be Project."
            )

        if not isinstance(
            settings_service,
            SettingsService,
        ):
            raise TypeError(
                "Project properties dialog service must be "
                "SettingsService."
            )

        self._project = project
        self._settings_service = settings_service
        self.updated_project: Project | None = None

        self.setWindowTitle(
            f"{project.name} Properties",
        )

        layout = QVBoxLayout(
            self,
        )
        form = QFormLayout()

        self._compiler_profile_combo = QComboBox()
        self._compiler_profile_combo.addItem(
            _USE_GLOBAL_DEFAULT_LABEL,
            None,
        )

        for profile in (
            settings_service.current.compilers.profiles
        ):
            self._compiler_profile_combo.addItem(
                profile.display_name,
                profile.profile_id,
            )

        current_index = (
            self._compiler_profile_combo.findData(
                project.properties.default_compiler_profile_id,
            )
        )
        self._compiler_profile_combo.setCurrentIndex(
            current_index
            if current_index >= 0
            else 0,
        )

        form.addRow(
            "Default compiler profile:",
            self._compiler_profile_combo,
        )
        layout.addLayout(
            form,
        )

        button_row = QHBoxLayout()
        button_row.addStretch()

        ok_button = QPushButton(
            "OK",
        )
        ok_button.clicked.connect(
            self._apply_and_accept,
        )
        button_row.addWidget(
            ok_button,
        )

        cancel_button = QPushButton(
            "Cancel",
        )
        cancel_button.clicked.connect(
            self.reject,
        )
        button_row.addWidget(
            cancel_button,
        )

        layout.addLayout(
            button_row,
        )

    def _apply_and_accept(
        self,
    ) -> None:
        """Build the updated project, then close the dialog as accepted."""

        self.updated_project = replace(
            self._project,
            properties=replace(
                self._project.properties,
                default_compiler_profile_id=(
                    self._compiler_profile_combo.currentData()
                ),
            ),
        )

        self.accept()
