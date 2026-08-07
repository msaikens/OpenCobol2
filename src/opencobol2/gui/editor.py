"""A tabbed source-code editor backed by the Qt-independent document model."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFocusEvent,
    QFont,
    QFontDatabase,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextBlock,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from opencobol2.compiler import CompilerDiagnostic
from opencobol2.documents import (
    DocumentAlreadyOpenError,
    DocumentDecodeError,
    DocumentService,
    TextDocument,
    WorkspaceDocument,
)
from opencobol2.gui.bookmarks_panel import BookmarkEntry
from opencobol2.gui.breakpoints_panel import BreakpointEntry
from opencobol2.gui.coding_area_guides import CodingAreaGuides
from opencobol2.gui.find_results_panel import FindResult
from opencobol2.gui.syntax_highlighter import CobolSyntaxHighlighter
from opencobol2.gui.welcome_page import WelcomePageWidget
from opencobol2.language import (
    compute_completions,
    compute_fold_ranges,
    compute_hover,
    compute_outline,
    compute_quick_fix,
    compute_signature_help,
    find_definition,
    find_references,
    parse_snippet_body,
    CompletionItem,
    CompletionItemKind,
    FoldRange,
    HoverInfo,
    LexDiagnostic,
    OutlineNode,
    ParseDiagnostic,
    QuickFix,
    SourceLocation,
)
from opencobol2.settings import CobolGuideSettings, EditorSettings
from opencobol2.theming import Theme


_FOLD_MARKER_WIDTH = 14


_BREAKPOINT_MARKER_WIDTH = 10
_BOOKMARK_MARKER_WIDTH = 4


_MINIMAP_WIDTH = 80
_MINIMAP_MAX_LINE_CHARS = 80


_COBOL_SOURCE_EXTENSIONS = (
    ".cbl",
    ".cob",
)


_COMPLETION_DEBOUNCE_MILLISECONDS = 150
_COMPLETION_POPUP_WIDTH = 320
_COMPLETION_POPUP_HEIGHT = 160

# Hyphen-inclusive, the same word-boundary convention
# `rename_symbol_at_cursor` and `opencobol2.language.completion` both
# already use, since COBOL names legally contain hyphens.
_IDENTIFIER_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "abcdefghijklmnopqrstuvwxyz" "0123456789-"
)


def _is_identifier_character(
    text: str,
) -> bool:
    """Return whether a `QKeyEvent.text()` value is one COBOL identifier character."""

    return (
        len(text) == 1
        and text in _IDENTIFIER_CHARACTERS
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


class _MinimapArea(QWidget):
    """The scaled-down document-overview strip alongside one editor."""

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
            self._editor.minimap_area_width(),
            0,
        )

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        self._editor.paint_minimap(
            event,
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        self._editor.handle_minimap_click(
            event.position().toPoint(),
        )

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._editor.handle_minimap_click(
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


class _CompletionPopup(QWidget):
    """A floating overlay listing completion candidates for one editor.

    The same "floating overlay child widget positioned relative to the
    editor's viewport" pattern `_FindReplaceBar` already establishes,
    just triggered by typing instead of a menu command.
    """

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
        self.setFocusPolicy(
            Qt.FocusPolicy.NoFocus,
        )

        layout = QVBoxLayout(
            self,
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(
            Qt.FocusPolicy.NoFocus,
        )
        self.list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked,
        )
        layout.addWidget(
            self.list_widget,
        )

        self._items: tuple[
            CompletionItem,
            ...,
        ] = ()

    def set_items(
        self,
        items: tuple[CompletionItem, ...],
    ) -> None:
        """Replace the candidate list and select the first entry."""

        self._items = items
        self.list_widget.clear()

        for item in items:
            self.list_widget.addItem(
                item.label
                if item.detail is None
                else f"{item.label}  —  {item.detail}"
            )

        if items:
            self.list_widget.setCurrentRow(
                0,
            )

    def selected_item(
        self,
    ) -> CompletionItem | None:
        """Return the currently highlighted candidate, if any."""

        row = self.list_widget.currentRow()

        if 0 <= row < len(self._items):
            return self._items[row]

        return None

    def select_next(
        self,
    ) -> None:
        """Move the highlight to the next candidate, wrapping around."""

        if not self._items:
            return

        row = self.list_widget.currentRow()
        self.list_widget.setCurrentRow(
            (row + 1) % len(self._items),
        )

    def select_previous(
        self,
    ) -> None:
        """Move the highlight to the previous candidate, wrapping around."""

        if not self._items:
            return

        row = self.list_widget.currentRow()
        self.list_widget.setCurrentRow(
            (row - 1) % len(self._items),
        )

    def _handle_item_double_clicked(
        self,
        _list_item,
    ) -> None:
        self._editor.accept_selected_completion()


class SourceEditorWidget(QPlainTextEdit):
    """A plain-text editor for exactly one open document."""

    bookmarks_changed = Signal()
    """Emitted whenever a bookmark is toggled on or off."""

    breakpoints_changed = Signal()
    """Emitted whenever a breakpoint is toggled on or off."""

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

        # Coding-area column guides (and printing) are painted from
        # "one visual row == one logical line starting at column 1" --
        # true only without word-wrap. Fixed-format COBOL is
        # column-sensitive by convention anyway, so a horizontal
        # scrollbar on an overly-long line is the right trade-off here,
        # not silently wrapping it and desyncing every guide line past
        # the first visual row.
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap,
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
        self._minimap_enabled = True
        self._minimap_area = _MinimapArea(
            self,
        )
        self._apply_minimap_colors(
            theme,
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
        self._breakpointed_blocks: list[
            QTextBlock,
        ] = []
        self._breakpoint_color = QColor(
            224,
            60,
            60,
        )

        self._completion_popup = _CompletionPopup(
            self,
        )
        self._completion_popup.hide()
        self._completion_prefix_start: int | None = None
        self._completion_debounce_timer = QTimer(
            self,
        )
        self._completion_debounce_timer.setSingleShot(
            True,
        )
        self._completion_debounce_timer.setInterval(
            _COMPLETION_DEBOUNCE_MILLISECONDS,
        )
        self._completion_debounce_timer.timeout.connect(
            self._refresh_completions,
        )
        self._active_snippet_stops: list[
            QTextCursor,
        ] | None = None
        self._active_snippet_index = 0

        self.blockCountChanged.connect(
            self._update_line_number_area_width,
        )
        # textChanged, not blockCountChanged: an in-place edit that
        # keeps the same line count (e.g. replacing an IF line's text
        # with a DISPLAY statement on that same physical line) still
        # changes which lines should fold, but never fires
        # blockCountChanged -- leaving toggle_fold() working off a
        # now-stale range for a fold-start line that may not even be a
        # fold-start anymore.
        self.textChanged.connect(
            self._update_fold_ranges,
        )
        self.updateRequest.connect(
            self._update_line_number_area,
        )
        self.updateRequest.connect(
            self._update_minimap,
        )
        self.blockCountChanged.connect(
            self._update_minimap,
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
        self._apply_minimap_colors(
            theme,
        )
        self._minimap_area.update()
        self._guides.apply_theme(
            theme,
        )

        if self._highlighter is not None:
            self._highlighter.apply_theme(
                theme,
            )

    def refresh_cobol_support(
        self,
        path: Path | None,
        theme: Theme,
    ) -> None:
        """Re-evaluate COBOL support after this tab's on-disk path changes.

        `is_cobol_source`/the highlighter/folding are otherwise only
        ever set up once, from the path given at construction time --
        Save As can turn a plain-text tab into a `.cbl`/`.cob` one (or
        the reverse) without the tab ever being recreated, so nothing
        would otherwise notice. Must be called explicitly after a
        successful Save As.
        """

        new_is_cobol_source = _is_cobol_source(
            path,
        )

        if new_is_cobol_source == self.is_cobol_source:
            return

        self.is_cobol_source = new_is_cobol_source

        if self._highlighter is not None:
            # Detach before dropping the reference -- parented to the
            # document, it would otherwise keep being invoked by Qt's
            # own rendering pipeline even with no Python reference
            # left to it.
            self._highlighter.setDocument(
                None,
            )
            self._highlighter = None

        if self.is_cobol_source:
            self._highlighter = CobolSyntaxHighlighter(
                self.document(),
                theme=theme,
            )

        # Folding is gated on `self._highlighter is not None`;
        # re-running this recomputes _folding_enabled and expands any
        # folds if support was just lost.
        self.apply_editor_settings(
            self._editor_settings,
        )

    def _apply_minimap_colors(
        self,
        theme: Theme,
    ) -> None:
        self._minimap_foreground_color = QColor(
            theme.colors.editor_foreground,
        )
        self._minimap_viewport_color = QColor(
            theme.colors.current_line_highlight,
        )

    def _update_minimap(
        self,
        *_args,
    ) -> None:
        self._minimap_area.update()

    def apply_editor_settings(
        self,
        editor_settings: EditorSettings,
    ) -> None:
        """Apply the configured font and tab width."""

        self._editor_settings = editor_settings

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
        self._minimap_enabled = editor_settings.show_minimap
        self._minimap_area.setVisible(
            self._minimap_enabled,
        )
        self._update_line_number_area_width()
        self._position_minimap_area()
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
            + _BREAKPOINT_MARKER_WIDTH
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
        breakpoint_lines = set(
            self.breakpoint_lines,
        )
        marker_width = (
            _BREAKPOINT_MARKER_WIDTH
            + _BOOKMARK_MARKER_WIDTH
        )
        number_width = (
            self._line_number_area.width()
            - marker_width
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
                    marker_width,
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
                        marker_width
                        + number_width,
                        top,
                        _FOLD_MARKER_WIDTH,
                        self.fontMetrics().height(),
                        Qt.AlignmentFlag.AlignCenter,
                        marker,
                    )

                if line_number in bookmarked_lines:
                    painter.fillRect(
                        _BREAKPOINT_MARKER_WIDTH,
                        top,
                        _BOOKMARK_MARKER_WIDTH,
                        bottom - top,
                        self._bookmark_color,
                    )

                if line_number in breakpoint_lines:
                    painter.setPen(
                        Qt.PenStyle.NoPen,
                    )
                    painter.setBrush(
                        self._breakpoint_color,
                    )
                    diameter = min(
                        _BREAKPOINT_MARKER_WIDTH,
                        bottom - top,
                    ) - 2
                    painter.drawEllipse(
                        QPointF(
                            _BREAKPOINT_MARKER_WIDTH / 2,
                            (top + bottom) / 2,
                        ),
                        diameter / 2,
                        diameter / 2,
                    )
                    painter.setBrush(
                        Qt.BrushStyle.NoBrush,
                    )
                    painter.setPen(
                        self._line_number_color,
                    )

            block = block.next()
            top = bottom
            bottom = top + round(
                self.blockBoundingRect(
                    block,
                ).height()
            )
            block_number += 1

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
        """Expand Tab to spaces when configured, otherwise default handling.

        The lexer computes every highlight/diagnostic column against a
        tab-*expanded* copy of each line (`language/lexer.py`'s own
        `expandtabs`), but a literal `\\t` character in the real
        document text shifts every subsequent column on that line out
        from under those positions -- there's no way to reconcile the
        two without either translating columns back through expansion
        everywhere they're consumed, or simply not letting a literal
        tab reach the document in the first place. `insert_spaces`
        already exists for `format_document()`'s on-demand conversion;
        honoring it here for live typing closes the gap at the source
        instead.
        """

        if (
            self._active_snippet_stops is not None
            and self._handle_snippet_session_key(
                event,
            )
        ):
            return

        if (
            self._completion_popup.isVisible()
            and self._handle_completion_popup_key(
                event,
            )
        ):
            return

        if (
            event.key() == Qt.Key.Key_Space
            and event.modifiers()
            == Qt.KeyboardModifier.ControlModifier
        ):
            self.trigger_suggest()
            return

        if (
            event.key() == Qt.Key.Key_Tab
            and self._editor_settings.insert_spaces
            and not self.textCursor().hasSelection()
        ):
            cursor = self.textCursor()
            tab_width = self._editor_settings.tab_width
            column = cursor.positionInBlock()
            spaces_needed = tab_width - (column % tab_width)
            cursor.insertText(
                " " * spaces_needed,
            )
            return

        super().keyPressEvent(
            event,
        )

        if not self.is_cobol_source:
            return

        if _is_identifier_character(
            event.text(),
        ) or event.key() == Qt.Key.Key_Backspace:
            self._completion_debounce_timer.start()
        else:
            self._close_completion_popup()

    def _handle_snippet_session_key(
        self,
        event: QKeyEvent,
    ) -> bool:
        """Handle a keypress while a snippet tab-stop session is active.

        Only Tab (advance) and Escape (cancel) are intercepted --
        every other key, including ordinary typing, falls through to
        normal editing, which replaces a stop's selected default text
        via Qt's own selection-replace semantics with no special
        handling needed here.
        """

        if event.key() == Qt.Key.Key_Tab:
            self._advance_snippet_stop()
            return True

        if event.key() == Qt.Key.Key_Escape:
            self._end_snippet_session()
            return True

        return False

    def _handle_completion_popup_key(
        self,
        event: QKeyEvent,
    ) -> bool:
        """Handle a keypress while the completion popup is visible."""

        if event.key() == Qt.Key.Key_Escape:
            self._close_completion_popup()
            return True

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
        ):
            self.accept_selected_completion()
            return True

        if event.key() == Qt.Key.Key_Up:
            self._completion_popup.select_previous()
            return True

        if event.key() == Qt.Key.Key_Down:
            self._completion_popup.select_next()
            return True

        return False

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
        self._position_minimap_area()
        self._position_find_bar()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """Dismiss the completion popup before any click repositions the cursor."""

        self._close_completion_popup()
        super().mousePressEvent(
            event,
        )

    def focusOutEvent(
        self,
        event: QFocusEvent,
    ) -> None:
        """Dismiss the completion popup when focus leaves this editor."""

        self._close_completion_popup()
        super().focusOutEvent(
            event,
        )

    def _position_minimap_area(
        self,
    ) -> None:
        contents_rect = self.contentsRect()
        width = self.minimap_area_width()
        self._minimap_area.setGeometry(
            QRect(
                contents_rect.right() - width,
                contents_rect.top(),
                width,
                contents_rect.height(),
            )
        )

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

    def event(
        self,
        event: QEvent,
    ) -> bool:
        """Intercept tooltip events to show hover info over COBOL identifiers."""

        if event.type() == QEvent.Type.ToolTip:
            info = self.hover_info_at(
                event.pos(),
            )

            if info is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(
                    event.globalPos(),
                    info.detail,
                    self,
                )

            return True

        return super().event(
            event,
        )

    def contextMenuEvent(
        self,
        event: QContextMenuEvent,
    ) -> None:
        """Show the standard context menu, plus a quick fix if one applies."""

        menu = self.build_context_menu(
            event.pos(),
        )
        menu.exec(
            event.globalPos(),
        )

    def build_context_menu(
        self,
        pos: QPoint,
    ) -> QMenu:
        """Build the context menu for a position, without showing it.

        Kept separate from `contextMenuEvent` so the menu's *contents*
        are directly testable: `QMenu.exec()` opens a real, blocking
        native popup loop that doesn't return until dismissed, and
        (unlike overriding a Qt virtual method by subclassing) it can't
        be intercepted by monkeypatching `QMenu.exec` at the class level
        -- PySide6 exposes it as a bound C++ method, not a plain
        Python-overridable descriptor, so a test that patched it and
        called `contextMenuEvent` directly would hang forever waiting
        on a popup nothing will ever dismiss.
        """

        menu = self.createStandardContextMenu(
            pos,
        )
        quick_fix = self.quick_fix_at(
            pos,
        )

        if quick_fix is not None:
            fix_action = menu.addAction(
                quick_fix.title,
            )
            fix_action.triggered.connect(
                lambda: self.apply_quick_fix(
                    quick_fix,
                )
            )
            existing_actions = menu.actions()
            menu.insertAction(
                existing_actions[0],
                fix_action,
            )
            menu.insertSeparator(
                existing_actions[0],
            )

        return menu

    def quick_fix_at(
        self,
        pos: QPoint,
    ) -> QuickFix | None:
        """Return the quick fix for a diagnostic on the line at a position, if any."""

        if not self.is_cobol_source:
            return None

        line = (
            self.cursorForPosition(
                pos,
            ).blockNumber()
            + 1
        )
        text = self.toPlainText()

        for diagnostic in self.diagnostics:
            if diagnostic.position.line != line:
                continue

            fix = compute_quick_fix(
                text,
                diagnostic,
            )

            if fix is not None:
                return fix

        return None

    def apply_quick_fix(
        self,
        fix: QuickFix,
    ) -> None:
        """Apply a quick fix's single text insertion."""

        block = self.document().findBlockByNumber(
            fix.line - 1,
        )
        cursor = QTextCursor(
            block,
        )
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            fix.column - 1,
        )
        cursor.insertText(
            fix.insert_text,
        )

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

    def toggle_breakpoint_at_cursor(
        self,
    ) -> None:
        """Toggle a breakpoint on the cursor's current line.

        Purely local, visual state -- syncing it to a real GDB
        breakpoint when a debug session is active is the caller's job
        (see `opencobol2.gui.debug_session.DebugSessionController`).
        Stored as `QTextBlock` handles for the same reason bookmarks
        are: keeping a breakpoint tracking its physical line of text
        across edits elsewhere, not whatever line now has the same
        number.
        """

        self._prune_invalid_breakpoints()
        cursor_block = self.textCursor().block()
        cursor_line = cursor_block.blockNumber()

        for index, block in enumerate(
            self._breakpointed_blocks,
        ):
            if block.blockNumber() == cursor_line:
                del self._breakpointed_blocks[
                    index
                ]
                break
        else:
            self._breakpointed_blocks.append(
                cursor_block,
            )

        self._line_number_area.update()
        self.breakpoints_changed.emit()

    @property
    def breakpoint_lines(
        self,
    ) -> tuple[int, ...]:
        """Return every breakpointed 1-based line number, sorted."""

        self._prune_invalid_breakpoints()

        return tuple(
            sorted(
                block.blockNumber() + 1
                for block in self._breakpointed_blocks
            )
        )

    def _prune_invalid_breakpoints(
        self,
    ) -> None:
        self._breakpointed_blocks = [
            block
            for block in self._breakpointed_blocks
            if block.isValid()
        ]

    @property
    def diagnostics(
        self,
    ) -> tuple[LexDiagnostic | ParseDiagnostic, ...]:
        """Return this tab's live lex/parse/semantic diagnostics, if any."""

        if self._highlighter is None:
            return ()

        return self._highlighter.diagnostics()

    def go_to_definition(
        self,
    ) -> bool:
        """Jump the cursor to the definition of whatever it's on.

        Single-file only, same scope as `find_definition` itself. Returns
        whether a definition was found and navigated to.
        """

        cursor = self.textCursor()
        location = find_definition(
            self.toPlainText(),
            line=cursor.blockNumber() + 1,
            column=cursor.columnNumber() + 1,
        )

        if location is None:
            return False

        self.go_to_line(
            location.line,
            location.column,
        )

        return True

    def references_at_cursor(
        self,
    ) -> tuple[SourceLocation, ...]:
        """Return every reference to (and definition of) whatever the cursor is on."""

        cursor = self.textCursor()

        return find_references(
            self.toPlainText(),
            line=cursor.blockNumber() + 1,
            column=cursor.columnNumber() + 1,
        )

    def rename_symbol_at_cursor(
        self,
        new_name: str,
    ) -> int:
        """Replace every reference to whatever the cursor is on with a new name.

        Single-file only, same scope as `references_at_cursor` itself.

        Deliberately does NOT trust `SourceLocation.column` as the exact
        start of the name text: two documented AST precision limits --
        a data item's own definition location points at its level
        number, not its name, and a MOVE target's reference location
        points at the MOVE statement's own start, not the target name --
        make that unsafe for an editing operation (unlike navigation,
        where landing a few characters off is a minor UX issue, not
        overwritten source code). Instead, each affected LINE is
        rewritten by matching the old name as a whole COBOL word --
        bounded by anything other than a letter, digit, or hyphen, since
        hyphens are legal name characters -- so every real occurrence on
        that line is renamed regardless of exactly where the AST says it
        starts, and a same-named-but-longer identifier sharing a prefix
        (`WS-COUNT-TOTAL`) is never partially matched.
        """

        locations = self.references_at_cursor()

        if not locations:
            return 0

        old_name = locations[0].name
        pattern = re.compile(
            r"(?<![A-Za-z0-9-])"
            + re.escape(
                old_name,
            )
            + r"(?![A-Za-z0-9-])",
            re.IGNORECASE,
        )

        edit_cursor = self.textCursor()
        edit_cursor.beginEditBlock()
        total_replacements = 0

        for line in sorted(
            {
                location.line
                for location in locations
            },
            reverse=True,
        ):
            block = self.document().findBlockByNumber(
                line - 1,
            )
            original_text = block.text()
            new_text, count = pattern.subn(
                new_name,
                original_text,
            )

            if not count:
                continue

            total_replacements += count
            line_cursor = QTextCursor(
                block,
            )
            line_cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            line_cursor.insertText(
                new_text,
            )

        edit_cursor.endEditBlock()
        return total_replacements

    def format_document(
        self,
    ) -> bool:
        """Trim trailing whitespace on every line; expand tabs if configured.

        Deliberately conservative: fixed-format COBOL source is
        column-sensitive, so this never attempts COBOL-aware
        re-indentation. Converting literal tab characters to spaces only
        happens when `EditorSettings.insert_spaces` is enabled -- the
        reverse direction (spaces to tabs) is a lossy, ambiguous guess
        about which runs of spaces "should" become a tab, so it's never
        done. Returns whether anything actually changed, and applies
        every change inside one undo step.
        """

        document = self.document()
        changed = False
        edit_cursor = self.textCursor()
        edit_cursor.beginEditBlock()

        for line_index in range(
            document.blockCount(),
        ):
            block = document.findBlockByNumber(
                line_index,
            )
            original_text = block.text()
            formatted_text = original_text.rstrip()

            if self._editor_settings.insert_spaces:
                formatted_text = formatted_text.expandtabs(
                    self._editor_settings.tab_width,
                )

            if formatted_text == original_text:
                continue

            changed = True
            line_cursor = QTextCursor(
                block,
            )
            line_cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            line_cursor.insertText(
                formatted_text,
            )

        edit_cursor.endEditBlock()
        return changed

    def hover_info_at(
        self,
        pos: QPoint,
    ) -> HoverInfo | None:
        """Describe the data item, paragraph, section, or call under a position.

        Signature help takes priority over ordinary hover: being inside
        the parentheses of a `FUNCTION name(...)` call is a narrower,
        more specific condition than "hovering over some token", so it
        wins when both could apply. Reuses the exact same `QToolTip`
        wiring as symbol/keyword hover -- no separate popup mechanism.
        """

        if not self.is_cobol_source:
            return None

        cursor = self.cursorForPosition(
            pos,
        )
        text = self.toPlainText()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1

        signature_help = compute_signature_help(
            text,
            line=line,
            column=column,
        )

        if signature_help is not None:
            return HoverInfo(
                name=signature_help.name,
                kind="function-signature",
                detail=signature_help.signature,
            )

        return compute_hover(
            text,
            line=line,
            column=column,
        )

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

    def trigger_suggest(
        self,
    ) -> None:
        """Show completion candidates for the cursor's position now.

        Bypasses the debounce timer that otherwise paces candidate
        refreshes while typing -- an explicit request (Ctrl+Space, or
        the Edit > Trigger Suggest command) should respond immediately.
        """

        self._completion_debounce_timer.stop()
        self._refresh_completions()

    def accept_selected_completion(
        self,
    ) -> None:
        """Insert the highlighted completion candidate at the cursor.

        Replaces the prefix that was typed to trigger the popup, then
        either inserts the candidate's text directly or, for a
        snippet, starts a tab-stop session via `insert_snippet`.
        """

        item = self._completion_popup.selected_item()
        prefix_start = self._completion_prefix_start
        self._close_completion_popup()

        if item is None or prefix_start is None:
            return

        cursor = self.textCursor()
        cursor.setPosition(
            prefix_start,
        )
        cursor.setPosition(
            self.textCursor().position(),
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.beginEditBlock()
        cursor.removeSelectedText()

        if (
            item.kind is CompletionItemKind.SNIPPET
            and item.snippet_body is not None
        ):
            cursor.endEditBlock()
            self.setTextCursor(
                cursor,
            )
            self.insert_snippet(
                item.snippet_body,
            )
        else:
            cursor.insertText(
                item.insert_text,
            )
            cursor.endEditBlock()
            self.setTextCursor(
                cursor,
            )

    def insert_snippet(
        self,
        body: str,
    ) -> None:
        """Insert a snippet's expansion at the cursor, selecting its
        first tab stop.

        Tab (while the session is active) advances to the next stop;
        Escape cancels it. Typing while a stop is selected replaces
        its default text via Qt's own selection-replace semantics --
        no special-casing needed.

        Each stop's start/end is tracked as plain integer offsets
        while inserting, not as a live `QTextCursor` created mid-loop:
        Qt auto-adjusts every live cursor on a document when text is
        inserted elsewhere, including growing a cursor's selection
        forward when a later segment happens to be inserted exactly at
        its current end -- which every later segment in this same
        snippet always is, since they're all inserted back-to-back
        through one advancing cursor. Building each stop's real
        `QTextCursor` only after every segment has already been
        inserted sidesteps that entirely: there's nothing left to
        insert, and therefore nothing left to shift it.
        """

        segments = parse_snippet_body(
            body,
        )
        cursor = self.textCursor()
        base_position = cursor.position()
        cursor.beginEditBlock()
        offset = 0
        indexed_ranges: list[
            tuple[int, int, int]
        ] = []

        try:
            for segment in segments:
                cursor.insertText(
                    segment.text,
                )
                start = base_position + offset
                offset += len(
                    segment.text,
                )
                end = base_position + offset

                if segment.is_placeholder:
                    indexed_ranges.append(
                        (segment.stop_index, start, end),
                    )
        finally:
            cursor.endEditBlock()

        if not indexed_ranges:
            self.setTextCursor(
                cursor,
            )
            return

        indexed_ranges.sort(
            key=lambda triple: triple[0],
        )
        stops: list[QTextCursor] = []

        for _, start, end in indexed_ranges:
            stop_cursor = QTextCursor(
                self.document(),
            )
            stop_cursor.setPosition(
                start,
            )
            stop_cursor.setPosition(
                end,
                QTextCursor.MoveMode.KeepAnchor,
            )
            stops.append(
                stop_cursor,
            )

        self._active_snippet_stops = stops
        self._active_snippet_index = 0
        self.setTextCursor(
            self._active_snippet_stops[0],
        )

    def _advance_snippet_stop(
        self,
    ) -> None:
        stops = self._active_snippet_stops

        if stops is None:
            return

        self._active_snippet_index += 1

        if self._active_snippet_index >= len(
            stops,
        ):
            self._end_snippet_session()
            return

        self.setTextCursor(
            stops[self._active_snippet_index],
        )

    def _end_snippet_session(
        self,
    ) -> None:
        self._active_snippet_stops = None
        self._active_snippet_index = 0

    def _refresh_completions(
        self,
    ) -> None:
        if not self.is_cobol_source:
            return

        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1

        items = compute_completions(
            self.toPlainText(),
            line=line,
            column=column,
        )

        if not items:
            self._close_completion_popup()
            return

        self._completion_prefix_start = (
            self._prefix_start_position(
                cursor,
            )
        )
        self._completion_popup.set_items(
            items,
        )
        self._position_completion_popup()
        self._completion_popup.show()
        self._completion_popup.raise_()

    def _close_completion_popup(
        self,
    ) -> None:
        self._completion_debounce_timer.stop()
        self._completion_prefix_start = None
        self._completion_popup.hide()

    def _prefix_start_position(
        self,
        cursor: QTextCursor,
    ) -> int:
        """Return the document position where the word ending at a
        cursor's position starts, scanning left over identifier
        characters within the same block."""

        block_text = cursor.block().text()
        start = cursor.positionInBlock()

        while (
            start > 0
            and block_text[start - 1] in _IDENTIFIER_CHARACTERS
        ):
            start -= 1

        return cursor.block().position() + start

    def _position_completion_popup(
        self,
    ) -> None:
        cursor_rect = self.cursorRect()
        self._completion_popup.setFixedSize(
            _COMPLETION_POPUP_WIDTH,
            _COMPLETION_POPUP_HEIGHT,
        )
        x = max(
            0,
            min(
                cursor_rect.left(),
                self.viewport().width()
                - _COMPLETION_POPUP_WIDTH,
            ),
        )
        y = max(
            0,
            min(
                cursor_rect.bottom() + 2,
                self.viewport().height()
                - _COMPLETION_POPUP_HEIGHT,
            ),
        )
        self._completion_popup.move(
            x,
            y,
        )

    def _update_line_number_area_width(
        self,
        _new_block_count: int = 0,
    ) -> None:
        self.setViewportMargins(
            self.line_number_area_width(),
            0,
            self.minimap_area_width(),
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

    def minimap_area_width(
        self,
    ) -> int:
        """Return the minimap strip's width, or 0 when it's turned off."""

        return (
            _MINIMAP_WIDTH
            if self._minimap_enabled
            else 0
        )

    def paint_minimap(
        self,
        event: QPaintEvent,
    ) -> None:
        """Paint a density map of every line, plus the visible-viewport indicator."""

        painter = QPainter(
            self._minimap_area,
        )
        painter.fillRect(
            event.rect(),
            self.palette().color(
                self.backgroundRole(),
            ),
        )

        document = self.document()
        total_lines = max(
            document.blockCount(),
            1,
        )
        area_width = self._minimap_area.width()
        line_height = (
            self._minimap_area.height()
            / total_lines
        )

        painter.setPen(
            self._minimap_foreground_color,
        )
        block = document.begin()
        line_index = 0

        while block.isValid():
            text_length = len(
                block.text().strip(),
            )

            if text_length:
                y = line_index * line_height
                tick_width = (
                    min(
                        text_length,
                        _MINIMAP_MAX_LINE_CHARS,
                    )
                    / _MINIMAP_MAX_LINE_CHARS
                    * (area_width - 4)
                )
                painter.drawLine(
                    QPointF(
                        2,
                        y,
                    ),
                    QPointF(
                        2 + tick_width,
                        y,
                    ),
                )

            block = block.next()
            line_index += 1

        first_visible_line = (
            self.firstVisibleBlock().blockNumber()
        )
        last_visible_line = (
            self._last_visible_block_number()
        )
        indicator_top = (
            first_visible_line * line_height
        )
        indicator_height = max(
            (
                last_visible_line
                - first_visible_line
                + 1
            )
            * line_height,
            2,
        )
        painter.fillRect(
            QRectF(
                0,
                indicator_top,
                area_width,
                indicator_height,
            ),
            self._minimap_viewport_color,
        )

    def handle_minimap_click(
        self,
        position: QPoint,
    ) -> None:
        """Move the cursor to the line the minimap was clicked/dragged over."""

        self.go_to_line(
            self.minimap_line_for_position(
                position.y(),
            )
            + 1,
        )

    def minimap_line_for_position(
        self,
        y: float,
    ) -> int:
        """Return the 0-based document line a minimap y-coordinate points at."""

        total_lines = max(
            self.document().blockCount(),
            1,
        )
        line_height = (
            self._minimap_area.height()
            / total_lines
        )

        if line_height <= 0:
            return 0

        return max(
            0,
            min(
                int(
                    y / line_height,
                ),
                total_lines - 1,
            ),
        )

    def _visible_line_count(
        self,
    ) -> int:
        """Return how many lines currently fit in the viewport."""

        line_height = self.fontMetrics().height()

        if line_height <= 0:
            return 1

        return max(
            1,
            round(
                self.viewport().height()
                / line_height,
            ),
        )

    def _last_visible_block_number(
        self,
    ) -> int:
        """Return the highest document block index shown in the viewport.

        Folding can make a small number of on-screen rows span a much
        wider range of block indices -- hidden blocks in between
        consume no screen space but still occupy minimap-scale index
        range. This walks forward from the first visible block,
        consuming one row of the viewport's row budget per *visible*
        block (line-wrap is forced off, so one visible block is always
        exactly one rendered row) to find the actual last block index
        the viewport currently covers, rather than assuming the
        visible row count and the block-index span are the same thing.
        """

        block = self.firstVisibleBlock()

        if not block.isValid():
            return 0

        remaining_rows = self._visible_line_count()
        last_block_number = block.blockNumber()

        while (
            block.isValid()
            and remaining_rows > 0
        ):
            last_block_number = block.blockNumber()

            if block.isVisible():
                remaining_rows -= 1

            block = block.next()

        return last_block_number

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

    breakpoints_changed = Signal()
    """Emitted whenever any open tab's breakpoints change."""

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

        self._autosave_timer = QTimer(
            self,
        )
        self._autosave_timer.timeout.connect(
            self._handle_autosave_timeout,
        )
        self._configure_autosave_timer()

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

        self._configure_autosave_timer()

    def _configure_autosave_timer(
        self,
    ) -> None:
        if self._editor_settings.autosave_enabled:
            self._autosave_timer.setInterval(
                self._editor_settings.autosave_interval_seconds
                * 1000,
            )
            self._autosave_timer.start()
        else:
            self._autosave_timer.stop()

    def _handle_autosave_timeout(
        self,
    ) -> None:
        """Silently save every modified, already-named open document.

        Runs on a background timer, so it must never interrupt the user:
        untitled documents (no path yet) are skipped rather than prompted
        for Save As, and a save failure is swallowed rather than shown in
        a blocking dialog.
        """

        for index in range(self.count()):
            editor = self._editor_at(
                index,
            )
            workspace_document = (
                self._document_service.workspace.get_document(
                    editor.document_id,
                )
            )

            if not (
                workspace_document.document.is_modified
                and workspace_document.document.path
                is not None
            ):
                continue

            try:
                self._document_service.save_document(
                    editor.document_id,
                )
            except OSError:
                continue

            self._refresh_tab_chrome(
                editor.document_id,
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

        try:
            workspace_document = (
                self._document_service.open_document(
                    path,
                )
            )
        except (
            OSError,
            DocumentDecodeError,
        ) as error:
            QMessageBox.critical(
                self,
                "Open File",
                f"Unable to open file: {error}",
            )
            return

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
        editor.breakpoints_changed.connect(
            self.breakpoints_changed.emit,
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

    def current_diagnostics(
        self,
    ) -> tuple[CompilerDiagnostic, ...]:
        """Return the active tab's live diagnostics, converted for display.

        Scoped to the active tab only, same as `current_outline()` --
        background tabs' diagnostics aren't tracked.
        """

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return ()

        workspace_document = (
            self._document_service.workspace.get_document(
                editor.document_id,
            )
        )
        source_path = workspace_document.document.path

        return tuple(
            CompilerDiagnostic(
                severity=diagnostic.severity,
                message=diagnostic.message,
                source_path=source_path,
                line=diagnostic.position.line,
                column=diagnostic.position.column,
            )
            for diagnostic in editor.diagnostics
        )

    def go_to_definition_on_active_tab(
        self,
    ) -> bool:
        """Jump the active tab's cursor to whatever definition it's on."""

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return False

        return editor.go_to_definition()

    def rename_symbol_on_active_tab(
        self,
        new_name: str,
    ) -> int:
        """Rename every reference to whatever the active tab's cursor is on."""

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return 0

        return editor.rename_symbol_at_cursor(
            new_name,
        )

    def print_active_tab(
        self,
        printer: QPrinter,
    ) -> bool:
        """Print the active tab's document contents, if one is open.

        `QPlainTextEdit.print_()` uses the document's standard
        print/layout path, which doesn't consult per-block visibility
        -- folded-away content is included in full regardless, with
        nothing on the printed page to show it was ever collapsed on
        screen. Rather than reimplement printing to filter out folded
        content (losing formatting/line-numbering fidelity for a
        printout that would then be silently *missing* source lines,
        arguably a worse surprise than the current one), this warns
        and lets the user cancel instead.
        """

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return False

        if editor._collapsed_start_lines:
            choice = QMessageBox.question(
                self,
                "Print File",
                "This document has folded (collapsed) sections. "
                "Printing always includes their full content, "
                "regardless of what's currently visible on screen. "
                "Continue?",
                (
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                ),
                QMessageBox.StandardButton.Yes,
            )

            if choice != QMessageBox.StandardButton.Yes:
                return False

        editor.print_(
            printer,
        )
        return True

    def format_active_tab(
        self,
    ) -> bool:
        """Format the active tab's document contents, if one is open."""

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return False

        return editor.format_document()

    def trigger_suggest_on_active_tab(
        self,
    ) -> bool:
        """Show completion candidates for the active tab, if one is open."""

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return False

        editor.trigger_suggest()
        return True

    def undo_active_tab(
        self,
    ) -> None:
        """Undo the active tab's last edit, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.undo()

    def redo_active_tab(
        self,
    ) -> None:
        """Redo the active tab's last undone edit, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.redo()

    def cut_active_tab(
        self,
    ) -> None:
        """Cut the active tab's selection to the clipboard, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.cut()

    def copy_active_tab(
        self,
    ) -> None:
        """Copy the active tab's selection to the clipboard, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.copy()

    def paste_active_tab(
        self,
    ) -> None:
        """Paste the clipboard into the active tab, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.paste()

    def delete_selection_on_active_tab(
        self,
    ) -> None:
        """Delete the active tab's selection (or the next character), if open."""

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return

        cursor = editor.textCursor()

        if not cursor.hasSelection():
            cursor.deleteChar()
        else:
            cursor.removeSelectedText()

        editor.setTextCursor(
            cursor,
        )

    def select_all_on_active_tab(
        self,
    ) -> None:
        """Select the active tab's entire contents, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.selectAll()

    def go_to_line_on_active_tab(
        self,
        line_number: int,
    ) -> None:
        """Move the active tab's cursor to a 1-based line, if one is open."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.go_to_line(
                line_number,
            )

    def find_references_for_active_tab(
        self,
    ) -> tuple[FindResult, ...]:
        """Find every reference to whatever the active tab's cursor is on.

        Only works for a document that's already been saved -- a
        `FindResult` needs a real path to display and later navigate
        back to, which an untitled document doesn't have.
        """

        editor = self.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return ()

        workspace_document = (
            self._document_service.workspace.get_document(
                editor.document_id,
            )
        )
        source_path = workspace_document.document.path

        if source_path is None:
            return ()

        document = editor.document()

        return tuple(
            FindResult(
                path=source_path,
                line=location.line,
                column=location.column,
                line_text=document.findBlockByNumber(
                    location.line - 1,
                ).text().strip(),
            )
            for location in editor.references_at_cursor()
        )

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

        self._reveal_document_location(
            document_id,
            line_number,
            column,
        )

    def toggle_breakpoint_on_active_tab(
        self,
    ) -> None:
        """Toggle a breakpoint on the active tab's cursor line, if any."""

        editor = self.currentWidget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.toggle_breakpoint_at_cursor()

    def all_breakpoints(
        self,
    ) -> tuple[BreakpointEntry, ...]:
        """Return every breakpoint across every open tab."""

        entries: list[BreakpointEntry] = []

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

            for line in editor.breakpoint_lines:
                block = editor.document().findBlockByNumber(
                    line - 1,
                )
                entries.append(
                    BreakpointEntry(
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

    def reveal_breakpoint(
        self,
        document_id: UUID,
        line_number: int,
        column: int = 1,
    ) -> None:
        """Activate the tab for a document and move its cursor to a line."""

        self._reveal_document_location(
            document_id,
            line_number,
            column,
        )

    def editor_for_document(
        self,
        document_id: UUID,
    ) -> SourceEditorWidget | None:
        """Return the open editor for a document, if its tab is still open."""

        return self._editor_for(document_id)

    def _reveal_document_location(
        self,
        document_id: UUID,
        line_number: int,
        column: int,
    ) -> None:
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

        editor.refresh_cobol_support(
            Path(
                path_str,
            ),
            self._theme,
        )
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

        # The Bookmarks/Breakpoints panels only refresh on these two
        # signals, which otherwise only fire on an explicit toggle --
        # without this, a closed tab's markers keep showing in those
        # panels (with a now-meaningless file name) until some
        # unrelated toggle elsewhere happens to trigger a refresh.
        self.bookmarks_changed.emit()
        self.breakpoints_changed.emit()

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
