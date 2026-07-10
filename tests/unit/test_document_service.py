"""Unit tests for document application workflows."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.documents import (
    DocumentAlreadyOpenError,
    DocumentHasUnsavedChangesError,
    DocumentSavePathRequiredError,
    DocumentService,
    LineEnding,
)


def test_new_document_adds_untitled_document_to_workspace() -> None:
    service = DocumentService()

    workspace_document = service.new_document(
        text="FIRST\r\nSECOND\r\n",
        encoding="latin-1",
        line_ending=LineEnding.CRLF,
    )

    document = workspace_document.document

    assert service.workspace.documents == (
        workspace_document,
    )
    assert (
        service.workspace.active_document
        is workspace_document
    )
    assert document.is_untitled is True
    assert document.text == "FIRST\nSECOND\n"
    assert document.encoding == "iso8859-1"
    assert document.line_ending is LineEnding.CRLF


def test_open_document_loads_and_adds_file(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_bytes(
        b"FIRST\r\nSECOND\r\n"
    )

    service = DocumentService()

    workspace_document = service.open_document(
        source_path,
    )

    document = workspace_document.document

    assert document.path == source_path
    assert document.text == "FIRST\nSECOND\n"
    assert document.line_ending is LineEnding.CRLF
    assert document.is_modified is False
    assert (
        service.workspace.active_document
        is workspace_document
    )


def test_opening_existing_path_returns_and_activates_existing_document(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.cob"
    second_path = tmp_path / "second.cob"

    first_path.write_text(
        "FIRST",
        encoding="utf-8",
    )
    second_path.write_text(
        "SECOND",
        encoding="utf-8",
    )

    service = DocumentService()

    first_document = service.open_document(
        first_path,
    )
    second_document = service.open_document(
        second_path,
    )

    reopened_document = service.open_document(
        first_path,
    )

    assert reopened_document is first_document
    assert service.workspace.document_count == 2
    assert (
        service.workspace.active_document
        is first_document
    )
    assert second_document in service.workspace.documents


def test_opening_existing_path_without_activation_preserves_active_document(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.cob"
    second_path = tmp_path / "second.cob"

    first_path.write_text(
        "FIRST",
        encoding="utf-8",
    )
    second_path.write_text(
        "SECOND",
        encoding="utf-8",
    )

    service = DocumentService()

    first_document = service.open_document(
        first_path,
    )
    second_document = service.open_document(
        second_path,
    )

    reopened_document = service.open_document(
        first_path,
        activate=False,
    )

    assert reopened_document is first_document
    assert (
        service.workspace.active_document
        is second_document
    )


def test_save_document_writes_modified_document(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_bytes(
        b"ORIGINAL\r\n"
    )

    service = DocumentService()

    workspace_document = service.open_document(
        source_path,
    )

    workspace_document.document.replace_text(
        "CHANGED\n",
    )

    saved_path = service.save_document(
        workspace_document.document_id,
    )

    assert saved_path == source_path
    assert source_path.read_bytes() == (
        b"CHANGED\r\n"
    )
    assert (
        workspace_document.document.is_modified
        is False
    )


def test_save_untitled_document_requires_save_as() -> None:
    service = DocumentService()

    workspace_document = service.new_document(
        text="PROGRAM",
    )

    with pytest.raises(
        DocumentSavePathRequiredError,
        match="requires Save As",
    ):
        service.save_document(
            workspace_document.document_id,
        )


def test_save_document_as_assigns_path(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "new-program.cob"

    service = DocumentService()

    workspace_document = service.new_document(
        text="FIRST\nSECOND\n",
        line_ending=LineEnding.CRLF,
    )

    saved_path = service.save_document_as(
        workspace_document.document_id,
        destination,
    )

    assert saved_path == destination
    assert destination.read_bytes() == (
        b"FIRST\r\nSECOND\r\n"
    )
    assert (
        workspace_document.document.path
        == destination
    )
    assert (
        workspace_document.document.is_untitled
        is False
    )
    assert (
        workspace_document.document.is_modified
        is False
    )


def test_save_document_as_rejects_path_open_by_another_document(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.cob"
    second_path = tmp_path / "second.cob"

    first_path.write_text(
        "FIRST",
        encoding="utf-8",
    )
    second_path.write_text(
        "SECOND",
        encoding="utf-8",
    )

    service = DocumentService()

    first_document = service.open_document(
        first_path,
    )
    second_document = service.open_document(
        second_path,
    )

    first_document.document.replace_text(
        "CHANGED",
    )

    with pytest.raises(
        DocumentAlreadyOpenError,
        match="already open",
    ):
        service.save_document_as(
            first_document.document_id,
            second_path,
        )

    assert first_path.read_text(
        encoding="utf-8",
    ) == "FIRST"
    assert second_path.read_text(
        encoding="utf-8",
    ) == "SECOND"
    assert first_document.document.is_modified is True
    assert (
        second_document.document.path
        == second_path
    )


def test_save_document_as_allows_own_current_path(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_text(
        "ORIGINAL",
        encoding="utf-8",
    )

    service = DocumentService()

    workspace_document = service.open_document(
        source_path,
    )

    workspace_document.document.replace_text(
        "CHANGED",
    )

    saved_path = service.save_document_as(
        workspace_document.document_id,
        source_path,
    )

    assert saved_path == source_path
    assert source_path.read_text(
        encoding="utf-8",
    ) == "CHANGED"
    assert (
        workspace_document.document.is_modified
        is False
    )


def test_modified_document_cannot_close_without_discard() -> None:
    service = DocumentService()

    workspace_document = service.new_document(
        text="ORIGINAL",
    )

    workspace_document.document.replace_text(
        "CHANGED",
    )

    with pytest.raises(
        DocumentHasUnsavedChangesError,
        match="unsaved changes",
    ):
        service.close_document(
            workspace_document.document_id,
        )

    assert service.workspace.documents == (
        workspace_document,
    )


def test_modified_document_can_close_when_changes_are_discarded() -> None:
    service = DocumentService()

    workspace_document = service.new_document(
        text="ORIGINAL",
    )

    workspace_document.document.replace_text(
        "CHANGED",
    )

    closed_document = service.close_document(
        workspace_document.document_id,
        discard_changes=True,
    )

    assert closed_document is workspace_document
    assert service.workspace.documents == ()
    assert service.workspace.active_document is None


def test_clean_document_can_close_without_discard() -> None:
    service = DocumentService()

    workspace_document = service.new_document(
        text="PROGRAM",
    )

    closed_document = service.close_document(
        workspace_document.document_id,
    )

    assert closed_document is workspace_document
    assert service.workspace.documents == ()