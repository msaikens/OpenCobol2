"""A recursive-descent parser for COBOL token streams.

This parser gives real structure to program identity, data description
entries, and procedure division control flow (paragraphs, sections, IF,
PERFORM, EVALUATE). Every other statement verb (ADD, CALL, STRING, and
so on) is parsed as a `GenericStatement` — its verb and raw tokens are
captured, but its internal grammar is not modeled yet. The environment
division is recognized but not structurally parsed.

COBOL's implicit, period-based scope termination (a "." can end not
just the current statement but every enclosing IF/PERFORM/EVALUATE
body at once) is handled by propagating a `_sentence_terminated` flag
up through the recursive statement-list calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)
from opencobol2.language.ast_nodes import (
    CompilationUnitNode,
    DataDescriptionClause,
    DataDivisionNode,
    DataItemNode,
    DataSectionNode,
    DisplayStatement,
    EnvironmentDivisionNode,
    EvaluateStatement,
    EvaluateWhenBranch,
    GenericStatement,
    GobackStatement,
    IdentificationDivisionNode,
    IfStatement,
    MoveStatement,
    ParagraphNode,
    PerformStatement,
    ProcedureDivisionNode,
    ProcedureSectionNode,
    StopRunStatement,
)
from opencobol2.language.diagnostics import (
    ParseDiagnostic,
)
from opencobol2.language.lexer import (
    LexResult,
)
from opencobol2.language.tokens import (
    SourcePosition,
    SourceSpan,
    Token,
    TokenKind,
)


_DIVISION_NAMES = (
    "IDENTIFICATION",
    "ENVIRONMENT",
    "DATA",
    "PROCEDURE",
)

_DATA_SECTION_NAMES = (
    "WORKING-STORAGE",
    "LOCAL-STORAGE",
    "LINKAGE",
    "FILE",
    "SCREEN",
    "REPORT",
)

_DATA_CLAUSE_KEYWORDS = frozenset(
    {
        "PIC",
        "PICTURE",
        "VALUE",
        "VALUES",
        "OCCURS",
        "REDEFINES",
        "RENAMES",
        "USAGE",
        "COMP",
        "COMPUTATIONAL",
        "COMP-1",
        "COMP-2",
        "COMP-3",
        "COMP-4",
        "COMP-5",
        "BINARY",
        "PACKED-DECIMAL",
        "DISPLAY",
        "JUSTIFIED",
        "JUST",
        "SIGN",
        "SYNCHRONIZED",
        "SYNC",
        "BLANK",
        "GLOBAL",
        "EXTERNAL",
    },
)

STATEMENT_VERBS = frozenset(
    {
        "ACCEPT",
        "ADD",
        "ALTER",
        "CALL",
        "CANCEL",
        "CLOSE",
        "COMPUTE",
        "CONTINUE",
        "DELETE",
        "DISPLAY",
        "DIVIDE",
        "EVALUATE",
        "EXIT",
        "GO",
        "GOBACK",
        "IF",
        "INITIALIZE",
        "INSPECT",
        "INVOKE",
        "MERGE",
        "MOVE",
        "MULTIPLY",
        "OPEN",
        "PERFORM",
        "READ",
        "RELEASE",
        "RETURN",
        "REWRITE",
        "SEARCH",
        "SET",
        "SORT",
        "START",
        "STOP",
        "STRING",
        "SUBTRACT",
        "UNSTRING",
        "WRITE",
    },
)

_STRUCTURAL_TERMINATORS = frozenset(
    {
        "ELSE",
        "END-IF",
        "END-PERFORM",
        "END-EVALUATE",
        "WHEN",
    },
)


@dataclass(slots=True)
class ParseResult:
    """The AST and diagnostics produced by parsing one COBOL document."""

    unit: CompilationUnitNode | None
    diagnostics: tuple[ParseDiagnostic, ...] = ()

    @property
    def has_errors(
        self,
    ) -> bool:
        """Return whether any diagnostic is an error."""

        return any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )


class _Cursor:
    """A position cursor over a fixed token sequence."""

    __slots__ = (
        "_tokens",
        "_index",
        "last_end",
    )

    def __init__(
        self,
        tokens: tuple[Token, ...],
    ) -> None:
        self._tokens = tokens
        self._index = 0
        self.last_end: SourcePosition = tokens[0].span.start

    def current(
        self,
    ) -> Token:
        """Return the token at the cursor."""

        return self._tokens[self._index]

    def peek(
        self,
        offset: int,
    ) -> Token:
        """Return the token `offset` positions ahead of the cursor."""

        index = min(
            self._index + offset,
            len(
                self._tokens,
            )
            - 1,
        )

        return self._tokens[index]

    def at_end(
        self,
    ) -> bool:
        """Return whether the cursor is at the end-of-file token."""

        return self.current().kind is TokenKind.END_OF_FILE

    def advance(
        self,
    ) -> Token:
        """Consume and return the token at the cursor."""

        token = self.current()

        if token.kind is not TokenKind.END_OF_FILE:
            self._index += 1

        self.last_end = token.span.end

        return token


def _word(
    token: Token,
) -> str:
    """Return a token's upper-cased word text, or '' if not word-like."""

    if token.kind in (
        TokenKind.RESERVED_WORD,
        TokenKind.IDENTIFIER,
    ):
        return token.text.upper()

    return ""


class CobolParser:
    """Parses a COBOL lexer result into an AST."""

    def __init__(
        self,
        lex_result: LexResult,
    ) -> None:
        """Initialize the parser over one lexer result."""

        if not isinstance(
            lex_result,
            LexResult,
        ):
            raise TypeError(
                "Lex result must be LexResult."
            )

        code_tokens = tuple(
            token
            for token in lex_result.tokens
            if token.kind is not TokenKind.COMMENT
        )

        if (
            not code_tokens
            or code_tokens[-1].kind is not TokenKind.END_OF_FILE
        ):
            raise ValueError(
                "Lex result must end with an END_OF_FILE token."
            )

        self._cursor = _Cursor(
            code_tokens,
        )
        self._diagnostics: list[ParseDiagnostic] = []
        self._sentence_terminated = False

    def parse(
        self,
    ) -> ParseResult:
        """Parse the token stream into one compilation unit."""

        start = self._cursor.current().span.start

        if not self._at_division_header(
            "IDENTIFICATION",
        ):
            self._error(
                "Expected IDENTIFICATION DIVISION.",
                self._cursor.current(),
            )

            return ParseResult(
                unit=None,
                diagnostics=tuple(
                    self._diagnostics,
                ),
            )

        identification = self._parse_identification_division()
        environment = None
        data = None
        procedure = None

        if self._at_division_header(
            "ENVIRONMENT",
        ):
            environment = self._parse_environment_division()

        if self._at_division_header(
            "DATA",
        ):
            data = self._parse_data_division()

        if self._at_division_header(
            "PROCEDURE",
        ):
            procedure = self._parse_procedure_division()

        if self._at_end_program_marker():
            self._cursor.advance()
            self._cursor.advance()

            if self._cursor.current().kind is not TokenKind.PERIOD:
                self._cursor.advance()

            self._expect_period()

        while not self._cursor.at_end():
            token = self._cursor.current()
            self._error(
                f"Unexpected token after PROCEDURE DIVISION: "
                f"{token.text!r}.",
                token,
            )
            self._cursor.advance()

        unit = CompilationUnitNode(
            identification=identification,
            environment=environment,
            data=data,
            procedure=procedure,
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

        return ParseResult(
            unit=unit,
            diagnostics=tuple(
                self._diagnostics,
            ),
        )

    # --- shared helpers ----------------------------------------------

    def _error(
        self,
        message: str,
        token: Token,
    ) -> None:
        """Record one parser diagnostic at a token's position."""

        self._diagnostics.append(
            ParseDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                message=message,
                position=token.span.start,
            ),
        )

    def _at_division_header(
        self,
        name: str,
    ) -> bool:
        """Return whether the cursor is at `NAME DIVISION`."""

        return (
            _word(
                self._cursor.current(),
            )
            == name
            and _word(
                self._cursor.peek(
                    1,
                ),
            )
            == "DIVISION"
        )

    def _at_any_division_header(
        self,
    ) -> bool:
        """Return whether the cursor is at any recognized division header."""

        return any(
            self._at_division_header(
                name,
            )
            for name in _DIVISION_NAMES
        )

    def _at_data_section_header(
        self,
    ) -> bool:
        """Return whether the cursor is at `NAME SECTION` in the data division."""

        return (
            _word(
                self._cursor.current(),
            )
            in _DATA_SECTION_NAMES
            and _word(
                self._cursor.peek(
                    1,
                ),
            )
            == "SECTION"
        )

    def _at_procedure_section_header(
        self,
    ) -> bool:
        """Return whether the cursor is at a procedure division section header."""

        current_word = _word(
            self._cursor.current(),
        )

        return (
            bool(
                current_word,
            )
            and current_word not in STATEMENT_VERBS
            and _word(
                self._cursor.peek(
                    1,
                ),
            )
            == "SECTION"
        )

    def _at_paragraph_header(
        self,
    ) -> bool:
        """Return whether the cursor is at a procedure division paragraph name."""

        current_word = _word(
            self._cursor.current(),
        )

        return (
            bool(
                current_word,
            )
            and current_word not in STATEMENT_VERBS
            and self._cursor.peek(
                1,
            ).kind
            is TokenKind.PERIOD
        )

    def _at_level_number(
        self,
    ) -> bool:
        """Return whether the cursor is at a data item level number."""

        token = self._cursor.current()

        return (
            token.kind is TokenKind.NUMERIC_LITERAL
            and isinstance(
                token.value,
                int,
            )
        )

    def _at_statement_boundary(
        self,
    ) -> bool:
        """Return whether the cursor has left the current statement list.

        This treats "a word immediately followed by a period" as a
        boundary (a paragraph name). That heuristic is only safe when
        deciding whether to *start* a new statement — use
        `_at_division_boundary_only` instead inside a loop that is
        consuming a statement's own trailing operand tokens, since
        those are almost always immediately followed by a period too.
        """

        return (
            self._cursor.at_end()
            or self._at_any_division_header()
            or self._at_procedure_section_header()
            or self._at_paragraph_header()
            or self._at_end_program_marker()
        )

    def _at_division_boundary_only(
        self,
    ) -> bool:
        """Return whether the cursor is at end-of-file, a division header,
        or an `END PROGRAM` marker."""

        return (
            self._cursor.at_end()
            or self._at_any_division_header()
            or self._at_end_program_marker()
        )

    def _at_end_program_marker(
        self,
    ) -> bool:
        """Return whether the cursor is at an `END PROGRAM` marker.

        `END PROGRAM program-name.` terminates a compilation unit (used
        for multi-program source and as good practice for single
        programs). It is not modeled as an AST node yet, but every
        statement/operand loop must recognize and stop at it rather
        than silently absorbing the program name as an operand token.
        """

        return (
            _word(
                self._cursor.current(),
            )
            == "END"
            and _word(
                self._cursor.peek(
                    1,
                ),
            )
            == "PROGRAM"
        )

    def _at_next_verb(
        self,
    ) -> bool:
        """Return whether a new statement verb starts at the cursor.

        Multiple statements may share one sentence with no periods
        between them (for example `MOVE A TO B MOVE C TO D.`); operand
        token consumption for the current statement must stop as soon
        as the next statement's verb begins.
        """

        token = self._cursor.current()

        return (
            token.kind is TokenKind.RESERVED_WORD
            and token.text.upper() in STATEMENT_VERBS
        )

    def _at_structural_terminator(
        self,
    ) -> bool:
        """Return whether an enclosing scope-terminator keyword is next.

        Leaf statement parsers (DISPLAY, MOVE, and so on) do not track
        which scopes enclose them; without this check they would
        happily consume `END-IF`, `END-PERFORM`, `ELSE`, or `WHEN` as
        if it were an ordinary operand token.
        """

        token = self._cursor.current()

        return (
            token.kind is TokenKind.RESERVED_WORD
            and token.text.upper() in _STRUCTURAL_TERMINATORS
        )

    def _is_word_current(
        self,
        *words: str,
    ) -> bool:
        """Return whether the cursor's current token matches one of `words`."""

        return _word(
            self._cursor.current(),
        ) in words

    def _expect_period(
        self,
    ) -> None:
        """Consume a required period, recording a diagnostic if absent."""

        if self._cursor.current().kind is TokenKind.PERIOD:
            self._cursor.advance()
        else:
            self._error(
                "Expected '.'.",
                self._cursor.current(),
            )

    def _consume_optional_period(
        self,
    ) -> None:
        """Consume a trailing period if present, marking sentence end."""

        if self._cursor.current().kind is TokenKind.PERIOD:
            self._cursor.advance()
            self._sentence_terminated = True

    def _skip_to_period_or_division(
        self,
    ) -> None:
        """Advance past tokens until a period is consumed or a division starts."""

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
        ):
            token = self._cursor.advance()

            if token.kind is TokenKind.PERIOD:
                return

    # --- identification / environment divisions -----------------------

    def _parse_identification_division(
        self,
    ) -> IdentificationDivisionNode:
        """Parse the identification division."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        self._cursor.advance()
        self._expect_period()

        program_name: str | None = None

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
        ):
            token = self._cursor.current()

            if _word(
                token,
            ) == "PROGRAM-ID":
                self._cursor.advance()

                if self._cursor.current().kind is TokenKind.PERIOD:
                    self._cursor.advance()

                if (
                    self._cursor.current().kind is TokenKind.PERIOD
                    or self._at_any_division_header()
                ):
                    self._error(
                        "Expected a program name after PROGRAM-ID.",
                        token,
                    )
                else:
                    program_name = self._cursor.advance().text

                self._skip_to_period_or_division()
            else:
                self._skip_to_period_or_division()

        if program_name is None:
            self._error(
                "Expected PROGRAM-ID in IDENTIFICATION DIVISION.",
                self._cursor.current(),
            )
            program_name = "UNKNOWN"

        return IdentificationDivisionNode(
            program_name=program_name,
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_environment_division(
        self,
    ) -> EnvironmentDivisionNode:
        """Parse the environment division as an opaque block."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        self._cursor.advance()
        self._expect_period()

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
        ):
            self._cursor.advance()

        return EnvironmentDivisionNode(
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    # --- data division -------------------------------------------------

    def _parse_data_division(
        self,
    ) -> DataDivisionNode:
        """Parse the data division."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        self._cursor.advance()
        self._expect_period()

        sections: list[DataSectionNode] = []

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
        ):
            if self._at_data_section_header():
                sections.append(
                    self._parse_data_section(),
                )
            else:
                token = self._cursor.current()
                self._error(
                    "Expected a data division section header, "
                    f"found {token.text!r}.",
                    token,
                )
                self._cursor.advance()

        return DataDivisionNode(
            sections=tuple(
                sections,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_data_section(
        self,
    ) -> DataSectionNode:
        """Parse one data division section (WORKING-STORAGE, and so on)."""

        start = self._cursor.current().span.start
        name_token = self._cursor.advance()
        self._cursor.advance()
        self._expect_period()

        items: list[DataItemNode] = []

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
            and not self._at_data_section_header()
        ):
            if self._at_level_number() or self._is_word_current(
                "FD",
                "SD",
            ):
                items.append(
                    self._parse_data_item(),
                )
            else:
                token = self._cursor.current()
                self._error(
                    "Expected a data item level number, "
                    f"found {token.text!r}.",
                    token,
                )
                self._skip_to_period_or_division()

        return DataSectionNode(
            name=name_token.text.upper(),
            items=tuple(
                items,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_data_item(
        self,
    ) -> DataItemNode:
        """Parse one data description entry."""

        start = self._cursor.current().span.start
        level_token = self._cursor.advance()
        level_number = (
            level_token.value
            if isinstance(
                level_token.value,
                int,
            )
            else 0
        )
        name: str | None = None

        next_token = self._cursor.current()

        if (
            next_token.kind is TokenKind.IDENTIFIER
        ):
            name = self._cursor.advance().text
        elif _word(
            next_token,
        ) == "FILLER":
            self._cursor.advance()

        clauses: list[DataDescriptionClause] = []

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._at_any_division_header()
            and not self._at_data_section_header()
        ):
            clauses.append(
                self._parse_data_clause(),
            )

        if self._cursor.current().kind is TokenKind.PERIOD:
            self._cursor.advance()

        return DataItemNode(
            level_number=level_number,
            name=name,
            clauses=tuple(
                clauses,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_data_clause(
        self,
    ) -> DataDescriptionClause:
        """Parse one clause of a data description entry."""

        start = self._cursor.current().span.start
        keyword_token = self._cursor.advance()
        keyword = _word(
            keyword_token,
        ) or keyword_token.text.upper()
        tokens: list[Token] = [
            keyword_token,
        ]

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._at_any_division_header()
            and not self._at_data_section_header()
            and _word(
                self._cursor.current(),
            )
            not in _DATA_CLAUSE_KEYWORDS
        ):
            tokens.append(
                self._cursor.advance(),
            )

        return DataDescriptionClause(
            keyword=keyword,
            tokens=tuple(
                tokens,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    # --- procedure division ---------------------------------------------

    def _parse_procedure_division(
        self,
    ) -> ProcedureDivisionNode:
        """Parse the procedure division."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        self._cursor.advance()
        self._skip_to_period_or_division()

        paragraphs: list[ParagraphNode] = []
        sections: list[ProcedureSectionNode] = []

        leading_statements = self._parse_statement_list()

        if leading_statements:
            paragraphs.append(
                ParagraphNode(
                    name=None,
                    statements=tuple(
                        leading_statements,
                    ),
                    span=SourceSpan(
                        start=start,
                        end=self._cursor.last_end,
                    ),
                ),
            )

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
            and not self._at_end_program_marker()
        ):
            if self._at_procedure_section_header():
                sections.append(
                    self._parse_procedure_section(),
                )
            elif self._at_paragraph_header():
                paragraphs.append(
                    self._parse_paragraph(),
                )
            else:
                token = self._cursor.current()
                self._error(
                    "Expected a paragraph or section name, "
                    f"found {token.text!r}.",
                    token,
                )
                self._cursor.advance()

        return ProcedureDivisionNode(
            paragraphs=tuple(
                paragraphs,
            ),
            sections=tuple(
                sections,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_procedure_section(
        self,
    ) -> ProcedureSectionNode:
        """Parse one named section in the procedure division."""

        start = self._cursor.current().span.start
        name_token = self._cursor.advance()
        self._cursor.advance()
        self._expect_period()

        paragraphs: list[ParagraphNode] = []
        leading_statements = self._parse_statement_list()

        if leading_statements:
            paragraphs.append(
                ParagraphNode(
                    name=None,
                    statements=tuple(
                        leading_statements,
                    ),
                    span=SourceSpan(
                        start=start,
                        end=self._cursor.last_end,
                    ),
                ),
            )

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
            and not self._at_procedure_section_header()
            and self._at_paragraph_header()
        ):
            paragraphs.append(
                self._parse_paragraph(),
            )

        return ProcedureSectionNode(
            name=name_token.text,
            paragraphs=tuple(
                paragraphs,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_paragraph(
        self,
    ) -> ParagraphNode:
        """Parse one named paragraph in the procedure division."""

        start = self._cursor.current().span.start
        name_token = self._cursor.advance()
        self._expect_period()

        statements = self._parse_statement_list()

        return ParagraphNode(
            name=name_token.text,
            statements=tuple(
                statements,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_statement_list(
        self,
        *,
        terminators: frozenset[str] = frozenset(),
    ) -> list[object]:
        """Parse a list of statements until a boundary or terminator."""

        is_nested = bool(
            terminators,
        )
        statements: list[object] = []

        while True:
            if is_nested and self._sentence_terminated:
                break

            if not is_nested:
                self._sentence_terminated = False

            if self._at_statement_boundary():
                break

            token = self._cursor.current()

            if (
                is_nested
                and token.kind is TokenKind.RESERVED_WORD
                and token.text.upper() in terminators
            ):
                break

            if token.kind is TokenKind.PERIOD:
                self._cursor.advance()
                self._sentence_terminated = True

                if is_nested:
                    break

                continue

            statement = self._parse_statement()

            if statement is not None:
                statements.append(
                    statement,
                )

        return statements

    def _parse_statement(
        self,
    ) -> object | None:
        """Parse one procedure division statement."""

        token = self._cursor.current()
        word = _word(
            token,
        )

        if word == "MOVE":
            return self._parse_move()

        if word == "DISPLAY":
            return self._parse_display()

        if word == "STOP":
            return self._parse_stop_run()

        if word == "GOBACK":
            return self._parse_goback()

        if word == "IF":
            return self._parse_if()

        if word == "PERFORM":
            return self._parse_perform()

        if word == "EVALUATE":
            return self._parse_evaluate()

        if token.kind is TokenKind.RESERVED_WORD:
            return self._parse_generic_statement()

        self._error(
            f"Expected a statement, found {token.text!r}.",
            token,
        )
        self._cursor.advance()

        return None

    def _parse_generic_statement(
        self,
    ) -> GenericStatement:
        """Parse a statement whose verb is not given dedicated structure."""

        start = self._cursor.current().span.start
        verb_token = self._cursor.advance()
        verb = _word(
            verb_token,
        )
        scope_terminator = f"END-{verb}"
        tokens: list[Token] = [
            verb_token,
        ]

        while not self._cursor.at_end():
            current = self._cursor.current()

            if current.kind is TokenKind.PERIOD:
                self._cursor.advance()
                self._sentence_terminated = True
                break

            if (
                current.kind is TokenKind.RESERVED_WORD
                and current.text.upper() == scope_terminator
            ):
                self._cursor.advance()
                break

            if (
                self._at_division_boundary_only()
                or self._at_next_verb()
                or self._at_structural_terminator()
            ):
                break

            tokens.append(
                self._cursor.advance(),
            )

        return GenericStatement(
            verb=verb,
            tokens=tuple(
                tokens,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_move(
        self,
    ) -> MoveStatement:
        """Parse a MOVE statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        source_tokens: list[Token] = []

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._is_word_current(
                "TO",
            )
            and not self._at_division_boundary_only()
            and not self._at_next_verb()
            and not self._at_structural_terminator()
        ):
            source_tokens.append(
                self._cursor.advance(),
            )

        target_names: list[str] = []

        if self._is_word_current(
            "TO",
        ):
            self._cursor.advance()

            while (
                not self._cursor.at_end()
                and self._cursor.current().kind is not TokenKind.PERIOD
                and not self._at_division_boundary_only()
                and not self._at_next_verb()
                and not self._at_structural_terminator()
            ):
                token = self._cursor.current()

                if token.kind in (
                    TokenKind.IDENTIFIER,
                    TokenKind.RESERVED_WORD,
                ):
                    target_names.append(
                        token.text,
                    )

                self._cursor.advance()

        self._consume_optional_period()

        return MoveStatement(
            source_tokens=tuple(
                source_tokens,
            ),
            target_names=tuple(
                target_names,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_display(
        self,
    ) -> DisplayStatement:
        """Parse a DISPLAY statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        operand_tokens: list[Token] = []

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._at_division_boundary_only()
            and not self._at_next_verb()
            and not self._at_structural_terminator()
        ):
            operand_tokens.append(
                self._cursor.advance(),
            )

        self._consume_optional_period()

        return DisplayStatement(
            operand_tokens=tuple(
                operand_tokens,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_stop_run(
        self,
    ) -> StopRunStatement:
        """Parse a STOP RUN statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()

        if self._is_word_current(
            "RUN",
        ):
            # Handled explicitly: bare "RUN" is not itself a statement
            # verb, so the generic boundary check below would mistake
            # "RUN." for a paragraph name.
            self._cursor.advance()

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._at_division_boundary_only()
            and not self._at_next_verb()
            and not self._at_structural_terminator()
        ):
            self._cursor.advance()

        self._consume_optional_period()

        return StopRunStatement(
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_goback(
        self,
    ) -> GobackStatement:
        """Parse a GOBACK statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()

        while (
            not self._cursor.at_end()
            and self._cursor.current().kind is not TokenKind.PERIOD
            and not self._at_division_boundary_only()
            and not self._at_next_verb()
            and not self._at_structural_terminator()
        ):
            self._cursor.advance()

        self._consume_optional_period()

        return GobackStatement(
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_if(
        self,
    ) -> IfStatement:
        """Parse an IF / ELSE / END-IF statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        condition_tokens: list[Token] = []

        while True:
            if self._cursor.at_end() or self._at_division_boundary_only():
                break

            current = self._cursor.current()

            if current.kind is TokenKind.PERIOD:
                break

            if current.kind is TokenKind.RESERVED_WORD:
                word = current.text.upper()

                if word == "THEN":
                    self._cursor.advance()
                    break

                if (
                    word in STATEMENT_VERBS
                    or word in _STRUCTURAL_TERMINATORS
                ):
                    break

            condition_tokens.append(
                self._cursor.advance(),
            )

        then_statements = tuple(
            self._parse_statement_list(
                terminators=frozenset(
                    {
                        "ELSE",
                        "END-IF",
                    },
                ),
            ),
        )
        else_statements: tuple[object, ...] = ()

        if not self._sentence_terminated:
            if self._is_word_current(
                "ELSE",
            ):
                self._cursor.advance()
                else_statements = tuple(
                    self._parse_statement_list(
                        terminators=frozenset(
                            {
                                "END-IF",
                            },
                        ),
                    ),
                )

            if (
                not self._sentence_terminated
                and self._is_word_current(
                    "END-IF",
                )
            ):
                self._cursor.advance()
                self._consume_optional_period()

        return IfStatement(
            condition_tokens=tuple(
                condition_tokens,
            ),
            then_statements=then_statements,
            else_statements=else_statements,
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_perform(
        self,
    ) -> PerformStatement:
        """Parse a PERFORM statement (out-of-line, inline, or both)."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        target_name: str | None = None
        through_name: str | None = None

        if (
            not self._at_division_boundary_only()
            and self._cursor.current().kind is not TokenKind.PERIOD
        ):
            current = self._cursor.current()
            current_word = _word(
                current,
            )
            # "PERFORM identifier TIMES" is a bounded inline loop where
            # the identifier is a data-name holding the repeat count —
            # not an out-of-line paragraph target, even though it is
            # otherwise indistinguishable from one at this position.
            followed_by_times = (
                _word(
                    self._cursor.peek(
                        1,
                    ),
                )
                == "TIMES"
            )
            looks_like_target = (
                not followed_by_times
                and (
                    current.kind is TokenKind.IDENTIFIER
                    or (
                        current.kind is TokenKind.RESERVED_WORD
                        and current_word not in STATEMENT_VERBS
                        and current_word not in _STRUCTURAL_TERMINATORS
                        and current_word
                        not in (
                            "UNTIL",
                            "VARYING",
                            "TIMES",
                            "WITH",
                            "TEST",
                        )
                    )
                )
            )

            if looks_like_target:
                target_name = self._cursor.advance().text

                if self._is_word_current(
                    "THRU",
                    "THROUGH",
                ):
                    self._cursor.advance()
                    through_name = self._cursor.advance().text

        modifier_tokens: list[Token] = []
        stopped_reason: str | None = None

        while not self._cursor.at_end():
            if self._at_division_boundary_only():
                stopped_reason = "boundary"
                break

            current = self._cursor.current()

            if current.kind is TokenKind.PERIOD:
                stopped_reason = "period"
                break

            if (
                current.kind is TokenKind.RESERVED_WORD
                and current.text.upper() == "END-PERFORM"
            ):
                stopped_reason = "end-perform"
                break

            if (
                current.kind is TokenKind.RESERVED_WORD
                and current.text.upper() in _STRUCTURAL_TERMINATORS
            ):
                stopped_reason = "boundary"
                break

            if (
                current.kind is TokenKind.RESERVED_WORD
                and current.text.upper() in STATEMENT_VERBS
            ):
                stopped_reason = "verb"
                break

            modifier_tokens.append(
                self._cursor.advance(),
            )

        body: tuple[object, ...] = ()

        # An out-of-line PERFORM (it named a target paragraph) is a
        # complete statement once its optional UNTIL/VARYING/TIMES
        # modifier ends — it never has an inline body or END-PERFORM,
        # even if a new statement verb happens to follow immediately.
        if target_name is not None:
            stopped_reason = None

        if stopped_reason == "verb":
            body = tuple(
                self._parse_statement_list(
                    terminators=frozenset(
                        {
                            "END-PERFORM",
                        },
                    ),
                ),
            )

            if (
                not self._sentence_terminated
                and self._is_word_current(
                    "END-PERFORM",
                )
            ):
                self._cursor.advance()
        elif stopped_reason == "end-perform":
            self._cursor.advance()

        self._consume_optional_period()

        return PerformStatement(
            target_name=target_name,
            through_name=through_name,
            modifier_tokens=tuple(
                modifier_tokens,
            ),
            body=body,
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_evaluate(
        self,
    ) -> EvaluateStatement:
        """Parse an EVALUATE / WHEN / END-EVALUATE statement."""

        start = self._cursor.current().span.start
        self._cursor.advance()
        subject_tokens: list[Token] = []

        while (
            not self._cursor.at_end()
            and not self._at_division_boundary_only()
        ):
            current = self._cursor.current()

            if current.kind is TokenKind.PERIOD:
                break

            if self._is_word_current(
                "WHEN",
            ) or self._at_structural_terminator():
                break

            subject_tokens.append(
                self._cursor.advance(),
            )

        branches: list[EvaluateWhenBranch] = []

        while (
            not self._sentence_terminated
            and self._is_word_current(
                "WHEN",
            )
        ):
            branch_start = self._cursor.current().span.start
            self._cursor.advance()
            condition_tokens: list[Token] = []

            while (
                not self._cursor.at_end()
                and not self._at_division_boundary_only()
            ):
                current = self._cursor.current()

                if current.kind is TokenKind.PERIOD:
                    break

                if current.kind is TokenKind.RESERVED_WORD and (
                    current.text.upper() in STATEMENT_VERBS
                    or current.text.upper()
                    in _STRUCTURAL_TERMINATORS
                ):
                    break

                condition_tokens.append(
                    self._cursor.advance(),
                )

            branch_statements = tuple(
                self._parse_statement_list(
                    terminators=frozenset(
                        {
                            "WHEN",
                            "END-EVALUATE",
                        },
                    ),
                ),
            )
            branches.append(
                EvaluateWhenBranch(
                    condition_tokens=tuple(
                        condition_tokens,
                    ),
                    statements=branch_statements,
                    span=SourceSpan(
                        start=branch_start,
                        end=self._cursor.last_end,
                    ),
                ),
            )

        if (
            not self._sentence_terminated
            and self._is_word_current(
                "END-EVALUATE",
            )
        ):
            self._cursor.advance()

        self._consume_optional_period()

        return EvaluateStatement(
            subject_tokens=tuple(
                subject_tokens,
            ),
            branches=tuple(
                branches,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )


def parse_cobol_tokens(
    lex_result: LexResult,
) -> ParseResult:
    """Parse a lexer result into one compilation unit."""

    return CobolParser(
        lex_result,
    ).parse()
