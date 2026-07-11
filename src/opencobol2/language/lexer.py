"""A tokenizer for COBOL source text (fixed and free format)."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.models import (
    CobolSourceFormat,
)
from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)
from opencobol2.language.diagnostics import (
    LexDiagnostic,
)
from opencobol2.language.keywords import (
    is_reserved_word,
)
from opencobol2.language.tokens import (
    SourcePosition,
    SourceSpan,
    Token,
    TokenKind,
)


FIXED_FORMAT_SEQUENCE_AREA_WIDTH = 6
FIXED_FORMAT_INDICATOR_COLUMN = 7
FIXED_FORMAT_CONTENT_START_COLUMN = 8
FIXED_FORMAT_CONTENT_END_COLUMN = 72

_RECOGNIZED_INDICATORS = (
    " ",
    "",
    "*",
    "/",
    "-",
    "D",
    "d",
)

_TWO_CHARACTER_OPERATORS: dict[str, TokenKind] = {
    "**": TokenKind.DOUBLE_ASTERISK,
    ">=": TokenKind.GREATER_THAN_OR_EQUAL,
    "<=": TokenKind.LESS_THAN_OR_EQUAL,
    "<>": TokenKind.NOT_EQUAL,
    "==": TokenKind.PSEUDO_TEXT_DELIMITER,
}

_ONE_CHARACTER_OPERATORS: dict[str, TokenKind] = {
    ".": TokenKind.PERIOD,
    ",": TokenKind.COMMA,
    ";": TokenKind.SEMICOLON,
    "(": TokenKind.LEFT_PARENTHESIS,
    ")": TokenKind.RIGHT_PARENTHESIS,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.ASTERISK,
    "/": TokenKind.SLASH,
    "=": TokenKind.EQUALS,
    ">": TokenKind.GREATER_THAN,
    "<": TokenKind.LESS_THAN,
    ":": TokenKind.COLON,
}


@dataclass(slots=True)
class LexResult:
    """Tokens and diagnostics produced by lexing one COBOL document."""

    tokens: tuple[Token, ...]
    diagnostics: tuple[LexDiagnostic, ...] = ()

    @property
    def has_errors(
        self,
    ) -> bool:
        """Return whether any diagnostic is an error."""

        return any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )


@dataclass(slots=True)
class _PreparedLine:
    """One physical source line, normalized for tokenization."""

    line_number: int
    content: str
    content_start_column: int
    is_comment: bool
    is_continuation: bool
    indicator: str


@dataclass(slots=True)
class _PendingLiteral:
    """State for an alphanumeric literal continued across source lines."""

    quote_character: str
    parts: list[str]
    raw_parts: list[str]
    start_position: SourcePosition


class CobolLexer:
    """Tokenizes COBOL source text into a flat token stream."""

    def __init__(
        self,
        source: str,
        *,
        source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
    ) -> None:
        """Initialize the lexer over one COBOL source document."""

        if not isinstance(
            source,
            str,
        ):
            raise TypeError(
                "Source must be a string."
            )

        if not isinstance(
            source_format,
            CobolSourceFormat,
        ):
            raise TypeError(
                "Source format must be CobolSourceFormat."
            )

        self._source = source
        self._source_format = source_format

    def tokenize(
        self,
    ) -> LexResult:
        """Tokenize the source document into tokens and diagnostics."""

        tokens: list[Token] = []
        diagnostics: list[LexDiagnostic] = []
        pending_literal: _PendingLiteral | None = None

        for prepared_line in _prepare_lines(
            self._source,
            self._source_format,
        ):
            if (
                self._source_format
                is CobolSourceFormat.FIXED
                and prepared_line.indicator
                not in _RECOGNIZED_INDICATORS
            ):
                diagnostics.append(
                    LexDiagnostic(
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            "Unrecognized indicator area "
                            f"character: {prepared_line.indicator!r}."
                        ),
                        position=SourcePosition(
                            line=prepared_line.line_number,
                            column=FIXED_FORMAT_INDICATOR_COLUMN,
                        ),
                    ),
                )

            if prepared_line.is_comment:
                if pending_literal is not None:
                    diagnostics.append(
                        _unterminated_literal_diagnostic(
                            pending_literal,
                        ),
                    )
                    tokens.append(
                        _finalize_pending_literal(
                            pending_literal,
                        ),
                    )
                    pending_literal = None

                comment_token = _build_comment_token(
                    prepared_line,
                )

                if comment_token is not None:
                    tokens.append(
                        comment_token,
                    )

                continue

            if (
                prepared_line.is_continuation
                and pending_literal is None
            ):
                diagnostics.append(
                    LexDiagnostic(
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            "Continuation line found without a "
                            "literal to continue."
                        ),
                        position=SourcePosition(
                            line=prepared_line.line_number,
                            column=(
                                prepared_line.content_start_column
                            ),
                        ),
                    ),
                )
            elif (
                not prepared_line.is_continuation
                and pending_literal is not None
            ):
                diagnostics.append(
                    _unterminated_literal_diagnostic(
                        pending_literal,
                    ),
                )
                tokens.append(
                    _finalize_pending_literal(
                        pending_literal,
                    ),
                )
                pending_literal = None

            pending_literal = _scan_line(
                prepared_line,
                pending_literal=(
                    pending_literal
                    if prepared_line.is_continuation
                    else None
                ),
                tokens=tokens,
                diagnostics=diagnostics,
            )

        if pending_literal is not None:
            diagnostics.append(
                _unterminated_literal_diagnostic(
                    pending_literal,
                ),
            )
            tokens.append(
                _finalize_pending_literal(
                    pending_literal,
                ),
            )

        last_line = (
            self._source.count(
                "\n",
            )
            + 1
        )

        tokens.append(
            Token(
                kind=TokenKind.END_OF_FILE,
                text="",
                span=SourceSpan(
                    start=SourcePosition(
                        line=last_line,
                        column=1,
                    ),
                    end=SourcePosition(
                        line=last_line,
                        column=1,
                    ),
                ),
            ),
        )

        return LexResult(
            tokens=tuple(
                tokens,
            ),
            diagnostics=tuple(
                diagnostics,
            ),
        )


def tokenize_cobol_source(
    source: str,
    *,
    source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
) -> LexResult:
    """Tokenize one COBOL source document."""

    return CobolLexer(
        source,
        source_format=source_format,
    ).tokenize()


def _prepare_lines(
    source: str,
    source_format: CobolSourceFormat,
) -> list[_PreparedLine]:
    """Normalize raw source lines for the requested source format."""

    prepared_lines: list[_PreparedLine] = []

    for index, raw_line in enumerate(
        source.splitlines(),
        start=1,
    ):
        expanded_line = raw_line.expandtabs(
            8,
        )

        if source_format is CobolSourceFormat.FIXED:
            indicator = expanded_line[
                FIXED_FORMAT_SEQUENCE_AREA_WIDTH:
                FIXED_FORMAT_INDICATOR_COLUMN
            ]
            content = expanded_line[
                FIXED_FORMAT_CONTENT_START_COLUMN - 1:
                FIXED_FORMAT_CONTENT_END_COLUMN
            ]

            prepared_lines.append(
                _PreparedLine(
                    line_number=index,
                    content=content,
                    content_start_column=(
                        FIXED_FORMAT_CONTENT_START_COLUMN
                    ),
                    is_comment=indicator
                    in (
                        "*",
                        "/",
                    ),
                    is_continuation=indicator == "-",
                    indicator=indicator,
                ),
            )
        else:
            is_comment = (
                expanded_line.lstrip().startswith(
                    "*",
                )
            )

            prepared_lines.append(
                _PreparedLine(
                    line_number=index,
                    content=expanded_line,
                    content_start_column=1,
                    is_comment=is_comment,
                    is_continuation=False,
                    indicator="",
                ),
            )

    return prepared_lines


def _build_comment_token(
    prepared_line: _PreparedLine,
) -> Token | None:
    """Build a comment token for a whole-line comment, if non-blank."""

    text = prepared_line.content.rstrip()

    if not text.strip():
        return None

    return Token(
        kind=TokenKind.COMMENT,
        text=text,
        span=SourceSpan(
            start=SourcePosition(
                line=prepared_line.line_number,
                column=prepared_line.content_start_column,
            ),
            end=SourcePosition(
                line=prepared_line.line_number,
                column=(
                    prepared_line.content_start_column
                    + len(
                        text,
                    )
                ),
            ),
        ),
    )


def _unterminated_literal_diagnostic(
    pending_literal: _PendingLiteral,
) -> LexDiagnostic:
    """Build a diagnostic for a literal that was never terminated."""

    return LexDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        message="Alphanumeric literal is not terminated.",
        position=pending_literal.start_position,
    )


def _finalize_pending_literal(
    pending_literal: _PendingLiteral,
) -> Token:
    """Build a best-effort literal token from unterminated literal state."""

    return Token(
        kind=TokenKind.ALPHANUMERIC_LITERAL,
        text=(
            pending_literal.quote_character
            + "".join(
                pending_literal.raw_parts,
            )
        ),
        value="".join(
            pending_literal.parts,
        ),
        span=SourceSpan(
            start=pending_literal.start_position,
            end=pending_literal.start_position,
        ),
    )


def _scan_line(
    prepared_line: _PreparedLine,
    *,
    pending_literal: _PendingLiteral | None,
    tokens: list[Token],
    diagnostics: list[LexDiagnostic],
) -> _PendingLiteral | None:
    """Scan one prepared line's content, returning any still-open literal."""

    content = prepared_line.content
    line_number = prepared_line.line_number
    index = 0
    length = len(
        content,
    )

    if pending_literal is not None:
        stripped_index = _first_non_space_index(
            content,
        )

        if (
            stripped_index is None
            or content[stripped_index]
            != pending_literal.quote_character
        ):
            diagnostics.append(
                LexDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        "Continuation line does not begin with "
                        "the continued literal's quote character."
                    ),
                    position=SourcePosition(
                        line=line_number,
                        column=(
                            prepared_line.content_start_column
                        ),
                    ),
                ),
            )
            tokens.append(
                _finalize_pending_literal(
                    pending_literal,
                ),
            )
            pending_literal = None
        else:
            index = stripped_index + 1

    while index < length:
        column = (
            prepared_line.content_start_column
            + index
        )
        character = content[index]

        if (
            pending_literal is not None
            and character == pending_literal.quote_character
        ):
            if (
                index + 1 < length
                and content[index + 1]
                == pending_literal.quote_character
            ):
                pending_literal.parts.append(
                    pending_literal.quote_character,
                )
                pending_literal.raw_parts.append(
                    pending_literal.quote_character
                    * 2,
                )
                index += 2
                continue

            tokens.append(
                Token(
                    kind=TokenKind.ALPHANUMERIC_LITERAL,
                    text=(
                        pending_literal.quote_character
                        + "".join(
                            pending_literal.raw_parts,
                        )
                        + pending_literal.quote_character
                    ),
                    value="".join(
                        pending_literal.parts,
                    ),
                    span=SourceSpan(
                        start=pending_literal.start_position,
                        end=SourcePosition(
                            line=line_number,
                            column=column + 1,
                        ),
                    ),
                ),
            )
            pending_literal = None
            index += 1
            continue

        if pending_literal is not None:
            pending_literal.parts.append(
                character,
            )
            pending_literal.raw_parts.append(
                character,
            )
            index += 1
            continue

        if character.isspace():
            index += 1
            continue

        if (
            character == "*"
            and index + 1 < length
            and content[index + 1] == ">"
        ):
            comment_text = content[index:].rstrip()

            tokens.append(
                Token(
                    kind=TokenKind.COMMENT,
                    text=comment_text,
                    span=SourceSpan(
                        start=SourcePosition(
                            line=line_number,
                            column=column,
                        ),
                        end=SourcePosition(
                            line=line_number,
                            column=(
                                column
                                + len(
                                    comment_text,
                                )
                            ),
                        ),
                    ),
                ),
            )

            return None

        if character in (
            "'",
            '"',
        ):
            (
                literal_token,
                new_pending_literal,
                index,
            ) = _scan_alphanumeric_literal(
                content,
                index,
                line_number,
                prepared_line.content_start_column,
            )

            if literal_token is not None:
                tokens.append(
                    literal_token,
                )

            if new_pending_literal is not None:
                return new_pending_literal

            continue

        if character.isalnum():
            (
                word_token,
                index,
            ) = _scan_word(
                content,
                index,
                line_number,
                prepared_line.content_start_column,
            )
            tokens.append(
                word_token,
            )
            continue

        two_character = content[
            index:
            index + 2
        ]

        if two_character in _TWO_CHARACTER_OPERATORS:
            tokens.append(
                Token(
                    kind=_TWO_CHARACTER_OPERATORS[
                        two_character
                    ],
                    text=two_character,
                    span=SourceSpan(
                        start=SourcePosition(
                            line=line_number,
                            column=column,
                        ),
                        end=SourcePosition(
                            line=line_number,
                            column=column + 2,
                        ),
                    ),
                ),
            )
            index += 2
            continue

        if character in _ONE_CHARACTER_OPERATORS:
            tokens.append(
                Token(
                    kind=_ONE_CHARACTER_OPERATORS[
                        character
                    ],
                    text=character,
                    span=SourceSpan(
                        start=SourcePosition(
                            line=line_number,
                            column=column,
                        ),
                        end=SourcePosition(
                            line=line_number,
                            column=column + 1,
                        ),
                    ),
                ),
            )
            index += 1
            continue

        diagnostics.append(
            LexDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Unexpected character: {character!r}."
                ),
                position=SourcePosition(
                    line=line_number,
                    column=column,
                ),
            ),
        )
        tokens.append(
            Token(
                kind=TokenKind.UNKNOWN,
                text=character,
                span=SourceSpan(
                    start=SourcePosition(
                        line=line_number,
                        column=column,
                    ),
                    end=SourcePosition(
                        line=line_number,
                        column=column + 1,
                    ),
                ),
            ),
        )
        index += 1

    return pending_literal


def _first_non_space_index(
    content: str,
) -> int | None:
    """Return the index of the first non-space character, if any."""

    for index, character in enumerate(
        content,
    ):
        if not character.isspace():
            return index

    return None


def _scan_alphanumeric_literal(
    content: str,
    index: int,
    line_number: int,
    content_start_column: int,
) -> tuple[Token | None, _PendingLiteral | None, int]:
    """Scan a quote-delimited literal, possibly left open at end of line."""

    quote_character = content[index]
    start_column = content_start_column + index
    start_position = SourcePosition(
        line=line_number,
        column=start_column,
    )
    length = len(
        content,
    )
    cursor = index + 1
    parts: list[str] = []
    raw_parts: list[str] = []

    while cursor < length:
        character = content[cursor]

        if character == quote_character:
            if (
                cursor + 1 < length
                and content[cursor + 1] == quote_character
            ):
                parts.append(
                    quote_character,
                )
                raw_parts.append(
                    quote_character * 2,
                )
                cursor += 2
                continue

            value = "".join(
                parts,
            )
            token = Token(
                kind=TokenKind.ALPHANUMERIC_LITERAL,
                text=content[
                    index:
                    cursor + 1
                ],
                value=value,
                span=SourceSpan(
                    start=start_position,
                    end=SourcePosition(
                        line=line_number,
                        column=(
                            content_start_column
                            + cursor
                            + 1
                        ),
                    ),
                ),
            )

            return token, None, cursor + 1

        parts.append(
            character,
        )
        raw_parts.append(
            character,
        )
        cursor += 1

    pending_literal = _PendingLiteral(
        quote_character=quote_character,
        parts=parts,
        raw_parts=raw_parts,
        start_position=start_position,
    )

    return None, pending_literal, length


def _scan_word(
    content: str,
    index: int,
    line_number: int,
    content_start_column: int,
) -> tuple[Token, int]:
    """Scan a maximal identifier/reserved-word/numeral run."""

    length = len(
        content,
    )
    start_column = content_start_column + index
    cursor = index

    while cursor < length:
        character = content[cursor]

        if character.isalnum():
            cursor += 1
            continue

        if (
            character == "-"
            and cursor + 1 < length
            and content[cursor + 1].isalnum()
        ):
            cursor += 1
            continue

        break

    word = content[
        index:
        cursor
    ]
    end_column = content_start_column + cursor
    span = SourceSpan(
        start=SourcePosition(
            line=line_number,
            column=start_column,
        ),
        end=SourcePosition(
            line=line_number,
            column=end_column,
        ),
    )

    if word.isdigit():
        if (
            cursor + 1 < length
            and content[cursor] == "."
            and content[cursor + 1].isdigit()
        ):
            fraction_start = cursor + 1
            fraction_end = fraction_start

            while (
                fraction_end < length
                and content[fraction_end].isdigit()
            ):
                fraction_end += 1

            full_text = content[
                index:
                fraction_end
            ]
            span = SourceSpan(
                start=span.start,
                end=SourcePosition(
                    line=line_number,
                    column=(
                        content_start_column
                        + fraction_end
                    ),
                ),
            )

            return (
                Token(
                    kind=TokenKind.NUMERIC_LITERAL,
                    text=full_text,
                    value=float(
                        full_text,
                    ),
                    span=span,
                ),
                fraction_end,
            )

        return (
            Token(
                kind=TokenKind.NUMERIC_LITERAL,
                text=word,
                value=int(
                    word,
                ),
                span=span,
            ),
            cursor,
        )

    kind = (
        TokenKind.RESERVED_WORD
        if is_reserved_word(
            word,
        )
        else TokenKind.IDENTIFIER
    )

    return (
        Token(
            kind=kind,
            text=word,
            span=span,
        ),
        cursor,
    )
