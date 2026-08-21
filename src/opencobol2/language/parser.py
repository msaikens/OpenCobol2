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

_PIC_CLAUSE_KEYWORDS = frozenset(
    {
        "PIC",
        "PICTURE",
    },
)

_VALUE_CLAUSE_KEYWORDS = frozenset(
    {
        "VALUE",
        "VALUES",
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
    """The AST and diagnostics produced by parsing one COBOL document.

    :ivar unit: The parsed compilation unit, or None if parsing could
        not even establish an IDENTIFICATION DIVISION and gave up.
    :ivar diagnostics: Every diagnostic recorded while parsing, in the
        order encountered. Defaults to empty.
    """

    unit: CompilationUnitNode | None
    diagnostics: tuple[ParseDiagnostic, ...] = ()

    @property
    def has_errors(
        self,
    ) -> bool:
        """Return whether any diagnostic is an error.

        :returns: True if `diagnostics` contains at least one
            diagnostic whose severity is
            :attr:`DiagnosticSeverity.ERROR`, False otherwise.
        """

        return any(
            diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        )


class _Cursor:
    """A position cursor over a fixed token sequence.

    :ivar _tokens: The complete, immutable token sequence being
        walked.
    :ivar _index: The index into `_tokens` of the token under the
        cursor.
    :ivar last_end: The source position immediately after the last
        token consumed by :meth:`advance`, used as the end position
        of AST node spans.
    """

    __slots__ = (
        "_tokens",
        "_index",
        "last_end",
    )

    def __init__(
        self,
        tokens: tuple[Token, ...],
    ) -> None:
        """Initialize the cursor at the start of `tokens`.

        :param tokens: The complete token sequence to walk. Must be
            non-empty.
        :returns: None.
        """

        self._tokens = tokens
        self._index = 0
        self.last_end: SourcePosition = tokens[0].span.start

    def current(
        self,
    ) -> Token:
        """Return the token at the cursor.

        :returns: The token at the current cursor position, without
            consuming it.
        """

        return self._tokens[self._index]

    def peek(
        self,
        offset: int,
    ) -> Token:
        """Return the token `offset` positions ahead of the cursor.

        :param offset: How many tokens ahead of the cursor to look.
        :returns: The token at `offset` positions ahead, without
            consuming anything. Clamped to the final token (the
            END_OF_FILE sentinel) if `offset` would run past the end
            of the token sequence.
        """

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
        """Return whether the cursor is at the end-of-file token.

        :returns: True if the current token is the END_OF_FILE
            sentinel, False otherwise.
        """

        return self.current().kind is TokenKind.END_OF_FILE

    def advance(
        self,
    ) -> Token:
        """Consume and return the token at the cursor.

        :returns: The token that was at the cursor before advancing.
            Also updates `last_end` to that token's end position. The
            cursor does not move past the END_OF_FILE sentinel, so
            calling this repeatedly at end of file keeps returning it.
        """

        token = self.current()

        if token.kind is not TokenKind.END_OF_FILE:
            self._index += 1

        self.last_end = token.span.end

        return token


def _word(
    token: Token,
) -> str:
    """Return a token's upper-cased word text, or '' if not word-like.

    Includes `NUMERIC_LITERAL` tokens so a purely-numeric paragraph or
    section name (`0100.`, a real, historically common IBM-mainframe
    numbering convention) is recognized as a header by
    `_at_paragraph_header`/`_at_procedure_section_header` -- see Editor
    Phase 4 tracker findings Parser-2/Parser-10.

    :param token: The token to inspect.
    :returns: The token's upper-cased text if it is a reserved word,
        identifier, or numeric literal; otherwise the empty string.
    """

    if token.kind in (
        TokenKind.RESERVED_WORD,
        TokenKind.IDENTIFIER,
        TokenKind.NUMERIC_LITERAL,
    ):
        return token.text.upper()

    return ""


def _is_valid_level_number(
    value: int,
) -> bool:
    """Return whether `value` is a legal COBOL data item level number.

    :param value: The numeric level number to validate.
    :returns: True if `value` is 1 through 49, or is one of the
        special level numbers 66 (RENAMES), 77 (independent item), or
        88 (condition-name); False otherwise.
    """

    return 1 <= value <= 49 or value in (
        66,
        77,
        88,
    )


class CobolParser:
    """Parses a COBOL lexer result into an AST.

    :ivar _cursor: The token cursor this parser advances through as it
        recognizes grammar productions.
    :ivar _diagnostics: Every diagnostic recorded so far, in the order
        encountered.
    :ivar _sentence_terminated: Whether the period just consumed ended
        not just the current statement but also every statement list
        enclosing it, per COBOL's implicit scope-termination rule (see
        the module docstring).
    """

    def __init__(
        self,
        lex_result: LexResult,
    ) -> None:
        """Initialize the parser over one lexer result.

        :param lex_result: The lexer output to parse. Comment tokens
            are filtered out before parsing begins.
        :returns: None.
        :raises TypeError: If `lex_result` is not a :class:`LexResult`.
        :raises ValueError: If, after filtering out comments, the
            remaining tokens are empty or do not end with an
            END_OF_FILE token.
        """

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
        """Parse the token stream into one compilation unit.

        :returns: A :class:`ParseResult` whose `unit` is None (with an
            error diagnostic recorded) if the source does not even
            open with an IDENTIFICATION DIVISION header; otherwise a
            populated :class:`CompilationUnitNode` together with every
            diagnostic recorded while parsing it, including one for
            each unexpected token found after the PROCEDURE DIVISION
            (or its optional `END PROGRAM` marker).
        """

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

    def _error(
        self,
        message: str,
        token: Token,
    ) -> None:
        """Record one parser diagnostic at a token's position.

        :param message: The human-readable diagnostic message.
        :param token: The token whose start position the diagnostic is
            attached to.
        :returns: None. Appends a new error-severity
            :class:`ParseDiagnostic` to `_diagnostics`.
        """

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
        """Return whether the cursor is at `NAME DIVISION`.

        :param name: The division name to test for, for example
            `"PROCEDURE"`.
        :returns: True if the current token is `name` and the next
            token is the word `DIVISION`, False otherwise.
        """

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
        """Return whether the cursor is at any recognized division header.

        :returns: True if the cursor is at one of the four COBOL
            division headers (IDENTIFICATION, ENVIRONMENT, DATA,
            PROCEDURE), False otherwise.
        """

        return any(
            self._at_division_header(
                name,
            )
            for name in _DIVISION_NAMES
        )

    def _at_data_section_header(
        self,
    ) -> bool:
        """Return whether the cursor is at `NAME SECTION` in the data division.

        :returns: True if the current token names a recognized data
            division section (WORKING-STORAGE, LOCAL-STORAGE, LINKAGE,
            FILE, SCREEN, or REPORT) and the next token is the word
            `SECTION`, False otherwise.
        """

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
        """Return whether the cursor is at a procedure division section header.

        :returns: True if the current token is a word that is not a
            statement verb and the next token is the word `SECTION`,
            False otherwise.
        """

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
        """Return whether the cursor is at a procedure division paragraph name.

        :returns: True if the current token is a word that is not a
            statement verb and the next token is a period, False
            otherwise.
        """

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
        """Return whether the cursor is at a data item level number.

        :returns: True if the current token is a numeric literal with
            an integer value, False otherwise.
        """

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

        :returns: True if the cursor is at end-of-file, any division
            header, a procedure section header, a paragraph header, or
            an `END PROGRAM` marker, False otherwise.
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
        or an `END PROGRAM` marker.

        :returns: True if the cursor is at end-of-file, any division
            header, or an `END PROGRAM` marker, False otherwise.
        """

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

        :returns: True if the current token is the word `END` and the
            next token is the word `PROGRAM`, False otherwise.
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

        :returns: True if the current token is a reserved word listed
            in `STATEMENT_VERBS`, False otherwise.
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

        :returns: True if the current token is a reserved word listed
            in `_STRUCTURAL_TERMINATORS` (`ELSE`, `END-IF`,
            `END-PERFORM`, `END-EVALUATE`, or `WHEN`), False otherwise.
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
        """Return whether the cursor's current token matches one of `words`.

        :param words: The candidate upper-cased word texts to match
            against.
        :returns: True if the current token's word text (per `_word`)
            is one of `words`, False otherwise.
        """

        return _word(
            self._cursor.current(),
        ) in words

    def _expect_period(
        self,
    ) -> None:
        """Consume a required period, recording a diagnostic if absent.

        :returns: None. Advances past the period if present; otherwise
            records an error diagnostic at the current token without
            advancing.
        """

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
        """Consume a trailing period if present, marking sentence end.

        :returns: None. If the current token is a period, advances
            past it and sets `_sentence_terminated` to True; otherwise
            does nothing.
        """

        if self._cursor.current().kind is TokenKind.PERIOD:
            self._cursor.advance()
            self._sentence_terminated = True

    def _skip_to_period_or_division(
        self,
    ) -> None:
        """Advance past tokens until a period is consumed or a division starts.

        :returns: None. Used to recover from a malformed entry by
            discarding tokens up to its terminating period, or up to
            the next division header if no period is found first.
        """

        while (
            not self._cursor.at_end()
            and not self._at_any_division_header()
        ):
            token = self._cursor.advance()

            if token.kind is TokenKind.PERIOD:
                return

    def _parse_identification_division(
        self,
    ) -> IdentificationDivisionNode:
        """Parse the identification division.

        :returns: The parsed :class:`IdentificationDivisionNode`. If
            no `PROGRAM-ID` paragraph is found, records an error
            diagnostic and substitutes the placeholder program name
            `"UNKNOWN"`.
        """

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
        """Parse the environment division as an opaque block.

        :returns: The parsed :class:`EnvironmentDivisionNode`,
            spanning from the `ENVIRONMENT DIVISION` header to the
            start of the next division header (or end of file). Its
            internal content is not structurally parsed.
        """

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

    def _parse_data_division(
        self,
    ) -> DataDivisionNode:
        """Parse the data division.

        :returns: The parsed :class:`DataDivisionNode` containing
            every recognized section. A token that is neither a
            division header nor a recognized data section header
            records an error diagnostic and is skipped one at a time.
        """

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
        """Parse one data division section (WORKING-STORAGE, and so on).

        :returns: The parsed :class:`DataSectionNode` containing every
            data item found before the next division header or data
            section header. A token that is neither a level number nor
            `FD`/`SD` records an error diagnostic and is recovered from
            by skipping to the next period or division.
        """

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
        """Parse one data description entry.

        :returns: The parsed :class:`DataItemNode`, including its
            level number, optional name (absent for `FILLER` or an
            unnamed entry), and every data description clause found
            before the terminating period. Records an error diagnostic
            if the level number is numeric but not a legal COBOL level
            number (see `_is_valid_level_number`), and delegates to
            `_check_duplicate_data_clauses` for duplicate-clause
            diagnostics.
        """

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

        if (
            level_token.kind is TokenKind.NUMERIC_LITERAL
            and not _is_valid_level_number(
                level_number,
            )
        ):
            self._error(
                "Invalid data item level number: "
                f"{level_number}.",
                level_token,
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

        self._check_duplicate_data_clauses(
            clauses,
        )

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

    def _check_duplicate_data_clauses(
        self,
        clauses: list[DataDescriptionClause],
    ) -> None:
        """Diagnose a second `PIC`/`PICTURE` or `VALUE`/`VALUES` clause
        on one data item.

        Both pairs are true COBOL synonyms of one clause kind, not
        independently repeatable clauses -- unlike a genuinely
        parseable duplicate today, which is silently accepted with the
        last occurrence winning downstream (see the debugger's
        PICTURE/USAGE resolution).

        :param clauses: The data item's already-parsed clauses to
            scan for duplicates.
        :returns: None. Records an error diagnostic for a second
            `PIC`/`PICTURE` clause and, separately, for a second
            `VALUE`/`VALUES` clause.
        """

        pic_seen = False
        value_seen = False

        for clause in clauses:
            if clause.keyword in _PIC_CLAUSE_KEYWORDS:
                if pic_seen:
                    self._error(
                        "Duplicate PIC clause on this data item.",
                        clause.tokens[0],
                    )

                pic_seen = True
            elif clause.keyword in _VALUE_CLAUSE_KEYWORDS:
                if value_seen:
                    self._error(
                        "Duplicate VALUE clause on this data item.",
                        clause.tokens[0],
                    )

                value_seen = True

    def _parse_data_clause(
        self,
    ) -> DataDescriptionClause:
        """Parse one clause of a data description entry.

        :returns: The parsed :class:`DataDescriptionClause`, capturing
            its keyword and every raw token up to (but not including)
            the terminating period, the next division/data-section
            header, or the next recognized data clause keyword.
        """

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

    def _parse_procedure_division(
        self,
    ) -> ProcedureDivisionNode:
        """Parse the procedure division.

        Any statements found directly after the `PROCEDURE DIVISION`
        header, before the first named paragraph or section, are
        collected into a synthetic, unnamed leading
        :class:`ParagraphNode`. That synthetic paragraph's span starts
        at its own first statement rather than at the enclosing
        `PROCEDURE DIVISION` header, so that an editor feature built
        on paragraph spans -- "select this paragraph's text", or
        code folding -- does not end up including the division header
        itself.

        :returns: The parsed :class:`ProcedureDivisionNode`, with
            every top-level paragraph (including the synthetic leading
            paragraph, if any) and every named section. A token that
            is neither a section header nor a paragraph header records
            an error diagnostic and is skipped one at a time.
        """

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
                        start=leading_statements[
                            0
                        ].span.start,
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
        """Parse one named section in the procedure division.

        Mirrors `_parse_procedure_division`'s handling of a synthetic
        leading paragraph: any statements found directly after the
        section header, before its first named paragraph, are
        collected into a synthetic, unnamed leading
        :class:`ParagraphNode` whose span starts at its own first
        statement rather than at the section header, for the same
        editor-feature reason given there.

        :returns: The parsed :class:`ProcedureSectionNode`, with every
            paragraph nested under it (including the synthetic leading
            paragraph, if any).
        """

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
                        start=leading_statements[
                            0
                        ].span.start,
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
        """Parse one named paragraph in the procedure division.

        :returns: The parsed :class:`ParagraphNode`, with every
            statement found in its body.
        """

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
        """Parse a list of statements until a boundary or terminator.

        :param terminators: The reserved words (for example
            `{"ELSE", "END-IF"}`) that end this statement list when
            nested inside an enclosing construct. An empty frozenset
            (the default) means this call is parsing a top-level
            paragraph or section body rather than a nested statement
            list, which changes how a period is handled: at top level
            a period only ends the current sentence and parsing
            continues, while in a nested list it also ends the list
            itself, since a period closes every enclosing statement
            scope at once per COBOL's implicit scope-termination rule.
        :returns: Every statement parsed, in source order.
        """

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
        """Parse one procedure division statement.

        :returns: The parsed statement node for a recognized verb
            (EXIT, MOVE, DISPLAY, STOP, GOBACK, IF, PERFORM, EVALUATE)
            or a :class:`GenericStatement` for any other reserved-word
            verb. Returns None, after recording an error diagnostic
            and advancing past the offending token, if the current
            token is not a reserved word at all.
        """

        token = self._cursor.current()
        word = _word(
            token,
        )

        if word == "EXIT":
            return self._parse_exit()

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

    def _parse_exit(
        self,
    ) -> GenericStatement:
        """Parse an `EXIT`/`EXIT PERFORM`/`EXIT PARAGRAPH`/`EXIT SECTION`/
        `EXIT PROGRAM` statement.

        Handled as its own case rather than falling into
        `_parse_generic_statement`: EXIT's own optional operand keyword
        can itself be a statement verb (`PERFORM`), which the generic
        operand loop's next-verb boundary check would otherwise mistake
        for the start of a brand-new, unrelated statement -- destroying
        `EXIT PERFORM` into a bare `EXIT` plus a phantom out-of-line
        `PerformStatement`, and (when written directly inside a loop
        body rather than nested in an `IF`) letting that phantom
        PERFORM's own modifier scan consume the enclosing loop's real
        `END-PERFORM` as its own terminator.

        :returns: The parsed :class:`GenericStatement` with verb
            `"EXIT"`, including its optional
            `PERFORM`/`PARAGRAPH`/`SECTION`/`PROGRAM` operand keyword
            if present.
        """

        start = self._cursor.current().span.start
        exit_token = self._cursor.advance()
        tokens: list[Token] = [
            exit_token,
        ]

        if self._is_word_current(
            "PERFORM",
            "PARAGRAPH",
            "SECTION",
            "PROGRAM",
        ):
            tokens.append(
                self._cursor.advance(),
            )

        self._consume_optional_period()

        return GenericStatement(
            verb="EXIT",
            tokens=tuple(
                tokens,
            ),
            span=SourceSpan(
                start=start,
                end=self._cursor.last_end,
            ),
        )

    def _parse_generic_statement(
        self,
    ) -> GenericStatement:
        """Parse a statement whose verb is not given dedicated structure.

        :returns: The parsed :class:`GenericStatement`, capturing the
            verb and every raw token up to (and including, where
            present) a matching `END-<VERB>` scope terminator, or up
            to (and including) a terminating period, or up to (but
            excluding) the next division boundary, next statement
            verb, or structural terminator -- whichever comes first.
        """

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
        """Parse a MOVE statement.

        While scanning `TO`-clause target names, a target's own
        subscript (`WS-TABLE(I)`) is not itself another MOVE target --
        only the qualifier keyword and its own subscript, if any, are
        skipped; likewise, an `OF`/`IN` qualifier is not a second
        target name, just a link to the enclosing group that the
        preceding target is qualified by.

        :returns: The parsed :class:`MoveStatement`, with the raw
            source-side tokens and every target data-name found after
            `TO`.
        """

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
            paren_depth = 0

            while (
                not self._cursor.at_end()
                and self._cursor.current().kind is not TokenKind.PERIOD
                and not self._at_division_boundary_only()
                and not self._at_next_verb()
                and not self._at_structural_terminator()
            ):
                token = self._cursor.current()

                if token.kind is TokenKind.LEFT_PARENTHESIS:
                    paren_depth += 1
                elif token.kind is TokenKind.RIGHT_PARENTHESIS:
                    paren_depth = max(
                        0,
                        paren_depth - 1,
                    )
                elif (
                    paren_depth == 0
                    and token.kind
                    in (
                        TokenKind.IDENTIFIER,
                        TokenKind.RESERVED_WORD,
                    )
                    and _word(
                        token,
                    )
                    not in (
                        "OF",
                        "IN",
                    )
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
        """Parse a DISPLAY statement.

        :returns: The parsed :class:`DisplayStatement`, with every raw
            operand token found before the statement ends.
        """

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
        """Parse a STOP RUN statement.

        The optional `RUN` keyword after `STOP` is consumed explicitly
        here rather than left to the generic operand-boundary check
        below: bare `RUN` is not itself a statement verb, so without
        this explicit handling the boundary check would mistake
        `RUN.` for a paragraph name and stop before consuming it.

        :returns: The parsed :class:`StopRunStatement`, with every raw
            operand token found after the optional `RUN` keyword.
        """

        start = self._cursor.current().span.start
        self._cursor.advance()

        if self._is_word_current(
            "RUN",
        ):
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

        return StopRunStatement(
            operand_tokens=tuple(
                operand_tokens,
            ),
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
                    # A purely-numeric paragraph name (`PERFORM 0200`,
                    # the same legacy mainframe numbering style as
                    # Parser-2's header fix) is a legitimate PERFORM
                    # target too, not just an IDENTIFIER/RESERVED_WORD.
                    or current.kind is TokenKind.NUMERIC_LITERAL
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
                    through_candidate = self._cursor.current()
                    through_word = _word(
                        through_candidate,
                    )
                    # Guarded the same way `looks_like_target` above is:
                    # an absent/malformed through-target (source ending
                    # right after THRU, or a period immediately
                    # following it) must not be blindly consumed as the
                    # through-name text -- doing so either swallows the
                    # real statement terminator or, at end of file,
                    # produces an empty string that
                    # `PerformStatement.__post_init__`'s own validation
                    # then rejects by raising uncaught (Parser-4).
                    through_looks_valid = (
                        through_candidate.kind
                        is TokenKind.IDENTIFIER
                        or through_candidate.kind
                        is TokenKind.NUMERIC_LITERAL
                        or (
                            through_candidate.kind
                            is TokenKind.RESERVED_WORD
                            and through_word
                            not in STATEMENT_VERBS
                            and through_word
                            not in _STRUCTURAL_TERMINATORS
                        )
                    )

                    if through_looks_valid:
                        through_name = (
                            self._cursor.advance().text
                        )
                    else:
                        self._error(
                            "Expected a paragraph name after "
                            "THRU/THROUGH.",
                            through_candidate,
                        )

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
