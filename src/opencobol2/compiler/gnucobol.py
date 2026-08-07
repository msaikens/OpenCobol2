"""GnuCOBOL compiler command construction and invocation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
import subprocess
import time

from opencobol2.compiler.gnucobol_diagnostics import (
    parse_gnucobol_diagnostics,
)
from opencobol2.compiler.gnucobol_models import (
    GnuCobolCompilation,
)
from opencobol2.compiler.models import (
    CobolSourceFormat,
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
    CompilerOutputKind,
)
from opencobol2.toolchains import GnuCobolToolchain


_DEFAULT_TIMEOUT_SECONDS = 30.0

_OUTPUT_KIND_ARGUMENTS = {
    CompilerOutputKind.EXECUTABLE: "-x",
    CompilerOutputKind.MODULE: "-m",
}

_SOURCE_FORMAT_ARGUMENTS = {
    CobolSourceFormat.FIXED: "-fixed",
    CobolSourceFormat.FREE: "-free",
}


@dataclass(frozen=True, slots=True)
class GnuCobolCompiler:
    """Invokes a validated GnuCOBOL compiler toolchain."""

    toolchain: GnuCobolToolchain
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate compiler service configuration."""
        if self.timeout_seconds <= 0:
            raise ValueError(
                "Compiler timeout must be greater than zero."
            )

    def compile(
        self,
        request: CompileRequest,
        *,
        base_environment: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> GnuCobolCompilation:
        """Compile one COBOL request and parse captured diagnostics.

        Editor §CompilerProcess-6: `timeout_seconds`, when given,
        overrides `self.timeout_seconds` for this call only -- the
        single activated compiler instance is reused for every file in
        a whole-project build, so one legitimately slow-to-compile
        file shouldn't need to change the timeout for every other file
        too (mirrors the equivalent per-call override this tracker
        already added to the Git service layer).
        """
        process_result = self._invoke(
            request,
            base_environment=base_environment,
            timeout_seconds=timeout_seconds,
        )

        diagnostics = parse_gnucobol_diagnostics(
            _collect_diagnostic_output(
                process_result,
            )
        )

        return GnuCobolCompilation(
            process_result=process_result,
            diagnostics=diagnostics,
        )

    def _invoke(
        self,
        request: CompileRequest,
        *,
        base_environment: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> CompileResult:
        """Invoke the configured GnuCOBOL compiler process."""
        command = build_gnucobol_command(
            self.toolchain,
            request,
        )

        environment = self.toolchain.process_environment(
            os.environ
            if base_environment is None
            else base_environment
        )

        effective_timeout_seconds = (
            self.timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )

        if effective_timeout_seconds <= 0:
            raise ValueError(
                "Compiler timeout must be greater than zero."
            )

        started_at = time.perf_counter()

        try:
            completed_process = subprocess.run(
                command,
                cwd=request.working_directory,
                env=environment,
                capture_output=True,
                text=True,
                # Editor §CompilerProcess-3: without a pinned
                # `encoding=`, decoding falls back to the system's
                # preferred encoding (`cp1252` on Windows), silently
                # mangling non-ASCII diagnostic text -- the same bug
                # shape already found and fixed for Git's own
                # subprocess layer (`git/process.py`).
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            elapsed_seconds = time.perf_counter() - started_at

            return CompileResult(
                request=request,
                command=command,
                status=CompilerExecutionStatus.TIMED_OUT,
                stdout=_normalize_process_output(error.stdout),
                stderr=_normalize_process_output(error.stderr),
                elapsed_seconds=elapsed_seconds,
                error_message=(
                    "GnuCOBOL compilation timed out after "
                    f"{effective_timeout_seconds:g} seconds."
                ),
            )
        except OSError as error:
            elapsed_seconds = time.perf_counter() - started_at

            return CompileResult(
                request=request,
                command=command,
                status=CompilerExecutionStatus.FAILED_TO_START,
                elapsed_seconds=elapsed_seconds,
                error_message=(
                    "Unable to start GnuCOBOL compiler: "
                    f"{error}"
                ),
            )

        elapsed_seconds = time.perf_counter() - started_at

        return CompileResult(
            request=request,
            command=command,
            status=CompilerExecutionStatus.COMPLETED,
            return_code=completed_process.returncode,
            stdout=completed_process.stdout or "",
            stderr=completed_process.stderr or "",
            elapsed_seconds=elapsed_seconds,
        )


def build_gnucobol_command(
    toolchain: GnuCobolToolchain,
    request: CompileRequest,
) -> tuple[str, ...]:
    """Build the argument sequence for one GnuCOBOL compilation."""
    command: list[str] = [
        str(toolchain.compiler_path),
        _OUTPUT_KIND_ARGUMENTS[request.output_kind],
    ]

    if request.debug_symbols:
        # `-g` alone only emits line-number debug info; `-debug` is
        # what additionally makes GnuCOBOL emit the runtime checks
        # and the generated `<name>.c.l.h`/`.c.h` headers the debugger
        # needs to map COBOL data names to their memory locations (see
        # `opencobol2.debugger.gnucobol_symbols`) -- verified against a
        # real `cobc -x -g -debug` build inspected under a real `gdb`.
        command.extend(("-g", "-debug"))

    command.extend(
        (
            "-o",
            str(request.output_path),
        )
    )

    if request.listing_path is not None:
        command.extend(
            (
                "-t",
                str(request.listing_path),
            )
        )

    if request.standard is not None:
        command.append(f"-std={request.standard}")

    if request.source_format is not None:
        command.append(
            _SOURCE_FORMAT_ARGUMENTS[request.source_format]
        )

    for directory in request.copy_directories:
        command.extend(
            (
                "-I",
                str(directory),
            )
        )

    for directory in request.library_directories:
        command.extend(
            (
                "-L",
                str(directory),
            )
        )

    for library in request.libraries:
        command.extend(
            (
                "-l",
                library,
            )
        )

    command.extend(request.additional_arguments)

    command.append(str(request.source_path))

    command.extend(
        str(path)
        for path in request.additional_inputs
    )

    return tuple(command)


def _collect_diagnostic_output(
    process_result: CompileResult,
) -> str:
    """Collect captured process streams for diagnostic parsing."""
    return "\n".join(
        output
        for output in (
            process_result.stdout,
            process_result.stderr,
        )
        if output
    )


def _normalize_process_output(
    output: bytes | str | None,
) -> str:
    """Normalize captured subprocess output to text."""
    if output is None:
        return ""

    if isinstance(output, bytes):
        return output.decode(
            "utf-8",
            errors="replace",
        )

    return output