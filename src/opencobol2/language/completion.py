"""Code completion candidates for COBOL source.

Follows the same never-raise pipeline shape every other per-position
language service in this package already uses (`compute_hover`,
`compute_signature_help`, `navigation._prepare`): lex, optionally parse
and semantically analyze, and swallow any failure at any stage rather
than ever breaking the editor mid-keystroke. Unlike those, the
prefix-matching itself needs no resolved token at the cursor -- a
partial, still-being-typed word is matched by scanning source text
directly, not by lexing (lexing still happens for the symbol-table
lookup below, which needs a real parse to run at all).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.keywords import RESERVED_WORDS
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.parser import parse_cobol_tokens
from opencobol2.language.semantic import (
    ProcedureSymbolKind,
    analyze_compilation_unit,
)
from opencobol2.language.signature_help import (
    _INTRINSIC_FUNCTION_SIGNATURES,
)
from opencobol2.language.snippets import BUILTIN_SNIPPETS


class CompletionItemKind(Enum):
    """What kind of candidate a `CompletionItem` represents."""

    KEYWORD = "keyword"
    INTRINSIC_FUNCTION = "intrinsic-function"
    DATA_ITEM = "data-item"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    SNIPPET = "snippet"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionItem:
    """One completion candidate offered at the cursor."""

    label: str
    kind: CompletionItemKind
    insert_text: str
    detail: str | None = None
    snippet_body: str | None = None
    """Set only when `kind` is `SNIPPET` -- the raw, unexpanded body an
    editor should pass to its own snippet-insertion/tab-stop logic
    instead of inserting `insert_text` literally."""


_IDENTIFIER_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "abcdefghijklmnopqrstuvwxyz" "0123456789-"
)

# The user's own names rank above generic keywords/intrinsics when both
# match the same prefix -- their own code is usually the more relevant
# suggestion. Snippets sit in between: more specific than a bare
# keyword, but not tied to this file's own symbol table.
_KIND_SORT_PRIORITY: dict[CompletionItemKind, int] = {
    CompletionItemKind.DATA_ITEM: 0,
    CompletionItemKind.PARAGRAPH: 0,
    CompletionItemKind.SECTION: 0,
    CompletionItemKind.SNIPPET: 1,
    CompletionItemKind.KEYWORD: 2,
    CompletionItemKind.INTRINSIC_FUNCTION: 2,
}


def compute_completions(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> tuple[CompletionItem, ...]:
    """List completion candidates for the partial word ending at a
    1-based line/column.

    Never raises: any failure at any stage yields fewer candidates
    (or none) rather than breaking the editor -- in particular, a
    source file that fails to lex/parse/analyze still yields keyword,
    intrinsic-function, and snippet candidates, since only the
    symbol-table lookup depends on a successful parse.
    """

    prefix = _prefix_at(
        source_text,
        line=line,
        column=column,
    )

    if not prefix:
        return ()

    normalized_prefix = prefix.upper()
    items: list[CompletionItem] = []

    for word in RESERVED_WORDS:
        if word.startswith(normalized_prefix):
            items.append(
                CompletionItem(
                    label=word,
                    kind=CompletionItemKind.KEYWORD,
                    insert_text=word,
                )
            )

    for name, signature in _INTRINSIC_FUNCTION_SIGNATURES.items():
        if name.startswith(normalized_prefix):
            items.append(
                CompletionItem(
                    label=name,
                    kind=CompletionItemKind.INTRINSIC_FUNCTION,
                    insert_text=name,
                    detail=signature,
                )
            )

    for snippet in BUILTIN_SNIPPETS:
        if snippet.trigger.upper().startswith(normalized_prefix):
            items.append(
                CompletionItem(
                    label=snippet.trigger,
                    kind=CompletionItemKind.SNIPPET,
                    insert_text=snippet.trigger,
                    detail=snippet.label,
                    snippet_body=snippet.body,
                )
            )

    items.extend(
        _symbol_candidates(
            source_text,
            normalized_prefix,
            source_format,
        )
    )

    return _sort_and_dedupe(items)


def _prefix_at(
    source_text: str,
    *,
    line: int,
    column: int,
) -> str:
    """Return the run of COBOL-identifier characters ending at a
    1-based line/column, scanning left from the cursor.

    Hyphen-inclusive, the same word-boundary convention
    `SourceEditorWidget.rename_symbol_at_cursor` already uses, since
    COBOL names legally contain hyphens (`WS-COUNT-TOTAL`).
    """

    lines = source_text.splitlines()

    if not (1 <= line <= len(lines)):
        return ""

    text_line = lines[line - 1]
    end_index = column - 1

    if not (0 <= end_index <= len(text_line)):
        return ""

    start_index = end_index

    while (
        start_index > 0
        and text_line[start_index - 1] in _IDENTIFIER_CHARACTERS
    ):
        start_index -= 1

    return text_line[start_index:end_index]


def _symbol_candidates(
    source_text: str,
    normalized_prefix: str,
    source_format: CobolSourceFormat,
) -> tuple[CompletionItem, ...]:
    """List data-item/paragraph/section candidates from this file's own
    symbol table, or nothing if the source doesn't lex/parse/analyze
    cleanly right now -- an expected, transient state while typing."""

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
        parse_result = parse_cobol_tokens(
            lex_result,
        )
    except Exception:
        return ()

    if parse_result.unit is None:
        return ()

    try:
        semantic_result = analyze_compilation_unit(
            parse_result.unit,
        )
    except Exception:
        return ()

    items: list[CompletionItem] = []
    seen_names: set[tuple[str, CompletionItemKind]] = set()

    for symbol in semantic_result.symbol_table.data_symbols:
        key = (symbol.name.upper(), CompletionItemKind.DATA_ITEM)

        if (
            symbol.name.upper().startswith(normalized_prefix)
            and key not in seen_names
        ):
            seen_names.add(key)
            items.append(
                CompletionItem(
                    label=symbol.name,
                    kind=CompletionItemKind.DATA_ITEM,
                    insert_text=symbol.name,
                )
            )

    for symbol in semantic_result.symbol_table.procedure_symbols:
        kind = (
            CompletionItemKind.SECTION
            if symbol.kind is ProcedureSymbolKind.SECTION
            else CompletionItemKind.PARAGRAPH
        )
        key = (symbol.name.upper(), kind)

        if (
            symbol.name.upper().startswith(normalized_prefix)
            and key not in seen_names
        ):
            seen_names.add(key)
            items.append(
                CompletionItem(
                    label=symbol.name,
                    kind=kind,
                    insert_text=symbol.name,
                )
            )

    return tuple(items)


def _sort_and_dedupe(
    items: list[CompletionItem],
) -> tuple[CompletionItem, ...]:
    deduped: dict[tuple[str, CompletionItemKind], CompletionItem] = {}

    for item in items:
        key = (item.label.upper(), item.kind)
        deduped.setdefault(key, item)

    return tuple(
        sorted(
            deduped.values(),
            key=lambda item: (
                _KIND_SORT_PRIORITY[item.kind],
                item.label.upper(),
            ),
        )
    )
