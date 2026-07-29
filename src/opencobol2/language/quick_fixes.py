"""Mechanical quick fixes for real, structurally-backed diagnostics.

Scoped to exactly one fix for now: inserting the missing closing quote
for an unterminated alphanumeric literal. Deliberately narrow --
inventing a fix for a diagnostic without an unambiguous, mechanically
correct repair (e.g. "Undefined data name" -- there's no way to know
what the user meant) would risk silently applying the wrong edit,
which is worse than offering no fix at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.models import CobolSourceFormat
from opencobol2.language.diagnostics import LexDiagnostic, ParseDiagnostic
from opencobol2.language.lexer import (
    FIXED_FORMAT_CONTENT_END_COLUMN,
    FIXED_FORMAT_CONTENT_START_COLUMN,
)


_UNTERMINATED_LITERAL_MESSAGE = (
    "Alphanumeric literal is not terminated."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class QuickFix:
    """A single, mechanically-applicable fix for one diagnostic."""

    title: str
    line: int
    column: int
    insert_text: str


def compute_quick_fix(
    source_text: str,
    diagnostic: LexDiagnostic | ParseDiagnostic,
    *,
    source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
) -> QuickFix | None:
    """Return a mechanical fix for a diagnostic, if one is known.

    Assumes an unterminated literal is a same-line mistake (by far the
    common case: a forgotten closing quote) rather than a genuine
    multi-line continuation -- the diagnostic's position is the
    literal's *opening* quote, not where it actually stopped scanning,
    so that's the only line this can safely reason about. The fix is
    always offered as a suggestion the user explicitly applies (and can
    undo in one step), not an automatic rewrite.
    """

    if diagnostic.message != _UNTERMINATED_LITERAL_MESSAGE:
        return None

    lines = source_text.splitlines()
    line_index = diagnostic.position.line - 1

    if not (
        0
        <= line_index
        < len(
            lines,
        )
    ):
        return None

    line_text = lines[line_index]
    quote_index = diagnostic.position.column - 1

    if not (
        0
        <= quote_index
        < len(
            line_text,
        )
    ):
        return None

    quote_character = line_text[quote_index]

    if quote_character not in (
        "'",
        '"',
    ):
        return None

    # FIXED-format source only ever lexes columns 8-72 as program text;
    # anything from column 73 onward is the sequence-number/reference
    # area and is never read. Appending at the raw line's physical end
    # can land past that boundary (a trailing-content-past-column-72
    # line), leaving the fix outside the window the lexer scans at all
    # -- applying it would appear to succeed while leaving the
    # diagnostic unchanged. Instead of the raw line length, the
    # insertion point is the end of the FIXED-format content area's
    # own *real* content -- trailing whitespace within that area
    # trimmed off -- which is always at or before column 72 by
    # construction.
    if source_format is CobolSourceFormat.FIXED:
        content_area = line_text[
            FIXED_FORMAT_CONTENT_START_COLUMN
            - 1 : FIXED_FORMAT_CONTENT_END_COLUMN
        ].rstrip()
        insert_column = (
            FIXED_FORMAT_CONTENT_START_COLUMN
            + len(
                content_area,
            )
        )

        if insert_column > FIXED_FORMAT_CONTENT_END_COLUMN + 1:
            # No room left in the content area to insert a closing
            # quote at all -- offering a fix that can't actually help
            # is worse than offering none.
            return None
    else:
        insert_column = (
            len(
                line_text,
            )
            + 1
        )

    return QuickFix(
        title=(
            f"Insert missing closing {quote_character}"
        ),
        line=diagnostic.position.line,
        column=insert_column,
        insert_text=quote_character,
    )
