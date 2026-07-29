"""Unit tests for go-to-definition and find-references."""

from __future__ import annotations

from opencobol2.language import find_definition, find_references


_SAMPLE_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-COUNT PIC 9(3).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 1 TO WS-COUNT\n"
    "           PERFORM OTHER-PARA\n"
    "           STOP RUN.\n"
    "       OTHER-PARA.\n"
    "           DISPLAY WS-COUNT.\n"
)


def _text_at(
    source_text: str,
    line: int,
    column: int,
) -> str:
    """Return the source text starting at a 1-based line/column."""

    return source_text.splitlines()[
        line - 1
    ][
        column - 1 :
    ]


def _column_of(
    source_text: str,
    line: int,
    substring: str,
) -> int:
    """Return the 1-based column where a substring starts on a line."""

    return (
        source_text.splitlines()[
            line - 1
        ].index(
            substring,
        )
        + 1
    )


def test_find_definition_of_a_data_name_usage() -> None:
    usage_line = 8
    usage_column = _column_of(
        _SAMPLE_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    location = find_definition(
        _SAMPLE_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    assert location is not None
    assert location.name == "WS-COUNT"
    # The definition (line 5) is not the usage site (line 8) itself. The
    # location points at the data item entry's own start (its level
    # number, "01"), not at the name itself -- `DataItemNode.span` covers
    # the whole entry, so "WS-COUNT" appears later on the same line
    # rather than exactly at this column.
    assert location.line == 5
    assert (
        "WS-COUNT"
        in _text_at(
            _SAMPLE_PROGRAM,
            location.line,
            location.column,
        ).upper()
    )


def test_find_definition_of_a_paragraph_usage() -> None:
    usage_line = 9
    usage_column = _column_of(
        _SAMPLE_PROGRAM,
        usage_line,
        "OTHER-PARA",
    )

    location = find_definition(
        _SAMPLE_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    assert location is not None
    assert location.name == "OTHER-PARA"
    assert location.line == 11
    assert (
        _text_at(
            _SAMPLE_PROGRAM,
            location.line,
            location.column,
        )
        .upper()
        .startswith(
            "OTHER-PARA",
        )
    )


def test_find_definition_returns_none_for_an_undefined_name() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE 1 TO WS-MISSING.\n"
    )
    column = _column_of(
        source,
        4,
        "WS-MISSING",
    )

    assert (
        find_definition(
            source,
            line=4,
            column=column,
        )
        is None
    )


def test_find_definition_returns_none_off_an_identifier() -> None:
    # Column 1 of the IDENTIFICATION DIVISION line is a reserved word, not
    # a user-defined identifier.
    assert (
        find_definition(
            _SAMPLE_PROGRAM,
            line=1,
            column=8,
        )
        is None
    )


def test_find_definition_on_malformed_source_returns_none_without_raising() -> (
    None
):
    assert (
        find_definition(
            "not a real cobol program {{{",
            line=1,
            column=1,
        )
        is None
    )


def test_find_references_includes_the_definition_and_every_usage() -> None:
    usage_line = 8
    usage_column = _column_of(
        _SAMPLE_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    locations = find_references(
        _SAMPLE_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    lines_found = {
        location.line
        for location in locations
    }
    # Definition (5), the MOVE target (8), and the DISPLAY operand (12).
    assert lines_found == {5, 8, 12}
    assert all(
        location.name.upper() == "WS-COUNT"
        for location in locations
    )


def test_find_references_are_sorted_by_position() -> None:
    usage_line = 8
    usage_column = _column_of(
        _SAMPLE_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    locations = find_references(
        _SAMPLE_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    line_numbers = [
        location.line
        for location in locations
    ]
    assert line_numbers == sorted(
        line_numbers,
    )


def test_find_references_for_a_paragraph_name() -> None:
    usage_line = 9
    usage_column = _column_of(
        _SAMPLE_PROGRAM,
        usage_line,
        "OTHER-PARA",
    )

    locations = find_references(
        _SAMPLE_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    lines_found = {
        location.line
        for location in locations
    }
    assert lines_found == {9, 11}


def test_find_references_returns_nothing_off_an_identifier() -> None:
    assert (
        find_references(
            _SAMPLE_PROGRAM,
            line=1,
            column=8,
        )
        == ()
    )


def test_find_references_on_malformed_source_returns_nothing_without_raising() -> (
    None
):
    assert (
        find_references(
            "not a real cobol program {{{",
            line=1,
            column=1,
        )
        == ()
    )


# --- Editor §Editor-Facing-7: data-name/procedure-name namespace collision --

_COLLISION_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-COUNT PIC 9(3).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 5 TO WS-COUNT\n"
    "           PERFORM WS-COUNT\n"
    "           STOP RUN.\n"
    "       WS-COUNT.\n"
    "           DISPLAY 'IN PARAGRAPH'.\n"
)


def test_find_definition_on_a_move_target_resolves_the_data_item_not_the_paragraph() -> (
    None
):
    # A data item and a paragraph legally share a name -- a MOVE target
    # is structurally guaranteed to be a data name by the grammar, so
    # go-to-definition must not always check the procedure symbol table
    # first regardless of context.
    usage_line = 8
    usage_column = _column_of(
        _COLLISION_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    location = find_definition(
        _COLLISION_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    assert location is not None
    assert location.line == 5


def test_find_definition_on_a_perform_target_resolves_the_paragraph_not_the_data_item() -> (
    None
):
    usage_line = 9
    usage_column = _column_of(
        _COLLISION_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    location = find_definition(
        _COLLISION_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    assert location is not None
    assert location.line == 11


def test_find_references_on_a_move_target_excludes_the_paragraph_usages() -> None:
    usage_line = 8
    usage_column = _column_of(
        _COLLISION_PROGRAM,
        usage_line,
        "WS-COUNT",
    )

    locations = find_references(
        _COLLISION_PROGRAM,
        line=usage_line,
        column=usage_column,
    )

    lines_found = {
        location.line
        for location in locations
    }
    assert lines_found == {
        5,
        8,
    }
