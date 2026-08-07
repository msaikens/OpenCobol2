"""Unit tests for GnuCOBOL command construction."""

from pathlib import Path

from opencobol2.compiler import (
    CobolSourceFormat,
    CompileRequest,
    CompilerOutputKind,
    build_gnucobol_command,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
)


def _toolchain() -> GnuCobolToolchain:
    """Create a deterministic toolchain model for command tests."""
    return GnuCobolToolchain(
        compiler_path=(
            Path("toolchains")
            / "gnucobol"
            / "bin"
            / "cobc"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2.0",
        version_text="cobc 3.2.0",
        info_text="build environment: test",
    )


def test_builds_executable_command() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("bin") / "hello",
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-x",
        "-o",
        str(Path("bin") / "hello"),
        "hello.cob",
    )


def test_builds_module_command() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("service.cob"),
        output_path=Path("bin") / "service",
        output_kind=CompilerOutputKind.MODULE,
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-m",
        "-o",
        str(Path("bin") / "service"),
        "service.cob",
    )


def test_adds_compiler_standard() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("modern.cob"),
        output_path=Path("modern"),
        standard="cobol2014",
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert "-std=cobol2014" in command


def test_adds_fixed_source_format() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("fixed.cob"),
        output_path=Path("fixed"),
        source_format=CobolSourceFormat.FIXED,
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert "-fixed" in command
    assert "-free" not in command


def test_adds_free_source_format() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("free.cob"),
        output_path=Path("free"),
        source_format=CobolSourceFormat.FREE,
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert "-free" in command
    assert "-fixed" not in command


def test_adds_search_paths_and_libraries() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("database.cob"),
        output_path=Path("database"),
        copy_directories=(
            Path("copy"),
            Path("vendor") / "copybooks",
        ),
        library_directories=(
            Path("lib"),
        ),
        libraries=(
            "sqlite3",
            "cob",
        ),
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-x",
        "-o",
        "database",
        "-I",
        "copy",
        "-I",
        str(Path("vendor") / "copybooks"),
        "-L",
        "lib",
        "-l",
        "sqlite3",
        "-l",
        "cob",
        "database.cob",
    )


def test_adds_additional_arguments_and_inputs_before_compilation() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("program.cob"),
        output_path=Path("program"),
        additional_inputs=(
            Path("support.o"),
            Path("generated.c"),
        ),
        additional_arguments=(
            "-Wall",
            "-Wextra",
        ),
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-x",
        "-o",
        "program",
        "-Wall",
        "-Wextra",
        "program.cob",
        "support.o",
        "generated.c",
    )


def test_adds_debug_symbols_flags_right_after_output_kind() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("demo.cbl"),
        output_path=Path("demo"),
        debug_symbols=True,
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-x",
        "-g",
        "-debug",
        "-o",
        "demo",
        "demo.cbl",
    )


def test_omits_debug_symbols_flags_by_default() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("demo.cbl"),
        output_path=Path("demo"),
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert "-g" not in command
    assert "-debug" not in command


def test_adds_listing_flag_right_after_output_path() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("demo.cbl"),
        output_path=Path("demo"),
        listing_path=Path("demo.lst"),
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert command == (
        str(toolchain.compiler_path),
        "-x",
        "-o",
        "demo",
        "-t",
        "demo.lst",
        "demo.cbl",
    )


def test_omits_listing_flag_by_default() -> None:
    toolchain = _toolchain()
    request = CompileRequest(
        source_path=Path("demo.cbl"),
        output_path=Path("demo"),
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert "-t" not in command


def test_paths_with_spaces_remain_single_arguments() -> None:
    toolchain = _toolchain()
    source_path = (
        Path("source files")
        / "hello world.cob"
    )
    output_path = (
        Path("build output")
        / "hello world"
    )

    request = CompileRequest(
        source_path=source_path,
        output_path=output_path,
    )

    command = build_gnucobol_command(
        toolchain,
        request,
    )

    assert str(source_path) in command
    assert str(output_path) in command
    assert f'"{source_path}"' not in command
    assert f'"{output_path}"' not in command