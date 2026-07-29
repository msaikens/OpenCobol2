"""Unit tests for configured toolchain application services."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pytest

import opencobol2.services.toolchains as toolchain_services
from opencobol2.compiler.providers import (
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
    JsonValue,
)
from opencobol2.services import (
    DefaultCompilerProfileNotConfiguredError,
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
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


def _create_gnucobol_profile(
    *,
    configuration: dict[str, JsonValue] | None = None,
    environment_overrides: dict[str, str] | None = None,
) -> CompilerProfile:
    """Create an isolated GnuCOBOL compiler profile."""
    return CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="Test GnuCOBOL",
        configuration=(
            {}
            if configuration is None
            else configuration
        ),
        environment_overrides=(
            {}
            if environment_overrides is None
            else environment_overrides
        ),
    )


def _configure_default_profile(
    settings_service: SettingsService,
    profile: CompilerProfile,
) -> None:
    """Persist one selected compiler profile."""
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        )
    )


def test_discovery_uses_profile_compiler_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    compiler_path = Path(
        "C:/custom/gnucobol/bin/cobc.exe"
    )
    profile = _create_gnucobol_profile(
        configuration={
            "compiler_path": str(
                compiler_path,
            ),
        },
    )
    _configure_default_profile(
        settings_service,
        profile,
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


def test_profile_environment_overrides_base_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        environment_overrides={
            "COB_CONFIG_DIR": "configured",
            "OPENCOBOL2_TEST_VALUE": "enabled",
        },
    )
    _configure_default_profile(
        settings_service,
        profile,
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
        captured_environment[
            "OPENCOBOL2_TEST_VALUE"
        ]
        == "enabled"
    )
    assert (
        captured_environment["PRESERVED_VALUE"]
        == "yes"
    )


def test_structured_configuration_overrides_profile_environment(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        configuration={
            "config_directory": "structured-config",
            "copy_directory": "structured-copy",
            "library_path": "structured-library",
        },
        environment_overrides={
            "COB_CONFIG_DIR": "profile-config",
            "COB_COPY_DIR": "profile-copy",
            "COB_LIBRARY_PATH": "profile-library",
        },
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    environment = service.process_environment(
        profile,
        {
            "COB_CONFIG_DIR": "base-config",
            "COB_COPY_DIR": "base-copy",
            "COB_LIBRARY_PATH": "base-library",
        },
    )

    assert (
        environment["COB_CONFIG_DIR"]
        == "structured-config"
    )
    assert (
        environment["COB_COPY_DIR"]
        == "structured-copy"
    )
    assert (
        environment["COB_LIBRARY_PATH"]
        == "structured-library"
    )


def test_padded_compiler_path_is_stripped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Editor §CompilerAbstraction-1: a whitespace-padded compiler path
    # used to be passed through unstripped, so `Path(padded).is_file()`
    # would fail to resolve even when the unpadded file genuinely
    # exists, silently treating a configured compiler as absent.
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        configuration={
            "compiler_path": "  C:/custom/gnucobol/bin/cobc.exe  ",
        },
    )
    _configure_default_profile(
        settings_service,
        profile,
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
        base_environment={},
    )

    assert captured_path == Path(
        "C:/custom/gnucobol/bin/cobc.exe",
    )


def test_padded_structured_environment_value_is_stripped(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        configuration={
            "copy_directory": "  C:/tools/copybooks  ",
        },
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    environment = service.process_environment(
        profile,
        {},
    )

    assert (
        environment["COB_COPY_DIR"]
        == "C:/tools/copybooks"
    )


def test_environment_override_replaces_a_differently_cased_base_key(
    tmp_path: Path,
) -> None:
    # Editor §CompilerAbstraction-2: `os.environ` is case-insensitive
    # on Windows, but a plain dict is not -- a naive `.update()` used
    # to leave both the original ambient key and the differently-cased
    # override present, with which one a spawned child process actually
    # observes left to incidental dict ordering.
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        environment_overrides={
            "Path": "Z:/overridden/bin",
        },
    )

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    environment = service.process_environment(
        profile,
        {
            "PATH": "C:/original/bin",
        },
    )

    matching_keys = [
        key
        for key in environment
        if key.casefold() == "path"
    ]
    assert matching_keys == ["Path"]
    assert environment["Path"] == "Z:/overridden/bin"


def test_process_environment_does_not_mutate_base_mapping(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    profile = _create_gnucobol_profile(
        environment_overrides={
            "COB_CONFIG_DIR": "configured",
        },
    )
    base_environment = {
        "PATH": "base-path",
        "COB_CONFIG_DIR": "base",
    }

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    environment = service.process_environment(
        profile,
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


def test_discovery_reads_latest_default_profile(
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
    profile = _create_gnucobol_profile(
        configuration={
            "compiler_path": str(
                compiler_path,
            ),
        },
    )
    _configure_default_profile(
        settings_service,
        profile,
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


def test_discovery_accepts_explicit_gnucobol_profile(
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
        "E:/alternate/cobc.exe"
    )
    profile = _create_gnucobol_profile(
        configuration={
            "compiler_path": str(
                compiler_path,
            ),
        },
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
        profile,
        base_environment={},
    )

    assert captured_path == compiler_path


def test_non_gnucobol_profile_is_rejected(
    tmp_path: Path,
) -> None:
    settings_service = _create_settings_service(
        tmp_path,
    )
    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )
    profile = CompilerProfile(
        provider_id="example.other-compiler",
        display_name="Other Compiler",
    )

    with pytest.raises(
        ValueError,
        match="GnuCOBOL toolchain discovery requires provider",
    ):
        service.discover(
            profile,
            base_environment={},
        )


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

    service = GnuCobolToolchainService(
        settings_service=settings_service,
    )

    # Editor §CompilerAbstraction-3: this used to be a bare ValueError,
    # inconsistent with the typed error
    # `CompilerProfileService.resolve_default` already raises for the
    # identical condition.
    with pytest.raises(
        DefaultCompilerProfileNotConfiguredError,
        match="No default compiler profile is configured",
    ):
        service.discover(
            base_environment={},
        )


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