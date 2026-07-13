"""A short, human-readable summary for hovering over an identifier.

Scoped to symbols the real symbol table already knows about -- data
items, paragraphs, and sections -- the same scope `find_definition`/
`find_references` use. Reserved-word documentation ("what does MOVE do")
is a separate, not-yet-built feature (Documentation lookup).
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.navigation import identifier_at
from opencobol2.language.parser import parse_cobol_tokens
from opencobol2.language.semantic import (
    analyze_compilation_unit,
    DataSymbol,
    ProcedureSymbolKind,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class HoverInfo:
    """A short description of the symbol under the cursor."""

    name: str
    kind: str
    detail: str


def compute_hover(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> HoverInfo | None:
    """Describe the data item, paragraph, or section at a 1-based position.

    Never raises: any failure at any stage just returns `None` rather
    than breaking the editor.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
        parse_result = parse_cobol_tokens(
            lex_result,
        )
    except Exception:
        return None

    if parse_result.unit is None:
        return None

    name = identifier_at(
        lex_result,
        line=line,
        column=column,
    )

    if name is None:
        return None

    try:
        semantic_result = analyze_compilation_unit(
            parse_result.unit,
        )
    except Exception:
        return None

    procedure_symbol = (
        semantic_result.symbol_table.find_procedure_symbol(
            name,
        )
    )

    if procedure_symbol is not None:
        kind_label = (
            "section"
            if procedure_symbol.kind
            is ProcedureSymbolKind.SECTION
            else "paragraph"
        )
        return HoverInfo(
            name=procedure_symbol.name,
            kind=kind_label,
            detail=(
                f"{kind_label.capitalize()}: "
                f"{procedure_symbol.name}"
            ),
        )

    data_symbols = (
        semantic_result.symbol_table.find_data_symbols(
            name,
        )
    )

    if data_symbols:
        return HoverInfo(
            name=data_symbols[0].name,
            kind="data-item",
            detail=_describe_data_item(
                data_symbols[0],
            ),
        )

    return None


def _describe_data_item(
    symbol: DataSymbol,
) -> str:
    parts = [
        f"{symbol.level_number:02d}",
    ]

    if symbol.item.name is not None:
        parts.append(
            symbol.item.name,
        )

    parts.extend(
        _render_tokens(
            clause.tokens,
        )
        for clause in symbol.item.clauses
    )

    return " ".join(
        parts,
    )


def _render_tokens(
    tokens,
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
