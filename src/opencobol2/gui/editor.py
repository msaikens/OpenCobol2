"""A tabbed source-code editor backed by the Qt-independent document model."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QWidget,
)

from opencobol2.documents import (
    DocumentAlreadyOpenError,
    DocumentService,
    TextDocument,
    WorkspaceDocument,
)


class SourceEditorWidget(QPlainTextEdit):
    """A plain-text editor for exactly one open document."""

    def __init__(
        self,
        *,
        document_id: UUID,
        initial_text: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build an editor preloaded with one document's text."""

        super().__init__(
            parent,
        )

        self.document_id = document_id
        self.setPlainText(
            initial_text,
        )


class EditorTabsWidget(QTabWidget):
    """Docks every open document from a `DocumentService` as its own tab."""

    def __init__(
        self,
        *,
        document_service: DocumentService,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty editor tab area backed by a document service."""

        super().__init__(
            parent,
        )

        if not isinstance(
            document_service,
            DocumentService,
        ):
            raise TypeError(
                "Editor tabs document service must be DocumentService."
            )

        self._document_service = document_service

        self.setTabsClosable(
            True,
        )
        self.tabCloseRequested.connect(
            self._close_tab,
        )

    @property
    def document_service(
        self,
    ) -> DocumentService:
        """Return the document service backing this editor area."""

        return self._document_service

    def open_path(
        self,
        path: Path | str,
    ) -> None:
        """Open a file, activating its tab if it's already open."""

        workspace_document = (
            self._document_service.open_document(
                path,
            )
        )
        self._show_document(
            workspace_document,
        )

    def new_file(
        self,
    ) -> None:
        """Create and show a new untitled document."""

        workspace_document = (
            self._document_service.new_document()
        )
        self._show_document(
            workspace_document,
        )

    def open_file_dialog(
        self,
    ) -> None:
        """Prompt for a file to open and show it."""

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
        )

        if path_str:
            self.open_path(
                path_str,
            )

    def save_active_document(
        self,
    ) -> None:
        """Save the active tab's document, prompting for a path if untitled."""

        index = self.currentIndex()

        if index >= 0:
            self._save_tab(
                index,
            )

    def save_active_document_as(
        self,
    ) -> None:
        """Save the active tab's document to a newly chosen path."""

        index = self.currentIndex()

        if index >= 0:
            self._save_tab_as(
                index,
            )

    def save_all_documents(
        self,
    ) -> None:
        """Save every modified open document that already has a path."""

        for index in range(self.count()):
            editor = self._editor_at(
                index,
            )
            workspace_document = (
                self._document_service.workspace.get_document(
                    editor.document_id,
                )
            )

            if (
                workspace_document.document.is_modified
                and workspace_document.document.path is not None
            ):
                self._save_tab(
                    index,
                )

    def close_active_document(
        self,
    ) -> None:
        """Close the active tab, prompting to save unsaved changes."""

        index = self.currentIndex()

        if index >= 0:
            self._close_tab(
                index,
            )

    def close_all_documents(
        self,
    ) -> None:
        """Close every open tab, prompting to save unsaved changes."""

        for index in reversed(
            range(
                self.count(),
            )
        ):
            self._close_tab(
                index,
            )

    def _show_document(
        self,
        workspace_document: WorkspaceDocument,
    ) -> None:
        """Activate an existing tab for a document, or create a new one."""

        existing_index = self._index_for(
            workspace_document.document_id,
        )

        if existing_index >= 0:
            self.setCurrentIndex(
                existing_index,
            )
            return

        editor = SourceEditorWidget(
            document_id=workspace_document.document_id,
            initial_text=workspace_document.document.text,
        )
        document_id = workspace_document.document_id
        editor.textChanged.connect(
            lambda: self._handle_text_changed(
                document_id,
            )
        )

        index = self.addTab(
            editor,
            _tab_title(
                workspace_document.document,
            ),
        )
        self.setTabToolTip(
            index,
            _tab_tooltip(
                workspace_document.document,
            ),
        )
        self.setCurrentIndex(
            index,
        )

    def _handle_text_changed(
        self,
        document_id: UUID,
    ) -> None:
        """Sync an editor's text back into its document model."""

        editor = self._editor_for(
            document_id,
        )

        if editor is None:
            return

        workspace_document = (
            self._document_service.workspace.get_document(
                document_id,
            )
        )
        workspace_document.document.replace_text(
            editor.toPlainText(),
        )
        self._refresh_tab_chrome(
            document_id,
        )

    def _refresh_tab_chrome(
        self,
        document_id: UUID,
    ) -> None:
        """Refresh a tab's title and tooltip from its document's state."""

        index = self._index_for(
            document_id,
        )

        if index < 0:
            return

        document = (
            self._document_service.workspace.get_document(
                document_id,
            ).document
        )
        self.setTabText(
            index,
            _tab_title(
                document,
            ),
        )
        self.setTabToolTip(
            index,
            _tab_tooltip(
                document,
            ),
        )

    def _save_tab(
        self,
        index: int,
    ) -> None:
        """Save one tab's document, redirecting untitled ones to Save As."""

        editor = self._editor_at(
            index,
        )
        workspace_document = (
            self._document_service.workspace.get_document(
                editor.document_id,
            )
        )

        if workspace_document.document.path is None:
            self._save_tab_as(
                index,
            )
            return

        try:
            self._document_service.save_document(
                editor.document_id,
            )
        except OSError as error:
            QMessageBox.critical(
                self,
                "Save File",
                f"Unable to save file: {error}",
            )
            return

        self._refresh_tab_chrome(
            editor.document_id,
        )

    def _save_tab_as(
        self,
        index: int,
    ) -> None:
        """Save one tab's document to a newly chosen filesystem path."""

        editor = self._editor_at(
            index,
        )
        workspace_document = (
            self._document_service.workspace.get_document(
                editor.document_id,
            )
        )
        default_path = (
            str(
                workspace_document.document.path,
            )
            if workspace_document.document.path is not None
            else ""
        )

        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save File As",
            default_path,
        )

        if not path_str:
            return

        try:
            self._document_service.save_document_as(
                editor.document_id,
                path_str,
            )
        except (
            OSError,
            DocumentAlreadyOpenError,
        ) as error:
            QMessageBox.critical(
                self,
                "Save File As",
                f"Unable to save file: {error}",
            )
            return

        self._refresh_tab_chrome(
            editor.document_id,
        )

    def _close_tab(
        self,
        index: int,
    ) -> None:
        """Close one tab, prompting to save unsaved changes first."""

        editor = self._editor_at(
            index,
        )
        document_id = editor.document_id
        workspace_document = (
            self._document_service.workspace.get_document(
                document_id,
            )
        )

        if workspace_document.document.is_modified:
            choice = QMessageBox.question(
                self,
                "Close File",
                "Save changes to "
                f"{_display_name(workspace_document.document)!r} "
                "before closing?",
                (
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel
                ),
                QMessageBox.StandardButton.Save,
            )

            if choice == QMessageBox.StandardButton.Cancel:
                return

            if choice == QMessageBox.StandardButton.Save:
                self._save_tab(
                    index,
                )

                if workspace_document.document.is_modified:
                    # Save As was cancelled; leave the tab open.
                    return

        self._document_service.close_document(
            document_id,
            discard_changes=True,
        )
        self.removeTab(
            index,
        )

    def _editor_at(
        self,
        index: int,
    ) -> SourceEditorWidget:
        """Return the editor widget at a tab index."""

        return self.widget(
            index,
        )

    def _editor_for(
        self,
        document_id: UUID,
    ) -> SourceEditorWidget | None:
        """Return the editor widget open for a document, if any."""

        index = self._index_for(
            document_id,
        )

        return (
            None
            if index < 0
            else self._editor_at(
                index,
            )
        )

    def _index_for(
        self,
        document_id: UUID,
    ) -> int:
        """Return the tab index open for a document, or -1."""

        for index in range(self.count()):
            widget = self.widget(
                index,
            )

            if (
                isinstance(
                    widget,
                    SourceEditorWidget,
                )
                and widget.document_id == document_id
            ):
                return index

        return -1


def _display_name(
    document: TextDocument,
) -> str:
    """Return a document's display name: its file name, or 'Untitled'."""

    return (
        document.path.name
        if document.path is not None
        else "Untitled"
    )


def _tab_title(
    document: TextDocument,
) -> str:
    """Return a tab's title, marking unsaved changes with a trailing `*`."""

    name = _display_name(
        document,
    )

    return (
        f"{name} *"
        if document.is_modified
        else name
    )


def _tab_tooltip(
    document: TextDocument,
) -> str:
    """Return a tab's tooltip: its full path, or 'Untitled'."""

    return (
        str(
            document.path,
        )
        if document.path is not None
        else "Untitled"
    )
