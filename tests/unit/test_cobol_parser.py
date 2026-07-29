"""Unit tests for the COBOL parser."""

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language import (
    CobolParser,
    DisplayStatement,
    EvaluateStatement,
    GenericStatement,
    GobackStatement,
    IfStatement,
    MoveStatement,
    PerformStatement,
    StopRunStatement,
    parse_cobol_tokens,
    tokenize_cobol_source,
)


def _fixed(
    body: str,
) -> str:
    """Wrap a PROCEDURE DIVISION body in a minimal fixed-format program."""

    lines = "\n".join(
        f"           {line}"
        for line in body.strip(
            "\n",
        ).splitlines()
    )

    return (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        f"{lines}\n"
    )


def _parse(
    source: str,
    *,
    source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
):
    """Lex and parse one COBOL source document, asserting no lex errors."""

    lex_result = tokenize_cobol_source(
        source,
        source_format=source_format,
    )
    assert lex_result.diagnostics == (), lex_result.diagnostics

    return parse_cobol_tokens(
        lex_result,
    )


def _statements(
    body: str,
):
    """Parse a PROCEDURE DIVISION body and return MAIN-PARA's statements."""

    result = _parse(
        _fixed(
            body,
        ),
    )
    assert result.diagnostics == (), result.diagnostics

    return result.unit.procedure.paragraphs[0].statements


# --- CobolParser construction ----------------------------------------------


def test_parser_rejects_non_lex_result() -> None:
    with pytest.raises(
        TypeError,
        match="must be LexResult",
    ):
        CobolParser("not a lex result")  # type: ignore[arg-type]


def test_parse_result_has_errors_reflects_diagnostics() -> None:
    result = _parse(
        "       DATA DIVISION.\n",
    )

    assert result.unit is None
    assert result.has_errors is True


# --- identification division -----------------------------------------------


def test_program_name_extracted() -> None:
    result = _parse(
        _fixed(
            "STOP RUN.",
        ),
    )

    assert result.unit.identification.program_name == "TEST"


def test_missing_program_id_reports_error_but_recovers() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       AUTHOR. SOMEONE.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.has_errors is True
    assert result.unit.identification.program_name == "UNKNOWN"
    assert (
        result.unit.procedure.paragraphs[0].name
        == "MAIN-PARA"
    )


def test_unknown_identification_paragraph_is_skipped() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       AUTHOR. SOMEONE.\n"
        "       DATE-WRITTEN. TODAY.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    assert result.unit.identification.program_name == "TEST"


# --- data division -----------------------------------------------------


def test_data_item_with_pic_and_value() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-PAY  PIC 9(5)V99 VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    section = result.unit.data.sections[0]
    assert section.name == "WORKING-STORAGE"
    item = section.items[0]
    assert item.level_number == 1
    assert item.name == "WS-PAY"
    clause_keywords = [
        clause.keyword
        for clause in item.clauses
    ]
    assert clause_keywords == ["PIC", "VALUE"]

    pic_clause = item.clauses[0]
    assert [
        token.text
        for token in pic_clause.tokens
    ] == ["PIC", "9", "(", "5", ")", "V99"]


def test_data_item_filler_has_no_name() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  FILLER  PIC X(3).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    item = result.unit.data.sections[0].items[0]
    assert item.name is None


def test_file_section_fd_entry() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD  FPRINTER.\n"
        "       01  PRINTER-RECORD  PIC X(80).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    section = result.unit.data.sections[0]
    assert section.name == "FILE"
    assert section.items[0].name == "FPRINTER"
    assert section.items[1].name == "PRINTER-RECORD"


def test_multiple_data_items_do_not_bleed_into_each_other() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A  PIC 9(3) VALUE 0.\n"
        "       01  WS-B  PIC 9(3) VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    items = result.unit.data.sections[0].items
    assert [item.name for item in items] == [
        "WS-A",
        "WS-B",
    ]


def test_unexpected_token_in_data_division_reports_error() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       BOGUS SECTION.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.has_errors is True


# --- environment division (opaque) -----------------------------------------


def test_environment_division_is_recognized_but_opaque() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SOURCE-COMPUTER. IBM.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC X.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    assert result.unit.environment is not None
    assert result.unit.data is not None


# --- MOVE / DISPLAY / STOP RUN / GOBACK -------------------------------------


def test_move_single_target() -> None:
    statements = _statements(
        "MOVE 40 TO WS-HOURS.",
    )

    assert len(statements) == 1
    move = statements[0]
    assert isinstance(move, MoveStatement)
    assert move.target_names == ("WS-HOURS",)
    assert [
        token.text
        for token in move.source_tokens
    ] == ["40"]


def test_move_multiple_targets() -> None:
    statements = _statements(
        "MOVE 0 TO WS-A WS-B WS-C.",
    )

    move = statements[0]
    assert move.target_names == (
        "WS-A",
        "WS-B",
        "WS-C",
    )


def test_chained_statements_without_periods_are_all_parsed() -> None:
    statements = _statements(
        """
        MOVE 40 TO WS-HOURS
        MOVE 12.50 TO WS-RATE
        DISPLAY WS-HOURS
        STOP RUN.
        """,
    )

    assert [
        type(statement).__name__
        for statement in statements
    ] == [
        "MoveStatement",
        "MoveStatement",
        "DisplayStatement",
        "StopRunStatement",
    ]


def test_display_operand_tokens() -> None:
    statements = _statements(
        "DISPLAY 'HELLO' WS-NAME.",
    )

    display = statements[0]
    assert isinstance(display, DisplayStatement)
    assert [
        token.text
        for token in display.operand_tokens
    ] == ["'HELLO'", "WS-NAME"]


def test_stop_run_statement() -> None:
    statements = _statements(
        "STOP RUN.",
    )

    assert isinstance(
        statements[0],
        StopRunStatement,
    )


def test_stop_run_followed_by_another_paragraph_has_no_stray_paragraph() -> (
    None
):
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM CLEANUP-PARA\n"
        "           STOP RUN.\n"
        "       CLEANUP-PARA.\n"
        "           DISPLAY 'DONE'.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    paragraph_names = [
        paragraph.name
        for paragraph in result.unit.procedure.paragraphs
    ]
    assert paragraph_names == [
        "MAIN-PARA",
        "CLEANUP-PARA",
    ]


def test_goback_statement() -> None:
    statements = _statements(
        "GOBACK.",
    )

    assert isinstance(
        statements[0],
        GobackStatement,
    )


def test_generic_statement_for_unmodeled_verb() -> None:
    statements = _statements(
        "ADD 1 TO WS-COUNTER.",
    )

    statement = statements[0]
    assert isinstance(statement, GenericStatement)
    assert statement.verb == "ADD"


def test_generic_statement_with_scope_terminator() -> None:
    statements = _statements(
        "ADD 1 TO WS-COUNTER END-ADD STOP RUN.",
    )

    assert [
        type(statement).__name__
        for statement in statements
    ] == [
        "GenericStatement",
        "StopRunStatement",
    ]


def test_generic_statement_with_nested_statement_clause_is_a_known_limitation() -> (
    None
):
    # A verb's ON SIZE ERROR / AT END / ON OVERFLOW clause can contain a
    # nested statement (here DISPLAY). GenericStatement does not model
    # per-verb clause grammar, so ADD's own token consumption stops as
    # soon as the nested DISPLAY verb appears, and the dangling END-ADD
    # that follows is swallowed as an ordinary DISPLAY operand token
    # instead of being recognized as ADD's own scope terminator. This
    # is a documented simplification, not a regression target.
    statements = _statements(
        """
        ADD 1 TO WS-COUNTER ON SIZE ERROR
            DISPLAY 'OVERFLOW'
        END-ADD
        STOP RUN.
        """,
    )

    assert [
        type(statement).__name__
        for statement in statements
    ] == [
        "GenericStatement",
        "DisplayStatement",
        "StopRunStatement",
    ]
    assert statements[1].operand_tokens[-1].text == "END-ADD"


# --- IF / ELSE / END-IF -----------------------------------------------------


def test_if_then_else_end_if() -> None:
    statements = _statements(
        """
        IF WS-PAY > 999
            DISPLAY 'BIG'
        ELSE
            DISPLAY 'SMALL'
        END-IF
        STOP RUN.
        """,
    )

    assert len(statements) == 2
    if_statement = statements[0]
    assert isinstance(if_statement, IfStatement)
    assert len(if_statement.then_statements) == 1
    assert len(if_statement.else_statements) == 1
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


def test_if_without_else() -> None:
    statements = _statements(
        """
        IF WS-PAY > 999
            DISPLAY 'BIG'
        END-IF
        STOP RUN.
        """,
    )

    if_statement = statements[0]
    assert len(if_statement.then_statements) == 1
    assert if_statement.else_statements == ()


def test_if_terminated_implicitly_by_period() -> None:
    statements = _statements(
        """
        IF WS-PAY > 999
            DISPLAY 'BIG'.
        DISPLAY 'AFTER'.
        """,
    )

    assert len(statements) == 2
    if_statement = statements[0]
    assert len(if_statement.then_statements) == 1
    assert if_statement.else_statements == ()
    assert isinstance(
        statements[1],
        DisplayStatement,
    )


def test_nested_if_statements() -> None:
    statements = _statements(
        """
        IF WS-A > 0
            IF WS-B > 0
                DISPLAY 'BOTH'
            END-IF
        END-IF
        STOP RUN.
        """,
    )

    outer_if = statements[0]
    inner_if = outer_if.then_statements[0]
    assert isinstance(inner_if, IfStatement)
    assert len(inner_if.then_statements) == 1


# --- PERFORM ---------------------------------------------------------------


def test_perform_out_of_line_simple() -> None:
    statements = _statements(
        """
        PERFORM CLEANUP-PARA
        STOP RUN.
        """,
    )

    perform = statements[0]
    assert isinstance(perform, PerformStatement)
    assert perform.target_name == "CLEANUP-PARA"
    assert perform.through_name is None
    assert perform.modifier_tokens == ()
    assert perform.body == ()
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


def test_perform_out_of_line_thru() -> None:
    statements = _statements(
        "PERFORM PARA-A THRU PARA-C.",
    )

    perform = statements[0]
    assert perform.target_name == "PARA-A"
    assert perform.through_name == "PARA-C"


def test_perform_out_of_line_with_until_has_no_body() -> None:
    statements = _statements(
        """
        PERFORM CLEANUP-PARA UNTIL WS-DONE
        STOP RUN.
        """,
    )

    perform = statements[0]
    assert perform.target_name == "CLEANUP-PARA"
    assert perform.body == ()
    assert [
        token.text
        for token in perform.modifier_tokens
    ] == ["UNTIL", "WS-DONE"]


def test_perform_inline_with_until_and_body() -> None:
    statements = _statements(
        """
        PERFORM UNTIL WS-HOURS > 5
            DISPLAY WS-HOURS
            ADD 1 TO WS-HOURS
        END-PERFORM
        STOP RUN.
        """,
    )

    perform = statements[0]
    assert perform.target_name is None
    assert len(perform.body) == 2
    assert [
        type(statement).__name__
        for statement in perform.body
    ] == [
        "DisplayStatement",
        "GenericStatement",
    ]


def test_perform_inline_varying() -> None:
    statements = _statements(
        """
        PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 5
            DISPLAY WS-I
        END-PERFORM
        STOP RUN.
        """,
    )

    perform = statements[0]
    assert perform.target_name is None
    assert len(perform.body) == 1
    modifier_text = [
        token.text
        for token in perform.modifier_tokens
    ]
    assert modifier_text[0] == "VARYING"


def test_perform_data_name_times_is_not_mistaken_for_a_target() -> None:
    # "PERFORM identifier TIMES" is a bounded inline loop where the
    # identifier holds the repeat count; it must not be treated as an
    # out-of-line paragraph target just because it's an identifier.
    statements = _statements(
        """
        PERFORM WS-COUNT TIMES
            DISPLAY 'HI'
        END-PERFORM
        STOP RUN.
        """,
    )

    perform = statements[0]
    assert perform.target_name is None
    assert [
        token.text
        for token in perform.modifier_tokens
    ] == ["WS-COUNT", "TIMES"]
    assert len(perform.body) == 1


def test_end_program_marker_is_consumed_cleanly() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
        "       END PROGRAM TEST.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    assert len(
        result.unit.procedure.paragraphs[0].statements,
    ) == 1


# --- EVALUATE ----------------------------------------------------------


def test_evaluate_with_when_branches_and_other() -> None:
    statements = _statements(
        """
        EVALUATE WS-CODE
            WHEN 1
                DISPLAY 'ONE'
            WHEN 2
                DISPLAY 'TWO'
            WHEN OTHER
                DISPLAY 'OTHER'
        END-EVALUATE
        STOP RUN.
        """,
    )

    evaluate = statements[0]
    assert isinstance(evaluate, EvaluateStatement)
    assert len(evaluate.branches) == 3
    assert [
        token.text
        for token in evaluate.branches[2].condition_tokens
    ] == ["OTHER"]
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


# --- procedure division structure ------------------------------------------


def test_procedure_division_with_sections() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       SECTION-ONE SECTION.\n"
        "       PARA-A.\n"
        "           DISPLAY 'A'.\n"
        "       SECTION-TWO SECTION.\n"
        "       PARA-B.\n"
        "           DISPLAY 'B'.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    sections = result.unit.procedure.sections
    assert [section.name for section in sections] == [
        "SECTION-ONE",
        "SECTION-TWO",
    ]
    assert sections[0].paragraphs[0].name == "PARA-A"
    assert sections[1].paragraphs[0].name == "PARA-B"


def test_leading_unnamed_paragraph() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY 'NO PARAGRAPH NAME'\n"
        "           STOP RUN.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    assert result.unit.procedure.paragraphs[0].name is None


# --- Phase 4 fixes (tracker Parser-1/2/3/4/6/7/8/9/10/11/12) ----------------


def test_exit_perform_is_not_destroyed() -> None:
    # Editor §Parser-1: `EXIT PERFORM` nested in an IF used to split into
    # an orphaned GenericStatement('EXIT') plus a phantom PerformStatement.
    statements = _statements(
        "PERFORM UNTIL WS-DONE\n"
        "    IF WS-FLAG = 1\n"
        "        EXIT PERFORM\n"
        "    END-IF\n"
        "    DISPLAY WS-FLAG\n"
        "END-PERFORM\n"
        "STOP RUN.",
    )

    outer_perform = statements[0]
    assert isinstance(
        outer_perform,
        PerformStatement,
    )
    if_statement = outer_perform.body[0]
    exit_statement = if_statement.then_statements[0]

    assert isinstance(
        exit_statement,
        GenericStatement,
    )
    assert exit_statement.verb == "EXIT"
    assert [
        token.text.upper()
        for token in exit_statement.tokens
    ] == ["EXIT", "PERFORM"]
    # No phantom second statement in the IF's THEN branch.
    assert len(if_statement.then_statements) == 1
    # The outer loop's own body is untouched by the nested EXIT PERFORM.
    assert len(outer_perform.body) == 2


def test_exit_perform_in_loop_body_does_not_eat_the_real_end_perform() -> None:
    # Editor §Parser-9: EXIT PERFORM written directly in a loop body (not
    # nested inside an IF) used to have its phantom PerformStatement
    # consume the enclosing loop's real END-PERFORM, silently pulling
    # STOP RUN into the loop body.
    statements = _statements(
        "PERFORM UNTIL WS-DONE\n"
        "    DISPLAY 'X'\n"
        "    EXIT PERFORM\n"
        "END-PERFORM\n"
        "STOP RUN.",
    )

    assert len(statements) == 2
    outer_perform = statements[0]
    assert isinstance(
        outer_perform,
        PerformStatement,
    )
    assert len(outer_perform.body) == 2
    exit_statement = outer_perform.body[1]
    assert isinstance(
        exit_statement,
        GenericStatement,
    )
    assert exit_statement.verb == "EXIT"
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


def test_numeric_paragraph_names_are_recognized_as_headers() -> None:
    # Editor §Parser-2: `0100.`/`0200.` (a real, historically common
    # mainframe numbering convention) used to collapse into one
    # anonymous leading paragraph with two "Expected a statement" errors.
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       0100.\n"
        "           PERFORM 0200\n"
        "           STOP RUN.\n"
        "       0200.\n"
        "           DISPLAY 'IN 0200'.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()
    names = [
        paragraph.name
        for paragraph in result.unit.procedure.paragraphs
    ]
    assert names == ["0100", "0200"]


def test_perform_numeric_paragraph_target() -> None:
    # Editor §Parser-10: `PERFORM 0200` used to fail the target-detection
    # heuristic and swallow the following STOP RUN into a phantom body.
    statements = _statements(
        "PERFORM 0200\nSTOP RUN.",
    )

    assert len(statements) == 2
    perform = statements[0]
    assert isinstance(
        perform,
        PerformStatement,
    )
    assert perform.target_name == "0200"
    assert perform.body == ()
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


def test_move_qualified_target_does_not_leak_the_qualifier_keyword() -> None:
    # Editor §Parser-3: `MOVE x TO field OF group` used to inject the
    # qualifier keyword itself as a bogus third target name.
    statements = _statements(
        "MOVE 'X' TO CUSTOMER-NAME OF CUSTOMER-REC.",
    )
    move = statements[0]

    assert isinstance(
        move,
        MoveStatement,
    )
    assert move.target_names == (
        "CUSTOMER-NAME",
        "CUSTOMER-REC",
    )


def test_move_target_does_not_leak_a_subscript_identifier() -> None:
    # Editor §Parser-11: the same unguarded target loop also captured a
    # subscript variable (`WS-TABLE(I)`) as a bogus second target.
    statements = _statements(
        "MOVE 'X' TO WS-TABLE(I).",
    )
    move = statements[0]

    assert isinstance(
        move,
        MoveStatement,
    )
    assert move.target_names == ("WS-TABLE",)


def test_move_target_numeric_subscript_still_excluded() -> None:
    # Sanity check: a numeric subscript was never captured (only
    # identifier subscripts were affected by Parser-11).
    statements = _statements(
        "MOVE 'X' TO WS-TABLE(1).",
    )
    move = statements[0]

    assert move.target_names == ("WS-TABLE",)


def test_perform_thru_missing_target_does_not_crash() -> None:
    # Editor §Parser-4: `PERFORM PARA-A THRU` at end of file used to
    # crash with an uncaught ValueError from PerformStatement's own
    # non-empty-string validation.
    source = _fixed(
        "PERFORM PARA-A THRU",
    )
    result = _parse(
        source,
    )

    assert result.has_errors is True
    perform = result.unit.procedure.paragraphs[0].statements[0]
    assert isinstance(
        perform,
        PerformStatement,
    )
    assert perform.target_name == "PARA-A"
    assert perform.through_name is None


def test_perform_thru_period_does_not_swallow_the_terminator() -> None:
    # Editor §Parser-4: `PERFORM PARA-A THRU.` used to silently consume
    # the real statement-terminating period as bogus through-name text,
    # with zero diagnostics. It's now correctly diagnosed as malformed
    # (a real, though clearly mistaken, source construct) -- but the key
    # regression check is that the real period is no longer swallowed,
    # so STOP RUN still parses as its own separate statement afterward.
    result = _parse(
        _fixed(
            "PERFORM PARA-A THRU.\nSTOP RUN.",
        ),
    )

    assert result.has_errors is True
    statements = result.unit.procedure.paragraphs[0].statements
    assert len(statements) == 2
    perform = statements[0]
    assert isinstance(
        perform,
        PerformStatement,
    )
    assert perform.target_name == "PARA-A"
    assert perform.through_name is None
    assert isinstance(
        statements[1],
        StopRunStatement,
    )


def test_leading_paragraph_span_starts_at_its_first_statement() -> None:
    # Editor §Parser-6: the synthetic leading-unnamed-paragraph's span
    # used to start at the enclosing PROCEDURE DIVISION header, not its
    # own first statement.
    result = _parse(
        _fixed(
            "DISPLAY 'ONE'\nDISPLAY 'TWO'.",
        ).replace(
            "       MAIN-PARA.\n",
            "",
        ),
    )

    assert result.diagnostics == ()
    paragraph = result.unit.procedure.paragraphs[0]
    first_statement = paragraph.statements[0]

    assert paragraph.span.start == first_statement.span.start
    assert paragraph.span.start != result.unit.procedure.span.start


def test_stop_literal_retains_its_operand_tokens() -> None:
    # Editor §Parser-7: `STOP 'OPERATOR HALT'.` used to discard the
    # literal entirely, making it indistinguishable from a plain STOP RUN.
    statements = _statements(
        "STOP 'OPERATOR HALT'.",
    )
    stop = statements[0]

    assert isinstance(
        stop,
        StopRunStatement,
    )
    assert [
        token.value or token.text
        for token in stop.operand_tokens
    ] == ["OPERATOR HALT"]


def test_stop_run_has_no_operand_tokens() -> None:
    statements = _statements(
        "STOP RUN.",
    )
    stop = statements[0]

    assert stop.operand_tokens == ()


def test_duplicate_pic_clause_is_diagnosed() -> None:
    # Editor §Parser-8: two PIC clauses on one item used to be accepted
    # with no diagnostic at all, with the last one silently winning
    # downstream (the debugger's PICTURE/USAGE resolution).
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC 9(3) PIC X(10) VALUE 1 VALUE 2.\n"
    )
    result = _parse(
        source,
    )

    assert result.has_errors is True
    messages = [
        diagnostic.message
        for diagnostic in result.diagnostics
    ]
    assert any(
        "Duplicate PIC clause" in message
        for message in messages
    )
    assert any(
        "Duplicate VALUE clause" in message
        for message in messages
    )


def test_single_pic_and_value_clause_is_not_flagged() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC 9(3) VALUE 1.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()


def test_invalid_level_number_is_diagnosed() -> None:
    # Editor §Parser-12: a level number outside 01-49/66/77/88 used to
    # be accepted with no diagnostic at all.
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       100  WS-X PIC X.\n"
    )
    result = _parse(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Invalid data item level number" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_valid_level_numbers_are_not_flagged() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-GROUP.\n"
        "           05  WS-FIELD PIC X.\n"
        "       66  WS-RENAME RENAMES WS-FIELD.\n"
        "       01  WS-FLAG PIC X.\n"
        "           88  WS-FLAG-ON VALUE 'Y'.\n"
    )
    result = _parse(
        source,
    )

    assert result.diagnostics == ()


# --- real-world legacy files -------------------------------------------------


_TESTFILES_DIR = (
    Path(__file__).resolve().parents[2]
    / "legacy"
    / "opencobolide"
    / "tests"
    / "testfiles"
)


@pytest.mark.parametrize(
    "filename",
    [
        "HelloWorld.cbl",
        "HelloWorldFree.cbl",
        "HelloWorldLatin1.cbl",
        "TEST-PRINTER.cbl",
        "TEST-PRINTER2.cbl",
        "TEST-PRINTER3.cbl",
        "TEST-SINGLE-QUOTES.cbl",
        "VIRTUAL-PRINTER.cbl",
        "VIRTUAL-PRINTER2.cbl",
    ],
)
def test_real_legacy_file_parses_without_errors(
    filename: str,
) -> None:
    path = _TESTFILES_DIR / filename
    text = None

    for encoding in (
        "utf-8",
        "latin-1",
    ):
        try:
            text = path.read_text(
                encoding=encoding,
            )
            break
        except UnicodeDecodeError:
            continue

    assert text is not None

    source_format = (
        CobolSourceFormat.FREE
        if "Free" in filename
        else CobolSourceFormat.FIXED
    )
    lex_result = tokenize_cobol_source(
        text,
        source_format=source_format,
    )
    assert lex_result.diagnostics == ()

    result = parse_cobol_tokens(
        lex_result,
    )

    assert result.diagnostics == ()
    assert result.unit is not None
    assert result.unit.procedure is not None


def test_malformed_legacy_file_is_correctly_rejected() -> None:
    path = _TESTFILES_DIR / "MALFORMED.cbl"
    text = path.read_text(
        encoding="utf-8",
    )
    lex_result = tokenize_cobol_source(
        text,
        source_format=CobolSourceFormat.FIXED,
    )
    result = parse_cobol_tokens(
        lex_result,
    )

    assert result.has_errors is True
