"""Compiler diagnostic domain models.

Provides the severity enumeration and the frozen dataclass used to
represent one structured diagnostic (error, warning, or note) produced
by parsing a compiler's raw output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DiagnosticSeverity(StrEnum):
    """Describes the severity of a compiler diagnostic.

    :cvar ERROR: The diagnostic reports a compilation error.
    :cvar WARNING: The diagnostic reports a non-fatal warning.
    :cvar NOTE: The diagnostic reports an informational note.
    """

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerDiagnostic:
    """Describes one structured compiler diagnostic.

    :ivar severity: How severe the diagnostic is.
    :ivar message: The human-readable diagnostic text, stripped of
        surrounding whitespace.
    :ivar source_path: The source file the diagnostic refers to, if
        known.
    :ivar line: The 1-based source line the diagnostic refers to, if
        known.
    :ivar column: The 1-based source column the diagnostic refers to,
        if known. Never set without `line`.
    :ivar code: The compiler-specific diagnostic code, if any, with
        blank values normalized to None.
    :ivar raw_text: The original, unparsed diagnostic line the
        compiler emitted.
    """

    severity: DiagnosticSeverity
    message: str
    source_path: Path | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None
    raw_text: str = ""

    def __post_init__(self) -> None:
        """Normalize values and validate diagnostic invariants.

        :returns: None. `message` is stripped, `code` is normalized to
            None when blank, and `source_path` is coerced to a
            :class:`~pathlib.Path`, all in place on the frozen instance.
        :raises ValueError: If `message` is empty after stripping, if
            `line` or `column` is not greater than zero, or if `column`
            is set without a `line`.
        """
        normalized_message = self.message.strip()

        if not normalized_message:
            raise ValueError(
                "Compiler diagnostic message must not be empty."
            )

        if self.line is not None and self.line <= 0:
            raise ValueError(
                "Compiler diagnostic line must be greater than zero."
            )

        if self.column is not None and self.column <= 0:
            raise ValueError(
                "Compiler diagnostic column must be greater than zero."
            )

        if self.column is not None and self.line is None:
            raise ValueError(
                "Compiler diagnostic column requires a line number."
            )

        normalized_code: str | None = None

        if self.code is not None:
            stripped_code = self.code.strip()

            if stripped_code:
                normalized_code = stripped_code

        object.__setattr__(
            self,
            "message",
            normalized_message,
        )
        object.__setattr__(
            self,
            "code",
            normalized_code,
        )

        if self.source_path is not None:
            object.__setattr__(
                self,
                "source_path",
                Path(self.source_path),
            )

    @property
    def has_location(self) -> bool:
        """Return whether the diagnostic identifies a source line.

        :returns: True if both `source_path` and `line` are set,
            False otherwise.
        """
        return (
            self.source_path is not None
            and self.line is not None
        )