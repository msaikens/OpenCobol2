"""Tests for GnuCOBOL toolchain discovery."""

from __future__ import annotations

import os
from pathlib import Path

from opencobol2.toolchains.gnucobol import (
    _apply_layout_environment,
    _parse_64_bit_mode,
    _parse_info,
    _parse_version,
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