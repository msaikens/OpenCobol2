"""Integration tests for a real GnuCOBOL installation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from opencobol2.toolchains import ToolchainSource, discover_gnucobol


def test_discovered_gnucobol_can_compile_program(tmp_path: Path) -> None:
    """Discover a real compiler and use its modeled environment to compile COBOL."""
    toolchain = discover_gnucobol()

    if toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed or no valid cobc compiler was discovered."
        )

    assert toolchain.compiler_path.is_file()
    assert toolchain.version
    assert toolchain.version_text
    assert isinstance(toolchain.source, ToolchainSource)

    environment = toolchain.process_environment(os.environ)
    path_entries = environment.get("PATH", "").split(os.pathsep)

    assert path_entries
    assert Path(path_entries[0]) == toolchain.bin_directory

    source_path = tmp_path / "hello.cob"
    executable_path = tmp_path / (
        "hello.exe" if os.name == "nt" else "hello"
    )

    source_path.write_text(
        """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OPENCOBOL2-TEST.
       PROCEDURE DIVISION.
           DISPLAY "OPENCOBOL2-INTEGRATION-OK".
           STOP RUN.
""",
        encoding="utf-8",
    )

    completed_process = subprocess.run(
        [
            str(toolchain.compiler_path),
            "-x",
            str(source_path),
            "-o",
            str(executable_path),
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )

    assert completed_process.returncode == 0, (
        "Real GnuCOBOL compilation failed.\n"
        f"Compiler: {toolchain.compiler_path}\n"
        f"Source: {toolchain.source}\n"
        f"Version: {toolchain.version}\n"
        f"Output:\n{completed_process.stdout}"
    )
    assert executable_path.is_file()