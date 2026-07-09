"""Domain models for COBOL compiler invocation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class CompilerOutputKind(StrEnum):
    """Describes the artifact requested from a COBOL compiler."""

    EXECUTABLE = "executable"
    MODULE = "module"


class CobolSourceFormat(StrEnum):
    """Describes the physical source format of a COBOL document."""

    FIXED = "fixed"
    FREE = "free"


class CompilerExecutionStatus(StrEnum):
    """Describes how a compiler process invocation ended."""

    COMPLETED = "completed"
    FAILED_TO_START = "failed-to-start"
    TIMED_OUT = "timed-out"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompileRequest:
    """Describes one COBOL compilation request."""

    source_path: Path
    output_path: Path
    output_kind: CompilerOutputKind = CompilerOutputKind.EXECUTABLE
    working_directory: Path | None = None
    standard: str | None = None
    source_format: CobolSourceFormat | None = None
    copy_directories: tuple[Path, ...] = ()
    library_directories: tuple[Path, ...] = ()
    libraries: tuple[str, ...] = ()
    additional_inputs: tuple[Path, ...] = ()
    additional_arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize request values into stable domain types."""
        object.__setattr__(
            self,
            "source_path",
            Path(self.source_path),
        )
        object.__setattr__(
            self,
            "output_path",
            Path(self.output_path),
        )

        if self.working_directory is not None:
            object.__setattr__(
                self,
                "working_directory",
                Path(self.working_directory),
            )

        object.__setattr__(
            self,
            "copy_directories",
            tuple(Path(path) for path in self.copy_directories),
        )
        object.__setattr__(
            self,
            "library_directories",
            tuple(Path(path) for path in self.library_directories),
        )
        object.__setattr__(
            self,
            "additional_inputs",
            tuple(Path(path) for path in self.additional_inputs),
        )
        object.__setattr__(
            self,
            "libraries",
            tuple(
                library.strip()
                for library in self.libraries
                if library.strip()
            ),
        )
        object.__setattr__(
            self,
            "additional_arguments",
            tuple(str(argument) for argument in self.additional_arguments),
        )

        if self.standard is not None:
            normalized_standard = self.standard.strip()

            object.__setattr__(
                self,
                "standard",
                normalized_standard or None,
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompileResult:
    """Describes the outcome of one compiler process invocation."""

    request: CompileRequest
    command: tuple[str, ...]
    status: CompilerExecutionStatus
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate compiler result invariants."""
        normalized_command = tuple(
            str(argument)
            for argument in self.command
        )

        if not normalized_command:
            raise ValueError("Compiler command must not be empty.")

        if self.elapsed_seconds < 0:
            raise ValueError(
                "Compiler elapsed time must not be negative."
            )

        if (
            self.status is CompilerExecutionStatus.COMPLETED
            and self.return_code is None
        ):
            raise ValueError(
                "A completed compiler process must have a return code."
            )

        if (
            self.status is not CompilerExecutionStatus.COMPLETED
            and self.return_code is not None
        ):
            raise ValueError(
                "A compiler process that did not complete must not "
                "have a return code."
            )

        object.__setattr__(
            self,
            "command",
            normalized_command,
        )

    @property
    def succeeded(self) -> bool:
        """Return whether the compiler completed successfully."""
        return (
            self.status is CompilerExecutionStatus.COMPLETED
            and self.return_code == 0
        )