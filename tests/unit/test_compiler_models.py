"""Unit tests for compiler domain models."""

from pathlib import Path

import pytest

from opencobol2.compiler import (
    CobolSourceFormat,
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
    CompilerOutputKind,
)


def test_compile_request_normalizes_values() -> None:
    request = CompileRequest(
        source_path="program.cob",
        output_path="bin/program",
        output_kind=CompilerOutputKind.MODULE,
        working_directory=".",
        standard="  cobol2014  ",
        source_format=CobolSourceFormat.FREE,
        copy_directories=[
            "copy",
            "vendor/copy",
        ],
        library_directories=[
            "lib",
        ],
        libraries=[
            "  sqlite3  ",
            "",
            "cob",
        ],
        additional_inputs=[
            "support.o",
        ],
        additional_arguments=[
            "-Wall",
        ],
    )

    assert request.source_path == Path("program.cob")
    assert request.output_path == Path("bin/program")
    assert request.working_directory == Path(".")
    assert request.standard == "cobol2014"

    assert request.copy_directories == (
        Path("copy"),
        Path("vendor/copy"),
    )
    assert request.library_directories == (
        Path("lib"),
    )
    assert request.libraries == (
        "sqlite3",
        "cob",
    )
    assert request.additional_inputs == (
        Path("support.o"),
    )
    assert request.additional_arguments == (
        "-Wall",
    )


def test_compile_request_rejects_non_string_library() -> None:
    # Editor §CompilerAbstraction-6: a non-string `libraries` entry
    # used to crash with a bare `AttributeError` from `.strip()`
    # instead of a clear, typed validation error.
    with pytest.raises(
        TypeError,
        match="Compiler request libraries must be strings",
    ):
        CompileRequest(
            source_path="program.cob",
            output_path="program",
            libraries=[
                123,
            ],
        )


def test_compile_request_debug_symbols_defaults_to_false() -> None:
    request = CompileRequest(
        source_path="program.cob",
        output_path="program",
    )

    assert request.debug_symbols is False


def test_completed_zero_return_code_is_successful() -> None:
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("hello"),
    )

    result = CompileResult(
        request=request,
        command=(
            "cobc",
            "-x",
            "hello.cob",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=0,
        elapsed_seconds=0.25,
    )

    assert result.succeeded is True


def test_completed_nonzero_return_code_is_not_successful() -> None:
    request = CompileRequest(
        source_path=Path("broken.cob"),
        output_path=Path("broken"),
    )

    result = CompileResult(
        request=request,
        command=(
            "cobc",
            "-x",
            "broken.cob",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=1,
        stderr="syntax error",
    )

    assert result.succeeded is False


def test_completed_process_requires_return_code() -> None:
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("hello"),
    )

    with pytest.raises(
        ValueError,
        match="must have a return code",
    ):
        CompileResult(
            request=request,
            command=(
                "cobc",
                "hello.cob",
            ),
            status=CompilerExecutionStatus.COMPLETED,
        )


def test_failed_process_must_not_have_return_code() -> None:
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("hello"),
    )

    with pytest.raises(
        ValueError,
        match="must not have a return code",
    ):
        CompileResult(
            request=request,
            command=(
                "cobc",
                "hello.cob",
            ),
            status=CompilerExecutionStatus.FAILED_TO_START,
            return_code=127,
        )


def test_compiler_command_must_not_be_empty() -> None:
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("hello"),
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        CompileResult(
            request=request,
            command=(),
            status=CompilerExecutionStatus.FAILED_TO_START,
        )


def test_elapsed_time_must_not_be_negative() -> None:
    request = CompileRequest(
        source_path=Path("hello.cob"),
        output_path=Path("hello"),
    )

    with pytest.raises(
        ValueError,
        match="must not be negative",
    ):
        CompileResult(
            request=request,
            command=(
                "cobc",
                "hello.cob",
            ),
            status=CompilerExecutionStatus.TIMED_OUT,
            elapsed_seconds=-1.0,
        )