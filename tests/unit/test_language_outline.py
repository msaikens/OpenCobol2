"""Unit tests for COBOL outline extraction from the real parser."""

from __future__ import annotations

from opencobol2.language import compute_outline


_SAMPLE_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9(3).
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO".
       CLEANUP-PARA.
           DISPLAY "DONE".
"""


def test_outline_contains_every_division_at_its_start_line() -> None:
    outline = compute_outline(
        _SAMPLE_PROGRAM,
    )

    by_name = {
        node.name: node
        for node in outline
    }

    assert (
        by_name["IDENTIFICATION DIVISION (DEMO)"].line
        == 1
    )
    assert by_name["ENVIRONMENT DIVISION"].line == 3
    assert by_name["DATA DIVISION"].line == 4
    assert by_name["PROCEDURE DIVISION"].line == 7

    for node in outline:
        assert node.kind == "division"


def test_data_division_lists_its_sections_as_children() -> None:
    outline = compute_outline(
        _SAMPLE_PROGRAM,
    )
    data_division = next(
        node
        for node in outline
        if node.name == "DATA DIVISION"
    )

    assert len(
        data_division.children,
    ) == 1
    section = data_division.children[0]
    assert section.name == "WORKING-STORAGE SECTION"
    assert section.kind == "section"
    assert section.line == 5


def test_procedure_division_lists_top_level_paragraphs() -> None:
    outline = compute_outline(
        _SAMPLE_PROGRAM,
    )
    procedure_division = next(
        node
        for node in outline
        if node.name == "PROCEDURE DIVISION"
    )

    paragraph_names = [
        child.name
        for child in procedure_division.children
    ]
    assert paragraph_names == [
        "MAIN-PARA",
        "CLEANUP-PARA",
    ]
    assert all(
        child.kind == "paragraph"
        for child in procedure_division.children
    )
    assert (
        procedure_division.children[0].line
        == 8
    )
    assert (
        procedure_division.children[1].line
        == 10
    )


def test_procedure_sections_nest_their_paragraphs() -> None:
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       SETUP SECTION.
       INIT-PARA.
           DISPLAY "INIT".
       MAIN SECTION.
       MAIN-PARA.
           DISPLAY "MAIN".
"""

    outline = compute_outline(
        source,
    )
    procedure_division = next(
        node
        for node in outline
        if node.name == "PROCEDURE DIVISION"
    )

    section_names = [
        child.name
        for child in procedure_division.children
    ]
    assert section_names == [
        "SETUP SECTION",
        "MAIN SECTION",
    ]

    setup_section = procedure_division.children[0]
    assert setup_section.kind == "section"
    assert [
        paragraph.name
        for paragraph in setup_section.children
    ] == ["INIT-PARA"]

    main_section = procedure_division.children[1]
    assert [
        paragraph.name
        for paragraph in main_section.children
    ] == ["MAIN-PARA"]


def test_implicit_unnamed_leading_paragraph_is_excluded() -> None:
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
           DISPLAY "NO PARAGRAPH NAME YET".
       NAMED-PARA.
           DISPLAY "NAMED".
"""

    outline = compute_outline(
        source,
    )
    procedure_division = next(
        node
        for node in outline
        if node.name == "PROCEDURE DIVISION"
    )

    assert [
        child.name
        for child in procedure_division.children
    ] == ["NAMED-PARA"]


def test_division_absent_from_source_is_absent_from_outline() -> None:
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
"""

    outline = compute_outline(
        source,
    )

    assert [
        node.name
        for node in outline
    ] == ["IDENTIFICATION DIVISION (DEMO)"]


def test_malformed_source_returns_empty_outline_without_raising() -> None:
    assert compute_outline(
        "not a real cobol program at all {{{",
    ) == ()


def test_empty_source_returns_empty_outline() -> None:
    assert compute_outline(
        "",
    ) == ()
