"""Unit tests for reconstructing source text from real lexer tokens."""

from __future__ import annotations

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language import render_clause_tokens, tokenize_cobol_source


def _tokens_for_line(
    source_text: str,
    line: int,
) -> tuple:
    result = tokenize_cobol_source(
        source_text,
        source_format=CobolSourceFormat.FIXED,
    )

    return tuple(
        token
        for token in result.tokens
        if token.span.start.line == line
    )


def test_render_clause_tokens_reconstructs_adjacent_picture_spacing() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-PAY PIC 9(5)V99.\n"
    )
    tokens = _tokens_for_line(
        source,
        5,
    )

    rendered = render_clause_tokens(
        tokens,
    )

    assert "9(5)V99" in rendered
    assert "9(5) V99" not in rendered


def test_render_clause_tokens_preserves_a_real_gap() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-PAY PIC 9(5) VALUE 0.\n"
    )
    tokens = _tokens_for_line(
        source,
        5,
    )

    rendered = render_clause_tokens(
        tokens,
    )

    assert "VALUE 0" in rendered


def test_render_clause_tokens_of_empty_sequence_is_empty_string() -> None:
    assert render_clause_tokens(
        (),
    ) == ""
