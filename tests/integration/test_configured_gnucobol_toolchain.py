"""Integration tests for settings-driven GnuCOBOL discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler.providers import (
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.services import (
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)
from opencobol2.toolchains import (
    discover_gnucobol,
    ToolchainSource,
)


def test_saved_compiler_profile_drives_explicit_discovery(
    tmp_path: Path,
) -> None:
    available_toolchain = discover_gnucobol()

    if available_toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed or discoverable."
        )

    profile = CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="Configured GnuCOBOL",
        configuration={
            "compiler_path": str(
                available_toolchain.compiler_path,
            ),
        },
    )

    settings_path = tmp_path / "settings.json"

    settings_service = SettingsService(
        SettingsStorage(
            settings_path,
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

    reloaded_settings_service = SettingsService(
        SettingsStorage(
            settings_path,
        )
    )

    selected_profile = (
        reloaded_settings_service
        .current
        .compilers
        .default_profile
    )

    assert selected_profile is not None
    assert (
        selected_profile.profile_id
        == profile.profile_id
    )
    assert (
        selected_profile.provider_id
        == GNUCOBOL_PROVIDER_ID
    )

    service = GnuCobolToolchainService(
        settings_service=reloaded_settings_service,
    )

    configured_toolchain = service.discover()

    assert configured_toolchain is not None
    assert (
        configured_toolchain.compiler_path
        == available_toolchain.compiler_path
    )
    assert (
        configured_toolchain.source
        is ToolchainSource.EXPLICIT
    )