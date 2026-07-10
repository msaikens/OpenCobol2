"""Integration-style unit tests for Custom Local runtime activation."""

from __future__ import annotations

from pathlib import Path

from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    CompilerProfile,
    create_builtin_compiler_provider_registry,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryRegistry,
    CustomLocalCompilerRuntime,
    CustomLocalCompilerRuntimeFactory,
)
from opencobol2.services import (
    CompilerProfileService,
    CompilerRuntimeActivationService,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


def test_custom_local_profile_activates_custom_runtime(
    tmp_path: Path,
) -> None:
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Vendor COBOL",
        configuration={
            "executable_path": (
                "C:/Vendor COBOL/bin/compiler.exe"
            ),
        },
    )

    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        )
    )

    profile_service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=(
            create_builtin_compiler_provider_registry()
        ),
    )

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        CustomLocalCompilerRuntimeFactory()
    )

    activation_service = (
        CompilerRuntimeActivationService(
            profile_service=profile_service,
            runtime_factory_registry=runtime_registry,
        )
    )

    runtime = activation_service.activate_default()

    assert isinstance(
        runtime,
        CustomLocalCompilerRuntime,
    )
    assert runtime.profile_id == profile.profile_id
    assert (
        runtime.provider_id
        == CUSTOM_COMPILER_PROVIDER_ID
    )
    assert (
        runtime.configuration["executable_path"]
        == "C:/Vendor COBOL/bin/compiler.exe"
    )