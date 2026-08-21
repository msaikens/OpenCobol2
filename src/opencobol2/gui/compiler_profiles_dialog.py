"""A dialog for managing configured COBOL compiler profiles.

Presents the set of configured :class:`CompilerProfile` entries in a list,
lets the user add, remove, or designate one as the default, and renders a
per-provider configuration form (built from each provider's declared
:class:`CompilerConfigurationField` list) for editing the selected profile's
details.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.compiler.providers import (
    CompilerConfigurationField,
    CompilerConfigurationFieldKind,
    CompilerProfile,
    CompilerProviderRegistry,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
)


class _PathFieldEditor(QWidget):
    """A single-line path editor paired with a file-picker button.

    :ivar line_edit: The text field holding the current path, editable
        directly or filled in via the "Browse..." button.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build the line edit and browse button and lay them out horizontally.

        :param parent: The optional parent widget, forwarded to
            :class:`QWidget`.
        :returns: None.
        """

        super().__init__(
            parent,
        )

        layout = QHBoxLayout(
            self,
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.line_edit = QLineEdit()
        layout.addWidget(
            self.line_edit,
        )

        browse_button = QPushButton(
            "Browse...",
        )
        browse_button.clicked.connect(
            self._browse,
        )
        layout.addWidget(
            browse_button,
        )

    def _browse(
        self,
    ) -> None:
        """Prompt for a file via a native open-file dialog and store the choice.

        :returns: None. If the user picks a file, `line_edit` is updated
            with the chosen path; if they cancel, `line_edit` is left
            unchanged.
        """

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
        )

        if path_str:
            self.line_edit.setText(
                path_str,
            )

    def text(
        self,
    ) -> str:
        """Return the current path text.

        :returns: The current contents of `line_edit`.
        """

        return self.line_edit.text()

    def setText(
        self,
        text: str,
    ) -> None:
        """Replace the current path text.

        :param text: The path to display in `line_edit`.
        :returns: None. `line_edit` is updated in place.
        """

        self.line_edit.setText(
            text,
        )


def _confirm(
    parent: QWidget,
    title: str,
    message: str,
) -> bool:
    """Ask a yes/no confirmation question before a destructive action.

    :param parent: The widget the confirmation message box is shown over.
    :param title: The message box's title.
    :param message: The question text shown to the user.
    :returns: True if the user chose Yes, False if they chose No.
    """

    return (
        QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


class CompilerProfilesDialog(QDialog):
    """Adds, edits, removes, and selects configured compiler profiles.

    :ivar _settings_service: The service used to read the current compiler
        settings and persist changes when the dialog is accepted.
    :ivar _provider_registry: The registry of known compiler providers,
        used to resolve each profile's provider and its configuration
        fields.
    :ivar _profiles: The working, in-memory copy of the configured
        profiles, edited as the user interacts with the dialog and only
        written back through `_settings_service` on accept.
    :ivar _default_profile_id: The profile id currently marked as
        default, or None if there is no default.
    :ivar _field_widgets: The editor widgets currently shown in
        `_fields_form`, keyed by configuration field key, for the
        profile currently loaded into the form.
    :ivar _active_row: The index into `_profiles` whose values the form
        currently reflects, or None if the form doesn't reflect any row
        (nothing to commit). Tracked so that switching the list
        selection commits the previously-edited row's live form values
        before loading the newly selected row.
    :ivar _profile_list: The list widget showing one entry per profile.
    :ivar _display_name_edit: The line edit for the selected profile's
        display name.
    :ivar _provider_label: The read-only label showing the selected
        profile's provider display name.
    :ivar _fields_form: The form layout holding the selected profile's
        provider-specific configuration field widgets.
    """

    def __init__(
        self,
        *,
        settings_service: SettingsService,
        provider_registry: CompilerProviderRegistry,
        parent: QWidget | None = None,
    ) -> None:
        """Build the dialog, preloaded from the current compiler settings.

        :param settings_service: The service to read compiler settings
            from and persist them back to on accept.
        :param provider_registry: The registry used to resolve each
            profile's provider and its configuration fields.
        :param parent: The optional parent widget, forwarded to
            :class:`QDialog`.
        :returns: None.
        :raises TypeError: If `settings_service` is not a
            :class:`SettingsService`, or `provider_registry` is not a
            :class:`CompilerProviderRegistry`.
        """

        super().__init__(
            parent,
        )

        if not isinstance(
            settings_service,
            SettingsService,
        ):
            raise TypeError(
                "Compiler profiles dialog service must be "
                "SettingsService."
            )

        if not isinstance(
            provider_registry,
            CompilerProviderRegistry,
        ):
            raise TypeError(
                "Compiler profiles dialog registry must be "
                "CompilerProviderRegistry."
            )

        self._settings_service = settings_service
        self._provider_registry = provider_registry

        compilers = (
            settings_service.current.compilers
        )
        self._profiles: list[CompilerProfile] = list(
            compilers.profiles,
        )
        self._default_profile_id = (
            compilers.default_profile_id
        )
        self._field_widgets: dict[
            str,
            QWidget,
        ] = {}
        self._active_row: int | None = None

        self.setWindowTitle(
            "Compiler Profiles",
        )
        self.resize(
            520,
            480,
        )

        layout = QVBoxLayout(
            self,
        )

        top_row = QHBoxLayout()

        self._profile_list = QListWidget()
        self._profile_list.currentRowChanged.connect(
            self._on_selection_changed,
        )
        top_row.addWidget(
            self._profile_list,
            1,
        )

        button_column = QVBoxLayout()

        add_button = QPushButton(
            "Add...",
        )
        add_button.clicked.connect(
            self._add_profile,
        )
        button_column.addWidget(
            add_button,
        )

        remove_button = QPushButton(
            "Remove",
        )
        remove_button.clicked.connect(
            self._remove_profile,
        )
        button_column.addWidget(
            remove_button,
        )

        default_button = QPushButton(
            "Set as Default",
        )
        default_button.clicked.connect(
            self._set_selected_as_default,
        )
        button_column.addWidget(
            default_button,
        )

        button_column.addStretch()
        top_row.addLayout(
            button_column,
        )

        layout.addLayout(
            top_row,
        )

        details_group = QGroupBox(
            "Profile Details",
        )
        details_layout = QVBoxLayout(
            details_group,
        )

        name_form = QFormLayout()

        self._display_name_edit = QLineEdit()
        name_form.addRow(
            "Name:",
            self._display_name_edit,
        )

        self._provider_label = QLabel()
        name_form.addRow(
            "Provider:",
            self._provider_label,
        )

        details_layout.addLayout(
            name_form,
        )

        self._fields_form = QFormLayout()
        details_layout.addLayout(
            self._fields_form,
        )

        layout.addWidget(
            details_group,
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

        self._refresh_profile_list()

        if self._profiles:
            self._profile_list.setCurrentRow(
                0,
            )
        else:
            self._load_profile_into_form(
                None,
            )

    def _select_row_without_committing(
        self,
        row: int,
    ) -> None:
        """Select a row and reload the form for it deterministically.

        Used after the caller has already committed or discarded whatever
        the form previously held, so this must not trigger another commit
        via `currentRowChanged` — signals are blocked and the resulting
        state is applied directly instead.

        :param row: The row index to select, or a negative value to
            select nothing.
        :returns: None. The list selection and `_active_row` are updated,
            and the form is reloaded for the new row.
        """

        self._profile_list.blockSignals(
            True,
        )
        self._profile_list.setCurrentRow(
            row,
        )
        self._profile_list.blockSignals(
            False,
        )

        self._active_row = (
            row if row >= 0 else None
        )
        self._load_profile_into_form(
            self._active_row,
        )

    def _refresh_profile_list(
        self,
    ) -> None:
        """Rebuild the list widget's items from `_profiles`.

        Marks the default profile's entry with a " (default)" suffix.
        Signals are blocked around the rebuild so repopulating the list
        does not itself trigger `_on_selection_changed`.

        :returns: None. `_profile_list` is repopulated in place.
        """

        self._profile_list.blockSignals(
            True,
        )
        self._profile_list.clear()

        for profile in self._profiles:
            label = profile.display_name

            if profile.profile_id == self._default_profile_id:
                label += " (default)"

            self._profile_list.addItem(
                label,
            )

        self._profile_list.blockSignals(
            False,
        )

    def _on_selection_changed(
        self,
        row: int,
    ) -> None:
        """Commit the outgoing row's edits, then load the newly selected row.

        If committing the previous row's form values fails, the visible
        selection is moved back to the row whose form data just failed
        to commit, without touching the form itself -- the form still
        holds the user's unsaved, invalid text so they can see and fix
        it.

        :param row: The newly selected row index, or a negative value
            if nothing is selected.
        :returns: None. On successful commit, `_active_row` and the form
            are updated for `row`; on failed commit, the list selection
            is reverted to `_active_row` and the form is left untouched.
        """

        if not self._commit_current_profile_from_form():
            self._profile_list.blockSignals(
                True,
            )
            self._profile_list.setCurrentRow(
                self._active_row
                if self._active_row is not None
                else -1,
            )
            self._profile_list.blockSignals(
                False,
            )
            return

        self._active_row = (
            row if row >= 0 else None
        )
        self._load_profile_into_form(
            self._active_row,
        )

    def _clear_fields_form(
        self,
    ) -> None:
        """Remove every row from the provider configuration fields form.

        :returns: None. `_fields_form` is emptied and `_field_widgets`
            is reset to an empty mapping.
        """

        while self._fields_form.rowCount():
            self._fields_form.removeRow(
                0,
            )

        self._field_widgets = {}

    def _load_profile_into_form(
        self,
        row: int | None,
    ) -> None:
        """Populate the details form from one profile, or blank it out.

        :param row: The index into `_profiles` to load, or None (or an
            out-of-range index) to clear and disable the form instead.
        :returns: None. The name field, provider label, and
            provider-specific configuration fields are rebuilt in place.
        """

        self._clear_fields_form()

        if row is None or not (
            0 <= row < len(self._profiles)
        ):
            self._display_name_edit.clear()
            self._display_name_edit.setEnabled(
                False,
            )
            self._provider_label.setText(
                "",
            )
            return

        profile = self._profiles[row]
        provider = self._provider_registry.get(
            profile.provider_id,
        )

        self._display_name_edit.setEnabled(
            True,
        )
        self._display_name_edit.setText(
            profile.display_name,
        )
        self._provider_label.setText(
            provider.display_name,
        )

        for field in provider.configuration_fields:
            widget = _build_field_widget(
                field,
            )
            _write_field_value(
                field,
                widget,
                profile.configuration.get(
                    field.key,
                ),
            )

            label = field.title

            if field.required:
                label += " *"

            self._fields_form.addRow(
                label,
                widget,
            )
            self._field_widgets[
                field.key
            ] = widget

    def _commit_current_profile_from_form(
        self,
    ) -> bool:
        """Write the form's current field values back into `_profiles`.

        Editor §Dialogs-1: a malformed field (or any other parse
        error) used to raise straight out of this method, uncaught by
        any of its four callers -- inside `_on_selection_changed` that
        left the widget's visible selection and `_active_row` out of
        sync with each other for every edit afterward, and inside
        `_apply_and_accept` it meant clicking OK silently did nothing.
        Errors are now caught here, shown once via a critical dialog,
        and reported to the caller via the return value instead, so
        every caller can abort its own action cleanly without
        touching `_active_row` or the form.

        :returns: True if there was nothing to commit, or the commit
            succeeded; False if the current field values were invalid,
            in which case a critical dialog has already been shown and
            `_profiles` was left unmodified.
        """

        row = self._active_row

        if row is None or not (
            0 <= row < len(self._profiles)
        ):
            return True

        profile = self._profiles[row]
        provider = self._provider_registry.get(
            profile.provider_id,
        )

        configuration = {}

        try:
            for field in provider.configuration_fields:
                widget = self._field_widgets.get(
                    field.key,
                )

                if widget is None:
                    continue

                value = _read_field_value(
                    field,
                    widget,
                )

                if value is not None:
                    configuration[
                        field.key
                    ] = value

            display_name = (
                self._display_name_edit.text().strip()
                or profile.display_name
            )

            self._profiles[row] = replace(
                profile,
                display_name=display_name,
                configuration=configuration,
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                self,
                "Compiler Profiles",
                f"{profile.display_name}: {error}",
            )
            return False

        return True

    def _add_profile(
        self,
    ) -> None:
        """Prompt for a provider and append a new default-configured profile.

        Becomes the default profile if there was none before, and is
        selected in the list once added.

        :returns: None. On success, `_profiles` gains one entry, the
            list is refreshed, and the new row is selected; if committing
            the outgoing row fails or the user cancels the provider
            picker, nothing changes.
        """

        if not self._commit_current_profile_from_form():
            return

        providers = self._provider_registry.providers
        names = [
            provider.display_name
            for provider in providers
        ]

        choice, accepted = QInputDialog.getItem(
            self,
            "Add Compiler Profile",
            "Provider:",
            names,
            0,
            False,
        )

        if not accepted or not choice:
            return

        provider = next(
            provider
            for provider in providers
            if provider.display_name == choice
        )
        new_profile = CompilerProfile(
            provider_id=provider.provider_id,
            display_name=provider.display_name,
        )
        self._profiles.append(
            new_profile,
        )

        if self._default_profile_id is None:
            self._default_profile_id = (
                new_profile.profile_id
            )

        new_row = len(self._profiles) - 1
        self._refresh_profile_list()
        self._select_row_without_committing(
            new_row,
        )

    def _remove_profile(
        self,
    ) -> None:
        """Remove the selected profile after user confirmation.

        If the removed profile was the default, the first remaining
        profile (if any) becomes the new default.

        :returns: None. On confirmed removal, `_profiles` loses the
            selected entry, the list is refreshed, and a nearby row is
            selected; if nothing is selected or the user declines to
            confirm, nothing changes.
        """

        row = self._profile_list.currentRow()

        if not (
            0 <= row < len(self._profiles)
        ):
            return

        profile = self._profiles[row]

        if not _confirm(
            self,
            "Remove Compiler Profile",
            f"Remove profile {profile.display_name!r}?",
        ):
            return

        del self._profiles[row]

        if self._default_profile_id == profile.profile_id:
            self._default_profile_id = (
                self._profiles[0].profile_id
                if self._profiles
                else None
            )

        self._active_row = None
        self._refresh_profile_list()
        new_row = min(
            row,
            len(self._profiles) - 1,
        )
        self._select_row_without_committing(
            new_row,
        )

    def _set_selected_as_default(
        self,
    ) -> None:
        """Mark the selected profile as the default.

        :returns: None. On success, `_default_profile_id` is updated
            and the list is refreshed to show the new default marker;
            if nothing is selected or committing the outgoing row's
            form values fails, nothing changes.
        """

        row = self._profile_list.currentRow()

        if not (
            0 <= row < len(self._profiles)
        ):
            return

        if not self._commit_current_profile_from_form():
            return

        self._default_profile_id = (
            self._profiles[row].profile_id
        )
        self._refresh_profile_list()
        self._select_row_without_committing(
            row,
        )

    def _apply_and_accept(
        self,
    ) -> None:
        """Validate every profile, persist them, and close the dialog.

        Commits the currently-edited row, then validates every profile
        against its provider before attempting to persist. If either
        the commit, a per-profile validation, or the settings write
        fails, a critical dialog is shown and the dialog stays open so
        the user can fix the problem.

        :returns: None. On success, the settings are persisted and the
            dialog is accepted (closed); otherwise the dialog remains
            open with its current state.
        """

        if not self._commit_current_profile_from_form():
            return

        for profile in self._profiles:
            try:
                self._provider_registry.validate_profile(
                    profile,
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                QMessageBox.critical(
                    self,
                    "Compiler Profiles",
                    f"{profile.display_name}: {error}",
                )
                return

        try:
            self._settings_service.update_compilers(
                CompilerSettings(
                    default_profile_id=(
                        self._default_profile_id
                    ),
                    profiles=tuple(
                        self._profiles,
                    ),
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                self,
                "Compiler Profiles",
                str(error),
            )
            return

        self.accept()


def _build_field_widget(
    field: CompilerConfigurationField,
) -> QWidget:
    """Create the editor widget for one provider configuration field.

    :param field: The configuration field to build a widget for; its
        :attr:`~CompilerConfigurationField.kind` selects the widget type.
    :returns: A new, empty widget appropriate for `field.kind`: a
        :class:`QLineEdit` for STRING or INTEGER_LIST, a
        :class:`_PathFieldEditor` for PATH, a :class:`QCheckBox` for
        BOOLEAN, a :class:`QPlainTextEdit` for STRING_LIST or
        STRING_MAP, or a :class:`QComboBox` populated from
        `field.choices` for CHOICE.
    :raises AssertionError: If `field.kind` is not one of the known
        :class:`CompilerConfigurationFieldKind` values.
    """

    kind = field.kind

    if kind is CompilerConfigurationFieldKind.STRING:
        return QLineEdit()

    if kind is CompilerConfigurationFieldKind.PATH:
        return _PathFieldEditor()

    if kind is CompilerConfigurationFieldKind.BOOLEAN:
        return QCheckBox()

    if kind in (
        CompilerConfigurationFieldKind.STRING_LIST,
        CompilerConfigurationFieldKind.STRING_MAP,
    ):
        editor = QPlainTextEdit()
        editor.setPlaceholderText(
            "One entry per line."
            if kind
            is CompilerConfigurationFieldKind.STRING_LIST
            else "One key=value entry per line."
        )
        return editor

    if kind is CompilerConfigurationFieldKind.INTEGER_LIST:
        return QLineEdit()

    if kind is CompilerConfigurationFieldKind.CHOICE:
        combo = QComboBox()

        for choice in field.choices:
            combo.addItem(
                choice,
            )

        return combo

    raise AssertionError(
        f"Unhandled compiler configuration field kind: {kind}."
    )


def _write_field_value(
    field: CompilerConfigurationField,
    widget: QWidget,
    value: object,
) -> None:
    """Populate a field editor widget from a stored (or default) value.

    :param field: The configuration field being displayed; used to
        resolve `field.default` and to select which widget API to call
        for `field.kind`.
    :param widget: The widget previously built by
        :func:`_build_field_widget` for this field.
    :param value: The stored configuration value for this field, or
        None to fall back to `field.default`.
    :returns: None. `widget` is updated in place to reflect the
        resolved value.
    :raises AssertionError: If `field.kind` is not one of the known
        :class:`CompilerConfigurationFieldKind` values.
    """

    resolved_value = (
        field.default if value is None else value
    )
    kind = field.kind

    if kind in (
        CompilerConfigurationFieldKind.STRING,
        CompilerConfigurationFieldKind.PATH,
    ):
        widget.setText(
            str(resolved_value)
            if resolved_value is not None
            else "",
        )
        return

    if kind is CompilerConfigurationFieldKind.BOOLEAN:
        widget.setChecked(
            bool(resolved_value),
        )
        return

    if kind is CompilerConfigurationFieldKind.STRING_LIST:
        items = (
            resolved_value
            if resolved_value is not None
            else ()
        )
        widget.setPlainText(
            "\n".join(
                str(item) for item in items
            ),
        )
        return

    if kind is CompilerConfigurationFieldKind.STRING_MAP:
        mapping = (
            resolved_value
            if resolved_value is not None
            else {}
        )
        widget.setPlainText(
            "\n".join(
                f"{key}={item_value}"
                for key, item_value in mapping.items()
            ),
        )
        return

    if kind is CompilerConfigurationFieldKind.INTEGER_LIST:
        items = (
            resolved_value
            if resolved_value is not None
            else ()
        )
        widget.setText(
            " ".join(
                str(item) for item in items
            ),
        )
        return

    if kind is CompilerConfigurationFieldKind.CHOICE:
        text = (
            resolved_value
            if resolved_value is not None
            else (
                field.choices[0]
                if field.choices
                else ""
            )
        )
        index = widget.findText(
            text,
        )
        widget.setCurrentIndex(
            index if index >= 0 else 0,
        )
        return

    raise AssertionError(
        f"Unhandled compiler configuration field kind: {kind}."
    )


def _read_field_value(
    field: CompilerConfigurationField,
    widget: QWidget,
) -> object:
    """Extract the current value from a field editor widget.

    Returns `None` when the field is left blank, so the profile omits the
    key entirely and the provider's declared default applies instead.

    For STRING_MAP, each non-blank line is parsed as a ``key=value``
    pair and rejected up front rather than left for a later layer to
    catch: an empty key used to sail through here cleanly and only blow
    up two calls later inside :func:`dataclasses.replace`'s own
    re-validation, with a message that doesn't point back at this field
    or line at all, while a duplicate key used to silently overwrite the
    earlier value with no rejection and no warning, discarding it before
    any downstream layer could ever detect it happened. Both cases are
    now raised here instead.

    :param field: The configuration field being read; used to select
        which widget API to call for `field.kind`, and to name the
        field in raised error messages.
    :param widget: The widget previously built by
        :func:`_build_field_widget` for this field.
    :returns: The value entered in `widget`, converted to the type
        appropriate for `field.kind` (str, bool, a tuple of str, a dict
        of str to str, or a tuple of int), or None if the field is
        blank.
    :raises ValueError: If a STRING_MAP line has an empty key, or a key
        that duplicates an earlier line in the same widget; or if an
        INTEGER_LIST entry cannot be parsed as an integer.
    :raises AssertionError: If `field.kind` is not one of the known
        :class:`CompilerConfigurationFieldKind` values.
    """

    kind = field.kind

    if kind in (
        CompilerConfigurationFieldKind.STRING,
        CompilerConfigurationFieldKind.PATH,
    ):
        text = widget.text().strip()
        return text or None

    if kind is CompilerConfigurationFieldKind.BOOLEAN:
        return widget.isChecked()

    if kind is CompilerConfigurationFieldKind.STRING_LIST:
        items = tuple(
            line.strip()
            for line in widget.toPlainText().splitlines()
            if line.strip()
        )
        return items or None

    if kind is CompilerConfigurationFieldKind.STRING_MAP:
        mapping: dict[str, str] = {}

        for line in widget.toPlainText().splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            key, _, item_value = stripped.partition(
                "=",
            )
            normalized_key = key.strip()

            if not normalized_key:
                raise ValueError(
                    f"{field.title} has an entry with no key: "
                    f"{stripped!r}."
                )

            if normalized_key in mapping:
                raise ValueError(
                    f"{field.title} has a duplicate key: "
                    f"{normalized_key!r}."
                )

            mapping[normalized_key] = (
                item_value.strip()
            )

        return mapping or None

    if kind is CompilerConfigurationFieldKind.INTEGER_LIST:
        text = widget.text().strip()

        if not text:
            return None

        tokens = text.replace(
            ",",
            " ",
        ).split()

        return tuple(
            int(token) for token in tokens
        )

    if kind is CompilerConfigurationFieldKind.CHOICE:
        return widget.currentText()

    raise AssertionError(
        f"Unhandled compiler configuration field kind: {kind}."
    )


def create_show_compiler_profiles_handler(
    *,
    settings_service: SettingsService,
    provider_registry: CompilerProviderRegistry,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that opens the Compiler Profiles dialog.

    :param settings_service: The service passed through to the dialog
        for reading and persisting compiler settings.
    :param provider_registry: The provider registry passed through to
        the dialog for resolving profiles' providers and fields.
    :param parent_widget_provider: A callable returning the widget to
        parent the dialog to, or None for no parent. Defaults to a
        callable that always returns None.
    :returns: A :class:`CommandHandler` that shows the dialog when
        invoked.
    """

    def handle_show_compiler_profiles(
        context: CommandContext,
    ) -> None:
        """Build and modally show the Compiler Profiles dialog.

        :param context: The command context this handler was invoked
            with; unused, but required by the :class:`CommandHandler`
            signature.
        :returns: None. Blocks until the dialog is closed.
        """

        dialog = CompilerProfilesDialog(
            settings_service=settings_service,
            provider_registry=provider_registry,
            parent=parent_widget_provider(),
        )
        dialog.exec()

    return handle_show_compiler_profiles
