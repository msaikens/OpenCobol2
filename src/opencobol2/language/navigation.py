"""Go-to-definition and find-references for one COBOL compilation unit.

Both are single-file only: COBOL data-name/procedure-name resolution here
is scoped to the symbol table of one compilation unit (the real parser and
semantic analyzer never see more than one file at a time), and the project
model has no cross-file "this program calls that program" concept to walk
even if it did.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.parser import parse_cobol_tokens
from opencobol2.language.semantic import analyze_compilation_unit
from opencobol2.language.tokens import TokenKind


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceLocation:
    """One named, 1-based line/column location within a COBOL document."""

    name: str
    line: int
    column: int


def find_definition(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> SourceLocation | None:
    """Find the definition of the identifier at a 1-based line/column.

    Never raises: any failure at any stage (lexing, parsing, semantic
    analysis, or simply not finding an identifier at that position) just
    returns `None` rather than breaking the editor.
    """

    prepared = _prepare(
        source_text,
        line=line,
        column=column,
        source_format=source_format,
    )

    if prepared is None:
        return None

    name, symbol_table, _semantic_result, tokens, index = prepared
    kind = _reference_kind_at(
        tokens,
        index,
        name,
        symbol_table,
    )

    if kind != "data":
        procedure_symbol = symbol_table.find_procedure_symbol(
            name,
        )

        if procedure_symbol is not None:
            return SourceLocation(
                name=procedure_symbol.name,
                line=procedure_symbol.span.start.line,
                column=procedure_symbol.span.start.column,
            )

        if kind == "procedure":
            return None

    data_symbols = symbol_table.find_data_symbols(
        name,
    )

    if data_symbols:
        first_symbol = data_symbols[0]
        return SourceLocation(
            name=first_symbol.name,
            line=first_symbol.item.span.start.line,
            column=first_symbol.item.span.start.column,
        )

    return None


def find_references(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> tuple[SourceLocation, ...]:
    """Find every reference to (and the definition of) an identifier.

    Never raises, same as `find_definition`. Includes the definition
    itself alongside every usage, deduplicated and sorted by position.
    """

    prepared = _prepare(
        source_text,
        line=line,
        column=column,
        source_format=source_format,
    )

    if prepared is None:
        return ()

    name, symbol_table, semantic_result, tokens, index = prepared
    normalized_name = name.upper()
    locations: list[SourceLocation] = []
    kind = _reference_kind_at(
        tokens,
        index,
        name,
        symbol_table,
    )

    if kind != "data":
        procedure_symbol = symbol_table.find_procedure_symbol(
            name,
        )

        if procedure_symbol is not None:
            locations.append(
                SourceLocation(
                    name=procedure_symbol.name,
                    line=procedure_symbol.span.start.line,
                    column=procedure_symbol.span.start.column,
                )
            )

        for reference in (
            semantic_result.procedure_references
        ):
            if reference.name.upper() == normalized_name:
                locations.append(
                    SourceLocation(
                        name=reference.name,
                        line=reference.position.line,
                        column=reference.position.column,
                    )
                )

    if kind != "procedure":
        for data_symbol in symbol_table.find_data_symbols(
            name,
        ):
            locations.append(
                SourceLocation(
                    name=data_symbol.name,
                    line=data_symbol.item.span.start.line,
                    column=data_symbol.item.span.start.column,
                )
            )

        for reference in semantic_result.data_references:
            if reference.name.upper() == normalized_name:
                locations.append(
                    SourceLocation(
                        name=reference.name,
                        line=reference.position.line,
                        column=reference.position.column,
                    )
                )

    unique_keys = sorted(
        {
            (
                location.line,
                location.column,
                location.name,
            )
            for location in locations
        }
    )

    return tuple(
        SourceLocation(
            name=name_,
            line=line_,
            column=column_,
        )
        for line_, column_, name_ in unique_keys
    )


def _prepare(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat,
):
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

    index = _identifier_token_index_at(
        lex_result.tokens,
        line=line,
        column=column,
    )

    if index is None:
        return None

    try:
        semantic_result = analyze_compilation_unit(
            parse_result.unit,
        )
    except Exception:
        return None

    return (
        lex_result.tokens[index].text,
        semantic_result.symbol_table,
        semantic_result,
        lex_result.tokens,
        index,
    )


def _identifier_token_index_at(
    tokens,
    *,
    line: int,
    column: int,
) -> int | None:
    """Return the index of the IDENTIFIER token covering a position, if any."""

    for index, token in enumerate(
        tokens,
    ):
        if token.kind is not TokenKind.IDENTIFIER:
            continue

        if token.span.start.line != line:
            continue

        start_column = token.span.start.column

        if (
            start_column
            <= column
            < start_column
            + len(
                token.text,
            )
        ):
            return index

    return None


def identifier_token_at(
    lex_result,
    *,
    line: int,
    column: int,
):
    """Return the IDENTIFIER token covering a position, if any."""

    index = _identifier_token_index_at(
        lex_result.tokens,
        line=line,
        column=column,
    )

    return (
        lex_result.tokens[index]
        if index is not None
        else None
    )


def identifier_at(
    lex_result,
    *,
    line: int,
    column: int,
) -> str | None:
    """Return the text of the IDENTIFIER token covering a position, if any."""

    token = identifier_token_at(
        lex_result,
        line=line,
        column=column,
    )

    return token.text if token is not None else None


# A `MOVE`/`PERFORM` target's *semantic* position is recorded as the
# whole statement's own start (a pre-existing, documented AST precision
# limit -- neither statement stores a per-target-name token/span), so
# matching a cursor position exactly against `data_references`/
# `procedure_references` entries does not work for disambiguating a
# specific usage. Instead, the immediately preceding significant raw
# token tells us the grammatical context directly.
_DATA_CONTEXT_PRECEDING_WORDS = frozenset(
    {
        "TO",
        "FROM",
        "BY",
    },
)
_PROCEDURE_CONTEXT_PRECEDING_WORDS = frozenset(
    {
        "PERFORM",
        "THRU",
        "THROUGH",
    },
)


def _reference_kind_at(
    tokens,
    index: int,
    name: str,
    symbol_table,
) -> str | None:
    """Return `"data"`/`"procedure"` if the identifier at `tokens[index]`
    is unambiguously used in that context, or `None` if unknown.

    Real COBOL keeps procedure-names (paragraphs/sections) and
    data-names in separate namespaces -- the same name can legally
    denote two different symbols, which let go-to-definition/hover/
    find-references conflate two same-named-but-unrelated symbols
    before this fix (Editor §Editor-Facing-7). Two checks, in order:
    (1) is the cursor sitting on a symbol's own declaration (a
    procedure symbol's span starts exactly at its name token, but a
    data item's span starts at its *level number*, a separate
    documented AST precision limit, so line-level matching is used for
    data items instead of an exact position match); (2) if not, what
    does the immediately preceding significant token imply about this
    specific usage.
    """

    token = tokens[index]
    normalized = name.upper()

    for symbol in symbol_table.data_symbols:
        if (
            symbol.name.upper() == normalized
            and symbol.item.span.start.line
            == token.span.start.line
        ):
            return "data"

    for symbol in symbol_table.procedure_symbols:
        if symbol.name.upper() == normalized and (
            symbol.span.start.line,
            symbol.span.start.column,
        ) == (
            token.span.start.line,
            token.span.start.column,
        ):
            return "procedure"

    previous = None

    for candidate_index in range(
        index - 1,
        -1,
        -1,
    ):
        candidate = tokens[candidate_index]

        if candidate.kind is TokenKind.COMMENT:
            continue

        previous = candidate
        break

    if (
        previous is not None
        and previous.kind is TokenKind.RESERVED_WORD
    ):
        word = previous.text.upper()

        if word in _PROCEDURE_CONTEXT_PRECEDING_WORDS:
            return "procedure"

        if word in _DATA_CONTEXT_PRECEDING_WORDS:
            return "data"

    return None
