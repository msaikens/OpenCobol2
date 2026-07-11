"""Diagnostic domain models for COBOL language services."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)
from opencobol2.language.tokens import (
    SourcePosition,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class LexDiagnostic:
    """Describes one issue found while lexing COBOL source."""

    severity: DiagnosticSeverity
    message: str
    position: SourcePosition

    def __post_init__(self) -> None:
        """Normalize and validate lexer diagnostic state."""

        if not isinstance(
            self.severity,
            DiagnosticSeverity,
        ):
            raise TypeError(
                "Lex diagnostic severity must be DiagnosticSeverity."
            )

        normalized_message = self.message.strip()

        if not normalized_message:
            raise ValueError(
                "Lex diagnostic message must not be empty."
            )

        if not isinstance(
            self.position,
            SourcePosition,
        ):
            raise TypeError(
                "Lex diagnostic position must be SourcePosition."
            )

        object.__setattr__(
            self,
            "message",
            normalized_message,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseDiagnostic:
    """Describes one issue found while parsing COBOL source."""

    severity: DiagnosticSeverity
    message: str
    position: SourcePosition

    def __post_init__(self) -> None:
        """Normalize and validate parser diagnostic state."""

        if not isinstance(
            self.severity,
            DiagnosticSeverity,
        ):
            raise TypeError(
                "Parse diagnostic severity must be DiagnosticSeverity."
            )

        normalized_message = self.message.strip()

        if not normalized_message:
            raise ValueError(
                "Parse diagnostic message must not be empty."
            )

        if not isinstance(
            self.position,
            SourcePosition,
        ):
            raise TypeError(
                "Parse diagnostic position must be SourcePosition."
            )

        object.__setattr__(
            self,
            "message",
            normalized_message,
        )
