"""Application services for document workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from opencobol2.documents.models import (
    LineEnding,
)
from opencobol2.documents.storage import (
    DocumentStorage,
)
from opencobol2.documents.workspace import (
    DocumentAlreadyOpenError,
    DocumentWorkspace,
    WorkspaceDocument,
)


class DocumentSavePathRequiredError(ValueError):
    """Raised when a save operation requires a filesystem path."""


class DocumentHasUnsavedChangesError(RuntimeError):
    """Raised when closing a modified document without discarding changes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentService:
    """Coordinates document storage and open-workspace state."""

    storage: DocumentStorage = field(
        default_factory=DocumentStorage,
    )
    workspace: DocumentWorkspace = field(
        default_factory=DocumentWorkspace,
    )

    def new_document(
        self,
        *,
        text: str = "",
        encoding: str = "utf-8",
        line_ending: LineEnding | str = LineEnding.LF,
        activate: bool = True,
    ) -> WorkspaceDocument:
        """Create one new untitled document."""
        return self.workspace.create_untitled(
            text=text,
            encoding=encoding,
            line_ending=line_ending,
            activate=activate,
        )

    def open_document(
        self,
        path: Path | str,
        *,
        fallback_encoding: str | None = None,
        activate: bool = True,
    ) -> WorkspaceDocument:
        """Open a file or return its existing workspace document."""
        document_path = Path(
            path,
        )

        existing_document = self.workspace.find_by_path(
            document_path,
        )

        if existing_document is not None:
            if activate:
                self.workspace.set_active(
                    existing_document.document_id,
                )

            return existing_document

        document = self.storage.load(
            document_path,
            fallback_encoding=fallback_encoding,
        )

        return self.workspace.add_document(
            document,
            activate=activate,
        )

    def save_document(
        self,
        document_id: UUID,
    ) -> Path:
        """Save one open document to its assigned path."""
        workspace_document = self.workspace.get_document(
            document_id,
        )

        document = workspace_document.document

        if document.path is None:
            raise DocumentSavePathRequiredError(
                "An untitled document requires Save As."
            )

        return self.storage.save(
            document,
        )

    def save_document_as(
        self,
        document_id: UUID,
        path: Path | str,
    ) -> Path:
        """Save one open document to a selected filesystem path."""
        workspace_document = self.workspace.get_document(
            document_id,
        )

        destination = Path(
            path,
        )

        existing_document = self.workspace.find_by_path(
            destination,
        )

        if (
            existing_document is not None
            and existing_document.document_id != document_id
        ):
            raise DocumentAlreadyOpenError(
                "Cannot save document to a path already open "
                "in this workspace: "
                f"{destination}"
            )

        return self.storage.save(
            workspace_document.document,
            path=destination,
        )

    def close_document(
        self,
        document_id: UUID,
        *,
        discard_changes: bool = False,
    ) -> WorkspaceDocument:
        """Close one document, protecting unsaved changes by default."""
        workspace_document = self.workspace.get_document(
            document_id,
        )

        if (
            workspace_document.document.is_modified
            and not discard_changes
        ):
            raise DocumentHasUnsavedChangesError(
                "Document has unsaved changes."
            )

        return self.workspace.close_document(
            document_id,
        )