"""Scans COBOL comment tokens for TODO/FIXME-style task markers.

Scoped to comments only (real lexer `COMMENT` tokens), not a blind
substring search over the raw source -- a tag inside a string literal or
identifier isn't a task marker.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.tokens import TokenKind


DEFAULT_TASK_TAGS = (
    "TODO",
    "FIXME",
    "HACK",
    "XXX",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskListEntry:
    """One task-tagged comment found in a COBOL source document."""

    tag: str
    line: int
    column: int
    text: str


def compute_task_list_entries(
    source_text: str,
    *,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
    tags: tuple[str, ...] = DEFAULT_TASK_TAGS,
) -> tuple[TaskListEntry, ...]:
    """Find every task-tagged comment in a COBOL source document.

    Never raises: lexing errors or genuinely invalid mid-edit source just
    yield no entries for this pass, rather than breaking the editor. At
    most one entry per comment token -- the first recognized tag wins.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
    except Exception:
        return ()

    pattern = re.compile(
        r"\b("
        + "|".join(
            re.escape(
                tag,
            )
            for tag in tags
        )
        + r")\b",
        re.IGNORECASE,
    )

    entries: list[TaskListEntry] = []

    for token in lex_result.tokens:
        if token.kind is not TokenKind.COMMENT:
            continue

        match = pattern.search(
            token.text,
        )

        if match is None:
            continue

        entries.append(
            TaskListEntry(
                tag=match.group(
                    1,
                ).upper(),
                line=token.span.start.line,
                column=(
                    token.span.start.column
                    + match.start()
                ),
                text=token.text.strip(),
            )
        )

    return tuple(
        entries,
    )
