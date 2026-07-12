"""A tabbed source-code editor backed by the Qt-independent document model."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from opencobol2.documents import (
    DocumentAlreadyOpenError,
    DocumentService,
    TextDocument,
    WorkspaceDocument,
)
from opencobol2.theming import Theme


class _LineNumberArea(QWidget):
    """The gutter widget that paints one editor's line numbers."""

    def __init__(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        super().__init__(
            editor,
        )

        self._editor = editor

    def sizeHint(
        self,
    ) -> QSize:
        return QSize(
            self._editor.line_number_area_width(),
            0,
        )

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        self._editor.paint_line_number_area(
            event,
        )


class _FindReplaceBar(QWidget):
    """A floating overlay for finding and replacing text in one editor."""

    def __init__(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        super().__init__(
            editor,
        )

        self._editor = editor
        self.setAutoFillBackground(
            True,
        )

        layout = QVBoxLayout(
            self,
        )
        layout.setContentsMargins(
            6,
            4,
            6,
            4,
        )

        find_row = QHBoxLayout()

        self.find_edit = QLineEdit()
        self.find_edit.returnPressed.connect(
            self._handle_find_next,
        )
        find_row.addWidget(
            self.find_edit,
        )

        self.case_sensitive_check = QCheckBox(
            "Match case",
        )
        find_row.addWidget(
            self.case_sensitive_check,
        )

        previous_button = QPushButton(
            "Previous",
        )
        previous_button.clicked.connect(
            self._handle_find_previous,
        )
        find_row.addWidget(
            previous_button,
        )

        next_button = QPushButton(
            "Next",
        )
        next_button.clicked.connect(
            self._handle_find_next,
        )
        find_row.addWidget(
            next_button,
        )

        close_button = QPushButton(
            "Close",
        )
        close_button.clicked.connect(
            self._editor.hide_find_bar,
        )
        find_row.addWidget(
            close_button,
        )

        layout.addLayout(
            find_row,
        )

        self._replace_row_widget = QWidget()
        replace_row = QHBoxLayout(
            self._replace_row_widget,
        )
        replace_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.replace_edit = QLineEdit()
        replace_row.addWidget(
            self.replace_edit,
        )

        replace_button = QPushButton(
            "Replace",
        )
        replace_button.clicked.connect(
            self._handle_replace,
        )
        replace_row.addWidget(
            replace_button,
        )

        replace_all_button = QPushButton(
            "Replace All",
        )
        replace_all_button.clicked.connect(
            self._handle_replace_all,
        )
        replace_row.addWidget(
            replace_all_button,
        )

        layout.addWidget(
            self._replace_row_widget,
        )

        self.status_label = QLabel()
        layout.addWidget(
            self.status_label,
        )

    def set_replace_visible(
        self,
        visible: bool,
    ) -> None:
        """Show or hide the replace row for find-only vs. find-and-replace."""

        self._replace_row_widget.setVisible(
            visible,
        )

    def _flags(
        self,
    ) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(
            0,
        )

        if self.case_sensitive_check.isChecked():
            flags |= (
                QTextDocument.FindFlag.FindCaseSensitively
            )

        return flags

    def _handle_find_next(
        self,
    ) -> None:
        self._report_found(
            self._editor.find_text(
                self.find_edit.text(),
                backwards=False,
                flags=self._flags(),
            )
        )

    def _handle_find_previous(
        self,
    ) -> None:
        self._report_found(
            self._editor.find_text(
                self.find_edit.text(),
                backwards=True,
                flags=self._flags(),
            )
        )

    def _handle_replace(
        self,
    ) -> None:
        self._report_found(
            self._editor.replace_current(
                self.find_edit.text(),
                self.replace_edit.text(),
                flags=self._flags(),
            )
        )

    def _handle_replace_all(
        self,
    ) -> None:
        count = self._editor.replace_all(
            self.find_edit.text(),
            self.replace_edit.text(),
            flags=self._flags(),
        )
        self.status_label.setText(
            f"Replaced {count} occurrence(s)."
            if count
            else "No occurrences found."
        )

    def _report_found(
        self,
        found: bool,
    ) -> None:
        self.status_label.setText(
            ""
            if found
            else "No occurrences found.",
        )


class SourceEditorWidget(QPlainTextEdit):
    """A plain-text editor for exactly one open document."""

    def __init__(
        self,
        *,
        document_id: UUID,
        initial_text: str,
        theme: Theme,
        parent: QWidget | None = None,
    ) -> None:
        """Build an editor preloaded with one document's text."""

        super().__init__(
            parent,
        )

        self.document_id = document_id
        self._line_number_color = QColor(
            theme.colors.line_number_foreground,
        )
        self._current_line_color = QColor(
            theme.colors.current_line_highlight,
        )
        self._line_number_area = _LineNumberArea(
            self,
        )
        self._find_bar = _FindReplaceBar(
            self,
        )
        self._find_bar.hide()

        self.blockCountChanged.connect(
            self._update_line_number_area_width,
        )
        self.updateRequest.connect(
            self._update_line_number_area,
        )
        self.cursorPositionChanged.connect(
            self._highlight_current_line,
        )

        self.setPlainText(
            initial_text,
        )
        self._update_line_number_area_width()
        self._highlight_current_line()

    def apply_theme(
        self,
        theme: Theme,
    ) -> None:
        """Recolor the line-number gutter and current-line highlight."""

        self._line_number_color = QColor(
            theme.colors.line_number_foreground,
        )
        self._current_line_color = QColor(
            theme.colors.current_line_highlight,
        )
        self._highlight_current_line()
        self._line_number_area.update()

    def line_number_area_width(
        self,
    ) -> int:
        """Return the gutter width needed for the current line count."""

        digits = len(
            str(
                max(
                    1,
                    self.blockCount(),
                ),
            )
        )

        return (
            12
            + self.fontMetrics().horizontalAdvance(
                "9",
            )
            * digits
        )

    def paint_line_number_area(
        self,
        event: QPaintEvent,
    ) -> None:
        """Paint every visible block's line number into the gutter."""

        painter = QPainter(
            self._line_number_area,
        )
        painter.fillRect(
            event.rect(),
            self.palette().color(
                self.backgroundRole(),
            ),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(
                block,
            )
            .translated(
                self.contentOffset(),
            )
            .top()
        )
        bottom = top + round(
            self.blockBoundingRect(
                block,
            ).height()
        )
        painter.setPen(
            self._line_number_color,
        )

        while (
            block.isValid()
            and top <= event.rect().bottom()
        ):
            if (
                block.isVisible()
                and bottom >= event.rect().top()
            ):
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(
                        block_number + 1,
                    ),
                )

            block = block.next()
            top = bottom
            bottom = top + round(
                self.blockBoundingRect(
                    block,
                ).height()
            )
            block_number += 1

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        super().resizeEvent(
            event,
        )

        contents_rect = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(
                contents_rect.left(),
                contents_rect.top(),
                self.line_number_area_width(),
                contents_rect.height(),
            )
        )
        self._position_find_bar()

    def show_find_bar(
        self,
    ) -> None:
        """Reveal the find bar, prefilled from any current selection."""

        self._find_bar.set_replace_visible(
            False,
        )
        self._reveal_find_bar()

    def show_replace_bar(
        self,
    ) -> None:
        """Reveal the find bar with its replace row visible."""

        self._find_bar.set_replace_visible(
            True,
        )
        self._reveal_find_bar()

    def hide_find_bar(
        self,
    ) -> None:
        """Hide the find bar and return focus to the editor."""

        self._find_bar.hide()
        self.setFocus()

    def find_text(
        self,
        text: str,
        *,
        backwards: bool,
        flags: QTextDocument.FindFlag = QTextDocument.FindFlag(
            0,
        ),
    ) -> bool:
        """Find one occurrence, wrapping around the document once if needed."""

        if not text:
            return False

        search_flags = (
            flags | QTextDocument.FindFlag.FindBackward
            if backwards
            else flags
        )

        if self.find(
            text,
            search_flags,
        ):
            return True

        cursor = self.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End
            if backwards
            else QTextCursor.MoveOperation.Start,
        )
        self.setTextCursor(
            cursor,
        )

        return self.find(
            text,
            search_flags,
        )

    def replace_current(
        self,
        find_text_value: str,
        replace_text_value: str,
        *,
        flags: QTextDocument.FindFlag = QTextDocument.FindFlag(
            0,
        ),
    ) -> bool:
        """Replace the current match (if selected) and find the next one."""

        cursor = self.textCursor()

        if cursor.hasSelection() and _texts_match(
            cursor.selectedText(),
            find_text_value,
            flags,
        ):
            cursor.insertText(
                replace_text_value,
            )
            self.setTextCursor(
                cursor,
            )

        return self.find_text(
            find_text_value,
            backwards=False,
            flags=flags,
        )

    def replace_all(
        self,
        find_text_value: str,
        replace_text_value: str,
        *,
        flags: QTextDocument.FindFlag = QTextDocument.FindFlag(
            0,
        ),
    ) -> int:
        """Replace every occurrence in the document; return the count."""

        if not find_text_value:
            return 0

        cursor = self.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.Start,
        )
        self.setTextCursor(
            cursor,
        )

        replaced_count = 0

        while self.find(
            find_text_value,
            flags,
        ):
            match_cursor = self.textCursor()
            match_cursor.insertText(
                replace_text_value,
            )
            self.setTextCursor(
                match_cursor,
            )
            replaced_count += 1

        return replaced_count

    def _reveal_find_bar(
        self,
    ) -> None:
        self._find_bar.show()
        self._position_find_bar()
        self._find_bar.raise_()

        selected_text = self.textCursor().selectedText()

        if selected_text:
            self._find_bar.find_edit.setText(
                selected_text,
            )

        self._find_bar.find_edit.setFocus()
        self._find_bar.find_edit.selectAll()

    def _position_find_bar(
        self,
    ) -> None:
        if not self._find_bar.isVisible():
            return

        bar_width = min(
            420,
            max(
                self.width() - 8,
                1,
            ),
        )
        self._find_bar.setFixedWidth(
            bar_width,
        )
        self._find_bar.move(
            self.width() - bar_width - 4,
            4,
        )

    def _update_line_number_area_width(
        self,
        _new_block_count: int = 0,
    ) -> None:
        self.setViewportMargins(
            self.line_number_area_width(),
            0,
            0,
            0,
        )

    def _update_line_number_area(
        self,
        rect: QRect,
        scrolled_by: int,
    ) -> None:
        if scrolled_by:
            self._line_number_area.scroll(
                0,
                scrolled_by,
            )
        else:
            self._line_number_area.update(
                0,
                rect.y(),
                self._line_number_area.width(),
                rect.height(),
            )

        if rect.contains(
            self.viewport().rect(),
        ):
            self._update_line_number_area_width()

    def _highlight_current_line(
        self,
    ) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(
            self._current_line_color,
        )
        selection.format.setProperty(
            QTextFormat.Property.FullWidthSelection,
            True,
        )
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()

        self.setExtraSelections(
            [
                selection,
            ]
        )


class EditorTabsWidget(QTabWidget):
    """Docks every open document from a `DocumentService` as its own tab."""

    def __init__(
        self,
        *,
        document_service: DocumentService,
        theme: Theme,
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

        if not isinstance(
            theme,
            Theme,
        ):
            raise TypeError(
                "Editor tabs theme must be Theme."
            )

        self._document_service = document_service
        self._theme = theme

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

    def apply_theme(
        self,
        theme: Theme,
    ) -> None:
        """Recolor every open tab's line-number gutter and current line."""

        if not isinstance(
            theme,
            Theme,
        ):
            raise TypeError(
                "Editor tabs theme must be Theme."
            )

        self._theme = theme

        for index in range(self.count()):
            self._editor_at(
                index,
            ).apply_theme(
                theme,
            )

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

    def show_find(
        self,
    ) -> None:
        """Show the find bar on the active tab, if any."""

        editor = self.currentWidget()

        if editor is not None:
            editor.show_find_bar()

    def show_replace(
        self,
    ) -> None:
        """Show the find-and-replace bar on the active tab, if any."""

        editor = self.currentWidget()

        if editor is not None:
            editor.show_replace_bar()

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
            theme=self._theme,
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


def _texts_match(
    selected_text: str,
    target_text: str,
    flags: QTextDocument.FindFlag,
) -> bool:
    """Return whether selected text is the same match as the search text."""

    if bool(
        flags
        & QTextDocument.FindFlag.FindCaseSensitively,
    ):
        return selected_text == target_text

    return (
        selected_text.casefold()
        == target_text.casefold()
    )
