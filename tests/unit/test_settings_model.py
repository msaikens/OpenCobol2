"""Unit tests for typed OpenCobol2 settings models."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.providers import (
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.settings.models import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    CompilerSettings,
    DEFAULT_GNUCOBOL_PROFILE_ID,
    EditorSettings,
    ExternalToolSettings,
    ThemeSettings,
)
from opencobol2.theming import DEFAULT_THEME_ID


def test_application_settings_have_typed_defaults() -> None:
    settings = ApplicationSettings()

    assert settings.schema_version == 1
    assert isinstance(
        settings.compilers,
        CompilerSettings,
    )
    assert isinstance(
        settings.external_tools,
        ExternalToolSettings,
    )
    assert (
        settings.external_tools.git_executable_path
        is None
    )
    assert settings.editor.font_size == 11
    assert settings.editor.tab_width == 4
    assert settings.editor.insert_spaces is True
    assert (
        settings.editor.automatic_indentation
        is True
    )
    assert settings.editor.code_folding is True
    assert (
        settings.cobol.default_source_format
        is CobolSourceFormat.FIXED
    )
    assert (
        settings.cobol.guides.show_sequence_area
        is True
    )
    assert isinstance(
        settings.theme,
        ThemeSettings,
    )
    assert (
        settings.theme.active_theme_id
        == DEFAULT_THEME_ID
    )


def test_compiler_settings_have_default_gnucobol_profile() -> None:
    settings = CompilerSettings()

    assert len(settings.profiles) == 1
    assert (
        settings.default_profile_id
        == DEFAULT_GNUCOBOL_PROFILE_ID
    )

    profile = settings.profiles[0]

    assert (
        profile.profile_id
        == DEFAULT_GNUCOBOL_PROFILE_ID
    )
    assert (
        profile.provider_id
        == GNUCOBOL_PROVIDER_ID
    )
    assert profile.display_name == "GnuCOBOL"
    assert dict(profile.configuration) == {}
    assert dict(profile.environment_overrides) == {}


def test_compiler_profiles_are_normalized_to_tuple() -> None:
    profile = CompilerProfile(
        provider_id="example.compiler",
        display_name="Example Compiler",
    )

    settings = CompilerSettings(
        default_profile_id=profile.profile_id,
        profiles=[profile],  # type: ignore[arg-type]
    )

    assert isinstance(
        settings.profiles,
        tuple,
    )
    assert settings.profiles == (
        profile,
    )


def test_compiler_profile_ids_must_be_unique() -> None:
    profile_id = uuid4()

    first_profile = CompilerProfile(
        profile_id=profile_id,
        provider_id="example.first",
        display_name="First Compiler",
    )
    second_profile = CompilerProfile(
        profile_id=profile_id,
        provider_id="example.second",
        display_name="Second Compiler",
    )

    with pytest.raises(
        ValueError,
        match="Compiler profile IDs must be unique",
    ):
        CompilerSettings(
            default_profile_id=profile_id,
            profiles=(
                first_profile,
                second_profile,
            ),
        )


def test_compiler_profile_display_names_may_duplicate() -> None:
    first_profile = CompilerProfile(
        provider_id="example.first",
        display_name="COBOL",
    )
    second_profile = CompilerProfile(
        provider_id="example.second",
        display_name="COBOL",
    )

    settings = CompilerSettings(
        default_profile_id=first_profile.profile_id,
        profiles=(
            first_profile,
            second_profile,
        ),
    )

    assert len(settings.profiles) == 2


def test_default_profile_id_must_reference_existing_profile() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Default compiler profile ID must reference "
            "an existing compiler profile"
        ),
    ):
        CompilerSettings(
            default_profile_id=uuid4(),
            profiles=(),
        )


def test_compiler_settings_allow_no_default_profile() -> None:
    settings = CompilerSettings(
        default_profile_id=None,
        profiles=(),
    )

    assert settings.default_profile_id is None
    assert settings.default_profile is None


def test_compiler_settings_get_profile() -> None:
    first_profile = CompilerProfile(
        provider_id="example.first",
        display_name="First Compiler",
    )
    second_profile = CompilerProfile(
        provider_id="example.second",
        display_name="Second Compiler",
    )

    settings = CompilerSettings(
        default_profile_id=first_profile.profile_id,
        profiles=(
            first_profile,
            second_profile,
        ),
    )

    assert (
        settings.get_profile(
            second_profile.profile_id,
        )
        is second_profile
    )


def test_compiler_settings_get_unknown_profile_returns_none() -> None:
    settings = CompilerSettings()

    assert (
        settings.get_profile(
            uuid4(),
        )
        is None
    )


def test_compiler_settings_resolve_default_profile() -> None:
    settings = CompilerSettings()

    profile = settings.default_profile

    assert profile is not None
    assert (
        profile.profile_id
        == settings.default_profile_id
    )
    assert (
        profile.provider_id
        == GNUCOBOL_PROVIDER_ID
    )


def test_compiler_settings_do_not_require_registered_provider() -> None:
    profile = CompilerProfile(
        provider_id="plugin.example.compiler",
        display_name="Plugin Compiler",
    )

    settings = CompilerSettings(
        default_profile_id=profile.profile_id,
        profiles=(
            profile,
        ),
    )

    assert settings.default_profile is profile


def test_external_tool_settings_normalize_git_path() -> None:
    settings = ExternalToolSettings(
        git_executable_path="tools/git.exe",
    )

    assert (
        settings.git_executable_path
        == Path("tools/git.exe")
    )


@pytest.mark.parametrize(
    "font_size",
    [
        0,
        -1,
    ],
)
def test_editor_font_size_must_be_positive(
    font_size: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="font size must be positive",
    ):
        EditorSettings(
            font_size=font_size,
        )


def test_boolean_editor_setting_rejects_integer() -> None:
    with pytest.raises(
        TypeError,
        match="Code folding must be a boolean",
    ):
        EditorSettings(
            code_folding=1,  # type: ignore[arg-type]
        )


def test_cobol_source_format_is_normalized() -> None:
    settings = CobolSettings(
        default_source_format="free",
    )

    assert (
        settings.default_source_format
        is CobolSourceFormat.FREE
    )


def test_cobol_guide_settings_validate_booleans() -> None:
    with pytest.raises(
        TypeError,
        match="Area A visibility must be a boolean",
    ):
        CobolGuideSettings(
            show_area_a="yes",  # type: ignore[arg-type]
        )


def test_theme_settings_default_to_builtin_dark_theme() -> None:
    settings = ThemeSettings()

    assert settings.active_theme_id == DEFAULT_THEME_ID


def test_theme_settings_normalize_active_theme_id() -> None:
    settings = ThemeSettings(
        active_theme_id="  light  ",
    )

    assert settings.active_theme_id == "light"


def test_theme_settings_reject_empty_active_theme_id() -> None:
    with pytest.raises(
        ValueError,
        match="Active theme ID must not be empty",
    ):
        ThemeSettings(
            active_theme_id="   ",
        )


def test_theme_settings_reject_non_string_active_theme_id() -> None:
    with pytest.raises(
        TypeError,
        match="Active theme ID must be a string",
    ):
        ThemeSettings(
            active_theme_id=1,  # type: ignore[arg-type]
        )