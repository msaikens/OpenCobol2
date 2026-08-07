"""Built-in COBOL snippet skeletons with simple tab-stop placeholders.

Scoped to a fixed, hand-picked set of common constructs -- deliberately
not a user-authoring feature, the same "hand-picked, not exhaustive"
policy this package already uses for reserved-word documentation
(`hover._RESERVED_WORD_DOCS`) and intrinsic-function signatures
(`signature_help._INTRINSIC_FUNCTION_SIGNATURES`).

Placeholder syntax is intentionally minimal: `${n:default text}` or
`${n}` for an empty stop, numbered in the order they should be visited.
No nested placeholders, no transformations, no repeated references to
the same stop index -- the simplest tab-stop model that supports the
built-in set below.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True, kw_only=True)
class Snippet:
    """One built-in COBOL skeleton, keyed by its completion trigger word."""

    trigger: str
    label: str
    body: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SnippetSegment:
    """One piece of a parsed snippet body: literal text, or a tab stop."""

    text: str
    is_placeholder: bool = False
    stop_index: int = 0


_PLACEHOLDER_PATTERN = re.compile(r"\$\{(\d+)(?::([^}]*))?\}")


def parse_snippet_body(body: str) -> tuple[SnippetSegment, ...]:
    """Split a snippet body into literal-text and placeholder segments.

    Never raises: `body` is always one of this module's own `Snippet`
    entries in practice, but even arbitrary text just yields it back as
    one literal segment (no placeholder syntax means no matches).
    """

    segments: list[SnippetSegment] = []
    last_end = 0

    for match in _PLACEHOLDER_PATTERN.finditer(body):
        if match.start() > last_end:
            segments.append(
                SnippetSegment(
                    text=body[last_end : match.start()],
                )
            )

        segments.append(
            SnippetSegment(
                text=match.group(2) or "",
                is_placeholder=True,
                stop_index=int(match.group(1)),
            )
        )
        last_end = match.end()

    if last_end < len(body):
        segments.append(
            SnippetSegment(
                text=body[last_end:],
            )
        )

    return tuple(segments)


BUILTIN_SNIPPETS: tuple[Snippet, ...] = (
    Snippet(
        trigger="program",
        label="Program skeleton",
        body=(
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. ${1:PROGRAM-NAME}.\n"
            "DATA DIVISION.\n"
            "WORKING-STORAGE SECTION.\n"
            "PROCEDURE DIVISION.\n"
            "    ${2}\n"
            "    STOP RUN.\n"
        ),
    ),
    Snippet(
        trigger="if",
        label="IF / END-IF",
        body="IF ${1:condition}\n    ${2}\nEND-IF",
    ),
    Snippet(
        trigger="perform-until",
        label="PERFORM UNTIL",
        body="PERFORM UNTIL ${1:condition}\n    ${2}\nEND-PERFORM",
    ),
    Snippet(
        trigger="evaluate",
        label="EVALUATE",
        body=(
            "EVALUATE ${1:subject}\n"
            "    WHEN ${2:value}\n"
            "        ${3}\n"
            "    WHEN OTHER\n"
            "        ${4}\n"
            "END-EVALUATE"
        ),
    ),
    Snippet(
        trigger="paragraph",
        label="Paragraph",
        body="${1:PARAGRAPH-NAME}.\n    ${2}",
    ),
    Snippet(
        trigger="display",
        label="DISPLAY",
        body='DISPLAY ${1:"text"}',
    ),
)
