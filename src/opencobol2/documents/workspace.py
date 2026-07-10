"""Open-document workspace and session models"""

from __future__ import annotations
from dataclasses import dataclass

import os as os

from pathlib import Path

from typing import Text
from uuid import UUID, uuid4

from opencobol2.documents.models import TextDocument, LineEnding


class DocumentAlreadyOpenError(ValueError):
    """Raised when a document is already open in the workspace."""

class DocumentNotOpenError(ValueError):
    """Raised when a document is not open in the workspace."""

class DocumentNotFoundError(ValueError):
    """Raised when a document is not found in the workspace."""

@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceDocument:
    """Associates an open text document with stable workspace identity"""

    document_id: UUID
    document: TextDocument
"""CLASS END"""
"""CLASS START"""
class DocumentWorkspace:
    """ Tracks the documents open in one application workspace session. """

    __slots__ = ( "_documents", "_active_document_id",)

    def __init__(self) -> None:
        self._documents: dict [
            UUID,
            WorkspaceDocument,
        ] = {}
        self._active_document_id: UUID | None = None

    @property
    def documents(self,) -> tuple[WorkspaceDocument, ...]:
        """Return open documents in workspace insertion order"""
        return tuple(self._documents.values())

    @property
    def document_count (self,) -> int:
        """Return the number of open documents in the workspace"""
        return len(self._documents)

    @property
    def active_document_id(self,) -> UUID | None:
        """Return the document ID of the active document, if any"""
        return self._active_document_id

    @property
    def active_document(self,) -> WorkspaceDocument | None:
        """Return the active document, if any"""
        if self._active_document_id is None:
            return None

        return self._documents[self._active_document_id]

    def add_document(self, document: TextDocument, *, activate: bool = True,) -> WorkspaceDocument:
        """ Add a new document to the workspace"""
        if self._contains_document_object(document,):
            raise DocumentAlreadyOpenError("Document is already open in the workspace.")

        if document.path is not None:
            existing_document = self.find_by_path(document.path,)

            if existing_document is not None:
                raise DocumentAlreadyOpenError("Document is already open in the workspace")
    
        workspace_document = WorkspaceDocument(document_id=uuid4(), document=document,)

        self._documents[workspace_document.document_id] = workspace_document

        if ( activate or self._active_document_id is None):
            self._active_document_id = workspace_document.document_id

        return workspace_document

    def create_untitled(self, *, text: str="", encoding: str="utf-8", line_ending: LineEnding | str = LineEnding.LF, activate: bool = True,) -> WorkspaceDocument:
        """Create a new untitled document in the workspace"""
        document = TextDocument(text=text, encoding=encoding, line_ending=line_ending,)
        return self.add_document(document, activate=activate,)

    def get_document(self, document_id: UUID,) -> WorkspaceDocument:
        """Return the workspace document with the given ID"""
        try:
            return self._documents[document_id]
        except KeyError:
            raise DocumentNotOpenError(f"Document is not open in this workspace: {document_id}") from None

    def find_by_path(self, path: Path | str,) -> WorkspaceDocument | None:
        """Find the open document representing a filesystem patrh."""
        candidate_path = Path(path,)

        for workspace_document in self._documents.values():
            document_path = workspace_document.document.path

            if document_path is None:
                continue

            if _paths_match(document_path, candidate_path):
                return workspace_document

        return None

    def set_active(self, document_id: UUID,) -> None:
        """Make one open document the active document."""
        workspace_document = self.get_document(document_id,)
        self._active_document_id = workspace_document.document_id

    def close_document(self, document_id: UUID,) -> WorkspaceDocument:
        """Remove one document from the workspace"""
        workspace_document = self.get_document(document_id,)
        document_ids = tuple(self._documents)
        closed_index = document_ids.index(document_id)

        del self._documents[document_id]

        if self._active_document_id == document_id:
            remaining_document_ids = tuple(self._documents)

            if not remaining_document_ids:
                self._active_document_id = None
            else:
                replacement_index = min(closed_index, len(remaining_document_ids) - 1,)

                self._active_document_id = (remaining_document_ids[replacement_index])
        
        return workspace_document

    def _contains_document_object(self, document: TextDocument,) -> bool:
        """Returun whether the exact docuemtn object is already open"""
        return any(workspace_document.document is document
            for workspace_document in self._documents.values()
        )

"""CLASS DocumentWorkspace END"""

def _path_key(path: Path,) -> str:
    """Build a platform-normalized key-path"""
    try:
        normalized_path = path.resolve(strict=False,)
    except OSError:
        normalized_path = path.absolute()

    return os.path.normpath(os.fspath(normalized_path,))

def _paths_match(first_path: Path, second_path: Path,) -> bool:
    """Return whether two local filesystem paths identify one file."""
    if _path_key(first_path,) == _path_key(second_path,):
        return True

    try:
        return first_path.samefile(second_path,)
    except OSError: 
            return False

