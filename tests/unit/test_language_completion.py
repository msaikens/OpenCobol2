"""Unit tests for COBOL code completion candidates."""

from __future__ import annotations

from opencobol2.language import CompletionItemKind, compute_completions


_VALID_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-COUNT-TOTAL PIC 9(5).\n"
    "       01  WS-NAME PIC X(20).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           DISPLAY WS-NAME.\n"
    "           STOP RUN.\n"
)

_BROKEN_PROGRAM = "THIS IS NOT VALID COBOL AT ALL\nPROC"


def _column_after(
    source_text: str,
    line: int,
    substring: str,
) -> int:
    """Return the 1-based column right after `substring` ends on `line`."""

    line_text = source_text.splitlines()[line - 1]

    return line_text.index(substring) + len(substring) + 1


def _column_mid_word(
    source_text: str,
    line: int,
    word: str,
    prefix_length: int,
) -> int:
    """Return the 1-based column right after the first `prefix_length`
    characters of `word` on `line` -- simulating the cursor position
    partway through typing that word."""

    line_text = source_text.splitlines()[line - 1]

    return line_text.index(word) + prefix_length + 1


def test_matches_reserved_words_by_prefix() -> None:
    column = _column_mid_word(
        _VALID_PROGRAM,
        7,
        "PROCEDURE",
        4,
    )

    items = compute_completions(
        _VALID_PROGRAM,
        line=7,
        column=column,
    )

    labels = {item.label for item in items}

    assert "PROCEDURE" in labels
    assert all(
        item.kind is CompletionItemKind.KEYWORD
        for item in items
        if item.label == "PROCEDURE"
    )


def test_matches_intrinsic_functions_by_prefix() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY FUNCTION UPP\n"
    )

    items = compute_completions(
        source,
        line=4,
        column=len("           DISPLAY FUNCTION UPP") + 1,
    )

    matches = [
        item for item in items if item.label == "UPPER-CASE"
    ]

    assert len(matches) == 1
    assert matches[0].kind is CompletionItemKind.INTRINSIC_FUNCTION
    assert "UPPER-CASE" in matches[0].detail


def test_matches_snippet_triggers_case_insensitively() -> None:
    source = "       IDENTIFICATION DIVISION.\nEval"

    items = compute_completions(
        source,
        line=2,
        column=len("Eval") + 1,
    )

    matches = [item for item in items if item.kind is CompletionItemKind.SNIPPET]

    assert len(matches) == 1
    assert matches[0].label == "evaluate"
    assert matches[0].snippet_body is not None
    assert "EVALUATE" in matches[0].snippet_body


def test_matches_own_data_item_names_from_symbol_table() -> None:
    column = _column_mid_word(
        _VALID_PROGRAM,
        5,
        "WS-COUNT-TOTAL",
        4,
    )

    items = compute_completions(
        _VALID_PROGRAM,
        line=5,
        column=column,
    )

    matches = [
        item for item in items if item.label == "WS-COUNT-TOTAL"
    ]

    assert len(matches) == 1
    assert matches[0].kind is CompletionItemKind.DATA_ITEM
    assert matches[0].insert_text == "WS-COUNT-TOTAL"


def test_matches_own_paragraph_names_from_symbol_table() -> None:
    column = _column_mid_word(
        _VALID_PROGRAM,
        8,
        "MAIN-PARA",
        4,
    )

    items = compute_completions(
        _VALID_PROGRAM,
        line=8,
        column=column,
    )

    matches = [
        item for item in items if item.label == "MAIN-PARA"
    ]

    assert len(matches) == 1
    assert matches[0].kind is CompletionItemKind.PARAGRAPH


def test_own_names_are_ordered_before_keywords_for_the_same_prefix() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  DDD-FIELD PIC X(1).\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )

    items = compute_completions(
        source,
        line=5,
        column=_column_mid_word(source, 5, "DDD-FIELD", 3),
    )

    matching_labels = [
        item.label for item in items if item.label.startswith("DDD")
    ]

    assert matching_labels == ["DDD-FIELD"]


def test_empty_prefix_yields_no_candidates() -> None:
    items = compute_completions(
        _VALID_PROGRAM,
        line=1,
        column=1,
    )

    assert items == ()


def test_unparseable_source_still_yields_keyword_candidates() -> None:
    items = compute_completions(
        _BROKEN_PROGRAM,
        line=2,
        column=len("PROC") + 1,
    )

    assert any(
        item.label == "PROCEDURE"
        and item.kind is CompletionItemKind.KEYWORD
        for item in items
    )


def test_candidates_are_deduplicated_by_label_and_kind() -> None:
    items = compute_completions(
        _VALID_PROGRAM,
        line=7,
        column=_column_mid_word(_VALID_PROGRAM, 7, "PROCEDURE", 4),
    )

    keys = [(item.label, item.kind) for item in items]

    assert len(keys) == len(set(keys))


def test_out_of_range_position_returns_no_candidates() -> None:
    assert (
        compute_completions(
            _VALID_PROGRAM,
            line=1000,
            column=1,
        )
        == ()
    )
