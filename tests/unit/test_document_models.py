"""Unit tests for text document domain models."""

from pathlib import Path

import pytest

from opencobol2.documents import (
    LineEnding,
    TextDocument,
)


def test_document_normalizes_path_encoding_and_newlines() -> None:
    document = TextDocument(
        text="FIRST\r\nSECOND\rTHIRD\n",
        path="source/program.cob",
        encoding="UTF8",
        line_ending="\r\n",
    )

    assert document.path == Path(
        "source/program.cob"
    )
    assert document.text == (
        "FIRST\nSECOND\nTHIRD\n"
    )
    assert document.encoding == "utf-8"
    assert document.line_ending is LineEnding.CRLF
    assert document.is_modified is False


def test_new_untitled_document_is_clean() -> None:
    document = TextDocument(
        text="",
    )

    assert document.path is None
    assert document.is_untitled is True
    assert document.is_modified is False


def test_replacing_text_marks_document_modified() -> None:
    document = TextDocument(
        text="ORIGINAL",
        path="program.cob",
    )

    document.replace_text(
        "CHANGED",
    )

    assert document.text == "CHANGED"
    assert document.is_modified is True


def test_reverting_to_saved_text_clears_modified_state() -> None:
    document = TextDocument(
        text="ORIGINAL",
        path="program.cob",
    )

    document.replace_text(
        "CHANGED",
    )
    document.replace_text(
        "ORIGINAL",
    )

    assert document.is_modified is False


def test_encoding_changes_participate_in_modified_state() -> None:
    document = TextDocument(
        text="PROGRAM",
        path="program.cob",
        encoding="utf-8",
    )

    document.set_encoding(
        "UTF8",
    )

    assert document.is_modified is False

    document.set_encoding(
        "latin-1",
    )

    assert document.encoding == "iso8859-1"
    assert document.is_modified is True


def test_line_ending_changes_participate_in_modified_state() -> None:
    document = TextDocument(
        text="FIRST\nSECOND\n",
        path="program.cob",
        line_ending=LineEnding.LF,
    )

    document.set_line_ending(
        LineEnding.CRLF,
    )

    assert document.line_ending is LineEnding.CRLF
    assert document.is_modified is True


def test_mark_saved_updates_saved_state() -> None:
    document = TextDocument(
        text="ORIGINAL",
        path="program.cob",
    )

    document.replace_text(
        "CHANGED",
    )
    document.set_line_ending(
        LineEnding.CRLF,
    )

    assert document.is_modified is True

    document.mark_saved()

    assert document.is_modified is False

    document.replace_text(
        "CHANGED AGAIN",
    )

    assert document.is_modified is True


def test_mark_saved_can_assign_path_to_untitled_document() -> None:
    document = TextDocument(
        text="PROGRAM",
    )

    document.mark_saved(
        path="source/new-program.cob",
    )

    assert document.path == Path(
        "source/new-program.cob"
    )
    assert document.is_untitled is False
    assert document.is_modified is False


def test_untitled_document_requires_path_when_marked_saved() -> None:
    document = TextDocument(
        text="PROGRAM",
    )

    with pytest.raises(
        ValueError,
        match="cannot be marked saved without a path",
    ):
        document.mark_saved()


def test_unknown_encoding_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unknown document encoding",
    ):
        TextDocument(
            text="PROGRAM",
            encoding="definitely-not-a-real-encoding",
        )