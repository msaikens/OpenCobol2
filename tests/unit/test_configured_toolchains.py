"""Unit tests for configured toolchain application services."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pytest

import opencobol2.services.toolchains as toolchain_services
from opencobol2.services import (
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
    ToolchainSettings,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
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


def test_discovery_uses_configured_compiler_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    compiler_path = Path(
        "C:/custom/gnucobol/bin/cobc.exe"
    )

    settings_service.update_toolchains(
        ToolchainSettings(
            gnucobol_compiler_path=compiler_path,
        )
    )

    captured_path: Path | None = None

    def fake_discover(
        explicit_path=None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        nonlocal captured_path

        captured_path = explicit_path

        return None

    monkeypatch.setattr(
        toolchain_services,
        "discover_gnucobol",
        fake_discover,
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    service.discover(
        base_environment={
            "PATH": "base-path",
        },
    )

    assert captured_path == compiler_path


def test_configured_environment_overrides_base_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    settings_service.update_toolchains(
        ToolchainSettings(
            environment_overrides={
                "COB_CONFIG_DIR": "configured",
                "OPENCOBOL2_TEST_VALUE": "enabled",
            },
        )
    )

    captured_environment: dict[str, str] | None = None

    def fake_discover(
        explicit_path=None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        nonlocal captured_environment

        captured_environment = dict(
            environment
            if environment is not None
            else {}
        )

        return None

    monkeypatch.setattr(
        toolchain_services,
        "discover_gnucobol",
        fake_discover,
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    service.discover(
        base_environment={
            "PATH": "base-path",
            "COB_CONFIG_DIR": "base",
            "PRESERVED_VALUE": "yes",
        },
    )

    assert captured_environment is not None
    assert (
        captured_environment["PATH"]
        == "base-path"
    )
    assert (
        captured_environment["COB_CONFIG_DIR"]
        == "configured"
    )
    assert (
        captured_environment["OPENCOBOL2_TEST_VALUE"]
        == "enabled"
    )
    assert (
        captured_environment["PRESERVED_VALUE"]
        == "yes"
    )


def test_process_environment_does_not_mutate_base_mapping(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    settings_service.update_toolchains(
        ToolchainSettings(
            environment_overrides={
                "COB_CONFIG_DIR": "configured",
            },
        )
    )

    base_environment = {
        "PATH": "base-path",
        "COB_CONFIG_DIR": "base",
    }

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    environment = service.process_environment(
        base_environment,
    )

    assert base_environment == {
        "PATH": "base-path",
        "COB_CONFIG_DIR": "base",
    }

    assert environment == {
        "PATH": "base-path",
        "COB_CONFIG_DIR": "configured",
    }


def test_discovery_reads_latest_settings_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    compiler_path = Path(
        "D:/new-toolchain/bin/cobc.exe"
    )

    settings_service.update_toolchains(
        ToolchainSettings(
            gnucobol_compiler_path=compiler_path,
        )
    )

    captured_path: Path | None = None

    def fake_discover(
        explicit_path=None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        nonlocal captured_path

        captured_path = explicit_path

        return None

    monkeypatch.setattr(
        toolchain_services,
        "discover_gnucobol",
        fake_discover,
    )

    service.discover(
        base_environment={},
    )

    assert captured_path == compiler_path


def test_discovery_returns_discovered_toolchain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )

    expected_toolchain = GnuCobolToolchain(
        compiler_path=Path(
            "tools/cobc.exe"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2",
        version_text="cobc 3.2",
        info_text="build environment: test",
    )

    def fake_discover(
        explicit_path=None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> GnuCobolToolchain:
        return expected_toolchain

    monkeypatch.setattr(
        toolchain_services,
        "discover_gnucobol",
        fake_discover,
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    discovered_toolchain = service.discover(
        base_environment={},
    )

    assert discovered_toolchain is expected_toolchain