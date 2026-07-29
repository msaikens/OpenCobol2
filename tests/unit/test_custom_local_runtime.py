"""Unit tests for custom local COBOL compiler runtimes."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

import opencobol2.compiler.runtimes.custom_local as custom_local_runtime
from opencobol2.compiler import (
    CobolSourceFormat,
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
    CompilerOutputKind,
    CustomLocalCompilation,
)
from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    CompilerExecutionKind,
    CompilerProfile,
)
from opencobol2.compiler.runtimes import (
    CustomLocalCompilerRuntime,
    CustomLocalCompilerRuntimeFactory,
    build_custom_local_compiler_command,
)


def _create_profile(
    *,
    configuration=None,
    environment_overrides=None,
) -> CompilerProfile:
    """Create a configured custom local compiler profile."""

    return CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Example COBOL",
        configuration={
            "executable_path": "compiler.exe",
            **(
                {}
                if configuration is None
                else configuration
            ),
        },
        environment_overrides=(
            {}
            if environment_overrides is None
            else environment_overrides
        ),
    )


def _create_request() -> CompileRequest:
    """Create a representative local compilation request."""

    return CompileRequest(
        source_path=Path(
            "src/program.cob",
        ),
        output_path=Path(
            "build/program.exe",
        ),
        output_kind=CompilerOutputKind.EXECUTABLE,
    )


def test_factory_creates_custom_local_runtime() -> None:
    profile = _create_profile()

    factory = CustomLocalCompilerRuntimeFactory()

    runtime = factory.create_runtime(
        profile,
    )

    assert isinstance(
        runtime,
        CustomLocalCompilerRuntime,
    )
    assert runtime.profile_id == profile.profile_id
    assert runtime.display_name == "Example COBOL"
    assert (
        runtime.provider_id
        == CUSTOM_COMPILER_PROVIDER_ID
    )
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_factory_materializes_provider_defaults() -> None:
    profile = _create_profile()

    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            profile,
        )
    )

    assert runtime.configuration["compile_arguments"] == (
        "{source}",
        "-o",
        "{output}",
    )
    assert runtime.configuration["diagnostic_format"] == "gcc"
    assert runtime.configuration["success_return_codes"] == (
        0,
    )


def test_default_command_uses_source_and_output_templates() -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(),
        )
    )

    command = build_custom_local_compiler_command(
        runtime.configuration,
        _create_request(),
    )

    assert command == (
        "compiler.exe",
        "src\\program.cob",
        "-o",
        "build\\program.exe",
    )


def test_command_builds_configured_argument_groups() -> None:
    profile = _create_profile(
        configuration={
            "compile_arguments": (
                "/compile",
                "{source}",
                "/output:{output}",
            ),
            "executable_output_arguments": (
                "/exe",
            ),
            "module_output_arguments": (
                "/module",
            ),
            "fixed_format_arguments": (
                "/fixed",
            ),
            "free_format_arguments": (
                "/free",
            ),
            "standard_argument_template": (
                "/standard:{standard}"
            ),
            "copy_directory_argument_template": (
                "/copy:{directory}"
            ),
            "library_directory_argument_template": (
                "/libpath:{directory}"
            ),
            "library_argument_template": (
                "/library:{library}"
            ),
        },
    )

    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            profile,
        )
    )

    request = CompileRequest(
        source_path=Path(
            "program.cob",
        ),
        output_path=Path(
            "program.exe",
        ),
        output_kind=CompilerOutputKind.EXECUTABLE,
        standard="cobol2014",
        source_format=CobolSourceFormat.FIXED,
        copy_directories=(
            Path(
                "copy one",
            ),
        ),
        library_directories=(
            Path(
                "library path",
            ),
        ),
        libraries=(
            "runtime",
        ),
        additional_inputs=(
            Path(
                "helper.obj",
            ),
        ),
        additional_arguments=(
            "/debug",
        ),
    )

    command = build_custom_local_compiler_command(
        runtime.configuration,
        request,
    )

    assert command == (
        "compiler.exe",
        "/compile",
        "program.cob",
        "/output:program.exe",
        "/exe",
        "/fixed",
        "/standard:cobol2014",
        "/copy:copy one",
        "/libpath:library path",
        "/library:runtime",
        "/debug",
        "helper.obj",
    )


def test_module_output_arguments_are_selected() -> None:
    profile = _create_profile(
        configuration={
            "executable_output_arguments": (
                "--executable",
            ),
            "module_output_arguments": (
                "--module",
            ),
        },
    )

    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            profile,
        )
    )

    request = CompileRequest(
        source_path=Path(
            "program.cob",
        ),
        output_path=Path(
            "program.mod",
        ),
        output_kind=CompilerOutputKind.MODULE,
    )

    command = build_custom_local_compiler_command(
        runtime.configuration,
        request,
    )

    assert "--module" in command
    assert "--executable" not in command


def test_unknown_template_placeholder_is_rejected_at_profile_validation() -> (
    None
):
    # Editor §CompilerAbstraction-7: this used to only fail later, at
    # actual compile-command-building time (via
    # `build_custom_local_compiler_command`) -- a broken template is
    # now caught as soon as the profile is validated (which
    # `create_runtime` already does, via
    # `resolve_compiler_profile_configuration`), before a runtime is
    # ever created from it.
    profile = _create_profile(
        configuration={
            "compile_arguments": (
                "{unknown}",
            ),
        },
    )

    with pytest.raises(
        ValueError,
        match="Unknown placeholder 'unknown'",
    ):
        CustomLocalCompilerRuntimeFactory().create_runtime(
            profile,
        )


def test_profile_environment_overrides_base_environment() -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(
                environment_overrides={
                    "COMPILER_HOME": "configured",
                },
            )
        )
    )

    environment = runtime.process_environment(
        {
            "PATH": "base-path",
            "COMPILER_HOME": "base",
        }
    )

    assert environment == {
        "PATH": "base-path",
        "COMPILER_HOME": "configured",
    }


def test_compile_invokes_local_process_with_built_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(),
        )
    )
    request = _create_request()

    captured_command = None
    captured_environment = None

    process_result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=0,
    )

    def fake_invoke_local_compiler_process(
        *,
        request,
        command,
        timeout_seconds,
        compiler_name,
        working_directory,
        environment,
    ):
        nonlocal captured_command
        nonlocal captured_environment

        captured_command = command
        captured_environment = environment

        return process_result

    monkeypatch.setattr(
        custom_local_runtime,
        "invoke_local_compiler_process",
        fake_invoke_local_compiler_process,
    )

    result = runtime.compile(
        request,
        base_environment={
            "PATH": "test-path",
        },
    )

    assert isinstance(
        result,
        CustomLocalCompilation,
    )
    assert captured_command == (
        "compiler.exe",
        "src\\program.cob",
        "-o",
        "build\\program.exe",
    )
    assert captured_environment == {
        "PATH": "test-path",
    }
    assert result.process_result is process_result


def test_compile_parses_configured_diagnostic_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(
                configuration={
                    "diagnostic_format": "msvc",
                },
            )
        )
    )
    request = _create_request()

    process_result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=1,
        stderr=(
            "program.cob(4,2): "
            "error CB1000: invalid statement"
        ),
    )

    def fake_invoke_local_compiler_process(
        **kwargs,
    ):
        return process_result

    monkeypatch.setattr(
        custom_local_runtime,
        "invoke_local_compiler_process",
        fake_invoke_local_compiler_process,
    )

    result = runtime.compile(
        request,
        base_environment={},
    )

    assert len(
        result.diagnostics,
    ) == 1
    assert result.diagnostics[0].code == "CB1000"


def test_configured_nonzero_success_return_code_is_honored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(
                configuration={
                    "success_return_codes": (
                        0,
                        4,
                    ),
                },
            )
        )
    )
    request = _create_request()

    process_result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=4,
    )

    def fake_invoke_local_compiler_process(
        **kwargs,
    ):
        return process_result

    monkeypatch.setattr(
        custom_local_runtime,
        "invoke_local_compiler_process",
        fake_invoke_local_compiler_process,
    )

    result = runtime.compile(
        request,
        base_environment={},
    )

    assert process_result.succeeded is False
    assert result.succeeded is True


def test_unconfigured_return_code_is_not_successful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = (
        CustomLocalCompilerRuntimeFactory()
        .create_runtime(
            _create_profile(
                configuration={
                    "success_return_codes": (
                        0,
                        4,
                    ),
                },
            )
        )
    )
    request = _create_request()

    process_result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=8,
    )

    def fake_invoke_local_compiler_process(
        **kwargs,
    ):
        return process_result

    monkeypatch.setattr(
        custom_local_runtime,
        "invoke_local_compiler_process",
        fake_invoke_local_compiler_process,
    )

    result = runtime.compile(
        request,
        base_environment={},
    )

    assert result.succeeded is False


def test_factory_rejects_other_provider_profile() -> None:
    profile = CompilerProfile(
        provider_id="example.other",
        display_name="Other Compiler",
    )

    factory = CustomLocalCompilerRuntimeFactory()

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        factory.create_runtime(
            profile,
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
    ],
)
def test_factory_timeout_must_be_positive(
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="timeout must be greater than zero",
    ):
        CustomLocalCompilerRuntimeFactory(
            timeout_seconds=timeout_seconds,
        )


def test_custom_compilation_requires_unique_success_codes() -> None:
    request = _create_request()
    process_result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=0,
    )

    with pytest.raises(
        ValueError,
        match="Successful return codes must be unique",
    ):
        CustomLocalCompilation(
            process_result=process_result,
            success_return_codes=(
                0,
                0,
            ),
        )