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
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_BUFFER_DECLARATION_PATTERN = re.compile(
    r"static\s+cob_u8_t\s+(?P<variable>b_\d+)"
    r"\s*\[\s*(?P<size>\d+)\s*\]"
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

    return symbols
