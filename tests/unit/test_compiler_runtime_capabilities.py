"""Unit tests for compiler runtime capability contracts."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from opencobol2.compiler import (
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
    CompilerOutputKind,
    CustomLocalCompilation,
    GnuCobolCompilation,
    GnuCobolCompiler,
)
from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    CompilerExecutionKind,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.compiler.runtimes import (
    CustomLocalCompilerRuntime,
    GnuCobolRuntime,
    LocalCompilationResult,
    LocalCompilerRuntime,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
)


def _create_request() -> CompileRequest:
    """Create a representative local compilation request."""

    return CompileRequest(
        source_path=Path(
            "program.cob",
        ),
        output_path=Path(
            "program.exe",
        ),
        output_kind=CompilerOutputKind.EXECUTABLE,
    )


def _create_process_result() -> CompileResult:
    """Create a completed local process result."""

    request = _create_request()

    return CompileResult(
        request=request,
        command=(
            "compiler.exe",
            "program.cob",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=0,
    )


def _create_gnucobol_runtime() -> GnuCobolRuntime:
    """Create an activated GnuCOBOL runtime."""

    toolchain = GnuCobolToolchain(
        compiler_path=Path(
            "C:/gnucobol/bin/cobc.exe"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2",
        version_text="cobc 3.2",
        info_text="build environment: test",
    )

    return GnuCobolRuntime(
        profile_id=uuid4(),
        toolchain=toolchain,
        compiler=GnuCobolCompiler(
            toolchain=toolchain,
        ),
    )


def _create_custom_local_runtime() -> CustomLocalCompilerRuntime:
    """Create an activated custom local compiler runtime."""

    return CustomLocalCompilerRuntime(
        profile_id=uuid4(),
        display_name="Vendor COBOL",
        configuration={
            "executable_path": "compiler.exe",
            "version_arguments": (
                "--version",
            ),
            "compile_arguments": (
                "{source}",
                "-o",
                "{output}",
            ),
            "executable_output_arguments": (),
            "module_output_arguments": (),
            "fixed_format_arguments": (),
            "free_format_arguments": (),
            "diagnostic_format": "gcc",
            "success_return_codes": (
                0,
            ),
        },
        environment_overrides={},
    )


def test_gnucobol_runtime_has_local_compiler_capability() -> None:
    runtime = _create_gnucobol_runtime()

    assert isinstance(
        runtime,
        LocalCompilerRuntime,
    )
    assert (
        runtime.provider_id
        == GNUCOBOL_PROVIDER_ID
    )
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_custom_local_runtime_has_local_compiler_capability() -> None:
    runtime = _create_custom_local_runtime()

    assert isinstance(
        runtime,
        LocalCompilerRuntime,
    )
    assert (
        runtime.provider_id
        == CUSTOM_COMPILER_PROVIDER_ID
    )
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_gnucobol_compilation_has_local_result_capability() -> None:
    compilation = GnuCobolCompilation(
        process_result=_create_process_result(),
    )

    assert isinstance(
        compilation,
        LocalCompilationResult,
    )
    assert compilation.succeeded is True


def test_custom_local_compilation_has_local_result_capability() -> None:
    compilation = CustomLocalCompilation(
        process_result=_create_process_result(),
        success_return_codes=(
            0,
        ),
    )

    assert isinstance(
        compilation,
        LocalCompilationResult,
    )
    assert compilation.succeeded is True


class IdentityOnlyRuntime:
    """Runtime with activation identity but no compile capability."""

    @property
    def provider_id(
        self,
    ) -> str:
        """Return a provider identifier."""

        return "example.remote"

    @property
    def profile_id(
        self,
    ):
        """Return a profile identifier."""

        return uuid4()

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return a remote execution kind."""

        return CompilerExecutionKind.REMOTE_JOB


def test_identity_only_runtime_lacks_local_compiler_capability() -> None:
    runtime = IdentityOnlyRuntime()

    assert not isinstance(
        runtime,
        LocalCompilerRuntime,
    )