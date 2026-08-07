"""Maps COBOL data names to their internal GnuCOBOL-generated C symbols.

GnuCOBOL doesn't expose COBOL data items as GDB-lookupable symbols by
their COBOL name -- `WS-A` compiles to a raw byte buffer (`b_17`) with
no debug-visible link back to the name "WS-A" itself; `-data-evaluate-
expression WS-A` (or any mangled guess) fails with "No symbol in
current context." The COBOL name only survives in the generated C as
a `/* WS-A */` comment on the buffer's own declaration line, in the
`<program>.c.l.h` header GnuCOBOL emits alongside the compiled binary
when built with `-g`. This module parses those comments to recover the
mapping -- verified against real `cobc`-generated headers, not a
guessed format.

Editor §DebuggerLogic-1/3: a top-level elementary item gets its own
dedicated `cob_u8_t` buffer, matched by `_BUFFER_DECLARATION_PATTERN`
below -- but an elementary item *nested inside a group* (or a
REDEFINES view of another item) instead gets a `cob_field` struct
literal pointing into the group's own buffer, optionally with a
constant byte offset (`{size, buffer + offset, &attr}`), matched by
`_FIELD_DECLARATION_PATTERN`. Verified against real `cobc 3.2.0`
output across one, two, and three levels of group nesting: every
level's offset is always flattened back to the single outermost
buffer directly (never through an intermediate group's own symbol),
so matching this one pattern recovers a nested item regardless of how
deeply it's nested. This only recovers items GnuCOBOL actually chose
to give a `cob_field` for in the first place -- confirmed by real
compiles, a plain alphanumeric (`PIC X`) item nested in a group gets
neither a buffer nor a `cob_field` at all, and an OCCURS table
element's per-occurrence offset is computed inline at every use site
in the generated C with no static symbol whatsoever, for any usage
type -- both are a genuine absence in `cobc`'s own debug output, not
a gap in this parser, and there is nothing here to recover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_BUFFER_DECLARATION_PATTERN = re.compile(
    r"static\s+cob_u8_t\s+(?P<variable>b_\d+)"
    r"\s*\[\s*(?P<size>\d+)\s*\]"
    r"[^/\n]*/\*\s*(?P<name>[^*]+?)\s*\*/",
)

_FIELD_DECLARATION_PATTERN = re.compile(
    r"static\s+cob_field\s+\w+\s*=\s*\{\s*"
    r"(?P<size>\d+)\s*,\s*"
    r"(?P<base>b_\d+)"
    r"(?:\s*\+\s*(?P<offset>\d+))?"
    r"\s*,\s*&\w+\s*\}"
    r"[^/\n]*/\*\s*(?P<name>[^*]+?)\s*\*/",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedFieldSymbol:
    """Where one COBOL data item's raw bytes live in a compiled program."""

    cobol_name: str
    buffer_variable: str
    byte_length: int


def parse_generated_symbol_map(
    *header_texts: str,
) -> dict[str, GeneratedFieldSymbol]:
    """Build a COBOL-name -> `GeneratedFieldSymbol` map from generated C headers.

    Pass the contents of a compiled program's `<name>.c.l.h` (its
    program-local storage) and, if relevant, `<name>.c.h` (global
    storage) -- when the same name appears in more than one, whichever
    text is passed *last* wins, so pass the most specific/local header
    last if both might declare overlapping names.
    """

    symbols: dict[
        str,
        GeneratedFieldSymbol,
    ] = {}

    for header_text in header_texts:
        for match in (
            _BUFFER_DECLARATION_PATTERN.finditer(
                header_text,
            )
        ):
            cobol_name = (
                match.group(
                    "name",
                )
                .strip()
                .upper()
            )

            if not cobol_name:
                continue

            symbols[cobol_name] = (
                GeneratedFieldSymbol(
                    cobol_name=cobol_name,
                    buffer_variable=match.group(
                        "variable",
                    ),
                    byte_length=int(
                        match.group(
                            "size",
                        ),
                    ),
                )
            )

        for match in (
            _FIELD_DECLARATION_PATTERN.finditer(
                header_text,
            )
        ):
            cobol_name = (
                match.group(
                    "name",
                )
                .strip()
                .upper()
            )

            if not cobol_name:
                continue

            base = match.group(
                "base",
            )
            offset = match.group(
                "offset",
            )
            # GDB's own expression evaluator understands this exact
            # pointer-arithmetic shape (`buffer+N`), matching how
            # `cobc`'s generated C itself computes the field's base
            # address -- passed straight through as the address
            # argument to a later `-data-read-memory-bytes` command,
            # no separate offset field needed on this dataclass. No
            # space around `+`: MI commands are whitespace-delimited,
            # so a space here would split this into two arguments.
            buffer_expression = (
                base
                if offset is None
                else f"{base}+{offset}"
            )

            symbols[cobol_name] = (
                GeneratedFieldSymbol(
                    cobol_name=cobol_name,
                    buffer_variable=buffer_expression,
                    byte_length=int(
                        match.group(
                            "size",
                        ),
                    ),
                )
            )

    return symbols
