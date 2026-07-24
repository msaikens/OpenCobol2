"""Reconstructing readable source text from a run of real lexer tokens."""

from __future__ import annotations

from collections.abc import Iterable

from opencobol2.language.tokens import Token


def render_clause_tokens(
    tokens: Iterable[Token],
) -> str:
    """Join clause tokens back into readable text, e.g. `PIC 9(5)V99`.

    Uses each token's real span to tell whether it was directly adjacent
    to the previous one in the source (no space) or separated by
    whitespace (one space) -- exactly reconstructing the original
    spacing, rather than guessing from punctuation.
    """

    rendered = ""
    previous_token = None

    for token in tokens:
        if previous_token is not None and (
            token.span.start.line
            == previous_token.span.end.line
            and token.span.start.column
            == previous_token.span.end.column
        ):
            rendered += token.text
        elif rendered:
            rendered += f" {token.text}"
        else:
            rendered = token.text

        previous_token = token

    return rendered
