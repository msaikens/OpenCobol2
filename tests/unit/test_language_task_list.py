"""Unit tests for scanning COBOL comments for TODO/FIXME-style task markers."""

from __future__ import annotations

from opencobol2.language import compute_task_list_entries


def test_finds_a_todo_in_a_whole_line_comment() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * TODO clean this up\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert len(
        entries,
    ) == 1
    assert entries[0].tag == "TODO"
    assert entries[0].line == 3
    assert "clean this up" in entries[0].text


def test_finds_a_fixme_in_an_inline_comment() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        '           DISPLAY "HI" *> FIXME: use a real message\n'
    )

    entries = compute_task_list_entries(
        source,
    )

    assert len(
        entries,
    ) == 1
    assert entries[0].tag == "FIXME"
    assert entries[0].line == 4


def test_tag_matching_is_case_insensitive_but_reported_uppercase() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * todo lowercase tag\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert entries[0].tag == "TODO"


def test_does_not_match_a_tag_as_a_substring_of_another_word() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * TODOLIST and HACKATHON are not real tags\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert entries == ()


def test_does_not_match_a_tag_embedded_in_a_hyphenated_identifier() -> None:
    # Editor §Editor-Facing-4: `\b` alone treats `-` as a word boundary,
    # so a tag word hyphen-flanked inside a longer COBOL identifier
    # reference (hyphen-delimited, unlike ordinary English words) used
    # to be false-flagged as a real standalone tag.
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * See WS-HACK-FLAG for details on this switch.\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert entries == ()


def test_still_matches_a_real_tag_next_to_punctuation() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * TODO: fix this, it's a real tag.\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert len(entries) == 1
    assert entries[0].tag == "TODO"


def test_comment_without_a_recognized_tag_produces_no_entry() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * just an ordinary comment\n"
    )

    assert compute_task_list_entries(
        source,
    ) == ()


def test_a_tag_inside_a_string_literal_is_not_matched() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        '           DISPLAY "TODO: not a real task".\n'
    )

    assert compute_task_list_entries(
        source,
    ) == ()


def test_custom_tags_can_be_supplied() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * NOTE this is important\n"
    )

    entries = compute_task_list_entries(
        source,
        tags=(
            "NOTE",
        ),
    )

    assert len(
        entries,
    ) == 1
    assert entries[0].tag == "NOTE"


def test_multiple_comments_each_produce_their_own_entry() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "      * TODO first\n"
        "      * FIXME second\n"
    )

    entries = compute_task_list_entries(
        source,
    )

    assert [
        entry.tag
        for entry in entries
    ] == ["TODO", "FIXME"]
    assert [
        entry.line
        for entry in entries
    ] == [3, 4]


def test_malformed_source_returns_no_entries_without_raising() -> None:
    assert compute_task_list_entries(
        "not a real cobol program at all {{{",
    ) == ()


def test_empty_source_returns_no_entries() -> None:
    assert compute_task_list_entries(
        "",
    ) == ()
