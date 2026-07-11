"""Unit tests for COBOL semantic analysis."""

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
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
