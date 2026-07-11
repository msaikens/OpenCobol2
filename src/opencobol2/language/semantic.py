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

from dataclasses import dataclass
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

    def find_data_symbols(
        self,
        name: str,
    ) -> tuple[DataSymbol, ...]:
        """Return every data symbol matching a name, case-insensitively."""

        normalized = name.upper()

        return tuple(
            symbol
            for symbol in self.data_symbols
            if symbol.name.upper() == normalized
        )

    def find_procedure_symbol(
        self,
        name: str,
    ) -> ProcedureSymbol | None:
        """Return the first procedure symbol matching a name, if any."""

        normalized = name.upper()

        for symbol in self.procedure_symbols:
            if symbol.name.upper() == normalized:
                return symbol

        return None


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
) -> tuple[DataSymbol, ...]:
    """Build the data item symbol table, respecting level-number nesting."""

    symbols: list[DataSymbol] = []

    for section in unit.data.sections:
        stack: list[tuple[int, str | None]] = []
        last_non_condition_name: str | None = None

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
                parent_name = (
                    stack[-1][1]
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


def _build_procedure_symbols(
    procedure: ProcedureDivisionNode,
    diagnostics: list[ParseDiagnostic],
) -> tuple[ProcedureSymbol, ...]:
    """Build the paragraph/section symbol table, flagging duplicate names."""

    symbols: list[ProcedureSymbol] = []
    seen_names: set[str] = set()

    def _add(
        name: str | None,
        kind: ProcedureSymbolKind,
        span: object,
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

    for paragraph in procedure.paragraphs:
        _add(
            paragraph.name,
            ProcedureSymbolKind.PARAGRAPH,
            paragraph.span,
        )

    for section in procedure.sections:
        _add(
            section.name,
            ProcedureSymbolKind.SECTION,
            section.span,
        )

        for paragraph in section.paragraphs:
            _add(
                paragraph.name,
                ProcedureSymbolKind.PARAGRAPH,
                paragraph.span,
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
            _resolve_identifier_tokens(
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
    """Resolve a list of data name references, reporting problems."""

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
    """Resolve one PERFORM target/through name, reporting problems."""

    if name is None:
        return

    if symbol_table.find_procedure_symbol(
        name,
    ) is None:
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
