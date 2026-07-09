"""Compiler diagnostic domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DiagnosticSeverity(StrEnum):
    """Describes the severity of a compiler diagnostic."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerDiagnostic:
    """Describes one structured compiler diagnostic."""

    severity: DiagnosticSeverity
    message: str
    source_path: Path | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None
    raw_text: str = ""

    def __post_init__(self) -> None:
        """Normalize values and validate diagnostic invariants."""
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
        """Return whether the diagnostic identifies a source line."""
        return (
            self.source_path is not None
            and self.line is not None
        )