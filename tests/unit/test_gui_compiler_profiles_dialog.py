"""Unit tests for the Compiler Profiles dialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from opencobol2.compiler.providers import (
    CompilerConfigurationField,
    CompilerConfigurationFieldKind,
    CompilerExecutionKind,
    CompilerProviderRegistry,
    CustomLocalCompilerProvider,
    GnuCobolCompilerProvider,
)
from opencobol2.compiler.providers.builtins import (
    _DeclarativeCompilerProvider,
)
from opencobol2.gui.compiler_profiles_dialog import (
    CompilerProfilesDialog,
    create_show_compiler_profiles_handler,
    _build_field_widget,
    _read_field_value,
    _write_field_value,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


def _build_registry() -> CompilerProviderRegistry:
    registry = CompilerProviderRegistry()
    registry.register(GnuCobolCompilerProvider())
    registry.register(CustomLocalCompilerProvider())
    return registry


_STRING_MAP_PROVIDER_ID = "test.string-map-provider"


def _build_string_map_registry() -> CompilerProviderRegistry:
    """Build a registry with a synthetic STRING_MAP-field provider.

    None of the real built-in providers happen to have a STRING_MAP
    field, so Dialogs-1/2's repros (which are specifically about that
    field kind) need one built for the purpose, same as the original
    audit did.
    """

    registry = CompilerProviderRegistry()
    registry.register(
        _DeclarativeCompilerProvider(
            provider_id=_STRING_MAP_PROVIDER_ID,
            display_name="String Map Test Provider",
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            configuration_fields=(
                CompilerConfigurationField(
                    key="mapping",
                    title="Mapping",
                    kind=(
                        CompilerConfigurationFieldKind
                        .STRING_MAP
                    ),
                ),
            ),
        )
    )
    return registry


def _build_service(
    tmp_path: Path,
) -> SettingsService:
    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def test_dialog_preloads_default_gnucobol_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    assert [
        profile.display_name
        for profile in dialog._profiles
    ] == ["GnuCOBOL"]
    assert (
        dialog._profile_list.item(0).text()
        == "GnuCOBOL (default)"
    )
    assert (
        dialog._provider_label.text()
        == "GnuCOBOL"
    )
    assert set(
        dialog._field_widgets,
    ) == {
        "compiler_path",
        "config_directory",
        "copy_directory",
        "library_path",
    }


def test_dialog_rejects_non_settings_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Compiler profiles dialog service must be "
            "SettingsService"
        ),
    ):
        CompilerProfilesDialog(
            settings_service=object(),  # type: ignore[arg-type]
            provider_registry=_build_registry(),
        )


def test_dialog_rejects_non_provider_registry(
    qapp,
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Compiler profiles dialog registry must be "
            "CompilerProviderRegistry"
        ),
    ):
        CompilerProfilesDialog(
            settings_service=_build_service(
                tmp_path,
            ),
            provider_registry=object(),  # type: ignore[arg-type]
        )


def test_add_profile_appends_and_selects_new_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    assert [
        profile.display_name
        for profile in dialog._profiles
    ] == [
        "GnuCOBOL",
        "Custom local COBOL compiler",
    ]
    assert dialog._profile_list.currentRow() == 1
    assert set(
        dialog._field_widgets,
    ) >= {
        "executable_path",
        "compile_arguments",
        "diagnostic_format",
    }


def test_first_added_profile_becomes_default_when_none_configured(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    service.update_compilers(
        CompilerSettings(
            default_profile_id=None,
            profiles=(),
        )
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "GnuCOBOL",
            True,
        ),
    ):
        dialog._add_profile()

    assert dialog._default_profile_id == (
        dialog._profiles[0].profile_id
    )


def test_editing_fields_and_switching_selection_commits_changes(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    dialog._display_name_edit.setText(
        "My Compiler",
    )
    dialog._field_widgets[
        "executable_path"
    ].setText(
        str(
            tmp_path / "compiler.exe",
        )
    )
    dialog._field_widgets[
        "compile_arguments"
    ].setPlainText(
        "{source}\n-o\n{output}\n--extra",
    )

    # Switching back to row 0 must commit row 1's edits first.
    dialog._profile_list.setCurrentRow(
        0,
    )

    edited_profile = dialog._profiles[1]
    assert (
        edited_profile.display_name
        == "My Compiler"
    )
    assert (
        edited_profile.configuration[
            "executable_path"
        ]
        == str(
            tmp_path / "compiler.exe",
        )
    )
    assert edited_profile.configuration[
        "compile_arguments"
    ] == (
        "{source}",
        "-o",
        "{output}",
        "--extra",
    )


def test_malformed_string_map_on_row_switch_shows_error_and_keeps_selection(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §Dialogs-1: a malformed field value used to raise
    # straight out of `_commit_current_profile_from_form`, uncaught,
    # inside `_on_selection_changed` -- leaving the widget's visible
    # selection and `_active_row` out of sync with each other, so any
    # further edit silently landed in the wrong profile.
    service = _build_service(
        tmp_path,
    )
    # Start from zero profiles -- the default seeded GnuCOBOL profile
    # isn't resolvable against this test's synthetic-only registry.
    service.update_compilers(
        CompilerSettings(
            default_profile_id=None,
            profiles=(),
        )
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=(
            _build_string_map_registry()
        ),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "String Map Test Provider",
            True,
        ),
    ):
        dialog._add_profile()
        dialog._add_profile()

    assert dialog._active_row == 1
    dialog._field_widgets[
        "mapping"
    ].setPlainText(
        "=bad-no-key",
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.critical",
    ) as mock_critical:
        dialog._profile_list.setCurrentRow(
            0,
        )

    mock_critical.assert_called_once()
    assert dialog._profile_list.currentRow() == 1
    assert dialog._active_row == 1
    assert (
        dialog._field_widgets[
            "mapping"
        ].toPlainText()
        == "=bad-no-key"
    )


def test_remove_profile_prompts_and_respects_decline(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.No
        ),
    ):
        dialog._remove_profile()

    assert len(
        dialog._profiles,
    ) == 1


def test_remove_default_profile_reassigns_default(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )
    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    assert dialog._profile_list.currentRow() == 1

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    ):
        dialog._profile_list.setCurrentRow(
            0,
        )
        dialog._remove_profile()

    assert len(
        dialog._profiles,
    ) == 1
    assert (
        dialog._default_profile_id
        == dialog._profiles[0].profile_id
    )


def test_remove_last_profile_clears_default_and_form(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Yes
        ),
    ):
        dialog._remove_profile()

    assert dialog._profiles == []
    assert dialog._default_profile_id is None
    assert not dialog._display_name_edit.isEnabled()
    assert dialog._field_widgets == {}


def test_set_selected_as_default_updates_list_labels(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )
    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    dialog._profile_list.setCurrentRow(
        1,
    )
    dialog._set_selected_as_default()

    assert (
        dialog._default_profile_id
        == dialog._profiles[1].profile_id
    )
    assert (
        dialog._profile_list.item(0).text()
        == "GnuCOBOL"
    )
    assert (
        dialog._profile_list.item(1).text()
        == "Custom local COBOL compiler (default)"
    )


def test_apply_and_accept_blocks_on_missing_required_field(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )
    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()
    # executable_path (required) left blank.

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.critical",
    ) as mock_critical:
        dialog._apply_and_accept()

    mock_critical.assert_called_once()
    assert dialog.result() == 0

    reloaded = SettingsService(
        service.storage,
    )
    assert len(
        reloaded.current.compilers.profiles,
    ) == 1


def test_malformed_integer_list_blocks_apply_and_accept_with_an_error(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §Dialogs-1: this was the unguarded first line of
    # `_apply_and_accept`, entirely outside its own
    # `try`/`except (TypeError, ValueError)` around persistence -- the
    # dialog never called `accept()` and clicking OK silently did
    # nothing, with no error and no explanation.
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    dialog._field_widgets[
        "executable_path"
    ].setText(
        str(
            tmp_path / "compiler.exe",
        )
    )
    dialog._field_widgets[
        "success_return_codes"
    ].setText(
        "not-a-number",
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QMessageBox.critical",
    ) as mock_critical:
        dialog._apply_and_accept()

    mock_critical.assert_called_once()
    assert dialog.result() == 0


def test_apply_and_accept_persists_profiles(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )
    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    dialog._display_name_edit.setText(
        "My Compiler",
    )
    dialog._field_widgets[
        "executable_path"
    ].setText(
        str(
            tmp_path / "compiler.exe",
        )
    )
    dialog._set_selected_as_default()

    dialog._apply_and_accept()

    assert (
        dialog.result()
        == dialog.DialogCode.Accepted
    )

    reloaded = SettingsService(
        service.storage,
    )
    compilers = reloaded.current.compilers
    assert [
        profile.display_name
        for profile in compilers.profiles
    ] == [
        "GnuCOBOL",
        "My Compiler",
    ]
    assert (
        compilers.default_profile.display_name
        == "My Compiler"
    )
    assert (
        compilers.default_profile.configuration[
            "executable_path"
        ]
        == str(
            tmp_path / "compiler.exe",
        )
    )


def test_cancel_does_not_persist_changes(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = CompilerProfilesDialog(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "QInputDialog.getItem",
        return_value=(
            "Custom local COBOL compiler",
            True,
        ),
    ):
        dialog._add_profile()

    dialog.reject()

    reloaded = SettingsService(
        service.storage,
    )
    assert [
        profile.display_name
        for profile in reloaded.current.compilers.profiles
    ] == ["GnuCOBOL"]


def test_show_compiler_profiles_handler_opens_dialog(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    handler = create_show_compiler_profiles_handler(
        settings_service=service,
        provider_registry=_build_registry(),
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "CompilerProfilesDialog.exec",
        return_value=0,
    ) as mock_exec:
        handler(
            None,
        )

    mock_exec.assert_called_once()


def test_field_widget_round_trip_for_every_kind(
    qapp,
) -> None:
    cases = (
        (
            CompilerConfigurationField(
                key="flag",
                title="Flag",
                kind=(
                    CompilerConfigurationFieldKind.BOOLEAN
                ),
            ),
            True,
            True,
        ),
        (
            CompilerConfigurationField(
                key="mapping",
                title="Mapping",
                kind=(
                    CompilerConfigurationFieldKind.STRING_MAP
                ),
            ),
            {
                "FOO": "bar",
                "BAZ": "qux",
            },
            {
                "FOO": "bar",
                "BAZ": "qux",
            },
        ),
        (
            CompilerConfigurationField(
                key="numbers",
                title="Numbers",
                kind=(
                    CompilerConfigurationFieldKind
                    .INTEGER_LIST
                ),
            ),
            (
                0,
                1,
                2,
            ),
            (
                0,
                1,
                2,
            ),
        ),
        (
            CompilerConfigurationField(
                key="dialect",
                title="Dialect",
                kind=(
                    CompilerConfigurationFieldKind.CHOICE
                ),
                choices=(
                    "gcc",
                    "msvc",
                ),
            ),
            "msvc",
            "msvc",
        ),
    )

    for field, stored_value, expected in cases:
        widget = _build_field_widget(
            field,
        )
        _write_field_value(
            field,
            widget,
            stored_value,
        )
        assert (
            _read_field_value(
                field,
                widget,
            )
            == expected
        )


def test_boolean_field_defaults_to_unchecked_when_blank(
    qapp,
) -> None:
    field = CompilerConfigurationField(
        key="flag",
        title="Flag",
        kind=CompilerConfigurationFieldKind.BOOLEAN,
    )
    widget = _build_field_widget(
        field,
    )
    _write_field_value(
        field,
        widget,
        None,
    )

    assert (
        _read_field_value(
            field,
            widget,
        )
        is False
    )


def test_string_map_field_returns_none_when_blank(
    qapp,
) -> None:
    field = CompilerConfigurationField(
        key="mapping",
        title="Mapping",
        kind=CompilerConfigurationFieldKind.STRING_MAP,
    )
    widget = _build_field_widget(
        field,
    )
    _write_field_value(
        field,
        widget,
        None,
    )

    assert (
        _read_field_value(
            field,
            widget,
        )
        is None
    )


def test_string_map_field_rejects_a_duplicate_key(
    qapp,
) -> None:
    # Editor §Dialogs-2: a second `KEY=...` line used to simply
    # overwrite the first with no rejection and no warning -- the
    # duplicate's earlier value was already gone before any
    # downstream validation layer could ever detect it happened.
    field = CompilerConfigurationField(
        key="mapping",
        title="Mapping",
        kind=CompilerConfigurationFieldKind.STRING_MAP,
    )
    widget = _build_field_widget(
        field,
    )
    widget.setPlainText(
        "DEBUG=1\nDEBUG=0\nRELEASE=1",
    )

    with pytest.raises(
        ValueError,
        match="duplicate key",
    ):
        _read_field_value(
            field,
            widget,
        )


def test_string_map_field_rejects_an_entry_with_no_key(
    qapp,
) -> None:
    # Editor §Dialogs-1: an empty key used to sail through here
    # cleanly and only blow up two calls later inside
    # `dataclasses.replace`'s own re-validation, with a message that
    # doesn't point back at this field or line at all.
    field = CompilerConfigurationField(
        key="mapping",
        title="Mapping",
        kind=CompilerConfigurationFieldKind.STRING_MAP,
    )
    widget = _build_field_widget(
        field,
    )
    widget.setPlainText(
        "=bad-no-key",
    )

    with pytest.raises(
        ValueError,
        match="no key",
    ):
        _read_field_value(
            field,
            widget,
        )
