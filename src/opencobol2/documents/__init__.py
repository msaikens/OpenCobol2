"""Document models and services."""

from opencobol2.documents.models import (
    ByteOrderMark,
    LineEnding,
    TextDocument,
)
from opencobol2.documents.service import (
    DocumentHasUnsavedChangesError,
    DocumentSavePathRequiredError,
    DocumentService,
)
from opencobol2.documents.storage import (
    DocumentDecodeError,
    DocumentStorage,
)
from opencobol2.documents.workspace import (
    DocumentAlreadyOpenError,
    DocumentNotOpenError,
    DocumentWorkspace,
    WorkspaceDocument,
)


__all__ = [
    "ByteOrderMark",
    "DocumentAlreadyOpenError",
    "DocumentDecodeError",
    "DocumentHasUnsavedChangesError",
    "DocumentNotOpenError",
    "DocumentSavePathRequiredError",
    "DocumentService",
    "DocumentStorage",
    "DocumentWorkspace",
    "LineEnding",
    "TextDocument",
    "WorkspaceDocument",
]