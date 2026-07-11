"""Token domain models for lexed COBOL source."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TokenKind(StrEnum):
    """Describes the lexical category of one COBOL token."""

    IDENTIFIER = "identifier"
    RESERVED_WORD = "reserved-word"
    NUMERIC_LITERAL = "numeric-literal"
    ALPHANUMERIC_LITERAL = "alphanumeric-literal"
    COMMENT = "comment"
    PERIOD = "period"
    COMMA = "comma"
    SEMICOLON = "semicolon"
    LEFT_PARENTHESIS = "left-parenthesis"
    RIGHT_PARENTHESIS = "right-parenthesis"
    PLUS = "plus"
    MINUS = "minus"
    ASTERISK = "asterisk"
    DOUBLE_ASTERISK = "double-asterisk"
    SLASH = "slash"
    EQUALS = "equals"
    GREATER_THAN = "greater-than"
    LESS_THAN = "less-than"
    GREATER_THAN_OR_EQUAL = "greater-than-or-equal"
    LESS_THAN_OR_EQUAL = "less-than-or-equal"
    NOT_EQUAL = "not-equal"
    COLON = "colon"
    PSEUDO_TEXT_DELIMITER = "pseudo-text-delimiter"
    UNKNOWN = "unknown"
    END_OF_FILE = "end-of-file"


@dataclass(frozen=True, slots=True, kw_only=True)
class SourcePosition:
    """One 1-based line/column position in a COBOL source document."""

    line: int
    column: int

    def __post_init__(self) -> None:
        """Validate source position state."""

        if (
            not isinstance(
                self.line,
                int,
            )
            or isinstance(
                self.line,
                bool,
            )
        ):
            raise TypeError(
                "Source position line must be an integer."
            )

        if self.line <= 0:
            raise ValueError(
                "Source position line must be greater than zero."
            )

        if (
            not isinstance(
                self.column,
                int,
            )
            or isinstance(
                self.column,
                bool,
            )
        ):
            raise TypeError(
                "Source position column must be an integer."
            )

        if self.column <= 0:
            raise ValueError(
                "Source position column must be greater than zero."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSpan:
    """A half-open range between two source positions."""

    start: SourcePosition
    end: SourcePosition

    def __post_init__(self) -> None:
        """Validate source span state."""

        if not isinstance(
            self.start,
            SourcePosition,
        ):
            raise TypeError(
                "Source span start must be SourcePosition."
            )

        if not isinstance(
            self.end,
            SourcePosition,
        ):
            raise TypeError(
                "Source span end must be SourcePosition."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    """One lexed COBOL token."""

    kind: TokenKind
    text: str
    span: SourceSpan
    value: str | int | float | None = None

    def __post_init__(self) -> None:
        """Validate token state."""

        if not isinstance(
            self.kind,
            TokenKind,
        ):
            raise TypeError(
                "Token kind must be TokenKind."
            )

        if not isinstance(
            self.text,
            str,
        ):
            raise TypeError(
                "Token text must be a string."
            )

        if not isinstance(
            self.span,
            SourceSpan,
        ):
            raise TypeError(
                "Token span must be SourceSpan."
            )

        if self.value is not None and not isinstance(
            self.value,
            (
                str,
                int,
                float,
            ),
        ):
            raise TypeError(
                "Token value must be a string, number, or None."
            )

    @property
    def is_trivia(
        self,
    ) -> bool:
        """Return whether this token is non-code trivia (a comment)."""

        return self.kind is TokenKind.COMMENT
