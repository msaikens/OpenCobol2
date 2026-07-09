"""Tests for GnuCOBOL toolchain discovery."""

from __future__ import annotations

import os
from pathlib import Path
import stat

import pytest

from opencobol2.toolchains.gnucobol import (
    _apply_layout_environment,
    _parse_64_bit_mode,
    _parse_info,
    _parse_version,
    discover_gnucobol,
)
from opencobol2.toolchains.models import (
    GnuCobolToolchain,
    ToolchainSource,
)


def test_parse_version():
    output = """\
cobc (GnuCOBOL) 3.2.0
Copyright (C) 2023 Free Software Foundation, Inc.
"""

    assert _parse_version(output) == "3.2.0"


def test_parse_info():
    output = """\
build environment        : x86_64-w64-mingw32
COB_CONFIG_DIR           : /usr/share/gnucobol/config
COB_COPY_DIR             : /usr/share/gnucobol/copy
64bit-mode               : yes
"""

    information = _parse_info(output)

    assert information["build environment"] == "x86_64-w64-mingw32"
    assert information["COB_CONFIG_DIR"] == "/usr/share/gnucobol/config"
    assert information["COB_COPY_DIR"] == "/usr/share/gnucobol/copy"
    assert information["64bit-mode"] == "yes"


def test_parse_64_bit_mode():
    assert _parse_64_bit_mode("yes") is True
    assert _parse_64_bit_mode("no") is False
    assert _parse_64_bit_mode("unknown") is None
    assert _parse_64_bit_mode(None) is None


def test_apply_layout_environment(tmp_path):
    prefix = tmp_path / "toolchain"

    compiler_directory = prefix / "bin"
    config_directory = (
        prefix
        / "share"
        / "gnucobol"
        / "config"
    )
    copy_directory = (
        prefix
        / "share"
        / "gnucobol"
        / "copy"
    )
    library_directory = prefix / "lib" / "gnucobol"

    compiler_directory.mkdir(parents=True)
    config_directory.mkdir(parents=True)
    copy_directory.mkdir(parents=True)
    library_directory.mkdir(parents=True)

    compiler_path = compiler_directory / "cobc.exe"
    compiler_path.touch()

    (config_directory / "default.conf").touch()

    environment: dict[str, str] = {}

    _apply_layout_environment(
        compiler_path,
        environment,
    )

    assert environment["COB_CONFIG_DIR"] == str(
        config_directory.resolve()
    )
    assert environment["COB_COPY_DIR"] == str(
        copy_directory.resolve()
    )
    assert environment["COB_LIBRARY_PATH"] == str(
        library_directory.resolve()
    )


def test_layout_environment_preserves_user_overrides(tmp_path):
    prefix = tmp_path / "toolchain"

    compiler_directory = prefix / "bin"
    config_directory = (
        prefix
        / "share"
        / "gnucobol"
        / "config"
    )

    compiler_directory.mkdir(parents=True)
    config_directory.mkdir(parents=True)

    compiler_path = compiler_directory / "cobc.exe"
    compiler_path.touch()

    (config_directory / "default.conf").touch()

    environment = {
        "COB_CONFIG_DIR": "user-config-directory",
    }

    _apply_layout_environment(
        compiler_path,
        environment,
    )

    assert environment["COB_CONFIG_DIR"] == "user-config-directory"


def test_toolchain_process_environment_prepends_compiler_bin(tmp_path):
    compiler_directory = tmp_path / "bin"
    compiler_directory.mkdir()

    compiler_path = compiler_directory / "cobc.exe"
    compiler_path.touch()

    toolchain = GnuCobolToolchain(
        compiler_path=compiler_path,
        source=ToolchainSource.EXPLICIT,
        version="3.2.0",
        version_text="cobc (GnuCOBOL) 3.2.0",
        info_text="",
        environment={
            "COB_CONFIG_DIR": "config-directory",
        },
    )

    environment = toolchain.process_environment(
        {
            "PATH": "existing-path",
        }
    )

    path_entries = environment["PATH"].split(os.pathsep)

    assert path_entries[0] == str(compiler_directory)
    assert path_entries[1] == "existing-path"
    assert environment["COB_CONFIG_DIR"] == "config-directory"


@pytest.fixture
def fake_gnucobol(tmp_path):
    """Create a fake executable GnuCOBOL compiler."""
    compiler_name = "cobc.exe" if os.name == "nt" else "cobc"
    compiler_path = tmp_path / compiler_name

    if os.name == "nt":
        compiler_path.write_text(
            "@echo off\n"
            "if \"%1\"==\"--version\" (\n"
            "  echo cobc ^(GnuCOBOL^) 3.2.0\n"
            "  exit /b 0\n"
            ")\n"
            "if \"%1\"==\"--info\" (\n"
            "  echo build environment : fake-windows-target\n"
            "  echo 64bit-mode : yes\n"
            "  exit /b 0\n"
            ")\n"
            "exit /b 1\n",
            encoding="utf-8",
        )
    else:
        compiler_path.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then\n"
            "  echo 'cobc (GnuCOBOL) 3.2.0'\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = \"--info\" ]; then\n"
            "  echo 'build environment : fake-posix-target'\n"
            "  echo '64bit-mode : yes'\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )

        compiler_path.chmod(
            compiler_path.stat().st_mode
            | stat.S_IXUSR
        )

    return compiler_path


def test_discover_explicit_compiler(fake_gnucobol):
    toolchain = discover_gnucobol(
        explicit_path=fake_gnucobol,
        environment={
            "PATH": "",
        },
    )

    assert toolchain is not None
    assert toolchain.compiler_path == fake_gnucobol.resolve()
    assert toolchain.source == ToolchainSource.EXPLICIT
    assert toolchain.version == "3.2.0"
    assert toolchain.is_64_bit is True


def test_explicit_compiler_has_highest_priority(
    fake_gnucobol,
    tmp_path,
):
    path_directory = tmp_path / "path-toolchain"
    path_directory.mkdir()

    compiler_name = "cobc.exe" if os.name == "nt" else "cobc"
    path_compiler = path_directory / compiler_name

    path_compiler.write_bytes(
        fake_gnucobol.read_bytes()
    )

    if os.name != "nt":
        path_compiler.chmod(
            path_compiler.stat().st_mode
            | stat.S_IXUSR
        )

    toolchain = discover_gnucobol(
        explicit_path=fake_gnucobol,
        environment={
            "PATH": str(path_directory),
        },
    )

    assert toolchain is not None
    assert toolchain.compiler_path == fake_gnucobol.resolve()
    assert toolchain.source == ToolchainSource.EXPLICIT


def test_discover_compiler_from_path(fake_gnucobol):
    toolchain = discover_gnucobol(
        environment={
            "PATH": str(fake_gnucobol.parent),
        },
    )

    assert toolchain is not None
    assert toolchain.compiler_path == fake_gnucobol.resolve()
    assert toolchain.source == ToolchainSource.PATH


def test_invalid_explicit_candidate_falls_back_to_path(
    fake_gnucobol,
    tmp_path,
):
    invalid_compiler = tmp_path / "missing" / "cobc"

    toolchain = discover_gnucobol(
        explicit_path=invalid_compiler,
        environment={
            "PATH": str(fake_gnucobol.parent),
        },
    )

    assert toolchain is not None
    assert toolchain.compiler_path == fake_gnucobol.resolve()
    assert toolchain.source == ToolchainSource.PATH


def test_discovery_returns_none_when_no_candidate_is_valid(tmp_path):
    toolchain = discover_gnucobol(
        explicit_path=tmp_path / "missing-cobc",
        environment={
            "PATH": "",
            "SystemDrive": str(tmp_path),
            "ProgramFiles": str(tmp_path / "Program Files"),
            "ProgramFiles(x86)": str(
                tmp_path / "Program Files (x86)"
            ),
        },
    )

    assert toolchain is None