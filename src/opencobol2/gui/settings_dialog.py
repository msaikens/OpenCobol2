"""A dialog for editing OpenCobol2 application settings."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.compiler import CobolSourceFormat
from opencobol2.settings import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    EditorSettings,
    ExternalToolSettings,
    SettingsService,
    ThemeSettings,
)
from opencobol2.theming import ThemeRegistry


_GUIDE_FIELDS = (
    (
        "show_sequence_area",
        "Show sequence area",
    ),
    (
        "show_indicator_column",
        "Show indicator column",
    ),
    (
        "show_area_a",
        "Show Area A",
    ),
    (
        "show_area_b_boundary",
        "Show Area B boundary",
    ),
    (
        "show_reference_area",
        "Show reference area",
    ),
    (
        "shade_areas",
        "Shade areas",
    ),
)


class SettingsDialog(QDialog):
    """Edits editor, COBOL guide, and theme settings against a real service."""

    def __init__(
        self,
        *,
        settings_service: SettingsService,
        theme_registry: ThemeRegistry,
        parent: QWidget | None = None,
    ) -> None:
        """Build the settings dialog, preloaded from the current settings."""

        super().__init__(
            parent,
        )

        if not isinstance(
            settings_service,
            SettingsService,
        ):
            raise TypeError(
                "Settings dialog service must be SettingsService."
            )

        if not isinstance(
            theme_registry,
            ThemeRegistry,
        ):
            raise TypeError(
                "Settings dialog theme registry must be ThemeRegistry."
            )

        self._settings_service = settings_service
        self._theme_registry = theme_registry

        self.setWindowTitle(
            "Settings",
        )

        layout = QVBoxLayout(
            self,
        )

        tabs = QTabWidget()
        layout.addWidget(
            tabs,
        )

        tabs.addTab(
            self._build_editor_tab(),
            "Editor",
        )
        tabs.addTab(
            self._build_cobol_tab(),
            "COBOL",
        )
        tabs.addTab(
            self._build_theme_tab(),
            "Theme",
        )
        tabs.addTab(
            self._build_external_tools_tab(),
            "External Tools",
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

        self._load_from_settings()

    def _build_editor_tab(
        self,
    ) -> QWidget:
        """Build the Editor settings tab and its form fields."""

        tab = QWidget()
        form = QFormLayout(
            tab,
        )

        self._font_family_edit = QLineEdit()
        form.addRow(
            "Font family:",
            self._font_family_edit,
        )

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(
            1,
            200,
        )
        form.addRow(
            "Font size:",
            self._font_size_spin,
        )

        self._tab_width_spin = QSpinBox()
        self._tab_width_spin.setRange(
            1,
            16,
        )
        form.addRow(
            "Tab width:",
            self._tab_width_spin,
        )

        self._insert_spaces_check = QCheckBox()
        form.addRow(
            "Insert spaces:",
            self._insert_spaces_check,
        )

        self._auto_indent_check = QCheckBox()
        form.addRow(
            "Automatic indentation:",
            self._auto_indent_check,
        )

        self._indentation_width_spin = QSpinBox()
        self._indentation_width_spin.setRange(
            1,
            16,
        )
        form.addRow(
            "Indentation width:",
            self._indentation_width_spin,
        )

        self._code_folding_check = QCheckBox()
        form.addRow(
            "Code folding:",
            self._code_folding_check,
        )

        self._show_minimap_check = QCheckBox()
        form.addRow(
            "Minimap:",
            self._show_minimap_check,
        )

        self._autosave_check = QCheckBox()
        form.addRow(
            "Autosave:",
            self._autosave_check,
        )

        self._autosave_interval_spin = QSpinBox()
        self._autosave_interval_spin.setRange(
            5,
            3600,
        )
        self._autosave_interval_spin.setSuffix(
            " s",
        )
        form.addRow(
            "Autosave interval:",
            self._autosave_interval_spin,
        )

        return tab

    def _build_cobol_tab(
        self,
    ) -> QWidget:
        """Build the COBOL settings tab: source format and guide toggles."""

        tab = QWidget()
        layout = QVBoxLayout(
            tab,
        )

        form = QFormLayout()
        self._source_format_combo = QComboBox()
        self._source_format_combo.addItem(
            "Fixed",
            CobolSourceFormat.FIXED,
        )
        self._source_format_combo.addItem(
            "Free",
            CobolSourceFormat.FREE,
        )
        form.addRow(
            "Default source format:",
            self._source_format_combo,
        )
        layout.addLayout(
            form,
        )

        self._guide_checks: dict[
            str,
            QCheckBox,
        ] = {}

        for (
            field_name,
            label,
        ) in _GUIDE_FIELDS:
            checkbox = QCheckBox(
                label,
            )
            self._guide_checks[
                field_name
            ] = checkbox
            layout.addWidget(
                checkbox,
            )

        return tab

    def _build_theme_tab(
        self,
    ) -> QWidget:
        """Build the Theme settings tab: a picker over registered themes."""

        tab = QWidget()
        form = QFormLayout(
            tab,
        )

        self._theme_combo = QComboBox()

        for theme in self._theme_registry.themes:
            self._theme_combo.addItem(
                theme.display_name,
                theme.theme_id,
            )

        form.addRow(
            "Color theme:",
            self._theme_combo,
        )

        return tab

    def _build_external_tools_tab(
        self,
    ) -> QWidget:
        """Build the External Tools tab: overridable external executables."""

        tab = QWidget()
        form = QFormLayout(
            tab,
        )

        row = QWidget()
        row_layout = QHBoxLayout(
            row,
        )
        row_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._git_executable_path_edit = QLineEdit()
        row_layout.addWidget(
            self._git_executable_path_edit,
        )

        browse_button = QPushButton(
            "Browse...",
        )
        browse_button.clicked.connect(
            self._browse_for_git_executable,
        )
        row_layout.addWidget(
            browse_button,
        )

        form.addRow(
            "Git executable:",
            row,
        )

        return tab

    def _browse_for_git_executable(
        self,
    ) -> None:
        """Prompt for a Git executable and fill the path field with it."""

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select Git Executable",
        )

        if path_str:
            self._git_executable_path_edit.setText(
                path_str,
            )

    def _load_from_settings(
        self,
    ) -> None:
        """Populate every field from the current persisted settings."""

        settings = self._settings_service.current

        self._font_family_edit.setText(
            settings.editor.font_family,
        )
        self._font_size_spin.setValue(
            settings.editor.font_size,
        )
        self._tab_width_spin.setValue(
            settings.editor.tab_width,
        )
        self._insert_spaces_check.setChecked(
            settings.editor.insert_spaces,
        )
        self._auto_indent_check.setChecked(
            settings.editor.automatic_indentation,
        )
        self._indentation_width_spin.setValue(
            settings.editor.indentation_width,
        )
        self._code_folding_check.setChecked(
            settings.editor.code_folding,
        )
        self._show_minimap_check.setChecked(
            settings.editor.show_minimap,
        )
        self._autosave_check.setChecked(
            settings.editor.autosave_enabled,
        )
        self._autosave_interval_spin.setValue(
            settings.editor.autosave_interval_seconds,
        )

        source_format_index = (
            self._source_format_combo.findData(
                settings.cobol.default_source_format,
            )
        )

        if source_format_index >= 0:
            self._source_format_combo.setCurrentIndex(
                source_format_index,
            )

        for (
            field_name,
            checkbox,
        ) in self._guide_checks.items():
            checkbox.setChecked(
                getattr(
                    settings.cobol.guides,
                    field_name,
                )
            )

        theme_index = self._theme_combo.findData(
            settings.theme.active_theme_id,
        )

        if theme_index >= 0:
            self._theme_combo.setCurrentIndex(
                theme_index,
            )

        self._git_executable_path_edit.setText(
            str(
                settings.external_tools.git_executable_path,
            )
            if settings.external_tools.git_executable_path
            is not None
            else "",
        )

    def _apply_and_accept(
        self,
    ) -> None:
        """Persist every tab's settings, then close the dialog as accepted.

        Editor §Dialogs-3: the four `update_*` calls below used to run
        back-to-back with zero exception handling -- a failure partway
        through (e.g. an empty theme registry, so the theme combo
        returns `None` and `ThemeSettings` raises `TypeError`) left
        every category persisted *before* the failure already applied
        to disk, with no rollback and no error shown. Every settings
        object is now built and validated first; persistence only
        starts once all four have been constructed successfully,
        mirroring `CompilerProfilesDialog._apply_and_accept`'s
        existing validate-then-persist structure.
        """

        git_executable_path_text = (
            self._git_executable_path_edit.text().strip()
        )

        try:
            editor_settings = EditorSettings(
                font_family=self._font_family_edit.text(),
                font_size=self._font_size_spin.value(),
                tab_width=self._tab_width_spin.value(),
                insert_spaces=self._insert_spaces_check.isChecked(),
                automatic_indentation=(
                    self._auto_indent_check.isChecked()
                ),
                indentation_width=(
                    self._indentation_width_spin.value()
                ),
                code_folding=self._code_folding_check.isChecked(),
                show_minimap=(
                    self._show_minimap_check.isChecked()
                ),
                autosave_enabled=(
                    self._autosave_check.isChecked()
                ),
                autosave_interval_seconds=(
                    self._autosave_interval_spin.value()
                ),
            )
            cobol_settings = CobolSettings(
                default_source_format=(
                    self._source_format_combo.currentData()
                ),
                guides=CobolGuideSettings(
                    **{
                        field_name: checkbox.isChecked()
                        for field_name, checkbox in (
                            self._guide_checks.items()
                        )
                    },
                ),
            )
            theme_settings = ThemeSettings(
                active_theme_id=(
                    self._theme_combo.currentData()
                ),
            )
            external_tool_settings = ExternalToolSettings(
                git_executable_path=(
                    Path(
                        git_executable_path_text,
                    )
                    if git_executable_path_text
                    else None
                ),
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                self,
                "Settings",
                str(
                    error,
                ),
            )
            return

        self._settings_service.update_editor(
            editor_settings,
        )
        self._settings_service.update_cobol(
            cobol_settings,
        )
        self._settings_service.update_theme(
            theme_settings,
        )
        self._settings_service.update_external_tools(
            external_tool_settings,
        )

        self.accept()


def create_show_settings_handler(
    *,
    settings_service: SettingsService,
    theme_registry: ThemeRegistry,
    on_applied: Callable[
        [ApplicationSettings],
        None,
    ] = lambda settings: None,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that opens the settings dialog and applies changes."""

    def handle_show_settings(
        context: CommandContext,
    ) -> None:
        dialog = SettingsDialog(
            settings_service=settings_service,
            theme_registry=theme_registry,
            parent=parent_widget_provider(),
        )

        if dialog.exec():
            on_applied(
                settings_service.current,
            )

    return handle_show_settings
