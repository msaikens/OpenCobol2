"""Unit tests for compiler provider configuration resolution."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    CompilerProfile,
    CustomLocalCompilerProvider,
    resolve_compiler_profile_configuration,
)


def test_resolved_configuration_includes_provider_defaults() -> None:
    provider = CustomLocalCompilerProvider()
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Custom Compiler",
        configuration={
            "executable_path": "compiler.exe",
        },
    )

    configuration = (
        resolve_compiler_profile_configuration(
            provider,
            profile,
        )
    )

    assert configuration["executable_path"] == "compiler.exe"
    assert configuration["version_arguments"] == (
        "--version",
    )
    assert configuration["compile_arguments"] == (
        "{source}",
        "-o",
        "{output}",
    )
    assert configuration["diagnostic_format"] == "gcc"
    assert configuration["success_return_codes"] == (
        0,
    )


def test_explicit_profile_values_override_provider_defaults() -> None:
    provider = CustomLocalCompilerProvider()
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Custom Compiler",
        configuration={
            "executable_path": "compiler.exe",
            "compile_arguments": (
                "/compile",
                "{source}",
                "/out:{output}",
            ),
            "diagnostic_format": "msvc",
            "success_return_codes": (
                0,
                1,
            ),
        },
    )

    configuration = (
        resolve_compiler_profile_configuration(
            provider,
            profile,
        )
    )

    assert configuration["compile_arguments"] == (
        "/compile",
        "{source}",
        "/out:{output}",
    )
    assert configuration["diagnostic_format"] == "msvc"
    assert configuration["success_return_codes"] == (
        0,
        1,
    )


def test_resolved_configuration_is_read_only() -> None:
    provider = CustomLocalCompilerProvider()
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Custom Compiler",
        configuration={
            "executable_path": "compiler.exe",
        },
    )

    configuration = (
        resolve_compiler_profile_configuration(
            provider,
            profile,
        )
    )

    assert isinstance(
        configuration,
        MappingProxyType,
    )

    with pytest.raises(
        TypeError,
    ):
        configuration["diagnostic_format"] = "none"  # type: ignore[index]


def test_resolution_validates_profile_through_provider() -> None:
    provider = CustomLocalCompilerProvider()
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Invalid Custom Compiler",
        configuration={
            "executable_path": "compiler.exe",
            "unknown_setting": True,
        },
    )

    with pytest.raises(
        ValueError,
        match="Unknown compiler configuration fields",
    ):
        resolve_compiler_profile_configuration(
            provider,
            profile,
        )