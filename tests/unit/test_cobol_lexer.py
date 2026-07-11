"""Unit tests for the COBOL lexer."""

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language import (
    LexDiagnostic,
    SourcePosition,
    SourceSpan,
    Token,
    TokenKind,
    is_reserved_word,
    tokenize_cobol_source,
)
from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)


def _code_tokens(
    source: str,
    *,
    source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
) -> list[Token]:
    """Tokenize and drop the trailing end-of-file sentinel token."""

    result = tokenize_cobol_source(
        source,
        source_format=source_format,
    )
    assert result.diagnostics == (), result.diagnostics

    return [
        token
        for token in result.tokens
        if token.kind is not TokenKind.END_OF_FILE
    ]


def _fixed(
    line: str,
) -> str:
    """Build one fixed-format source line with a blank indicator area."""

    return "      " + " " + line + "\n"


# --- SourcePosition / SourceSpan / Token models --------------------------


def test_source_position_rejects_non_positive_line() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        SourcePosition(line=0, column=1)


def test_source_position_rejects_non_positive_column() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        SourcePosition(line=1, column=0)


def test_token_rejects_invalid_value_type() -> None:
    span = SourceSpan(
        start=SourcePosition(line=1, column=1),
        end=SourcePosition(line=1, column=2),
    )

    with pytest.raises(
        TypeError,
        match="must be a string, number, or None",
    ):
        Token(
            kind=TokenKind.IDENTIFIER,
            text="X",
            span=span,
            value=[1, 2, 3],  # type: ignore[arg-type]
        )


def test_token_comment_is_trivia() -> None:
    span = SourceSpan(
        start=SourcePosition(line=1, column=1),
        end=SourcePosition(line=1, column=2),
    )
    comment = Token(kind=TokenKind.COMMENT, text="hi", span=span)
    identifier = Token(kind=TokenKind.IDENTIFIER, text="X", span=span)

    assert comment.is_trivia is True
    assert identifier.is_trivia is False


def test_lex_diagnostic_rejects_blank_message() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        LexDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="   ",
            position=SourcePosition(line=1, column=1),
        )


# --- reserved words -----------------------------------------------------


def test_is_reserved_word_matches_case_insensitively() -> None:
    assert is_reserved_word("division") is True
    assert is_reserved_word("DIVISION") is True
    assert is_reserved_word("Division") is True


def test_is_reserved_word_rejects_unknown_word() -> None:
    assert is_reserved_word("WS-COUNTER") is False


# --- identifiers / reserved words / numerals -----------------------------


def test_tokenizes_reserved_words_and_identifiers() -> None:
    tokens = _code_tokens(
        _fixed("PROGRAM-ID. HELLO."),
    )

    assert [
        (token.kind, token.text)
        for token in tokens
    ] == [
        (TokenKind.RESERVED_WORD, "PROGRAM-ID"),
        (TokenKind.PERIOD, "."),
        (TokenKind.IDENTIFIER, "HELLO"),
        (TokenKind.PERIOD, "."),
    ]


def test_hyphenated_identifier_is_one_token() -> None:
    tokens = _code_tokens(
        _fixed("MOVE A TO WS-TOTAL-AMOUNT."),
    )
    identifiers = [
        token.text
        for token in tokens
        if token.kind is TokenKind.IDENTIFIER
    ]

    assert "WS-TOTAL-AMOUNT" in identifiers


def test_minus_with_spacing_is_an_operator_not_part_of_identifier() -> None:
    tokens = _code_tokens(
        _fixed("COMPUTE X = A - B."),
    )
    kinds = [token.kind for token in tokens]

    assert TokenKind.MINUS in kinds
    texts = [token.text for token in tokens]
    assert "A" in texts
    assert "B" in texts


def test_identifier_starting_with_digit_lexes_as_one_identifier() -> None:
    tokens = _code_tokens(
        _fixed("MOVE 1 TO 9V99."),
    )
    identifier_texts = [
        token.text
        for token in tokens
        if token.kind is TokenKind.IDENTIFIER
    ]

    assert "9V99" in identifier_texts


def test_integer_numeric_literal() -> None:
    tokens = _code_tokens(
        _fixed("MOVE 12345 TO X."),
    )
    numeric = next(
        token
        for token in tokens
        if token.kind is TokenKind.NUMERIC_LITERAL
    )

    assert numeric.text == "12345"
    assert numeric.value == 12345


def test_decimal_numeric_literal() -> None:
    tokens = _code_tokens(
        _fixed("MOVE 123.45 TO X."),
    )
    numeric = next(
        token
        for token in tokens
        if token.kind is TokenKind.NUMERIC_LITERAL
    )

    assert numeric.text == "123.45"
    assert numeric.value == 123.45


def test_trailing_period_is_not_absorbed_into_numeral() -> None:
    tokens = _code_tokens(
        _fixed("MOVE 5 TO X."),
    )
    kinds_and_text = [
        (token.kind, token.text)
        for token in tokens
    ]

    assert (TokenKind.NUMERIC_LITERAL, "5") in kinds_and_text
    assert (TokenKind.PERIOD, ".") in kinds_and_text


# --- alphanumeric literals ------------------------------------------------


def test_single_quoted_literal() -> None:
    tokens = _code_tokens(
        _fixed("DISPLAY 'HELLO WORLD'."),
    )
    literal = next(
        token
        for token in tokens
        if token.kind is TokenKind.ALPHANUMERIC_LITERAL
    )

    assert literal.text == "'HELLO WORLD'"
    assert literal.value == "HELLO WORLD"


def test_double_quoted_literal() -> None:
    tokens = _code_tokens(
        _fixed('DISPLAY "HELLO WORLD".'),
    )
    literal = next(
        token
        for token in tokens
        if token.kind is TokenKind.ALPHANUMERIC_LITERAL
    )

    assert literal.text == '"HELLO WORLD"'
    assert literal.value == "HELLO WORLD"


def test_doubled_quote_escape_preserved_in_raw_text() -> None:
    tokens = _code_tokens(
        _fixed("DISPLAY 'JOHN''S'."),
    )
    literal = next(
        token
        for token in tokens
        if token.kind is TokenKind.ALPHANUMERIC_LITERAL
    )

    assert literal.text == "'JOHN''S'"
    assert literal.value == "JOHN'S"


def test_unterminated_literal_at_end_of_file_reports_error() -> None:
    result = tokenize_cobol_source(
        _fixed("DISPLAY 'UNCLOSED"),
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.has_errors is True
    assert any(
        "not terminated" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_literal_continuation_across_fixed_format_lines() -> None:
    source = (
        "       01  X VALUE 'THIS IS A VERY LONG MESS\n"
        "      -    'AGE THAT CONTINUES'.\n"
    )
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.diagnostics == ()
    literal = next(
        token
        for token in result.tokens
        if token.kind is TokenKind.ALPHANUMERIC_LITERAL
    )

    assert (
        literal.value
        == "THIS IS A VERY LONG MESSAGE THAT CONTINUES"
    )


def test_continuation_line_without_pending_literal_warns() -> None:
    source = (
        "       DISPLAY 'OK'.\n"
        "      -    IGNORED.\n"
    )
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert any(
        diagnostic.severity is DiagnosticSeverity.WARNING
        and "without a literal" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_malformed_continuation_reports_error() -> None:
    source = (
        "       01  X VALUE 'UNCLOSED LITERAL\n"
        "      -    NOMATCHINGQUOTE.\n"
    )
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.has_errors is True


# --- comments -------------------------------------------------------------


def test_fixed_format_whole_line_comment() -> None:
    source = "      * a comment line\n       DISPLAY 'HI'.\n"
    tokens = _code_tokens(
        source,
    )
    comment = next(
        token
        for token in tokens
        if token.kind is TokenKind.COMMENT
    )

    assert "a comment line" in comment.text


def test_blank_comment_line_emits_no_token() -> None:
    source = "      *\n       DISPLAY 'HI'.\n"
    tokens = _code_tokens(
        source,
    )

    assert all(
        token.kind is not TokenKind.COMMENT
        for token in tokens
    )


def test_free_format_line_starting_with_asterisk_is_comment() -> None:
    tokens = _code_tokens(
        "* whole line comment\nDISPLAY 'HI'.\n",
        source_format=CobolSourceFormat.FREE,
    )
    comment = next(
        token
        for token in tokens
        if token.kind is TokenKind.COMMENT
    )

    assert "whole line comment" in comment.text


def test_free_format_inline_comment_marker() -> None:
    tokens = _code_tokens(
        "DISPLAY 'HI' *> trailing note\n",
        source_format=CobolSourceFormat.FREE,
    )
    comment = next(
        token
        for token in tokens
        if token.kind is TokenKind.COMMENT
    )

    assert comment.text == "*> trailing note"


def test_inline_comment_marker_supported_in_fixed_format_too() -> None:
    tokens = _code_tokens(
        _fixed("DISPLAY 'HI' *> trailing note"),
    )
    comment = next(
        token
        for token in tokens
        if token.kind is TokenKind.COMMENT
    )

    assert comment.text == "*> trailing note"


# --- operators / punctuation ----------------------------------------------


@pytest.mark.parametrize(
    ("source_text", "expected_kind"),
    [
        ("**", TokenKind.DOUBLE_ASTERISK),
        (">=", TokenKind.GREATER_THAN_OR_EQUAL),
        ("<=", TokenKind.LESS_THAN_OR_EQUAL),
        ("<>", TokenKind.NOT_EQUAL),
        ("==", TokenKind.PSEUDO_TEXT_DELIMITER),
    ],
)
def test_two_character_operators(
    source_text: str,
    expected_kind: TokenKind,
) -> None:
    tokens = _code_tokens(
        _fixed(f"IF A {source_text} B DISPLAY 'X' END-IF."),
    )

    assert any(
        token.kind is expected_kind
        and token.text == source_text
        for token in tokens
    )


@pytest.mark.parametrize(
    ("character", "expected_kind"),
    [
        (",", TokenKind.COMMA),
        (";", TokenKind.SEMICOLON),
        ("(", TokenKind.LEFT_PARENTHESIS),
        (")", TokenKind.RIGHT_PARENTHESIS),
        ("+", TokenKind.PLUS),
        ("*", TokenKind.ASTERISK),
        ("/", TokenKind.SLASH),
        ("=", TokenKind.EQUALS),
        (">", TokenKind.GREATER_THAN),
        ("<", TokenKind.LESS_THAN),
        (":", TokenKind.COLON),
    ],
)
def test_one_character_operators(
    character: str,
    expected_kind: TokenKind,
) -> None:
    tokens = _code_tokens(
        _fixed(f"COMPUTE X = A {character} B."),
    )

    assert any(
        token.kind is expected_kind
        and token.text == character
        for token in tokens
    )


def test_unknown_character_reports_error() -> None:
    result = tokenize_cobol_source(
        _fixed("DISPLAY @."),
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.has_errors is True
    assert any(
        token.kind is TokenKind.UNKNOWN
        for token in result.tokens
    )


# --- indicator area handling (fixed format) -------------------------------


def test_unrecognized_indicator_character_warns() -> None:
    source = "      Q  DISPLAY 'HI'.\n"
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert any(
        diagnostic.severity is DiagnosticSeverity.WARNING
        and "Unrecognized indicator" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_debug_indicator_line_lexes_as_code() -> None:
    source = "      D    DISPLAY 'DEBUG'.\n"
    tokens = _code_tokens(
        source,
    )

    assert any(
        token.kind is TokenKind.RESERVED_WORD
        and token.text == "DISPLAY"
        for token in tokens
    )


def test_content_past_column_72_is_ignored() -> None:
    # "DISPLAY 'X'." occupies columns 8-19; pad to column 73 before
    # appending trailing text that must fall outside the content area.
    line = (
        "      "
        + " "
        + "DISPLAY 'X'."
        + " " * 53
        + "IGNOREDTEXT"
    )
    tokens = _code_tokens(
        line + "\n",
    )

    assert not any(
        "IGNOREDTEXT" in token.text
        for token in tokens
    )


# --- LexResult --------------------------------------------------------


def test_end_of_file_token_is_always_last() -> None:
    result = tokenize_cobol_source(
        _fixed("DISPLAY 'HI'."),
    )

    assert result.tokens[-1].kind is TokenKind.END_OF_FILE


def test_has_errors_false_when_only_warnings_present() -> None:
    source = "      Q  DISPLAY 'HI'.\n"
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.has_errors is False


def test_lexer_rejects_non_string_source() -> None:
    from opencobol2.language import CobolLexer

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        CobolLexer(123)  # type: ignore[arg-type]


def test_lexer_rejects_invalid_source_format() -> None:
    from opencobol2.language import CobolLexer

    with pytest.raises(
        TypeError,
        match="must be CobolSourceFormat",
    ):
        CobolLexer("DISPLAY 'HI'.", source_format="fixed")  # type: ignore[arg-type]


# --- realistic full-program smoke test -------------------------------------


def test_full_program_lexes_without_errors() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PAYROLL.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-HOURS       PIC 9(3)V99 VALUE 0.\n"
        "       01  WS-RATE        PIC 9(3)V99 VALUE 0.\n"
        "       01  WS-PAY         PIC 9(5)V99 VALUE 0.\n"
        "       01  WS-NAME        PIC X(20) VALUE SPACES.\n"
        "      * Compute gross pay for one employee\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE 40 TO WS-HOURS\n"
        "           MOVE 12.50 TO WS-RATE\n"
        "           COMPUTE WS-PAY = WS-HOURS * WS-RATE\n"
        "           IF WS-PAY > 999.99\n"
        "               DISPLAY 'PAY EXCEEDS LIMIT'\n"
        "           ELSE\n"
        "               DISPLAY 'PAY IS ' WS-PAY\n"
        "           END-IF\n"
        "           STOP RUN.\n"
    )
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.has_errors is False
    assert result.tokens[-1].kind is TokenKind.END_OF_FILE
