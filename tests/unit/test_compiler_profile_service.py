"""Unit tests for compiler profile application services."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
    CompilerProviderNotFoundError,
    CompilerProviderRegistry,
    GNUCOBOL_PROVIDER_ID,
    GnuCobolCompilerProvider,
    VISUAL_COBOL_PROVIDER_ID,
    VisualCobolCompilerProvider,
)
from opencobol2.services import (
    CompilerProfileNotFoundError,
    CompilerProfileResolution,
    CompilerProfileService,
    DefaultCompilerProfileNotConfiguredError,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


def _create_settings_service(
    tmp_path: Path,
) -> SettingsService:
    """Create an isolated settings service."""
    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def _create_registry() -> CompilerProviderRegistry:
    """Create a small compiler provider registry for service tests."""
    registry = CompilerProviderRegistry()
    registry.register(
        GnuCobolCompilerProvider(),
    )
    registry.register(
        VisualCobolCompilerProvider(),
    )

    return registry


def test_resolve_default_returns_profile_and_provider(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    registry = _create_registry()
    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=registry,
    )

    resolution = service.resolve_default()

    assert isinstance(
        resolution,
        CompilerProfileResolution,
    )
    assert (
        resolution.profile
        is settings_service.current.compilers.default_profile
    )
    assert (
        resolution.provider.provider_id
        == GNUCOBOL_PROVIDER_ID
    )


def test_resolution_exposes_provider_execution_kind(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    resolution = service.resolve_default()

    assert (
        resolution.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_resolve_specific_configured_profile(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = CompilerProfile(
        provider_id=VISUAL_COBOL_PROVIDER_ID,
        display_name="Visual COBOL",
        configuration={
            "product_variant": "visual-cobol",
        },
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=None,
            profiles=(
                profile,
            ),
        )
    )

    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    resolution = service.resolve(
        profile.profile_id,
    )

    assert resolution.profile is profile
    assert (
        resolution.provider.provider_id
        == VISUAL_COBOL_PROVIDER_ID
    )


def test_resolve_reads_latest_settings_snapshot(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    profile = CompilerProfile(
        provider_id=VISUAL_COBOL_PROVIDER_ID,
        display_name="Visual COBOL",
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        )
    )

    resolution = service.resolve_default()

    assert resolution.profile is profile


def test_missing_default_profile_is_rejected(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=None,
            profiles=(),
        )
    )

    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    with pytest.raises(
        DefaultCompilerProfileNotConfiguredError,
        match="No default compiler profile is configured",
    ):
        service.resolve_default()


def test_unknown_profile_id_is_rejected(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )
    profile_id = uuid4()

    with pytest.raises(
        CompilerProfileNotFoundError,
        match="Compiler profile is not configured",
    ):
        service.resolve(
            profile_id,
        )


def test_unregistered_profile_provider_is_rejected(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = CompilerProfile(
        provider_id="plugin.example.compiler",
        display_name="Plugin Compiler",
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        )
    )

    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    with pytest.raises(
        CompilerProviderNotFoundError,
        match="Compiler provider is not registered",
    ):
        service.resolve_default()


def test_provider_validation_is_applied_during_resolution(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="Invalid GnuCOBOL",
        configuration={
            "unknown_setting": True,
        },
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        )
    )

    service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=_create_registry(),
    )

    with pytest.raises(
        ValueError,
        match="Unknown compiler configuration fields",
    ):
        service.resolve_default()


def test_resolution_rejects_mismatched_provider() -> None:
    profile = CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="GnuCOBOL",
    )
    provider = VisualCobolCompilerProvider()

    with pytest.raises(
        ValueError,
        match=(
            "Compiler profile provider ID does not match "
            "the resolved provider"
        ),
    ):
        CompilerProfileResolution(
            profile=profile,
            provider=provider,
        )