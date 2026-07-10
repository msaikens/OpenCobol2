"""Unit tests for built-in compiler provider definitions."""

from __future__ import annotations

import pytest

from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    GNUCOBOL_PROVIDER_ID,
    CompilerExecutionKind,
    CompilerProfile,
    CustomLocalCompilerProvider,
    GnuCobolCompilerProvider,
    create_builtin_compiler_provider_registry,
)


def test_gnucobol_accepts_explicit_paths() -> None:
    profile = CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="GnuCOBOL 3.2",
        configuration={
            "compiler_path": "C:/tools/cobc.exe",
            "copy_directory": "C:/tools/copy",
        },
    )

    GnuCobolCompilerProvider().validate_profile(
        profile,
    )


def test_gnucobol_rejects_unknown_configuration() -> None:
    profile = CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="GnuCOBOL",
        configuration={
            "mystery": True,
        },
    )

    with pytest.raises(
        ValueError,
        match="Unknown compiler configuration",
    ):
        GnuCobolCompilerProvider().validate_profile(
            profile,
        )


def test_custom_provider_accepts_flexible_local_configuration() -> None:
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Vendor COBOL",
        configuration={
            "executable_path": (
                "C:/vendor/compiler.exe"
            ),
            "version_arguments": (
                "/version",
            ),
            "compile_arguments": (
                "{source}",
                "/out:{output}",
            ),
            "fixed_format_arguments": (
                "/fixed",
            ),
            "free_format_arguments": (
                "/free",
            ),
            "diagnostic_format": "msvc",
            "success_return_codes": (
                0,
                4,
            ),
        },
        environment_overrides={
            "VENDOR_HOME": "C:/vendor",
        },
    )

    CustomLocalCompilerProvider().validate_profile(
        profile,
    )


def test_custom_provider_rejects_invalid_success_return_codes() -> None:
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Vendor COBOL",
        configuration={
            "executable_path": "compiler",
            "success_return_codes": (
                "0",
            ),
        },
    )

    with pytest.raises(
        TypeError,
        match="integer list",
    ):
        CustomLocalCompilerProvider().validate_profile(
            profile,
        )


def test_builtin_registry_contains_supported_compiler_paths() -> None:
    registry = (
        create_builtin_compiler_provider_registry()
    )

    assert tuple(
        provider.provider_id
        for provider in registry.providers
    ) == (
        GNUCOBOL_PROVIDER_ID,
        CUSTOM_COMPILER_PROVIDER_ID,
    )


def test_builtin_providers_are_local_process_compilers() -> None:
    registry = (
        create_builtin_compiler_provider_registry()
    )

    assert all(
        provider.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
        for provider in registry.providers
    )