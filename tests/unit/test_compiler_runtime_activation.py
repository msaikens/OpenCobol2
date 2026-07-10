"""Unit tests for compiler runtime activation services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    GNUCOBOL_PROVIDER_ID,
    CompilerExecutionKind,
    CompilerProfile,
    CompilerProviderRegistry,
    CustomLocalCompilerProvider,
    GnuCobolCompilerProvider,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntime,
    CompilerRuntimeFactoryRegistry,
)
from opencobol2.services import (
    CompilerProfileService,
    CompilerRuntimeActivationError,
    CompilerRuntimeActivationService,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class FakeCompilerRuntime:
    """Fake compiler runtime for activation tests."""

    provider_id: str
    profile_id: UUID
    execution_kind: CompilerExecutionKind


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class FakeCompilerRuntimeFactory:
    """Configurable fake compiler runtime factory."""

    provider_id: str
    execution_kind: CompilerExecutionKind
    runtime_provider_id: str | None = None
    runtime_profile_id: UUID | None = None
    runtime_execution_kind: (
        CompilerExecutionKind | None
    ) = None

    def create_runtime(
        self,
        profile: CompilerProfile,
    ) -> CompilerRuntime:
        """Create a configurable fake compiler runtime."""

        return FakeCompilerRuntime(
            provider_id=(
                self.provider_id
                if self.runtime_provider_id is None
                else self.runtime_provider_id
            ),
            profile_id=(
                profile.profile_id
                if self.runtime_profile_id is None
                else self.runtime_profile_id
            ),
            execution_kind=(
                self.execution_kind
                if self.runtime_execution_kind is None
                else self.runtime_execution_kind
            ),
        )


def _create_settings_service(
    tmp_path: Path,
) -> SettingsService:
    """Create isolated application settings."""

    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def _create_profile_service(
    settings_service: SettingsService,
) -> CompilerProfileService:
    """Create a compiler profile service with test providers."""

    provider_registry = CompilerProviderRegistry()
    provider_registry.register(
        GnuCobolCompilerProvider(),
    )
    provider_registry.register(
        CustomLocalCompilerProvider(),
    )

    return CompilerProfileService(
        settings_service=settings_service,
        provider_registry=provider_registry,
    )


def test_activate_default_runtime(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    runtime_registry = CompilerRuntimeFactoryRegistry()
    factory = FakeCompilerRuntimeFactory(
        provider_id=GNUCOBOL_PROVIDER_ID,
        execution_kind=(
            CompilerExecutionKind.LOCAL_PROCESS
        ),
    )
    runtime_registry.register(
        factory,
    )

    service = CompilerRuntimeActivationService(
        profile_service=_create_profile_service(
            settings_service,
        ),
        runtime_factory_registry=runtime_registry,
    )

    runtime = service.activate_default()

    default_profile = (
        settings_service
        .current
        .compilers
        .default_profile
    )

    assert default_profile is not None
    assert (
        runtime.provider_id
        == GNUCOBOL_PROVIDER_ID
    )
    assert (
        runtime.profile_id
        == default_profile.profile_id
    )
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_activate_specific_custom_local_runtime(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Vendor COBOL",
        configuration={
            "executable_path": "compiler.exe",
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

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        FakeCompilerRuntimeFactory(
            provider_id=CUSTOM_COMPILER_PROVIDER_ID,
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
        )
    )

    service = CompilerRuntimeActivationService(
        profile_service=_create_profile_service(
            settings_service,
        ),
        runtime_factory_registry=runtime_registry,
    )

    runtime = service.activate(
        profile.profile_id,
    )

    assert (
        runtime.provider_id
        == CUSTOM_COMPILER_PROVIDER_ID
    )
    assert (
        runtime.profile_id
        == profile.profile_id
    )
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_runtime_provider_identity_must_match_profile(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        FakeCompilerRuntimeFactory(
            provider_id=GNUCOBOL_PROVIDER_ID,
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            runtime_provider_id="example.wrong",
        )
    )

    service = CompilerRuntimeActivationService(
        profile_service=_create_profile_service(
            settings_service,
        ),
        runtime_factory_registry=runtime_registry,
    )

    with pytest.raises(
        CompilerRuntimeActivationError,
        match="provider ID does not match",
    ):
        service.activate_default()


def test_runtime_profile_identity_must_match_profile(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        FakeCompilerRuntimeFactory(
            provider_id=GNUCOBOL_PROVIDER_ID,
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            runtime_profile_id=UUID(
                "11111111-1111-1111-1111-111111111111"
            ),
        )
    )

    service = CompilerRuntimeActivationService(
        profile_service=_create_profile_service(
            settings_service,
        ),
        runtime_factory_registry=runtime_registry,
    )

    with pytest.raises(
        CompilerRuntimeActivationError,
        match="profile ID does not match",
    ):
        service.activate_default()


def test_runtime_execution_kind_must_match_provider(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        FakeCompilerRuntimeFactory(
            provider_id=GNUCOBOL_PROVIDER_ID,
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            runtime_execution_kind=(
                CompilerExecutionKind.REMOTE_JOB
            ),
        )
    )

    service = CompilerRuntimeActivationService(
        profile_service=_create_profile_service(
            settings_service,
        ),
        runtime_factory_registry=runtime_registry,
    )

    with pytest.raises(
        CompilerRuntimeActivationError,
        match="execution kind does not match",
    ):
        service.activate_default()