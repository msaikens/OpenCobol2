"""Unit tests for COBOL code-folding range extraction from the real parser."""

from __future__ import annotations

from opencobol2.language import compute_fold_ranges


_SAMPLE_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNT PIC 9(3).
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF WS-COUNT > 0
               DISPLAY "POSITIVE"
               DISPLAY "STILL POSITIVE"
           ELSE
               DISPLAY "NOT POSITIVE"
           END-IF
           PERFORM VARYING WS-COUNT FROM 1 BY 1 UNTIL WS-COUNT > 3
               DISPLAY WS-COUNT
           END-PERFORM
           STOP RUN.
       CLEANUP-PARA.
           DISPLAY "DONE".
"""


def _as_tuples(
    fold_ranges,
):
    return {
        (
            fold_range.start_line,
            fold_range.end_line,
        )
        for fold_range in fold_ranges
    }


def test_folds_every_division_section_paragraph_and_statement_block() -> None:
    ranges = _as_tuples(
        compute_fold_ranges(
            _SAMPLE_PROGRAM,
        )
    )

    assert (
        1,
        2,
    ) in ranges  # IDENTIFICATION DIVISION
    assert (
        4,
        6,
    ) in ranges  # DATA DIVISION
    assert (
        5,
        6,
    ) in ranges  # WORKING-STORAGE SECTION
    assert (
        7,
        20,
    ) in ranges  # PROCEDURE DIVISION
    assert (
        8,
        18,
    ) in ranges  # MAIN-PARA
    assert (
        9,
        14,
    ) in ranges  # IF/ELSE/END-IF
    assert (
        15,
        17,
    ) in ranges  # PERFORM/END-PERFORM
    assert (
        19,
        20,
    ) in ranges  # CLEANUP-PARA


def test_single_line_divisions_are_not_foldable() -> None:
    ranges = _as_tuples(
        compute_fold_ranges(
            _SAMPLE_PROGRAM,
        )
    )

    # ENVIRONMENT DIVISION is exactly one line long here -- nothing to fold.
    assert not any(
        start == 3
        for start, _ in ranges
    )


def test_ranges_are_sorted_by_start_line() -> None:
    ranges = compute_fold_ranges(
        _SAMPLE_PROGRAM,
    )

    start_lines = [
        fold_range.start_line
        for fold_range in ranges
    ]

    assert start_lines == sorted(
        start_lines,
    )


def test_ranges_contain_no_duplicates() -> None:
    ranges = compute_fold_ranges(
        _SAMPLE_PROGRAM,
    )

    keys = [
        (
            fold_range.start_line,
            fold_range.end_line,
        )
        for fold_range in ranges
    ]

    assert len(
        keys,
    ) == len(
        set(
            keys,
        )
    )


def test_out_of_line_perform_produces_no_fold_range() -> None:
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM OTHER-PARA.
           STOP RUN.
       OTHER-PARA.
           DISPLAY "HELLO".
"""

    ranges = _as_tuples(
        compute_fold_ranges(
            source,
        )
    )

    # A "PERFORM OTHER-PARA." with no inline body has nothing to fold, so
    # only the paragraphs themselves (and PROCEDURE DIVISION) should fold.
    assert (
        3,
        8,
    ) in ranges
    assert (
        4,
        6,
    ) in ranges
    assert (
        7,
        8,
    ) in ranges
    assert not any(
        start == 5
        for start, _ in ranges
    )


def test_empty_if_produces_no_fold_range() -> None:
    # Editor §Editor-Facing-5: an empty IF (both branches empty) used
    # to still get a fold range hiding zero lines of content,
    # inconsistent with the deliberate empty-out-of-line-PERFORM
    # exclusion just above.
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF 1 > 0
           END-IF
           STOP RUN.
"""

    ranges = _as_tuples(
        compute_fold_ranges(
            source,
        )
    )

    assert not any(
        start == 5
        for start, _ in ranges
    )


def test_evaluate_statement_and_branches_are_foldable() -> None:
    source = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EVALUATE WS-COUNT
               WHEN 1
                   DISPLAY "ONE"
                   DISPLAY "UNO"
               WHEN 2
                   DISPLAY "TWO"
           END-EVALUATE.
"""

    ranges = _as_tuples(
        compute_fold_ranges(
            source,
        )
    )

    assert (
        5,
        11,
    ) in ranges  # EVALUATE ... END-EVALUATE.
    assert (
        6,
        8,
    ) in ranges  # WHEN 1 branch (two statements)


def test_malformed_source_returns_no_fold_ranges_without_raising() -> None:
    ranges = compute_fold_ranges(
        "not a real cobol program at all {{{",
    )

    assert ranges == ()


def test_empty_source_returns_no_fold_ranges() -> None:
    assert compute_fold_ranges(
        "",
    ) == ()
