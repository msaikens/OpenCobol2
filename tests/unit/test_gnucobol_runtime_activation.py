"""Integration-style unit tests for GnuCOBOL runtime activation."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler.providers import (
    create_builtin_compiler_provider_registry,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryRegistry,
    GnuCobolRuntime,
    GnuCobolRuntimeFactory,
)
from opencobol2.services import (
    CompilerProfileService,
    CompilerRuntimeActivationService,
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
)


def test_default_profile_activates_gnucobol_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    toolchain = GnuCobolToolchain(
        compiler_path=Path(
            "C:/gnucobol/bin/cobc.exe"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2",
        version_text="cobc 3.2",
        info_text="build environment: test",
    )

    def fake_discover(
        self: GnuCobolToolchainService,
        profile=None,
        *,
        base_environment=None,
    ) -> GnuCobolToolchain:
        return toolchain

    monkeypatch.setattr(
        GnuCobolToolchainService,
        "discover",
        fake_discover,
    )

    profile_service = CompilerProfileService(
        settings_service=settings_service,
        provider_registry=(
            create_builtin_compiler_provider_registry()
        ),
    )

    toolchain_service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        GnuCobolRuntimeFactory(
            toolchain_service=toolchain_service,
        )
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
        GnuCobolRuntime,
    )
    assert (
        runtime.profile_id
        == settings_service
        .current
        .compilers
        .default_profile_id
    )
    assert runtime.toolchain is toolchain