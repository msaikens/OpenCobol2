"""Unit tests for typed OpenCobol2 settings models."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.settings import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    EditorSettings,
    ToolchainSettings,
)


def test_application_settings_have_typed_defaults() -> None:
    settings = ApplicationSettings()

    assert settings.schema_version == 1
    assert (
        settings.toolchains.gnucobol_compiler_path
        is None
    )
    assert (
        settings.toolchains.git_executable_path
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


def test_toolchain_settings_normalize_paths_and_copy_environment() -> None:
    environment = {
        "COB_CONFIG_DIR": "config",
    }

    settings = ToolchainSettings(
        gnucobol_compiler_path="tools/cobc.exe",
        git_executable_path="tools/git.exe",
        environment_overrides=environment,
    )

    environment[
        "COB_CONFIG_DIR"
    ] = "changed"

    assert (
        settings.gnucobol_compiler_path
        == Path("tools/cobc.exe")
    )
    assert (
        settings.git_executable_path
        == Path("tools/git.exe")
    )
    assert (
        settings.environment_overrides[
            "COB_CONFIG_DIR"
        ]
        == "config"
    )


def test_toolchain_environment_overrides_are_read_only() -> None:
    settings = ToolchainSettings(
        environment_overrides={
            "COB_CONFIG_DIR": "config",
        },
    )

    with pytest.raises(
        TypeError,
    ):
        settings.environment_overrides[
            "COB_CONFIG_DIR"
        ] = "changed"  # type: ignore[index]


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