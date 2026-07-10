"""Unit tests for the open-document workspace."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from opencobol2.documents import (
    DocumentAlreadyOpenError,
    DocumentNotOpenError,
    DocumentWorkspace,
    LineEnding,
    TextDocument,
)


def test_new_workspace_is_empty() -> None:
    workspace = DocumentWorkspace()

    assert workspace.documents == ()
    assert workspace.document_count == 0
    assert workspace.active_document_id is None
    assert workspace.active_document is None


def test_add_document_assigns_identity_and_activates() -> None:
    workspace = DocumentWorkspace()

    document = TextDocument(
        text="PROGRAM",
        path="program.cob",
    )

    workspace_document = workspace.add_document(
        document,
    )

    assert isinstance(
        workspace_document.document_id,
        UUID,
    )
    assert workspace_document.document is document
    assert workspace.documents == (
        workspace_document,
    )
    assert workspace.document_count == 1
    assert (
        workspace.active_document
        is workspace_document
    )


def test_first_document_becomes_active_when_activation_is_false() -> None:
    workspace = DocumentWorkspace()

    workspace_document = workspace.add_document(
        TextDocument(
            text="PROGRAM",
        ),
        activate=False,
    )

    assert (
        workspace.active_document
        is workspace_document
    )


def test_multiple_untitled_documents_have_distinct_identity() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()
    second_document = workspace.create_untitled()

    assert (
        first_document.document_id
        != second_document.document_id
    )
    assert (
        first_document.document
        is not second_document.document
    )
    assert first_document.document.is_untitled is True
    assert second_document.document.is_untitled is True
    assert workspace.document_count == 2


def test_create_untitled_preserves_document_configuration() -> None:
    workspace = DocumentWorkspace()

    workspace_document = workspace.create_untitled(
        text="FIRST\r\nSECOND\r\n",
        encoding="latin-1",
        line_ending=LineEnding.CRLF,
    )

    document = workspace_document.document

    assert document.text == "FIRST\nSECOND\n"
    assert document.encoding == "iso8859-1"
    assert document.line_ending is LineEnding.CRLF


def test_same_document_object_cannot_be_added_twice() -> None:
    workspace = DocumentWorkspace()

    document = TextDocument(
        text="PROGRAM",
    )

    workspace.add_document(
        document,
    )

    with pytest.raises(
        DocumentAlreadyOpenError,
        match="already open",
    ):
        workspace.add_document(
            document,
        )


def test_normalized_duplicate_path_is_rejected(
    tmp_path: Path,
) -> None:
    source_directory = tmp_path / "source"

    source_directory.mkdir()

    source_path = source_directory / "program.cob"

    source_path.write_text(
        "PROGRAM",
        encoding="utf-8",
    )

    alternate_path = (
        source_directory
        / ".."
        / "source"
        / "program.cob"
    )

    workspace = DocumentWorkspace()

    workspace.add_document(
        TextDocument(
            text="FIRST",
            path=source_path,
        )
    )

    with pytest.raises(
        DocumentAlreadyOpenError,
        match="already open",
    ):
        workspace.add_document(
            TextDocument(
                text="SECOND",
                path=alternate_path,
            )
        )


def test_find_by_path_uses_normalized_path_identity(
    tmp_path: Path,
) -> None:
    source_directory = tmp_path / "source"

    source_directory.mkdir()

    source_path = source_directory / "program.cob"

    source_path.write_text(
        "PROGRAM",
        encoding="utf-8",
    )

    workspace = DocumentWorkspace()

    workspace_document = workspace.add_document(
        TextDocument(
            text="PROGRAM",
            path=source_path,
        )
    )

    alternate_path = (
        source_directory
        / ".."
        / "source"
        / "program.cob"
    )

    assert (
        workspace.find_by_path(
            alternate_path,
        )
        is workspace_document
    )


def test_find_by_path_returns_none_for_unknown_path() -> None:
    workspace = DocumentWorkspace()

    workspace.create_untitled()

    assert (
        workspace.find_by_path(
            "unknown.cob",
        )
        is None
    )


def test_add_inactive_document_preserves_current_active_document() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()

    second_document = workspace.create_untitled(
        activate=False,
    )

    assert (
        workspace.active_document
        is first_document
    )
    assert second_document in workspace.documents


def test_set_active_changes_active_document() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()
    second_document = workspace.create_untitled()

    workspace.set_active(
        first_document.document_id,
    )

    assert (
        workspace.active_document
        is first_document
    )

    workspace.set_active(
        second_document.document_id,
    )

    assert (
        workspace.active_document
        is second_document
    )


def test_unknown_document_identifier_is_rejected() -> None:
    workspace = DocumentWorkspace()

    unknown_document_id = uuid4()

    with pytest.raises(
        DocumentNotOpenError,
        match="not open",
    ):
        workspace.get_document(
            unknown_document_id,
        )

    with pytest.raises(
        DocumentNotOpenError,
        match="not open",
    ):
        workspace.set_active(
            unknown_document_id,
        )

    with pytest.raises(
        DocumentNotOpenError,
        match="not open",
    ):
        workspace.close_document(
            unknown_document_id,
        )


def test_closing_inactive_document_preserves_active_document() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()
    second_document = workspace.create_untitled()

    workspace.set_active(
        second_document.document_id,
    )

    closed_document = workspace.close_document(
        first_document.document_id,
    )

    assert closed_document is first_document
    assert workspace.documents == (
        second_document,
    )
    assert (
        workspace.active_document
        is second_document
    )


def test_closing_active_middle_document_selects_next_document() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()
    second_document = workspace.create_untitled()
    third_document = workspace.create_untitled()

    workspace.set_active(
        second_document.document_id,
    )

    workspace.close_document(
        second_document.document_id,
    )

    assert workspace.documents == (
        first_document,
        third_document,
    )
    assert (
        workspace.active_document
        is third_document
    )


def test_closing_active_last_document_selects_previous_document() -> None:
    workspace = DocumentWorkspace()

    first_document = workspace.create_untitled()
    second_document = workspace.create_untitled()

    workspace.close_document(
        second_document.document_id,
    )

    assert workspace.documents == (
        first_document,
    )
    assert (
        workspace.active_document
        is first_document
    )


def test_closing_only_document_clears_active_document() -> None:
    workspace = DocumentWorkspace()

    workspace_document = workspace.create_untitled()

    workspace.close_document(
        workspace_document.document_id,
    )

    assert workspace.documents == ()
    assert workspace.document_count == 0
    assert workspace.active_document_id is None
    assert workspace.active_document is None