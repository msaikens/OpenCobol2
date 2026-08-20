"""Unit tests for COBOL semantic analysis."""

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.diagnostics import (
    DiagnosticSeverity,
)
from opencobol2.language import (
    ProcedureSymbolKind,
    analyze_compilation_unit,
    parse_cobol_tokens,
    tokenize_cobol_source,
)


def _analyze(
    source: str,
    *,
    source_format: CobolSourceFormat = CobolSourceFormat.FIXED,
):
    """Lex, parse, and analyze one COBOL document, asserting a clean unit."""

    lex_result = tokenize_cobol_source(
        source,
        source_format=source_format,
    )
    assert lex_result.diagnostics == ()

    parse_result = parse_cobol_tokens(
        lex_result,
    )
    assert parse_result.diagnostics == (), parse_result.diagnostics

    return analyze_compilation_unit(
        parse_result.unit,
    )


_PROGRAM_HEADER = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. TEST.\n"
)


def test_rejects_non_compilation_unit() -> None:
    with pytest.raises(
        TypeError,
        match="must be CompilationUnitNode",
    ):
        analyze_compilation_unit("not a unit")  # type: ignore[arg-type]


def test_no_data_or_procedure_division_yields_empty_tables() -> None:
    result = _analyze(
        _PROGRAM_HEADER,
    )

    assert result.symbol_table.data_symbols == ()
    assert result.symbol_table.procedure_symbols == ()
    assert result.diagnostics == ()


# --- data symbol nesting -----------------------------------------------


def _data_source(
    body: str,
) -> str:
    return (
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        + "       WORKING-STORAGE SECTION.\n"
        + body
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
    )


def test_group_and_elementary_item_nesting() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  WS-NAME  PIC X(20).\n"
            "           05  WS-CODE  PIC 9.\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-RECORD"].parent_name is None
    assert symbols["WS-NAME"].parent_name == "WS-RECORD"
    assert symbols["WS-CODE"].parent_name == "WS-RECORD"


def test_sibling_groups_do_not_nest_under_each_other() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-A.\n"
            "           05  WS-A-FIELD  PIC X.\n"
            "       01  WS-B.\n"
            "           05  WS-B-FIELD  PIC X.\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-A-FIELD"].parent_name == "WS-A"
    assert symbols["WS-B-FIELD"].parent_name == "WS-B"
    assert symbols["WS-B"].parent_name is None


def test_condition_name_attached_to_preceding_item() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-STATUS  PIC X.\n"
            "           88  WS-ACTIVE  VALUE 'A'.\n"
            "           88  WS-DONE    VALUE 'D'.\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-ACTIVE"].is_condition_name is True
    assert symbols["WS-ACTIVE"].parent_name == "WS-STATUS"
    assert symbols["WS-DONE"].parent_name == "WS-STATUS"


def test_level_77_is_always_standalone() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  WS-FIELD  PIC X.\n"
            "       77  WS-COUNTER  PIC 9(5).\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-COUNTER"].parent_name is None
    assert symbols["WS-COUNTER"].level_number == 77


def test_renames_entry_is_registered() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  WS-A  PIC X.\n"
            "           05  WS-B  PIC X.\n"
            "       66  WS-COMBINED RENAMES WS-A.\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-COMBINED"].is_renames is True


def test_renames_parent_name_is_the_enclosing_record_not_the_last_sibling() -> None:
    # Editor §Semantic-9: `parent_name` used to be taken from whatever
    # was on top of the level-nesting stack (the most recently
    # processed *sibling*), not the enclosing 01-level record.
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  WS-A  PIC X.\n"
            "           05  WS-B  PIC X.\n"
            "       66  WS-COMBINED RENAMES WS-A.\n",
        ),
    )
    symbols = {
        symbol.name: symbol
        for symbol in result.symbol_table.data_symbols
    }

    assert symbols["WS-COMBINED"].parent_name == "WS-RECORD"


def test_duplicate_sibling_data_item_names_report_error() -> None:
    # Editor §Semantic-3: no duplicate-name detection existed at all
    # for DATA DIVISION items.
    result = _analyze(
        _data_source(
            "       01  WS-GROUP.\n"
            "           05  WS-FIELD  PIC X.\n"
            "           05  WS-FIELD  PIC X(9).\n",
        ),
    )

    assert result.has_errors is True
    assert any(
        "Duplicate data item name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_same_name_under_different_parents_is_not_a_duplicate() -> None:
    # The same elementary-item name legitimately recurs under two
    # different groups -- only a true sibling collision is a duplicate.
    result = _analyze(
        _data_source(
            "       01  WS-GROUP-A.\n"
            "           05  WS-FIELD  PIC X.\n"
            "       01  WS-GROUP-B.\n"
            "           05  WS-FIELD  PIC X.\n",
        ),
    )

    assert result.diagnostics == ()


def test_filler_is_not_registered_as_a_symbol() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  FILLER   PIC X(5).\n"
            "           05  WS-CODE  PIC 9.\n",
        ),
    )
    names = [
        symbol.name
        for symbol in result.symbol_table.data_symbols
    ]

    assert "WS-CODE" in names
    assert len(names) == 2


def test_find_data_symbols_is_case_insensitive() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-FIELD  PIC X.\n",
        ),
    )

    assert len(
        result.symbol_table.find_data_symbols(
            "ws-field",
        ),
    ) == 1


# --- procedure symbols and duplicates ------------------------------------


def test_procedure_symbols_include_sections_and_paragraphs() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       SECTION-ONE SECTION.\n"
        "       PARA-A.\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )
    kinds = {
        symbol.name: symbol.kind
        for symbol in result.symbol_table.procedure_symbols
    }

    assert kinds["SECTION-ONE"] is ProcedureSymbolKind.SECTION
    assert kinds["PARA-A"] is ProcedureSymbolKind.PARAGRAPH


def test_duplicate_paragraph_name_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY 'DUPLICATE'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Duplicate procedure division name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_same_paragraph_name_reused_across_sections_is_not_a_duplicate() -> None:
    # Editor §Semantic-1: COBOL legally allows the same paragraph name
    # in different sections, disambiguated by `PERFORM x IN
    # section-name` -- this used to raise a false "duplicate procedure
    # division name" ERROR.
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       SECTION-ONE SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'ONE'.\n"
        "       SECTION-TWO SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'TWO'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()
    names = [
        symbol.name
        for symbol in result.symbol_table.procedure_symbols
        if symbol.name == "COMMON-EXIT"
    ]
    assert names == [
        "COMMON-EXIT",
        "COMMON-EXIT",
    ]


def test_duplicate_paragraph_name_within_one_section_still_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       SECTION-ONE SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'ONE'.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'TWO'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Duplicate procedure division name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_duplicate_section_name_still_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       SECTION-ONE SECTION.\n"
        "           DISPLAY 'ONE'.\n"
        "       SECTION-ONE SECTION.\n"
        "           DISPLAY 'TWO'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Duplicate procedure division name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_unqualified_reference_to_a_cross_section_duplicate_is_ambiguous() -> None:
    # Editor §Semantic-5: now that Semantic-1 legitimately allows the
    # same paragraph name in two sections, an unqualified reference to
    # it is a real, reachable ambiguity -- previously unreachable since
    # every such duplicate was rejected outright at declaration.
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM COMMON-EXIT.\n"
        "       SECTION-ONE SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'ONE'.\n"
        "       SECTION-TWO SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'TWO'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is False
    assert any(
        diagnostic.severity is DiagnosticSeverity.WARNING
        and "Ambiguous reference to paragraph or section" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_perform_in_section_resolves_the_qualifier_as_a_procedure_name() -> None:
    # Editor §Semantic-6: `PERFORM name IN section` used to route the
    # qualifier into a data-name lookup, producing a nonsensical
    # "possibly undefined data name" warning for a real section name.
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM COMMON-EXIT IN SECTION-ONE.\n"
        "       SECTION-ONE SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'ONE'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_perform_in_undefined_section_reports_undefined_procedure_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM COMMON-EXIT IN NO-SUCH-SECTION.\n"
        "       SECTION-ONE SECTION.\n"
        "       COMMON-EXIT.\n"
        "           DISPLAY 'ONE'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Undefined paragraph or section: NO-SUCH-SECTION"
        in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_go_to_a_defined_paragraph_is_clean() -> None:
    # Editor §Semantic-11: `GO TO` used to be checked against the DATA
    # symbol table instead of the procedure symbol table.
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           GO TO SUB-PARA.\n"
        "       SUB-PARA.\n"
        "           DISPLAY 'HI'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_go_to_an_undefined_paragraph_reports_undefined_procedure_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           GO TO TYPO-PARA.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Undefined paragraph or section: TYPO-PARA"
        in diagnostic.message
        for diagnostic in result.diagnostics
    )
    assert not any(
        "data name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_alter_defined_paragraphs_is_clean() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           ALTER PARA-A TO PROCEED TO PARA-B.\n"
        "       PARA-A.\n"
        "           DISPLAY 'A'.\n"
        "       PARA-B.\n"
        "           DISPLAY 'B'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_condition_name_used_as_move_target_reports_error() -> None:
    # Editor §Semantic-10: an 88-level condition-name is illegal as a
    # MOVE receiving field, but used to analyze cleanly with zero
    # diagnostics.
    source = (
        _data_source(
            "       01  WS-FLAG  PIC X.\n"
            "           88  WS-DONE  VALUE 'Y'.\n",
        ).replace(
            "           STOP RUN.\n",
            "           MOVE 'D' TO WS-DONE.\n",
        )
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Condition-name cannot be used as a MOVE target"
        in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_redefines_target_is_a_resolved_reference() -> None:
    # Editor §Semantic-4: a name used only inside a data-description
    # clause (REDEFINES, RENAMES, OCCURS DEPENDING ON) used to be
    # entirely invisible to `find_data_references`.
    result = _analyze(
        _data_source(
            "       01  WS-ORIGINAL  PIC 9(10).\n"
            "       01  WS-ALIAS REDEFINES WS-ORIGINAL PIC X(10).\n",
        ),
    )

    assert result.diagnostics == ()
    assert len(
        result.find_data_references(
            "WS-ORIGINAL",
        ),
    ) == 1


def test_occurs_depending_on_target_is_a_resolved_reference() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-COUNT  PIC 9(3).\n"
            "       01  WS-TABLE.\n"
            "           05  WS-ITEM PIC X OCCURS 1 TO 10 "
            "TIMES DEPENDING ON WS-COUNT.\n",
        ),
    )

    assert result.diagnostics == ()
    assert len(
        result.find_data_references(
            "WS-COUNT",
        ),
    ) == 1


def test_renames_thru_target_is_a_resolved_reference() -> None:
    result = _analyze(
        _data_source(
            "       01  WS-RECORD.\n"
            "           05  WS-A  PIC X.\n"
            "           05  WS-B  PIC X.\n"
            "       66  WS-COMBINED RENAMES WS-A THRU WS-B.\n",
        ),
    )

    assert result.diagnostics == ()
    assert len(
        result.find_data_references(
            "WS-B",
        ),
    ) == 1


def test_unnamed_leading_paragraph_is_not_a_symbol() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "           DISPLAY 'NO NAME'\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert result.symbol_table.procedure_symbols == ()


# --- reference resolution ------------------------------------------------


def test_move_to_undefined_data_name_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 1 TO WS-MISSING\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is True
    assert any(
        "Undefined data name: WS-MISSING" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_move_to_defined_data_name_is_clean() -> None:
    source = (
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-FIELD  PIC X.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 'A' TO WS-FIELD\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_ambiguous_data_name_reference_is_a_warning() -> None:
    source = (
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A.\n"
        "           05  WS-FIELD  PIC X.\n"
        "       01  WS-B.\n"
        "           05  WS-FIELD  PIC X.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 'A' TO WS-FIELD\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert result.has_errors is False
    assert any(
        "Ambiguous reference to data name" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_perform_undefined_paragraph_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM MISSING-PARA\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert any(
        "Undefined paragraph or section: MISSING-PARA"
        in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_perform_thru_undefined_reports_error() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM SUB-PARA THRU MISSING-END\n"
        "           STOP RUN.\n"
        "       SUB-PARA.\n"
        "           DISPLAY 'HI'.\n"
    )
    result = _analyze(
        source,
    )

    assert any(
        "Undefined paragraph or section: MISSING-END"
        in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_perform_defined_paragraph_is_clean() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM SUB-PARA\n"
        "           STOP RUN.\n"
        "       SUB-PARA.\n"
        "           DISPLAY 'HI'.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_references_resolved_inside_nested_if_and_perform_bodies() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           IF 1 = 1\n"
        "               PERFORM MISSING-IN-IF\n"
        "           END-IF\n"
        "           PERFORM UNTIL 1 = 2\n"
        "               MOVE 1 TO WS-MISSING-IN-LOOP\n"
        "           END-PERFORM\n"
        "           EVALUATE 1\n"
        "               WHEN 1\n"
        "                   PERFORM MISSING-IN-WHEN\n"
        "           END-EVALUATE\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )
    messages = " ".join(
        diagnostic.message
        for diagnostic in result.diagnostics
    )

    assert "MISSING-IN-IF" in messages
    assert "WS-MISSING-IN-LOOP" in messages
    assert "MISSING-IN-WHEN" in messages


# --- widened token-list coverage (best-effort, WARNING severity) ---------


def _data_procedure_source(
    procedure_body: str,
) -> str:
    return (
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-COUNTER  PIC 9(3).\n"
        "       01  WS-RATE     PIC 9(3)V99.\n"
        "       01  WS-PAY      PIC 9(5)V99.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        + procedure_body
    )


def test_move_source_token_resolved_when_defined() -> None:
    result = _analyze(
        _data_procedure_source(
            "           MOVE WS-RATE TO WS-PAY\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.diagnostics == ()


def test_move_source_token_warns_when_undefined() -> None:
    result = _analyze(
        _data_procedure_source(
            "           MOVE WS-BOGUS TO WS-PAY\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.has_errors is False
    assert any(
        "Possibly undefined data name: WS-BOGUS" in d.message
        for d in result.diagnostics
    )


def test_if_condition_token_resolved() -> None:
    result = _analyze(
        _data_procedure_source(
            "           IF WS-COUNTER > WS-BOGUS-COND\n"
            "               DISPLAY WS-PAY\n"
            "           END-IF\n"
            "           STOP RUN.\n",
        ),
    )

    assert any(
        "Possibly undefined data name: WS-BOGUS-COND" in d.message
        for d in result.diagnostics
    )


def test_perform_varying_modifier_token_resolved() -> None:
    result = _analyze(
        _data_procedure_source(
            "           PERFORM VARYING WS-COUNTER FROM 1 BY 1\n"
            "                   UNTIL WS-COUNTER > 5\n"
            "               DISPLAY WS-COUNTER\n"
            "           END-PERFORM\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.diagnostics == ()


def test_generic_statement_token_resolved() -> None:
    result = _analyze(
        _data_procedure_source(
            "           COMPUTE WS-PAY = WS-COUNTER * WS-RATE\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.diagnostics == ()


def test_generic_statement_token_warns_when_undefined() -> None:
    result = _analyze(
        _data_procedure_source(
            "           ADD WS-BOGUS TO WS-PAY\n"
            "           STOP RUN.\n",
        ),
    )

    assert any(
        "Possibly undefined data name: WS-BOGUS" in d.message
        for d in result.diagnostics
    )


def test_exit_paragraph_does_not_warn_as_an_undefined_data_name() -> None:
    # Editor §Semantic-12: `PARAGRAPH` was missing from the reserved-word
    # table, so `EXIT PARAGRAPH.` produced a false "possibly undefined
    # data name" warning via the generic-statement token scan.
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM UNTIL 1 > 2\n"
        "               EXIT PARAGRAPH\n"
        "           END-PERFORM.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


def test_display_operand_token_resolved() -> None:
    result = _analyze(
        _data_procedure_source(
            "           DISPLAY WS-PAY\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.diagnostics == ()


def test_condition_name_used_in_if_resolves_via_88_level() -> None:
    source = (
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-STATUS  PIC X.\n"
        "           88  WS-DONE  VALUE 'D'.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           IF WS-DONE\n"
        "               STOP RUN\n"
        "           END-IF.\n"
    )
    result = _analyze(
        source,
    )

    assert result.diagnostics == ()


# --- cross-reference index ------------------------------------------------


def test_find_data_references_collects_every_resolved_usage() -> None:
    result = _analyze(
        _data_procedure_source(
            "           MOVE 0 TO WS-COUNTER\n"
            "           DISPLAY WS-COUNTER\n"
            "           STOP RUN.\n",
        ),
    )

    positions = result.find_data_references(
        "ws-counter",
    )

    assert len(positions) == 2


def test_find_data_references_excludes_undefined_names() -> None:
    result = _analyze(
        _data_procedure_source(
            "           MOVE 0 TO WS-BOGUS\n"
            "           STOP RUN.\n",
        ),
    )

    assert result.find_data_references(
        "ws-bogus",
    ) == ()


def test_find_procedure_references_collects_perform_usages() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM SUB-PARA\n"
        "           PERFORM SUB-PARA\n"
        "           STOP RUN.\n"
        "       SUB-PARA.\n"
        "           DISPLAY 'HI'.\n"
    )
    result = _analyze(
        source,
    )

    assert len(
        result.find_procedure_references(
            "SUB-PARA",
        ),
    ) == 2


def test_find_procedure_references_excludes_undefined_names() -> None:
    source = (
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM MISSING-PARA\n"
        "           STOP RUN.\n"
    )
    result = _analyze(
        source,
    )

    assert result.find_procedure_references(
        "MISSING-PARA",
    ) == ()


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
        "TEST-PRINTER.cbl",
        "TEST-PRINTER2.cbl",
        "VIRTUAL-PRINTER.cbl",
    ],
)
def test_real_legacy_file_analyzes_without_crashing(
    filename: str,
) -> None:
    path = _TESTFILES_DIR / filename
    text = path.read_text(
        encoding="utf-8",
    )
    lex_result = tokenize_cobol_source(
        text,
        source_format=CobolSourceFormat.FIXED,
    )
    parse_result = parse_cobol_tokens(
        lex_result,
    )

    result = analyze_compilation_unit(
        parse_result.unit,
    )

    assert result.symbol_table is not None


# --- SymbolTable lookup indexing (correctness + scale) -----------------


def test_find_data_symbols_is_case_insensitive() -> None:
    result = _analyze(
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        + "       WORKING-STORAGE SECTION.\n"
        + "       01 WS-COUNT PIC 9(5).\n"
    )

    assert (
        len(
            result.symbol_table.find_data_symbols(
                "ws-count",
            )
        )
        == 1
    )
    assert (
        result.symbol_table.find_data_symbols(
            "ws-count",
        )[0].name
        == "WS-COUNT"
    )


def test_find_data_symbols_returns_every_duplicate_name() -> None:
    """Two data items sharing a name (legal in different groups) must
    both come back, exactly as the pre-indexing linear scan did --
    ambiguous-reference detection in `_resolve_data_names` depends on
    getting more than one match here."""

    result = _analyze(
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        + "       WORKING-STORAGE SECTION.\n"
        + "       01 GROUP-ONE.\n"
        + "           05 WS-FIELD PIC 9(5).\n"
        + "       01 GROUP-TWO.\n"
        + "           05 WS-FIELD PIC 9(5).\n"
    )

    assert (
        len(
            result.symbol_table.find_data_symbols(
                "WS-FIELD",
            )
        )
        == 2
    )


def test_find_data_symbols_returns_empty_for_an_unknown_name() -> None:
    result = _analyze(
        _PROGRAM_HEADER
        + "       DATA DIVISION.\n"
        + "       WORKING-STORAGE SECTION.\n"
        + "       01 WS-COUNT PIC 9(5).\n"
    )

    assert (
        result.symbol_table.find_data_symbols(
            "NO-SUCH-NAME",
        )
        == ()
    )


def test_find_procedure_symbols_is_case_insensitive() -> None:
    result = _analyze(
        _PROGRAM_HEADER
        + "       PROCEDURE DIVISION.\n"
        + "       MAIN-PARA.\n"
        + "           STOP RUN.\n"
    )

    assert (
        result.symbol_table.find_procedure_symbol(
            "main-para",
        )
        is not None
    )


def test_semantic_analysis_scales_to_many_data_items_and_references() -> (
    None
):
    """Regression guard for a real perf bug: `find_data_symbols`/
    `find_procedure_symbols` used to do a linear scan over every
    symbol on every call, and `_resolve_data_names`/
    `_resolve_identifier_tokens` call one of them once per name
    *reference* -- O(references x symbols), which measured ~800ms of
    GUI-thread-blocking work alone on a ~9,600-line synthetic file
    with 4,800 data items and 4,800 references, re-run on every
    keystroke since live diagnostics analyze on every edit (that's
    what a user reported as the editor "hanging" while backspacing).
    Indexing symbols by name once turned this into a lookup, not a
    scan. The generous 3-second ceiling here is about catching an
    accidental return to O(n^2), not asserting a specific speed.
    """

    import time

    lines = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. SCALETEST.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
    ]

    for index in range(2000):
        lines.append(
            f"       01 WS-FIELD-{index} PIC 9(5).",
        )

    lines.append(
        "       PROCEDURE DIVISION.",
    )

    for index in range(2000):
        lines.append(
            f"       DISPLAY WS-FIELD-{index}.",
        )

    lines.append(
        "       STOP RUN.",
    )
    source = "\n".join(
        lines,
    ) + "\n"

    lex_result = tokenize_cobol_source(
        source,
    )
    parse_result = parse_cobol_tokens(
        lex_result,
    )

    start = time.perf_counter()
    result = analyze_compilation_unit(
        parse_result.unit,
    )
    elapsed = time.perf_counter() - start

    assert len(result.symbol_table.data_symbols) == 2000
    assert elapsed < 3.0
