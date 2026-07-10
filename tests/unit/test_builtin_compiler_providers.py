"""Unit tests for built-in compiler provider definitions."""

from __future__ import annotations

import pytest

from opencobol2.compiler.providers import (
    CompilerProfile,
    CUSTOM_COMPILER_PROVIDER_ID,
    CustomLocalCompilerProvider,
    GNUCOBOL_PROVIDER_ID,
    GnuCobolCompilerProvider,
    IBM_ENTERPRISE_COBOL_ZOS_PROVIDER_ID,
    IbmEnterpriseCobolZosCompilerProvider,
    VISUAL_COBOL_PROVIDER_ID,
    VisualCobolCompilerProvider,
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


def test_visual_cobol_accepts_current_configuration() -> None:
    profile = CompilerProfile(
        provider_id=VISUAL_COBOL_PROVIDER_ID,
        display_name="Visual COBOL",
        configuration={
            "compiler_path": "C:/product/bin/cobol.exe",
            "product_variant": "enterprise-developer",
            "copybook_paths": [
                "C:/product/copy",
            ],
            "compiler_directives": [
                "SOURCEFORMAT(FREE)",
            ],
        },
        environment_overrides={
            "COBDIR": "C:/product",
        },
    )

    VisualCobolCompilerProvider().validate_profile(
        profile,
    )


def test_visual_cobol_rejects_invalid_product_variant() -> None:
    profile = CompilerProfile(
        provider_id=VISUAL_COBOL_PROVIDER_ID,
        display_name="Visual COBOL",
        configuration={
            "product_variant": "other",
        },
    )

    with pytest.raises(
        ValueError,
        match="must be one of",
    ):
        VisualCobolCompilerProvider().validate_profile(
            profile,
        )


def test_ibm_provider_requires_connection_profile() -> None:
    profile = CompilerProfile(
        provider_id=(
            IBM_ENTERPRISE_COBOL_ZOS_PROVIDER_ID
        ),
        display_name="IBM Enterprise COBOL",
    )

    with pytest.raises(
        ValueError,
        match="connection_profile_id",
    ):
        IbmEnterpriseCobolZosCompilerProvider().validate_profile(
            profile,
        )


def test_ibm_provider_accepts_jcl_profile() -> None:
    profile = CompilerProfile(
        provider_id=(
            IBM_ENTERPRISE_COBOL_ZOS_PROVIDER_ID
        ),
        display_name="PROD Enterprise COBOL",
        configuration={
            "connection_profile_id": "prod-zos",
            "compile_mode": "jcl-procedure",
            "compile_procedure": "IGYWCL",
            "compiler_options": [
                "OPT(2)",
                "SSRANGE",
            ],
        },
    )

    IbmEnterpriseCobolZosCompilerProvider().validate_profile(
        profile,
    )


def test_ibm_provider_accepts_zos_unix_profile() -> None:
    profile = CompilerProfile(
        provider_id=(
            IBM_ENTERPRISE_COBOL_ZOS_PROVIDER_ID
        ),
        display_name="DEV Enterprise COBOL",
        configuration={
            "connection_profile_id": "dev-zos",
            "compile_mode": "zos-unix",
            "zos_unix_command": "cob2",
        },
    )

    IbmEnterpriseCobolZosCompilerProvider().validate_profile(
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
            "version_arguments": [
                "/version",
            ],
            "compile_arguments": [
                "{source}",
                "/out:{output}",
            ],
            "fixed_format_arguments": [
                "/fixed",
            ],
            "free_format_arguments": [
                "/free",
            ],
            "diagnostic_format": "msvc",
            "success_return_codes": [
                0,
                4,
            ],
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
            "success_return_codes": [
                "0",
            ],
        },
    )

    with pytest.raises(
        TypeError,
        match="integer list",
    ):
        CustomLocalCompilerProvider().validate_profile(
            profile,
        )