"""A tabbed source-code editor backed by the Qt-independent document model."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
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
from opencobol2.gui.bookmarks_panel import BookmarkEntry
from opencobol2.gui.coding_area_guides import CodingAreaGuides
from opencobol2.gui.syntax_highlighter import CobolSyntaxHighlighter
from opencobol2.gui.welcome_page import WelcomePageWidget
from opencobol2.language import (
    compute_fold_ranges,
    compute_outline,
    FoldRange,
    OutlineNode,
)
from opencobol2.settings import CobolGuideSettings, EditorSettings
from opencobol2.theming import Theme


_FOLD_MARKER_WIDTH = 14


_COBOL_SOURCE_EXTENSIONS = (
    ".cbl",
    ".cob",
)


def _is_cobol_source(
    path: Path | None,
) -> bool:
    """Return whether a path is recognized COBOL source, or is untitled.

    Untitled (unsaved) documents are treated as COBOL source too, since
    this IDE has no other file type to open or create yet.
    """

    return (
        path is None
        or path.suffix.lower() in _COBOL_SOURCE_EXTENSIONS
    )


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

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        self._editor.handle_line_number_area_click(
            event.position().toPoint(),
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

    bookmarks_changed = Signal()
    """Emitted whenever a bookmark is toggled on or off."""

    def __init__(
        self,
        *,
        document_id: UUID,
        initial_text: str,
        theme: Theme,
        editor_settings: EditorSettings | None = None,
        guide_settings: CobolGuideSettings | None = None,
        path: Path | None = None,
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
        self._guides = CodingAreaGuides(
            self,
        )
        self._guides.apply_theme(
            theme,
        )
        self._guides.apply_guide_settings(
            guide_settings
            if guide_settings is not None
            else CobolGuideSettings(),
        )

        self.is_cobol_source = _is_cobol_source(
            path,
        )
        self._highlighter = (
            CobolSyntaxHighlighter(
                self.document(),
                theme=theme,
            )
            if self.is_cobol_source
            else None
        )
        self._folding_enabled = False
        self._fold_ranges: tuple[
            FoldRange,
            ...,
        ] = ()
        self._collapsed_start_lines: set[
            int,
        ] = set()
        self._bookmarked_blocks: list[
            QTextBlock,
        ] = []
        self._bookmark_color = QColor(
            255,
            165,
            0,
        )

        self.blockCountChanged.connect(
            self._update_line_number_area_width,
        )
        self.blockCountChanged.connect(
            self._update_fold_ranges,
        )
        self.updateRequest.connect(
            self._update_line_number_area,
        )
        self.cursorPositionChanged.connect(
            self._highlight_current_line,
        )

        self.apply_editor_settings(
            editor_settings
            if editor_settings is not None
            else EditorSettings(),
        )
        self.setPlainText(
            initial_text,
        )
        self._update_line_number_area_width()
        self._highlight_current_line()
        self._update_fold_ranges()

    def apply_theme(
        self,
        theme: Theme,
    ) -> None:
        """Recolor the line-number gutter, current-line highlight, and syntax."""

        self._line_number_color = QColor(
            theme.colors.line_number_foreground,
        )
        self._current_line_color = QColor(
            theme.colors.current_line_highlight,
        )
        self._highlight_current_line()
        self._line_number_area.update()
        self._guides.apply_theme(
            theme,
        )

        if self._highlighter is not None:
            self._highlighter.apply_theme(
                theme,
            )

    def apply_editor_settings(
        self,
        editor_settings: EditorSettings,
    ) -> None:
        """Apply the configured font and tab width."""

        if editor_settings.font_family:
            font = QFont(
                editor_settings.font_family,
            )
        else:
            font = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont,
            )
            font.setStyleHint(
                QFont.StyleHint.Monospace,
            )
            font.setFixedPitch(
                True,
            )

        font.setPointSize(
            editor_settings.font_size,
        )
        self.setFont(
            font,
        )

        char_width = self.fontMetrics().horizontalAdvance(
            " ",
        )
        self.setTabStopDistance(
            char_width * editor_settings.tab_width,
        )

        self._folding_enabled = (
            editor_settings.code_folding
            and self._highlighter is not None
        )

        if not self._folding_enabled:
            self._expand_all_folds()

        self._update_fold_ranges()
        self._update_line_number_area_width()
        self.viewport().update()

    def apply_guide_settings(
        self,
        guide_settings: CobolGuideSettings,
    ) -> None:
        """Change which fixed-format coding-area guides are shown."""

        self._guides.apply_guide_settings(
            guide_settings,
        )

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

        width = (
            12
            + self.fontMetrics().horizontalAdvance(
                "9",
            )
            * digits
        )

        if self._folding_enabled:
            width += _FOLD_MARKER_WIDTH

        return width

    def paint_line_number_area(
        self,
        event: QPaintEvent,
    ) -> None:
        """Paint every visible block's line number (and fold marker) into the gutter."""

        painter = QPainter(
            self._line_number_area,
        )
        painter.fillRect(
            event.rect(),
            self.palette().color(
                self.backgroundRole(),
            ),
        )

        fold_starts = (
            {
                fold_range.start_line
                for fold_range in self._fold_ranges
            }
            if self._folding_enabled
            else frozenset()
        )
        bookmarked_lines = set(
            self.bookmarked_lines,
        )
        number_width = (
            self._line_number_area.width()
            - 4
            - (
                _FOLD_MARKER_WIDTH
                if self._folding_enabled
                else 0
            )
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
                line_number = block_number + 1
                painter.drawText(
                    0,
                    top,
                    number_width,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(
                        line_number,
                    ),
                )

                if line_number in fold_starts:
                    marker = (
                        "+"
                        if line_number
                        in self._collapsed_start_lines
                        else "-"
                    )
                    painter.drawText(
                        number_width,
                        top,
                        _FOLD_MARKER_WIDTH,
                        self.fontMetrics().height(),
                        Qt.AlignmentFlag.AlignCenter,
                        marker,
                    )

                if line_number in bookmarked_lines:
                    painter.fillRect(
                        0,
                        top,
                        4,
                        bottom - top,
                        self._bookmark_color,
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

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        super().paintEvent(
            event,
        )

        painter = QPainter(
            self.viewport(),
        )
        self._guides.paint(
            painter,
        )
        self._paint_fold_indicators(
            painter,
        )
        painter.end()

    def _paint_fold_indicators(
        self,
        painter: QPainter,
    ) -> None:
        """Mark each collapsed fold's start line with a small `...` badge."""

        if not self._collapsed_start_lines:
            return

        label = " ⋯ "
        label_width = self.fontMetrics().horizontalAdvance(
            label,
        )
        margin = self.document().documentMargin()

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

        while (
            block.isValid()
            and top <= self.viewport().rect().bottom()
        ):
            line_number = block_number + 1

            if (
                block.isVisible()
                and line_number
                in self._collapsed_start_lines
                and bottom >= 0
            ):
                text_width = (
                    self.fontMetrics().horizontalAdvance(
                        block.text(),
                    )
                )
                badge_rect = QRectF(
                    margin + text_width + 6,
                    top,
                    label_width,
                    self.fontMetrics().height(),
                )
                painter.fillRect(
                    badge_rect,
                    self._current_line_color,
                )
                painter.setPen(
                    self._line_number_color,
                )
                painter.drawText(
                    badge_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )

            block = block.next()
            top = bottom
            bottom = top + round(
                self.blockBoundingRect(
                    block,
                ).height()
            )
            block_number += 1

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

    def go_to_line(
        self,
        line_number: int,
        column: int = 1,
    ) -> None:
        """Move the cursor to a 1-based line/column and reveal it."""

        block = self.document().findBlockByNumber(
            max(
                line_number - 1,
                0,
            )
        )

        if not block.isValid():
            return

        cursor = QTextCursor(
            block,
        )
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            max(
                column - 1,
                0,
            ),
        )
        self.setTextCursor(
            cursor,
        )
        self.setFocus()
        self.ensureCursorVisible()

    def toggle_bookmark_at_cursor(
        self,
    ) -> None:
        """Toggle a bookmark on the cursor's current line.

        Bookmarks are stored as `QTextBlock` handles rather than plain
        line numbers, so they keep tracking the same physical line of
        text (via Qt's own block bookkeeping) when edits elsewhere shift
        line numbers around them -- the same class of staleness problem
        `_expand_all_folds()` had to be fixed for earlier.
        """

        self._prune_invalid_bookmarks()
        cursor_block = self.textCursor().block()
        cursor_line = cursor_block.blockNumber()

        for index, block in enumerate(
            self._bookmarked_blocks,
        ):
            if block.blockNumber() == cursor_line:
                del self._bookmarked_blocks[
                    index
                ]
                break
        else:
            self._bookmarked_blocks.append(
                cursor_block,
            )

        self._line_number_area.update()
        self.bookmarks_changed.emit()

    @property
    def bookmarked_lines(
        self,
    ) -> tuple[int, ...]:
        """Return every bookmarked 1-based line number, sorted."""

        self._prune_invalid_bookmarks()

        return tuple(
            sorted(
                block.blockNumber() + 1
                for block in self._bookmarked_blocks
            )
        )

    def _prune_invalid_bookmarks(
        self,
    ) -> None:
        self._bookmarked_blocks = [
            block
            for block in self._bookmarked_blocks
            if block.isValid()
        ]

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

    def handle_line_number_area_click(
        self,
        position: QPoint,
    ) -> None:
        """Toggle a fold if the gutter was clicked on a foldable line."""

        if not self._folding_enabled:
            return

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

        while block.isValid() and top <= position.y():
            if (
                block.isVisible()
                and top <= position.y() <= bottom
            ):
                self.toggle_fold(
                    block_number + 1,
                )
                return

            block = block.next()
            top = bottom
            bottom = top + round(
                self.blockBoundingRect(
                    block,
                ).height()
            )
            block_number += 1

    def toggle_fold(
        self,
        start_line: int,
    ) -> None:
        """Collapse or expand the foldable range starting at a line, if any."""

        fold_range = next(
            (
                candidate
                for candidate in self._fold_ranges
                if candidate.start_line == start_line
            ),
            None,
        )

        if fold_range is None:
            return

        self._set_fold_collapsed(
            fold_range,
            start_line
            not in self._collapsed_start_lines,
        )

    def _set_fold_collapsed(
        self,
        fold_range: FoldRange,
        collapsed: bool,
    ) -> None:
        if collapsed:
            self._hide_range(
                fold_range,
            )
            self._collapsed_start_lines.add(
                fold_range.start_line,
            )
        else:
            self._show_range(
                fold_range,
            )
            self._collapsed_start_lines.discard(
                fold_range.start_line,
            )

            # Re-hide any nested range that was already collapsed on its
            # own -- expanding the parent must not silently expand it too.
            for nested_range in self._fold_ranges:
                if (
                    nested_range.start_line
                    in self._collapsed_start_lines
                    and fold_range.start_line
                    < nested_range.start_line
                    < fold_range.end_line
                ):
                    self._hide_range(
                        nested_range,
                    )

        document = self.document()
        document.markContentsDirty(
            0,
            document.characterCount(),
        )
        self._update_line_number_area_width()
        self._line_number_area.update()
        self.viewport().update()

    def _hide_range(
        self,
        fold_range: FoldRange,
    ) -> None:
        for block_number in range(
            fold_range.start_line,
            fold_range.end_line,
        ):
            block = self.document().findBlockByNumber(
                block_number,
            )

            if block.isValid():
                block.setVisible(
                    False,
                )

    def _show_range(
        self,
        fold_range: FoldRange,
    ) -> None:
        for block_number in range(
            fold_range.start_line,
            fold_range.end_line,
        ):
            block = self.document().findBlockByNumber(
                block_number,
            )

            if block.isValid():
                block.setVisible(
                    True,
                )

    def _expand_all_folds(
        self,
    ) -> None:
        """Force every block visible, regardless of what's tracked as folded.

        Used as a full reset (folding turned off, or the document structure
        shifted underneath a fold) rather than a normal toggle, so it does
        not try to map stale collapsed start lines onto current fold
        ranges -- that mapping is exactly what may no longer be valid.
        """

        if not self._collapsed_start_lines:
            return

        document = self.document()

        for block_number in range(
            document.blockCount(),
        ):
            block = document.findBlockByNumber(
                block_number,
            )

            if block.isValid():
                block.setVisible(
                    True,
                )

        self._collapsed_start_lines = set()
        document.markContentsDirty(
            0,
            document.characterCount(),
        )

    def _update_fold_ranges(
        self,
        _new_block_count: int = 0,
    ) -> None:
        if not self._folding_enabled:
            self._fold_ranges = ()
            return

        self._fold_ranges = compute_fold_ranges(
            self.toPlainText(),
        )
        valid_start_lines = {
            fold_range.start_line
            for fold_range in self._fold_ranges
        }

        if not self._collapsed_start_lines.issubset(
            valid_start_lines,
        ):
            # The document structure changed underneath a fold (lines were
            # added/removed); the safest recovery is to expand everything
            # rather than risk hiding the wrong lines.
            self._expand_all_folds()

        self._line_number_area.update()


class EditorTabsWidget(QTabWidget):
    """Docks every open document from a `DocumentService` as its own tab."""

    active_document_changed = Signal()
    """Emitted when the active tab switches, or its text changes."""

    bookmarks_changed = Signal()
    """Emitted whenever any open tab's bookmarks change."""

    def __init__(
        self,
        *,
        document_service: DocumentService,
        theme: Theme,
        editor_settings: EditorSettings | None = None,
        guide_settings: CobolGuideSettings | None = None,
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
        self._editor_settings = (
            editor_settings
            if editor_settings is not None
            else EditorSettings()
        )
        self._guide_settings = (
            guide_settings
            if guide_settings is not None
            else CobolGuideSettings()
        )

        self.setTabsClosable(
            True,
        )
        self.tabCloseRequested.connect(
            self._close_tab,
        )
        self.currentChanged.connect(
            lambda _index: self.active_document_changed.emit()
        )

        self._welcome_page = WelcomePageWidget(
            self,
        )
        self._update_welcome_page_visibility()

    @property
    def document_service(
        self,
    ) -> DocumentService:
        """Return the document service backing this editor area."""

        return self._document_service

    @property
    def welcome_page(
        self,
    ) -> WelcomePageWidget:
        """Return the overlay shown when no documents are open."""

        return self._welcome_page

    def resizeEvent(
        self,
        event: QResizeEvent,
    ) -> None:
        """Keep the welcome-page overlay sized to the full tab area."""

        super().resizeEvent(
            event,
        )

        self._welcome_page.setGeometry(
            self.rect(),
        )

    def _update_welcome_page_visibility(
        self,
    ) -> None:
        """Show the welcome page only when there are no open tabs."""

        has_open_documents = self.count() > 0
        self._welcome_page.setVisible(
            not has_open_documents,
        )

        if not has_open_documents:
            self._welcome_page.raise_()

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

    def apply_editor_settings(
        self,
        editor_settings: EditorSettings,
    ) -> None:
        """Apply the configured font and tab width to every open tab."""

        self._editor_settings = editor_settings

        for index in range(self.count()):
            self._editor_at(
                index,
            ).apply_editor_settings(
                editor_settings,
            )

    def apply_guide_settings(
        self,
        guide_settings: CobolGuideSettings,
    ) -> None:
        """Change which coding-area guides every open tab shows."""

        self._guide_settings = guide_settings

        for index in range(self.count()):
            self._editor_at(
                index,
            ).apply_guide_settings(
                guide_settings,
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

    def open_path_at_line(
        self,
        path: Path | str,
        line_number: int,
        column: int = 1,
    ) -> None:
        """Open a file (reusing an already-open tab) and reveal a location."""

        self.open_path(
            path,
        )
        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.go_to_line(
                line_number,
                column,
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
            editor_settings=self._editor_settings,
            guide_settings=self._guide_settings,
            path=workspace_document.document.path,
        )
        document_id = workspace_document.document_id
        editor.textChanged.connect(
            lambda: self._handle_text_changed(
                document_id,
            )
        )
        editor.textChanged.connect(
            lambda: self._handle_active_editor_text_changed(
                document_id,
            )
        )
        editor.bookmarks_changed.connect(
            self.bookmarks_changed.emit,
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
        self._update_welcome_page_visibility()

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

    def _handle_active_editor_text_changed(
        self,
        document_id: UUID,
    ) -> None:
        """Re-announce the active document changing on a same-tab edit."""

        if self._editor_for(
            document_id,
        ) is self.currentWidget():
            self.active_document_changed.emit()

    def current_outline(
        self,
    ) -> tuple[OutlineNode, ...]:
        """Return the active tab's COBOL outline, or `()` if none applies."""

        editor = self.currentWidget()

        if (
            isinstance(
                editor,
                SourceEditorWidget,
            )
            and editor.is_cobol_source
        ):
            return compute_outline(
                editor.toPlainText(),
            )

        return ()

    def go_to_active_line(
        self,
        line_number: int,
        column: int = 1,
    ) -> None:
        """Move the active tab's cursor to a 1-based line/column."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.go_to_line(
                line_number,
                column,
            )

    def toggle_bookmark_on_active_tab(
        self,
    ) -> None:
        """Toggle a bookmark on the active tab's cursor line, if any."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.toggle_bookmark_at_cursor()

    def all_bookmarks(
        self,
    ) -> tuple[BookmarkEntry, ...]:
        """Return every bookmark across every open tab."""

        entries: list[BookmarkEntry] = []

        for index in range(
            self.count(),
        ):
            editor = self._editor_at(
                index,
            )
            workspace_document = (
                self._document_service.workspace.get_document(
                    editor.document_id,
                )
            )

            for line in editor.bookmarked_lines:
                block = editor.document().findBlockByNumber(
                    line - 1,
                )
                entries.append(
                    BookmarkEntry(
                        document_id=editor.document_id,
                        display_name=_display_name(
                            workspace_document.document,
                        ),
                        line=line,
                        text=block.text().strip(),
                    )
                )

        return tuple(
            entries,
        )

    def reveal_bookmark(
        self,
        document_id: UUID,
        line_number: int,
        column: int = 1,
    ) -> None:
        """Activate the tab for a document and move its cursor to a line."""

        index = self._index_for(
            document_id,
        )

        if index < 0:
            return

        self.setCurrentIndex(
            index,
        )
        self._editor_at(
            index,
        ).go_to_line(
            line_number,
            column,
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
        self._update_welcome_page_visibility()

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
