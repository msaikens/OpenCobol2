"""Semantic analysis over a parsed COBOL compilation unit.

Builds a symbol table for data items (respecting level-number nesting,
including 66 RENAMES, 77 standalone items, and 88 condition names) and
for procedure division paragraphs/sections, then resolves name
references throughout the procedure division:

* MOVE targets and PERFORM targets are structurally guaranteed to be
  names by the grammar, so an unresolved reference is reported as an
  ERROR.
* Every other token list a statement carries (MOVE sources, IF/EVALUATE
  conditions, PERFORM modifiers, DISPLAY operands, and generic
  statement tokens for unmodeled verbs like ADD/CALL/STRING) is scanned
  best-effort for IDENTIFIER tokens and resolved as a WARNING instead —
  these lists mix data names with syntax this parser does not deeply
  model yet (intrinsic FUNCTION names, index-names, special registers),
  so lower confidence is intentional to avoid false-positive noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)
from opencobol2.language.ast_nodes import (
    CompilationUnitNode,
    DataItemNode,
    DisplayStatement,
    EvaluateStatement,
    GenericStatement,
    IfStatement,
    MoveStatement,
    PerformStatement,
    ProcedureDivisionNode,
)
from opencobol2.language.diagnostics import (
    ParseDiagnostic,
)
from opencobol2.language.tokens import (
    SourcePosition,
    SourceSpan,
    Token,
    TokenKind,
)


class ProcedureSymbolKind(StrEnum):
    """Distinguishes a procedure division section from a paragraph."""

    SECTION = "section"
    PARAGRAPH = "paragraph"


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSymbol:
    """One named data item, condition name, or renames entry."""

    name: str
    level_number: int
    item: DataItemNode
    parent_name: str | None
    is_condition_name: bool
    is_renames: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureSymbol:
    """One named paragraph or section in the procedure division."""

    name: str
    kind: ProcedureSymbolKind
    span: SourceSpan


@dataclass(slots=True)
class SymbolTable:
    """Data and procedure division symbols for one compilation unit."""

    data_symbols: tuple[DataSymbol, ...]
    procedure_symbols: tuple[ProcedureSymbol, ...]
    _data_symbols_by_name: dict[
        str,
        tuple[DataSymbol, ...],
    ] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _procedure_symbols_by_name: dict[
        str,
        tuple[ProcedureSymbol, ...],
    ] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def _ensure_indexed(
        self,
    ) -> None:
        """Build the name -> symbols indexes once, lazily, and cache them.

        `find_data_symbols`/`find_procedure_symbols` are called once per
        name *reference* during analysis (every MOVE target, DISPLAY
        operand, and so on) against the same `SymbolTable` instance --
        resolving them via a linear scan over every symbol made
        analysis cost O(references x symbols), which is fine for a
        typical small program but becomes seconds of GUI-thread-blocking
        work on a file with thousands of data items and references
        (measured: ~800ms of semantic analysis alone on a ~9,600-line
        synthetic file, re-run on every keystroke since live diagnostics
        analyze on every edit). Indexing once and reusing it drops that
        to O(references + symbols).
        """

        if self._data_symbols_by_name is not None:
            return

        data_index: dict[
            str,
            list[DataSymbol],
        ] = {}

        for symbol in self.data_symbols:
            data_index.setdefault(
                symbol.name.upper(),
                [],
            ).append(
                symbol,
            )

        self._data_symbols_by_name = {
            name: tuple(symbols)
            for name, symbols in data_index.items()
        }

        procedure_index: dict[
            str,
            list[ProcedureSymbol],
        ] = {}

        for symbol in self.procedure_symbols:
            procedure_index.setdefault(
                symbol.name.upper(),
                [],
            ).append(
                symbol,
            )

        self._procedure_symbols_by_name = {
            name: tuple(symbols)
            for name, symbols in procedure_index.items()
        }

    def find_data_symbols(
        self,
        name: str,
    ) -> tuple[DataSymbol, ...]:
        """Return every data symbol matching a name, case-insensitively."""

        self._ensure_indexed()

        return self._data_symbols_by_name.get(
            name.upper(),
            (),
        )

    def find_procedure_symbols(
        self,
        name: str,
    ) -> tuple[ProcedureSymbol, ...]:
        """Return every procedure symbol matching a name, case-insensitively."""

        self._ensure_indexed()

        return self._procedure_symbols_by_name.get(
            name.upper(),
            (),
        )

    def find_procedure_symbol(
        self,
        name: str,
    ) -> ProcedureSymbol | None:
        """Return the first procedure symbol matching a name, if any."""

        matches = self.find_procedure_symbols(
            name,
        )

        return matches[0] if matches else None


@dataclass(frozen=True, slots=True, kw_only=True)
class DataNameReference:
    """One resolved usage of a data name (or condition/renames name)."""

    name: str
    position: SourcePosition


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureNameReference:
    """One resolved usage of a paragraph or section name."""

    name: str
    position: SourcePosition


@dataclass(slots=True)
class SemanticAnalysisResult:
    """The symbol table, diagnostics, and cross-references from analysis."""

    symbol_table: SymbolTable
    diagnostics: tuple[ParseDiagnostic, ...] = ()
    data_references: tuple[DataNameReference, ...] = ()
    procedure_references: tuple[ProcedureNameReference, ...] = ()

    @property
    def has_errors(
        self,
    ) -> bool:
        """Return whether any diagnostic is an error."""

        return any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )

    def find_data_references(
        self,
        name: str,
    ) -> tuple[SourcePosition, ...]:
        """Return every usage location resolved for one data name."""

        normalized = name.upper()

        return tuple(
            reference.position
            for reference in self.data_references
            if reference.name.upper() == normalized
        )

    def find_procedure_references(
        self,
        name: str,
    ) -> tuple[SourcePosition, ...]:
        """Return every usage location resolved for one procedure name."""

        normalized = name.upper()

        return tuple(
            reference.position
            for reference in self.procedure_references
            if reference.name.upper() == normalized
        )


@dataclass(slots=True)
class _AnalysisContext:
    """Mutable accumulator threaded through one analysis pass."""

    diagnostics: list[ParseDiagnostic]
    data_references: list[DataNameReference]
    procedure_references: list[ProcedureNameReference]


def analyze_compilation_unit(
    unit: CompilationUnitNode,
) -> SemanticAnalysisResult:
    """Build a symbol table and resolve name references for one unit."""

    if not isinstance(
        unit,
        CompilationUnitNode,
    ):
        raise TypeError(
            "Compilation unit must be CompilationUnitNode."
        )

    context = _AnalysisContext(
        diagnostics=[],
        data_references=[],
        procedure_references=[],
    )

    data_symbols = (
        _build_data_symbols(
            unit,
            context.diagnostics,
        )
        if unit.data is not None
        else ()
    )
    procedure_symbols = (
        _build_procedure_symbols(
            unit.procedure,
            context.diagnostics,
        )
        if unit.procedure is not None
        else ()
    )
    symbol_table = SymbolTable(
        data_symbols=data_symbols,
        procedure_symbols=procedure_symbols,
    )

    if unit.data is not None:
        _resolve_data_clause_references(
            unit,
            symbol_table,
            context,
        )

    if unit.procedure is not None:
        _resolve_references(
            unit.procedure,
            symbol_table,
            context,
        )

    return SemanticAnalysisResult(
        symbol_table=symbol_table,
        diagnostics=tuple(
            context.diagnostics,
        ),
        data_references=tuple(
            context.data_references,
        ),
        procedure_references=tuple(
            context.procedure_references,
        ),
    )


def _build_data_symbols(
    unit: CompilationUnitNode,
    diagnostics: list[ParseDiagnostic],
) -> tuple[DataSymbol, ...]:
    """Build the data item symbol table, respecting level-number nesting."""

    symbols: list[DataSymbol] = []

    for section in unit.data.sections:
        stack: list[tuple[int, str | None]] = []
        last_non_condition_name: str | None = None
        # Scoped to this one section, not the whole data division --
        # WORKING-STORAGE and LINKAGE (for example) are separate areas
        # where the same name legitimately recurs. Only ordinary
        # (non-88, non-66) sibling items under the same immediate
        # parent are tracked here (Semantic-3); 88-level condition
        # names and 66-level RENAMES entries have their own separate
        # naming conventions and are not covered by this check.
        seen_siblings: set[tuple[str | None, str]] = set()

        for item in section.items:
            level = item.level_number

            if level == 88:
                if item.name is not None:
                    symbols.append(
                        DataSymbol(
                            name=item.name,
                            level_number=level,
                            item=item,
                            parent_name=last_non_condition_name,
                            is_condition_name=True,
                            is_renames=False,
                        ),
                    )

                continue

            if level == 66:
                # Editor §Semantic-9: the enclosing 01-level record --
                # the bottom of the ancestor stack, since a 66-level
                # RENAMES entry does not itself push onto the stack --
                # not `stack[-1]`, which is merely the most recently
                # processed *sibling* elementary item.
                parent_name = (
                    stack[0][1]
                    if stack
                    else None
                )

                if item.name is not None:
                    symbols.append(
                        DataSymbol(
                            name=item.name,
                            level_number=level,
                            item=item,
                            parent_name=parent_name,
                            is_condition_name=False,
                            is_renames=True,
                        ),
                    )
                    last_non_condition_name = item.name

                continue

            if level == 77:
                stack = []
                parent_name = None
            else:
                while (
                    stack
                    and stack[-1][0] >= level
                ):
                    stack.pop()

                parent_name = (
                    stack[-1][1]
                    if stack
                    else None
                )

            if item.name is not None:
                sibling_key = (
                    parent_name,
                    item.name.upper(),
                )

                if sibling_key in seen_siblings:
                    diagnostics.append(
                        ParseDiagnostic(
                            severity=DiagnosticSeverity.ERROR,
                            message=(
                                "Duplicate data item name under "
                                f"the same parent: {item.name}"
                            ),
                            position=item.span.start,
                        ),
                    )
                else:
                    seen_siblings.add(
                        sibling_key,
                    )

                symbols.append(
                    DataSymbol(
                        name=item.name,
                        level_number=level,
                        item=item,
                        parent_name=parent_name,
                        is_condition_name=False,
                        is_renames=False,
                    ),
                )
                last_non_condition_name = item.name
            else:
                last_non_condition_name = None

            if level != 77:
                stack.append(
                    (
                        level,
                        item.name,
                    ),
                )

    return tuple(
        symbols,
    )


_REFERENCE_BEARING_CLAUSE_KEYWORDS = frozenset(
    {
        "REDEFINES",
        "RENAMES",
        "OCCURS",
    },
)


def _resolve_data_clause_references(
    unit: CompilationUnitNode,
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve names referenced from within data-description clauses.

    Reference resolution otherwise only ever walks `unit.procedure`,
    so a name used only inside a data-description clause -- most
    notably a `REDEFINES` target, a `RENAMES ... THRU` range, or an
    `OCCURS ... DEPENDING ON` subscript-count -- was previously
    invisible to `find_data_references` (Editor §Semantic-4). Each
    qualifying clause's own token list is fed through the same
    best-effort `_resolve_identifier_tokens` scan already used for
    every other loosely-parsed token list in this module.
    """

    for section in unit.data.sections:
        for item in section.items:
            for clause in item.clauses:
                if (
                    clause.keyword
                    in _REFERENCE_BEARING_CLAUSE_KEYWORDS
                ):
                    _resolve_identifier_tokens(
                        clause.tokens,
                        symbol_table,
                        context,
                    )


def _build_procedure_symbols(
    procedure: ProcedureDivisionNode,
    diagnostics: list[ParseDiagnostic],
) -> tuple[ProcedureSymbol, ...]:
    """Build the paragraph/section symbol table, flagging duplicate names.

    Section names must be unique across the whole procedure division,
    but a paragraph name may legally repeat across two *different*
    sections (disambiguated by `PERFORM x IN section-name`) -- see
    Editor Phase 4 tracker finding Semantic-1. Duplicate detection is
    therefore scoped per enclosing paragraph list: the top-level
    (unsectioned) paragraphs are one scope, and each section's own
    paragraphs are a separate scope from every other section's.
    """

    symbols: list[ProcedureSymbol] = []
    section_names_seen: set[str] = set()

    def _add(
        name: str | None,
        kind: ProcedureSymbolKind,
        span: object,
        seen_names: set[str],
    ) -> None:
        if name is None:
            return

        normalized = name.upper()

        if normalized in seen_names:
            diagnostics.append(
                ParseDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Duplicate procedure division name: {name}"
                    ),
                    position=span.start,
                ),
            )
        else:
            seen_names.add(
                normalized,
            )

        symbols.append(
            ProcedureSymbol(
                name=name,
                kind=kind,
                span=span,
            ),
        )

    top_level_paragraph_names_seen: set[str] = set()

    for paragraph in procedure.paragraphs:
        _add(
            paragraph.name,
            ProcedureSymbolKind.PARAGRAPH,
            paragraph.span,
            top_level_paragraph_names_seen,
        )

    for section in procedure.sections:
        _add(
            section.name,
            ProcedureSymbolKind.SECTION,
            section.span,
            section_names_seen,
        )

        section_paragraph_names_seen: set[str] = set()

        for paragraph in section.paragraphs:
            _add(
                paragraph.name,
                ProcedureSymbolKind.PARAGRAPH,
                paragraph.span,
                section_paragraph_names_seen,
            )

    return tuple(
        symbols,
    )


def _resolve_references(
    procedure: ProcedureDivisionNode,
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve MOVE targets and PERFORM targets against the symbol table."""

    for paragraph in procedure.paragraphs:
        _resolve_statements(
            paragraph.statements,
            symbol_table,
            context,
        )

    for section in procedure.sections:
        for paragraph in section.paragraphs:
            _resolve_statements(
                paragraph.statements,
                symbol_table,
                context,
            )


def _resolve_statements(
    statements: tuple[object, ...],
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Recursively resolve references within a statement list."""

    for statement in statements:
        if isinstance(
            statement,
            MoveStatement,
        ):
            _resolve_data_names(
                statement.target_names,
                statement.span.start,
                symbol_table,
                context,
            )
            _resolve_identifier_tokens(
                statement.source_tokens,
                symbol_table,
                context,
            )
        elif isinstance(
            statement,
            DisplayStatement,
        ):
            _resolve_identifier_tokens(
                statement.operand_tokens,
                symbol_table,
                context,
            )
        elif isinstance(
            statement,
            PerformStatement,
        ):
            _resolve_procedure_name(
                statement.target_name,
                statement.span.start,
                symbol_table,
                context,
            )
            _resolve_procedure_name(
                statement.through_name,
                statement.span.start,
                symbol_table,
                context,
            )
            _resolve_perform_modifier_tokens(
                statement.modifier_tokens,
                symbol_table,
                context,
            )
            _resolve_statements(
                statement.body,
                symbol_table,
                context,
            )
        elif isinstance(
            statement,
            IfStatement,
        ):
            _resolve_identifier_tokens(
                statement.condition_tokens,
                symbol_table,
                context,
            )
            _resolve_statements(
                statement.then_statements,
                symbol_table,
                context,
            )
            _resolve_statements(
                statement.else_statements,
                symbol_table,
                context,
            )
        elif isinstance(
            statement,
            EvaluateStatement,
        ):
            _resolve_identifier_tokens(
                statement.subject_tokens,
                symbol_table,
                context,
            )

            for branch in statement.branches:
                _resolve_identifier_tokens(
                    branch.condition_tokens,
                    symbol_table,
                    context,
                )
                _resolve_statements(
                    branch.statements,
                    symbol_table,
                    context,
                )
        elif isinstance(
            statement,
            GenericStatement,
        ):
            # tokens[0] is always the verb itself (a reserved word, so
            # the identifier filter below already skips it).
            if statement.verb == "GO":
                _resolve_go_to_targets(
                    statement.tokens,
                    symbol_table,
                    context,
                )
            elif statement.verb == "ALTER":
                _resolve_alter_targets(
                    statement.tokens,
                    symbol_table,
                    context,
                )
            else:
                _resolve_identifier_tokens(
                    statement.tokens,
                    symbol_table,
                    context,
                )


def _resolve_data_names(
    names: tuple[str, ...],
    position: SourcePosition,
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve a list of data name references (MOVE targets), reporting
    problems.

    MOVE targets are always ordinary receiving fields, never
    condition-names -- `MOVE value TO condition-name` is illegal COBOL
    (Editor §Semantic-10), so a match that's exclusively a condition
    name is flagged even though the name itself did resolve.
    """

    for name in names:
        matches = symbol_table.find_data_symbols(
            name,
        )

        if not matches:
            context.diagnostics.append(
                ParseDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Undefined data name: {name}",
                    position=position,
                ),
            )
        else:
            context.data_references.append(
                DataNameReference(
                    name=name,
                    position=position,
                ),
            )

            if len(
                matches,
            ) > 1:
                context.diagnostics.append(
                    ParseDiagnostic(
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            f"Ambiguous reference to data name: {name}"
                        ),
                        position=position,
                    ),
                )
            elif matches[0].is_condition_name:
                context.diagnostics.append(
                    ParseDiagnostic(
                        severity=DiagnosticSeverity.ERROR,
                        message=(
                            "Condition-name cannot be used as a "
                            f"MOVE target: {name}"
                        ),
                        position=position,
                    ),
                )


def _resolve_identifier_tokens(
    tokens: tuple[Token, ...],
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Best-effort resolve IDENTIFIER tokens in a raw token list.

    Reserved words, literals, and punctuation are never IDENTIFIER
    tokens, so this only ever considers plausible name references. An
    unresolved or ambiguous match is reported as a WARNING (not an
    ERROR) since these token lists are not deeply parsed and may
    legitimately contain names this analysis cannot classify yet
    (intrinsic FUNCTION names, index-names, special registers).
    """

    for token in tokens:
        if token.kind is not TokenKind.IDENTIFIER:
            continue

        matches = symbol_table.find_data_symbols(
            token.text,
        )

        if not matches:
            context.diagnostics.append(
                ParseDiagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    message=(
                        f"Possibly undefined data name: {token.text}"
                    ),
                    position=token.span.start,
                ),
            )
        else:
            context.data_references.append(
                DataNameReference(
                    name=token.text,
                    position=token.span.start,
                ),
            )

            if len(
                matches,
            ) > 1:
                context.diagnostics.append(
                    ParseDiagnostic(
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            "Ambiguous reference to data name: "
                            f"{token.text}"
                        ),
                        position=token.span.start,
                    ),
                )


def _resolve_procedure_name(
    name: str | None,
    position: SourcePosition,
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve one paragraph/section name reference, reporting problems.

    Mirrors `_resolve_data_names`'s ambiguity handling (Editor
    §Semantic-5): since Semantic-1's fix legitimately allows the same
    paragraph name to be declared in two different sections, an
    unqualified reference matching more than one is now a real,
    reachable case, not the merely-hypothetical one it used to be
    while every such duplicate was rejected outright at declaration.
    """

    if name is None:
        return

    matches = symbol_table.find_procedure_symbols(
        name,
    )

    if not matches:
        context.diagnostics.append(
            ParseDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "Undefined paragraph or section: "
                    f"{name}"
                ),
                position=position,
            ),
        )
    else:
        context.procedure_references.append(
            ProcedureNameReference(
                name=name,
                position=position,
            ),
        )

        if len(
            matches,
        ) > 1:
            context.diagnostics.append(
                ParseDiagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    message=(
                        "Ambiguous reference to paragraph or "
                        f"section: {name}"
                    ),
                    position=position,
                ),
            )


_PERFORM_QUALIFIER_KEYWORDS = frozenset(
    {
        "IN",
        "OF",
    },
)


def _resolve_perform_modifier_tokens(
    modifier_tokens: tuple[Token, ...],
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve a PERFORM statement's modifier tokens.

    An `IN`/`OF` section qualifier (`PERFORM name IN section-name`) is
    routed to procedure-symbol resolution instead of the generic
    data-name scan below -- the parser has no dedicated AST field for
    this qualifier, so it lands in `modifier_tokens` alongside genuine
    data-name-bearing modifiers (`VARYING`, `WITH TEST`), and without
    this split a section name would be checked as if it might be a
    data item (Editor §Semantic-6).
    """

    length = len(
        modifier_tokens,
    )
    remaining: list[Token] = []
    index = 0

    while index < length:
        token = modifier_tokens[index]
        word = (
            token.text.upper()
            if token.kind is TokenKind.RESERVED_WORD
            else ""
        )

        if (
            word in _PERFORM_QUALIFIER_KEYWORDS
            and index + 1 < length
            and modifier_tokens[index + 1].kind
            in (
                TokenKind.IDENTIFIER,
                TokenKind.RESERVED_WORD,
            )
        ):
            qualifier_token = modifier_tokens[index + 1]
            _resolve_procedure_name(
                qualifier_token.text,
                qualifier_token.span.start,
                symbol_table,
                context,
            )
            index += 2
            continue

        remaining.append(
            token,
        )
        index += 1

    _resolve_identifier_tokens(
        tuple(
            remaining,
        ),
        symbol_table,
        context,
    )


def _resolve_go_to_targets(
    tokens: tuple[Token, ...],
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve a `GO TO` statement's paragraph-name target(s).

    `GO TO`'s target(s) belong in the procedure namespace, not the
    generic data-name scan (Editor §Semantic-11). The legacy
    multi-target `GO TO t1 t2 ... DEPENDING ON data-name` form's
    selector after `DEPENDING ON` is a genuine data name and is
    excluded from procedure-name resolution, falling back to the
    ordinary best-effort data-name scan instead.
    """

    after_depending = False
    selector_tokens: list[Token] = []

    # tokens[0] is the GO verb itself.
    for token in tokens[1:]:
        word = (
            token.text.upper()
            if token.kind is TokenKind.RESERVED_WORD
            else ""
        )

        if word == "DEPENDING":
            after_depending = True
            continue

        if word in (
            "TO",
            "ON",
        ):
            continue

        if after_depending:
            selector_tokens.append(
                token,
            )
        elif token.kind in (
            TokenKind.IDENTIFIER,
            TokenKind.NUMERIC_LITERAL,
        ):
            _resolve_procedure_name(
                token.text,
                token.span.start,
                symbol_table,
                context,
            )

    _resolve_identifier_tokens(
        tuple(
            selector_tokens,
        ),
        symbol_table,
        context,
    )


_ALTER_KEYWORDS = frozenset(
    {
        "TO",
        "PROCEED",
    },
)


def _resolve_alter_targets(
    tokens: tuple[Token, ...],
    symbol_table: SymbolTable,
    context: _AnalysisContext,
) -> None:
    """Resolve an `ALTER` statement's paragraph-name targets.

    Every operand of `ALTER para-1 TO [PROCEED TO] para-2[, para-3 TO
    [PROCEED TO] para-4]...` is a paragraph name -- there are no
    data-name operands at all, unlike `GO TO`'s DEPENDING ON form
    (Editor §Semantic-11).
    """

    # tokens[0] is the ALTER verb itself.
    for token in tokens[1:]:
        word = (
            token.text.upper()
            if token.kind is TokenKind.RESERVED_WORD
            else ""
        )

        if word in _ALTER_KEYWORDS:
            continue

        if token.kind in (
            TokenKind.IDENTIFIER,
            TokenKind.NUMERIC_LITERAL,
        ):
            _resolve_procedure_name(
                token.text,
                token.span.start,
                symbol_table,
                context,
            )
