"""A short, human-readable summary for hovering over an identifier or keyword.

Two independent lookups, tried in order:

1. Symbols the real symbol table already knows about -- data items,
   paragraphs, and sections -- the same scope `find_definition`/
   `find_references` use.
2. Reserved words with an entry in `_RESERVED_WORD_DOCS` (Documentation
   lookup) -- a hand-picked set of the most common division/section
   keywords and statement verbs, each with a short, generic, factual
   one-line description. Deliberately not exhaustive: COBOL's real
   reserved-word table has hundreds of entries, and a vague or wrong
   description would be worse than no hover at all, so a reserved word
   missing from the table just yields no hover rather than a guess.
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
from opencobol2.language.tokens import TokenKind


_RESERVED_WORD_DOCS: dict[str, str] = {
    "IDENTIFICATION": "Opens the division that names the program.",
    "ENVIRONMENT": (
        "Opens the division describing the program's runtime "
        "environment (configuration, file assignments)."
    ),
    "DATA": (
        "Opens the division that declares every data item the "
        "program uses."
    ),
    "PROCEDURE": (
        "Opens the division containing the program's executable "
        "statements."
    ),
    "DIVISION": "Marks the end of a division header.",
    "CONFIGURATION": (
        "Section of the Environment Division describing the "
        "source and object computers."
    ),
    "INPUT-OUTPUT": (
        "Section of the Environment Division describing file "
        "assignments."
    ),
    "FILE-CONTROL": (
        "Paragraph of the Input-Output Section naming and "
        "assigning each file."
    ),
    "FILE": "Opens the File Section, or names a file in a SELECT clause.",
    "WORKING-STORAGE": (
        "Section holding data items that persist for the life of "
        "the program."
    ),
    "LOCAL-STORAGE": (
        "Section holding data items reinitialized on every call."
    ),
    "LINKAGE": (
        "Section holding data items passed in from a calling "
        "program."
    ),
    "SECTION": "Marks the end of a section header.",
    "PROGRAM-ID": "Names the program; the first entry in most COBOL source.",
    "PIC": "Short form of PICTURE: declares a data item's storage format.",
    "PICTURE": "Declares a data item's storage format.",
    "VALUE": "Gives a data item its initial value.",
    "OCCURS": "Declares a data item as an array with a fixed element count.",
    "REDEFINES": (
        "Overlays a data item's storage on top of an "
        "already-declared item."
    ),
    "USAGE": "Declares a data item's internal representation (e.g. COMP).",
    "MOVE": "Copies a value from one data item (or literal) into another.",
    "ADD": "Adds one or more values, storing the result.",
    "SUBTRACT": "Subtracts one or more values, storing the result.",
    "MULTIPLY": "Multiplies two values, storing the result.",
    "DIVIDE": "Divides one value by another, storing the result.",
    "COMPUTE": (
        "Evaluates an arithmetic expression, storing the result "
        "in one or more data items."
    ),
    "IF": "Branches based on a condition.",
    "ELSE": "Introduces the branch taken when an IF condition is false.",
    "EVALUATE": "Branches based on one or more conditions or values, like a switch.",
    "WHEN": "Introduces one branch of an EVALUATE.",
    "PERFORM": "Executes a paragraph, section, or inline statement block.",
    "UNTIL": "Modifies PERFORM to loop until a condition becomes true.",
    "VARYING": "Modifies PERFORM to loop while varying one or more data items.",
    "TIMES": "Modifies PERFORM to loop a fixed number of times.",
    "CALL": "Invokes another program or a library routine.",
    "DISPLAY": "Writes a value to the console or a configured device.",
    "ACCEPT": "Reads a value from the console or a configured device.",
    "STOP": "Halts execution; STOP RUN ends the program.",
    "RUN": "Modifier of STOP; STOP RUN ends the program.",
    "GOBACK": "Returns control to the calling program.",
    "STRING": "Concatenates multiple data items/literals into one.",
    "UNSTRING": "Splits one data item into multiple data items.",
    "INSPECT": "Counts or replaces occurrences of characters in a data item.",
    "INITIALIZE": "Resets one or more data items to their default values.",
    "SET": "Assigns a value to an index, pointer, or condition name.",
    "OPEN": "Opens a file for the mode(s) given (INPUT, OUTPUT, I-O, EXTEND).",
    "CLOSE": "Closes a previously opened file.",
    "READ": "Reads the next (or a specific) record from a file.",
    "WRITE": "Writes a record to a file.",
    "REWRITE": "Rewrites an existing record in a file opened for I-O.",
    "DELETE": "Deletes a record from a file opened for I-O.",
    "START": "Positions a relative or indexed file at a given record.",
    "SORT": "Sorts records from one or more files or procedures.",
    "MERGE": "Merges records from multiple sorted files.",
    "SEARCH": "Searches an array (table) for an element matching a condition.",
    "EXIT": "Leaves a paragraph, PERFORM loop, or program.",
}


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
        return _hover_for_reserved_word(
            lex_result,
            line=line,
            column=column,
        )

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


def _hover_for_reserved_word(
    lex_result,
    *,
    line: int,
    column: int,
) -> HoverInfo | None:
    """Describe the reserved word at a 1-based position, if documented."""

    for token in lex_result.tokens:
        if token.kind is not TokenKind.RESERVED_WORD:
            continue

        if token.span.start.line != line:
            continue

        start_column = token.span.start.column

        if not (
            start_column
            <= column
            < start_column + len(token.text)
        ):
            continue

        description = _RESERVED_WORD_DOCS.get(
            token.text.upper(),
        )

        if description is None:
            return None

        return HoverInfo(
            name=token.text,
            kind="keyword",
            detail=f"{token.text}: {description}",
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
