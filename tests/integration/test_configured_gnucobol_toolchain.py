"""Integration tests for settings-driven GnuCOBOL discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.services import (
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
    ToolchainSettings,
)
from opencobol2.toolchains import (
    discover_gnucobol,
    ToolchainSource,
)


def test_saved_compiler_path_drives_explicit_discovery(
    tmp_path: Path,
) -> None:
    available_toolchain = discover_gnucobol()

    if available_toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed or discoverable."
        )

    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    settings_service.update_toolchains(
        ToolchainSettings(
            gnucobol_compiler_path=(
                available_toolchain.compiler_path
            ),
        )
    )

    reloaded_settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
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