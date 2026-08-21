"""A tabbed source-code editor backed by the Qt-independent document model.

Several module-level constants encode non-obvious behavioral decisions
that are worth recording here since there is nowhere else to attach a
docstring to a plain constant.

Fold ranges come from a full lex+parse of the whole document (see
:func:`opencobol2.language.compute_fold_ranges`) -- on a large file
that is real, measured work (roughly a second on a ~10,000-line file).
It was previously re-run synchronously on every single keystroke via
`textChanged`, on top of the highlighter's own equally-expensive
lex+parse+semantic pass for diagnostics. Held-key auto-repeat (e.g.
backspacing quickly) queues keystrokes faster than that can keep up,
which is exactly what reads as "the editor stopped responding" -- it
is real, growing, unbounded work piling up on the GUI thread, not a
hang or a bug in any one keystroke. `_FOLD_RANGE_DEBOUNCE_MILLISECONDS`
debounces the recompute the same way completion already is, so a burst
of edits collapses into one recompute after they settle, rather than
one full recompute per keystroke.

`_IDENTIFIER_CHARACTERS` is hyphen-inclusive, the same word-boundary
convention `SourceEditorWidget.rename_symbol_at_cursor` and
`opencobol2.language.completion` both already use, since COBOL names
legally contain hyphens.

`_COLUMN_SELECTION_ARROW_KEYS` lists the arrow keys that, combined
with Alt+Shift, extend a column (box) selection -- the same keybinding
Visual Studio and Notepad++ both already use for it. This is
deliberately not a separate "mode toggle" command, since the modifier
combination itself is the trigger.

`_MULTI_CURSOR_MOVEMENTS` replicates the primary cursor's own movement
at every secondary cursor so their relative positions stay aligned --
Home/End are deliberately excluded here since `QTextCursor`'s
StartOfLine/EndOfLine operations already work identically regardless
of which cursor calls them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
    QPalette,
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
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from opencobol2.compiler import CobolSourceFormat, CompilerDiagnostic
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

_FOLD_RANGE_DEBOUNCE_MILLISECONDS = 150

_IDENTIFIER_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "abcdefghijklmnopqrstuvwxyz" "0123456789-"
)


def _is_identifier_character(
    text: str,
) -> bool:
    """Return whether a `QKeyEvent.text()` value is one COBOL identifier character.

    :param text: The single-character text value from a `QKeyEvent`,
        as returned by `QKeyEvent.text()`.
    :returns: True if `text` is exactly one character and that
        character is a legal COBOL identifier character (letters,
        digits, or hyphen); False otherwise.
    """

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

    :param path: The document's on-disk path, or None for an untitled
        (unsaved) document.
    :returns: True if `path` is None or has a `.cbl`/`.cob` suffix
        (case-insensitively); False otherwise.
    """

    return (
        path is None
        or path.suffix.lower() in _COBOL_SOURCE_EXTENSIONS
    )


_COLUMN_SELECTION_ARROW_KEYS = frozenset(
    (
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
    )
)


@dataclass
class _ColumnSelectionState:
    """A rectangular (box) selection spanning one or more lines.

    Columns are plain character offsets within each line's text, not
    display/tab-expanded columns -- the same simplification the rest
    of this module already makes rather than reconciling literal-tab
    columns against the lexer's own tab-expanded ones (see
    `keyPressEvent`'s docstring).

    :ivar anchor_line: The 0-based line where the box selection
        started.
    :ivar anchor_column: The 0-based character column where the box
        selection started.
    :ivar active_line: The 0-based line of the corner last moved by
        keyboard or mouse.
    :ivar active_column: The 0-based character column of the corner
        last moved by keyboard or mouse.
    """

    anchor_line: int
    anchor_column: int
    active_line: int
    active_column: int


_MULTI_CURSOR_MOVEMENTS: dict[
    Qt.Key,
    QTextCursor.MoveOperation,
] = {
    Qt.Key.Key_Left: QTextCursor.MoveOperation.Left,
    Qt.Key.Key_Right: QTextCursor.MoveOperation.Right,
    Qt.Key.Key_Up: QTextCursor.MoveOperation.Up,
    Qt.Key.Key_Down: QTextCursor.MoveOperation.Down,
    Qt.Key.Key_Home: QTextCursor.MoveOperation.StartOfLine,
    Qt.Key.Key_End: QTextCursor.MoveOperation.EndOfLine,
}


class _LineNumberArea(QWidget):
    """The gutter widget that paints one editor's line numbers."""

    def __init__(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        """Attach this gutter to the editor it belongs to.

        :param editor: The editor whose line numbers this gutter paints.
        :returns: None.
        """

        super().__init__(
            editor,
        )

        self._editor = editor

    def sizeHint(
        self,
    ) -> QSize:
        """Return the preferred size, using the editor's own gutter width.

        :returns: A :class:`QSize` with the editor's computed line-number
            area width and a height of 0 (Qt stretches height to fit the
            layout).
        """

        return QSize(
            self._editor.line_number_area_width(),
            0,
        )

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        """Delegate painting to the owning editor.

        :param event: The Qt paint event describing the region to redraw.
        :returns: None. The gutter is repainted as a side effect.
        """

        self._editor.paint_line_number_area(
            event,
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """Delegate a click to the owning editor's fold-toggle handler.

        :param event: The Qt mouse event describing the click.
        :returns: None. May toggle a fold in the owning editor as a side
            effect.
        """

        self._editor.handle_line_number_area_click(
            event.position().toPoint(),
        )


class _MinimapArea(QWidget):
    """The scaled-down document-overview strip alongside one editor."""

    def __init__(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        """Attach this minimap strip to the editor it belongs to.

        :param editor: The editor whose overview this strip paints.
        :returns: None.
        """

        super().__init__(
            editor,
        )

        self._editor = editor

    def sizeHint(
        self,
    ) -> QSize:
        """Return the preferred size, using the editor's own minimap width.

        :returns: A :class:`QSize` with the editor's computed minimap
            area width and a height of 0 (Qt stretches height to fit the
            layout).
        """

        return QSize(
            self._editor.minimap_area_width(),
            0,
        )

    def paintEvent(
        self,
        event: QPaintEvent,
    ) -> None:
        """Delegate painting to the owning editor.

        :param event: The Qt paint event describing the region to redraw.
        :returns: None. The minimap is repainted as a side effect.
        """

        self._editor.paint_minimap(
            event,
        )

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """Delegate a click to the owning editor's minimap navigation.

        :param event: The Qt mouse event describing the click.
        :returns: None. Moves the owning editor's cursor as a side effect.
        """

        self._editor.handle_minimap_click(
            event.position().toPoint(),
        )

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """Continue minimap navigation while the left button is held and dragged.

        :param event: The Qt mouse event describing the drag.
        :returns: None. Moves the owning editor's cursor as a side effect
            when the left button is held.
        """

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
        """Build the find/replace row widgets, hidden by default.

        :param editor: The editor this bar searches and edits.
        :returns: None.
        """

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
        """Show or hide the replace row for find-only vs. find-and-replace.

        :param visible: Whether the replace row should be shown.
        :returns: None. The replace row's visibility is toggled in place.
        """

        self._replace_row_widget.setVisible(
            visible,
        )

    def _flags(
        self,
    ) -> QTextDocument.FindFlag:
        """Return the current search flags reflecting the case-sensitivity checkbox.

        :returns: `QTextDocument.FindFlag.FindCaseSensitively` if the
            "Match case" checkbox is checked, otherwise no flags.
        """

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
        """Find the next occurrence of the search text and report the result.

        :returns: None. Moves the editor's selection and updates the
            status label as side effects.
        """

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
        """Find the previous occurrence of the search text and report the result.

        :returns: None. Moves the editor's selection and updates the
            status label as side effects.
        """

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
        """Replace the current match, then find the next one.

        :returns: None. Edits the editor's text and updates the status
            label as side effects.
        """

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
        """Replace every occurrence and report how many were replaced.

        :returns: None. Edits the editor's text and updates the status
            label as side effects.
        """

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
        """Clear or set the status label based on whether a match was found.

        :param found: Whether the preceding find/replace operation
            located a match.
        :returns: None. Updates the status label in place.
        """

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
        """Build the candidate list widget, hidden by default.

        :param editor: The editor this popup offers completions for.
        :returns: None.
        """

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
        """Replace the candidate list and select the first entry.

        :param items: The new completion candidates to display, in
            display order.
        :returns: None. The list widget's contents are replaced in place.
        """

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
        """Return the currently highlighted candidate, if any.

        :returns: The highlighted :class:`CompletionItem`, or None if
            the list is empty or nothing is highlighted.
        """

        row = self.list_widget.currentRow()

        if 0 <= row < len(self._items):
            return self._items[row]

        return None

    def select_next(
        self,
    ) -> None:
        """Move the highlight to the next candidate, wrapping around.

        :returns: None. The list widget's current row is updated in place.
        """

        if not self._items:
            return

        row = self.list_widget.currentRow()
        self.list_widget.setCurrentRow(
            (row + 1) % len(self._items),
        )

    def select_previous(
        self,
    ) -> None:
        """Move the highlight to the previous candidate, wrapping around.

        :returns: None. The list widget's current row is updated in place.
        """

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
        """Accept the double-clicked candidate as if it had been selected.

        :param _list_item: The `QListWidgetItem` that was double-clicked;
            unused since the popup tracks the selection by row.
        :returns: None. Inserts the accepted completion into the editor
            as a side effect.
        """

        self._editor.accept_selected_completion()


class SourceEditorWidget(QPlainTextEdit):
    """A plain-text editor for exactly one open document."""

    bookmarks_changed = Signal()
    """Emitted whenever a bookmark is toggled on or off."""

    breakpoints_changed = Signal()
    """Emitted whenever a breakpoint is toggled on or off."""

    focused = Signal()
    """Emitted when this editor gains keyboard focus.

    A split tab's `_SplitEditorPane` listens for this on each of its
    views to track which one is "active" -- the one every
    active-tab-scoped operation (go to definition, format document, and
    so on) should act on -- since a plain-QSplitter tab has no other
    signal for "which of my two children does the user mean right now."
    """

    def __init__(
        self,
        *,
        document_id: UUID,
        initial_text: str,
        theme: Theme,
        editor_settings: EditorSettings | None = None,
        guide_settings: CobolGuideSettings | None = None,
        source_format: CobolSourceFormat = (
            CobolSourceFormat.FIXED
        ),
        path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build an editor preloaded with one document's text.

        Word-wrap is always disabled: coding-area column guides (and
        printing) are painted from "one visual row == one logical line
        starting at column 1", which is only true without word-wrap.
        Fixed-format COBOL is column-sensitive by convention anyway, so
        a horizontal scrollbar on an overly-long line is the right
        trade-off here, rather than silently wrapping it and desyncing
        every guide line past the first visual row.

        :param document_id: The identity of the document this editor
            displays, used to look it up again in a `DocumentService`.
        :param initial_text: The document's starting text content.
        :param theme: The color theme to render with.
        :param editor_settings: Font, tab width, and other editing
            preferences to apply; defaults to :class:`EditorSettings`'
            defaults when None.
        :param guide_settings: Which fixed-format coding-area guides to
            show; defaults to :class:`CobolGuideSettings`' defaults when
            None.
        :param source_format: Whether to assume fixed-format or
            free-format COBOL column conventions.
        :param path: The document's on-disk path, or None if it is
            untitled; used only to decide whether COBOL support
            (highlighting, folding, language services) applies.
        :param parent: The optional parent widget.
        :returns: None.
        """

        super().__init__(
            parent,
        )

        self._source_format = source_format

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
        self._secondary_cursor_color = QColor(
            theme.colors.editor_foreground,
        )
        self._secondary_cursors: list[
            QTextCursor,
        ] = []
        self._column_selection: (
            _ColumnSelectionState | None
        ) = None
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
                source_format=self._source_format,
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

        self._fold_range_debounce_timer = QTimer(
            self,
        )
        self._fold_range_debounce_timer.setSingleShot(
            True,
        )
        self._fold_range_debounce_timer.setInterval(
            _FOLD_RANGE_DEBOUNCE_MILLISECONDS,
        )
        self._fold_range_debounce_timer.timeout.connect(
            self._update_fold_ranges,
        )

        self.blockCountChanged.connect(
            self._update_line_number_area_width,
        )
        self.textChanged.connect(
            self._schedule_fold_range_update,
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
            self._refresh_extra_selections,
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
        self._refresh_extra_selections()
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
        self._secondary_cursor_color = QColor(
            theme.colors.editor_foreground,
        )
        self._refresh_extra_selections()
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
                source_format=self._source_format,
            )

        # Folding is gated on `self._highlighter is not None`;
        # re-running this recomputes _folding_enabled and expands any
        # folds if support was just lost.
        self.apply_editor_settings(
            self._editor_settings,
        )

    def become_split_view_of(
        self,
        primary: "SourceEditorWidget",
    ) -> None:
        """Turn this editor into a second view of another editor's document.

        Used only when splitting a tab. This editor was constructed
        normally against its own throwaway document (built its own
        highlighter if COBOL-recognized, computed fold ranges for its
        starting text, and so on) -- all of that is discarded here in
        favor of sharing `primary`'s real `QTextDocument`, so highlighting
        for this view comes from `primary`'s own highlighter running
        against the document they now both point at, not a second one of
        this editor's own. Fold ranges, bookmarks, and breakpoints are
        NOT shared -- they're per-view state, so this view starts with
        none regardless of what `primary` already has, and the two can
        diverge from here as each is worked in independently.
        """

        if self._highlighter is not None:
            self._highlighter.setDocument(
                None,
            )
            self._highlighter = None

        self.setDocument(
            primary.document(),
        )
        self.is_cobol_source = primary.is_cobol_source
        self._source_format = primary._source_format

        # Folding is gated on `self._highlighter is not None`, which
        # `is_cobol_source` alone doesn't update.
        self.apply_editor_settings(
            self._editor_settings,
        )

    def apply_source_format(
        self,
        source_format: CobolSourceFormat,
    ) -> None:
        """Change which COBOL column convention this editor assumes.

        Fixed enforces the traditional sequence-area (columns 1-6),
        indicator column (7), and Area A (8-11) positions; Free treats
        every column as ordinary code. Affects highlighting, folding,
        and every on-demand language service this editor calls
        (completion, hover, signature help, go to definition, find
        references, quick fixes) -- all of them default to Fixed
        unless told otherwise, so this is the one place that has to
        keep them all in sync with each other.
        """

        self._source_format = source_format

        if self._highlighter is not None:
            self._highlighter.apply_source_format(
                source_format,
            )

        self._update_fold_ranges()

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

        if self._handle_column_selection_key(
            event,
        ):
            return

        if (
            self._secondary_cursors
            and self._handle_multi_cursor_key(
                event,
            )
        ):
            self._maybe_trigger_completion_after_key(
                event,
            )
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

        self._maybe_trigger_completion_after_key(
            event,
        )

    def _maybe_trigger_completion_after_key(
        self,
        event: QKeyEvent,
    ) -> None:
        """Debounce-trigger or dismiss completion after a handled keypress.

        Shared between ordinary single-cursor typing and multi-cursor
        typing (`_handle_multi_cursor_key`), which bypasses
        `super().keyPressEvent()` entirely and so needs this called
        explicitly instead.
        """

        if not self.is_cobol_source:
            return

        if _is_identifier_character(
            event.text(),
        ) or event.key() == Qt.Key.Key_Backspace:
            self._completion_debounce_timer.start()
        else:
            self._close_completion_popup()

    def _handle_multi_cursor_key(
        self,
        event: QKeyEvent,
    ) -> bool:
        """Replicate an editing/navigation key across every secondary cursor.

        Only reached when at least one secondary cursor exists (see
        `add_cursor_above`/`add_cursor_below`/`mousePressEvent`).
        Navigation keys move every cursor by the same operation so their
        relative positions stay aligned; typing, Backspace, Delete,
        Enter, and Tab (when `insert_spaces` is on) are replicated at
        every cursor as one undo step. Anything else falls through to
        ordinary single-cursor handling, which implicitly collapses back
        to just the primary cursor -- a plain click does this too, via
        `mousePressEvent`.
        """

        if event.key() == Qt.Key.Key_Escape:
            self.clear_secondary_cursors()
            return True

        movement = _MULTI_CURSOR_MOVEMENTS.get(
            event.key(),
        )

        if movement is not None:
            mode = (
                QTextCursor.MoveMode.KeepAnchor
                if event.modifiers()
                & Qt.KeyboardModifier.ShiftModifier
                else QTextCursor.MoveMode.MoveAnchor
            )
            primary = self.textCursor()
            primary.movePosition(
                movement,
                mode,
            )
            self.setTextCursor(
                primary,
            )

            for cursor in self._secondary_cursors:
                cursor.movePosition(
                    movement,
                    mode,
                )

            self._refresh_extra_selections()
            self.ensureCursorVisible()
            return True

        if event.key() == Qt.Key.Key_Backspace:
            self._apply_at_every_cursor(
                lambda cursor: cursor.deletePreviousChar()
            )
            return True

        if event.key() == Qt.Key.Key_Delete:
            self._apply_at_every_cursor(
                lambda cursor: cursor.deleteChar()
            )
            return True

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._apply_at_every_cursor(
                lambda cursor: cursor.insertText(
                    "\n",
                )
            )
            return True

        if (
            event.key() == Qt.Key.Key_Tab
            and self._editor_settings.insert_spaces
            and not self.textCursor().hasSelection()
            and not any(
                cursor.hasSelection()
                for cursor in self._secondary_cursors
            )
        ):
            tab_width = self._editor_settings.tab_width

            def insert_tab_spaces(
                cursor: QTextCursor,
            ) -> None:
                column = cursor.positionInBlock()
                spaces_needed = tab_width - (
                    column % tab_width
                )
                cursor.insertText(
                    " " * spaces_needed,
                )

            self._apply_at_every_cursor(
                insert_tab_spaces,
            )
            return True

        text = event.text()

        if text and text.isprintable():
            self._apply_at_every_cursor(
                lambda cursor: cursor.insertText(
                    text,
                )
            )
            return True

        return False

    def _apply_at_every_cursor(
        self,
        edit,
    ) -> None:
        """Apply `edit(cursor)` at the primary cursor and every secondary
        one, as a single undo step.

        Each `QTextCursor` involved is already registered with this
        editor's `QTextDocument`, so Qt keeps every OTHER cursor's
        position correctly adjusted as each edit runs in turn --
        iteration order doesn't matter, the same "live cursor" behavior
        `SourceEditorWidget.toggle_bookmark_at_cursor` already relies on
        for tracking a bookmarked line across edits elsewhere.
        """

        primary = self.textCursor()
        primary.beginEditBlock()
        edit(
            primary,
        )

        for cursor in self._secondary_cursors:
            edit(
                cursor,
            )

        primary.endEditBlock()
        self.setTextCursor(
            primary,
        )
        self._refresh_extra_selections()

    def add_cursor_above(
        self,
    ) -> None:
        """Add a secondary cursor directly above the last one, same column."""

        self._add_cursor_relative(
            -1,
        )

    def add_cursor_below(
        self,
    ) -> None:
        """Add a secondary cursor directly below the last one, same column."""

        self._add_cursor_relative(
            1,
        )

    def _add_cursor_relative(
        self,
        direction: int,
    ) -> None:
        reference_cursor = (
            self._secondary_cursors[-1]
            if self._secondary_cursors
            else self.textCursor()
        )
        reference_block = reference_cursor.block()
        target_block = (
            reference_block.next()
            if direction > 0
            else reference_block.previous()
        )

        if not target_block.isValid():
            return

        column = min(
            reference_cursor.positionInBlock(),
            max(
                0,
                target_block.length() - 1,
            ),
        )
        new_cursor = QTextCursor(
            target_block,
        )
        new_cursor.setPosition(
            target_block.position() + column,
        )
        self._secondary_cursors.append(
            new_cursor,
        )
        self._refresh_extra_selections()
        self.viewport().update()

    def clear_secondary_cursors(
        self,
    ) -> None:
        """Collapse back to just the primary cursor."""

        if not self._secondary_cursors:
            return

        self._secondary_cursors = []
        self._refresh_extra_selections()
        self.viewport().update()

    @property
    def has_secondary_cursors(
        self,
    ) -> bool:
        """Return whether any secondary (multi-)cursor is active."""

        return bool(
            self._secondary_cursors,
        )

    def _handle_column_selection_key(
        self,
        event: QKeyEvent,
    ) -> bool:
        """Extend, edit through, or exit an active column (box) selection.

        Alt+Shift+Arrow starts or extends the box, the same keybinding
        Visual Studio and Notepad++ both already use for it. Any other
        arrow key exits box mode and falls through to ordinary movement
        (returns `False` after clearing the state) rather than staying
        active underneath a now-unrelated cursor position.
        """

        modifiers = event.modifiers()
        is_box_extend = (
            modifiers
            == (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
            and event.key() in _COLUMN_SELECTION_ARROW_KEYS
        )

        if is_box_extend:
            self._extend_column_selection_keyboard(
                event.key(),
            )
            return True

        if self._column_selection is None:
            return False

        if event.key() in _COLUMN_SELECTION_ARROW_KEYS:
            self._clear_column_selection()
            return False

        if event.key() == Qt.Key.Key_Escape:
            self._clear_column_selection()
            return True

        if event.key() == Qt.Key.Key_Backspace:
            self._apply_column_edit(
                self._column_backspace,
            )
            return True

        if event.key() == Qt.Key.Key_Delete:
            self._apply_column_edit(
                self._column_delete,
            )
            return True

        text = event.text()

        if text and text.isprintable():
            self._apply_column_edit(
                lambda cursor: cursor.insertText(
                    text,
                )
            )
            return True

        return False

    @staticmethod
    def _column_backspace(
        cursor: QTextCursor,
    ) -> None:
        """Delete one character back, but never cross into the line above.

        `cursor` is confined to one line's column range by
        `_apply_column_edit`, but `QTextCursor.deletePreviousChar()`
        doesn't know that -- called at column 0 it would delete the
        newline before this line instead, silently merging it into the
        line above. Column editing should never do that.
        """

        if cursor.hasSelection():
            cursor.removeSelectedText()
        elif cursor.positionInBlock() > 0:
            cursor.deletePreviousChar()

    @staticmethod
    def _column_delete(
        cursor: QTextCursor,
    ) -> None:
        """Delete one character forward, but never cross into the line below.

        The mirror image of `_column_backspace`'s guard: at the last
        column of a line, `QTextCursor.deleteChar()` would delete the
        newline after it, merging the next line into this one.
        """

        if cursor.hasSelection():
            cursor.removeSelectedText()
        elif (
            cursor.positionInBlock()
            < cursor.block().length() - 1
        ):
            cursor.deleteChar()

    def _apply_column_edit(
        self,
        edit,
    ) -> None:
        """Apply `edit(cursor)` to each line's column-selection span.

        `cursor` is positioned as that line's column range: collapsed at
        the column if the selection is zero-width (just a multi-line
        caret), or spanning between the anchor/active columns as a real
        selection otherwise. A line shorter than the range's start
        column is skipped entirely -- there's no "virtual space" padding
        past the end of a line, the same trade-off Notepad++'s box
        selection makes.

        Every processed line ends up at the same relative column after a
        uniform edit, so the selection collapses to a zero-width caret
        there afterward -- without this, a second keystroke would insert
        at the SAME pre-edit column again on every line (since the state
        was never told the first keystroke moved anything), landing
        before the first character instead of after it and reversing the
        apparent typing order one keystroke at a time.
        """

        state = self._column_selection

        if state is None:
            return

        start_line = min(
            state.anchor_line,
            state.active_line,
        )
        end_line = max(
            state.anchor_line,
            state.active_line,
        )
        start_column = min(
            state.anchor_column,
            state.active_column,
        )
        end_column = max(
            state.anchor_column,
            state.active_column,
        )

        primary = self.textCursor()
        primary.beginEditBlock()
        new_column = start_column

        for line in range(
            start_line,
            end_line + 1,
        ):
            block = self.document().findBlockByNumber(
                line,
            )
            line_length = max(
                0,
                block.length() - 1,
            )

            if not block.isValid() or line_length < start_column:
                continue

            line_end_column = min(
                end_column,
                line_length,
            )
            cursor = QTextCursor(
                block,
            )
            cursor.setPosition(
                block.position() + start_column,
            )

            if line_end_column > start_column:
                cursor.setPosition(
                    block.position() + line_end_column,
                    QTextCursor.MoveMode.KeepAnchor,
                )

            edit(
                cursor,
            )
            new_column = cursor.positionInBlock()

        primary.endEditBlock()
        state.anchor_column = new_column
        state.active_column = new_column
        self._refresh_extra_selections()

    def _begin_column_selection(
        self,
        pos: QPoint,
    ) -> None:
        cursor = self.cursorForPosition(
            pos,
        )
        line = cursor.blockNumber()
        column = cursor.positionInBlock()
        self._column_selection = _ColumnSelectionState(
            anchor_line=line,
            anchor_column=column,
            active_line=line,
            active_column=column,
        )
        self._refresh_extra_selections()
        self.viewport().update()

    def _extend_column_selection_keyboard(
        self,
        key: Qt.Key,
    ) -> None:
        if self._column_selection is None:
            primary = self.textCursor()
            line = primary.blockNumber()
            column = primary.positionInBlock()
            self._column_selection = _ColumnSelectionState(
                anchor_line=line,
                anchor_column=column,
                active_line=line,
                active_column=column,
            )

        state = self._column_selection
        block_count = self.document().blockCount()

        if key == Qt.Key.Key_Up:
            state.active_line = max(
                0,
                state.active_line - 1,
            )
        elif key == Qt.Key.Key_Down:
            state.active_line = min(
                block_count - 1,
                state.active_line + 1,
            )
        elif key == Qt.Key.Key_Left:
            state.active_column = max(
                0,
                state.active_column - 1,
            )
        elif key == Qt.Key.Key_Right:
            state.active_column += 1

        active_block = self.document().findBlockByNumber(
            state.active_line,
        )
        clamped_column = min(
            state.active_column,
            max(
                0,
                active_block.length() - 1,
            ),
        )
        cursor = QTextCursor(
            active_block,
        )
        cursor.setPosition(
            active_block.position() + clamped_column,
        )
        self.setTextCursor(
            cursor,
        )
        self._refresh_extra_selections()
        self.ensureCursorVisible()

    def _clear_column_selection(
        self,
    ) -> None:
        if self._column_selection is None:
            return

        self._column_selection = None
        self._refresh_extra_selections()
        self.viewport().update()

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
        """Dismiss the completion popup before any click repositions the cursor.

        Ctrl+Alt+Click adds a secondary (multi-)cursor at the clicked
        position. Alt+Click (without Ctrl) starts a column (box)
        selection, extended on drag via `mouseMoveEvent`. Any other
        click collapses both back to an ordinary single cursor before
        falling through to normal click handling.
        """

        self._close_completion_popup()

        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers()
            == (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
            )
        ):
            self._secondary_cursors.append(
                self.cursorForPosition(
                    event.position().toPoint(),
                )
            )
            self._refresh_extra_selections()
            self.viewport().update()
            return

        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers()
            == Qt.KeyboardModifier.AltModifier
        ):
            self.clear_secondary_cursors()
            self._begin_column_selection(
                event.position().toPoint(),
            )
            return

        self.clear_secondary_cursors()
        self._clear_column_selection()
        super().mousePressEvent(
            event,
        )

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """Extend an in-progress column (box) selection while dragging."""

        if (
            self._column_selection is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            cursor = self.cursorForPosition(
                event.position().toPoint(),
            )
            self._column_selection.active_line = (
                cursor.blockNumber()
            )
            self._column_selection.active_column = (
                cursor.positionInBlock()
            )
            self._refresh_extra_selections()
            self.viewport().update()
            return

        super().mouseMoveEvent(
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

    def focusInEvent(
        self,
        event: QFocusEvent,
    ) -> None:
        """Announce focus so a split tab knows which view is active."""

        super().focusInEvent(
            event,
        )
        self.focused.emit()

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
        self._paint_multi_caret_overlays(
            painter,
        )
        painter.end()

    def _paint_multi_caret_overlays(
        self,
        painter: QPainter,
    ) -> None:
        """Draw every secondary cursor's caret, plus a column selection's.

        Neither is an `ExtraSelection` (see `_refresh_extra_selections`):
        a zero-width selection paints nothing, which is exactly the case
        for a caret with no selected text, so both are drawn here as
        plain thin vertical lines instead.
        """

        if (
            not self._secondary_cursors
            and self._column_selection is None
        ):
            return

        painter.save()
        painter.setPen(
            self._secondary_cursor_color,
        )

        for cursor in self._secondary_cursors:
            rect = self.cursorRect(
                cursor,
            )
            painter.drawLine(
                rect.topLeft(),
                rect.bottomLeft(),
            )

        if self._column_selection is not None:
            state = self._column_selection
            start_line = min(
                state.anchor_line,
                state.active_line,
            )
            end_line = max(
                state.anchor_line,
                state.active_line,
            )

            for line in range(
                start_line,
                end_line + 1,
            ):
                block = self.document().findBlockByNumber(
                    line,
                )

                if not block.isValid():
                    continue

                column = min(
                    state.active_column,
                    max(
                        0,
                        block.length() - 1,
                    ),
                )
                cursor = QTextCursor(
                    block,
                )
                cursor.setPosition(
                    block.position() + column,
                )
                rect = self.cursorRect(
                    cursor,
                )
                painter.drawLine(
                    rect.topLeft(),
                    rect.bottomLeft(),
                )

        painter.restore()

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
                source_format=self._source_format,
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
            source_format=self._source_format,
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
            source_format=self._source_format,
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
            source_format=self._source_format,
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
            source_format=self._source_format,
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
            source_format=self._source_format,
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

    def _refresh_extra_selections(
        self,
    ) -> None:
        """Rebuild every `ExtraSelection`: current-line highlight plus
        any active column (box) selection.

        Secondary multi-cursor carets are NOT extra selections -- a
        zero-width `ExtraSelection` paints nothing, which is exactly
        the case for a caret with no selected text. They're drawn
        directly in `paintEvent` instead (`_paint_multi_caret_overlays`).
        """

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
                *self._column_selection_extra_selections(),
            ]
        )

    def _column_selection_extra_selections(
        self,
    ) -> list[QTextEdit.ExtraSelection]:
        """Highlight ranges for an active column selection, one per line.

        Only lines where the selected column range is non-empty get a
        highlight -- a zero-width column selection (just a multi-line
        caret, no actual text spanned yet) has nothing to highlight here;
        `_paint_multi_caret_overlays` draws its caret lines instead.
        """

        state = self._column_selection

        if state is None:
            return []

        start_line = min(
            state.anchor_line,
            state.active_line,
        )
        end_line = max(
            state.anchor_line,
            state.active_line,
        )
        start_column = min(
            state.anchor_column,
            state.active_column,
        )
        end_column = max(
            state.anchor_column,
            state.active_column,
        )

        if start_column == end_column:
            return []

        highlight_color = self.palette().color(
            QPalette.ColorRole.Highlight,
        )
        highlighted_text_color = self.palette().color(
            QPalette.ColorRole.HighlightedText,
        )
        selections: list[QTextEdit.ExtraSelection] = []

        for line in range(
            start_line,
            end_line + 1,
        ):
            block = self.document().findBlockByNumber(
                line,
            )

            if not block.isValid():
                continue

            line_length = max(
                0,
                block.length() - 1,
            )
            selection_start = min(
                start_column,
                line_length,
            )
            selection_end = min(
                end_column,
                line_length,
            )

            if selection_end <= selection_start:
                continue

            cursor = QTextCursor(
                block,
            )
            cursor.setPosition(
                block.position() + selection_start,
            )
            cursor.setPosition(
                block.position() + selection_end,
                QTextCursor.MoveMode.KeepAnchor,
            )

            line_selection = QTextEdit.ExtraSelection()
            line_selection.format.setBackground(
                highlight_color,
            )
            line_selection.format.setForeground(
                highlighted_text_color,
            )
            line_selection.cursor = cursor
            selections.append(
                line_selection,
            )

        return selections

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

    def _schedule_fold_range_update(
        self,
    ) -> None:
        """Debounce a fold-range recompute (see the module-level comment
        on `_FOLD_RANGE_DEBOUNCE_MILLISECONDS`).

        `QTimer.start()` on an already-running single-shot timer just
        resets its remaining time rather than queueing a second firing,
        so a burst of keystrokes (in particular Backspace's own
        auto-repeat) collapses into one recompute after they stop,
        exactly like `CobolSyntaxHighlighter._schedule_full_rehighlight`
        already does for the same reason.
        """

        self._fold_range_debounce_timer.start()

    def _update_fold_ranges(
        self,
        _new_block_count: int = 0,
    ) -> None:
        if not self._folding_enabled:
            self._fold_ranges = ()
            return

        self._fold_ranges = compute_fold_ranges(
            self.toPlainText(),
            source_format=self._source_format,
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


class _SplitEditorPane(QWidget):
    """One tab page: one or two `SourceEditorWidget` views onto one document.

    Every tab in `EditorTabsWidget` is one of these, even when it holds
    only the single, un-split view most tabs will ever have -- keeping
    that case uniform rather than special-cased is what lets every
    "active tab" operation elsewhere in this module keep working
    unchanged: they all resolve through `EditorTabsWidget._editor_at`/
    `_active_editor_widget`, which unwrap this container, rather than
    assuming a tab's page widget IS a `SourceEditorWidget` directly.

    Splitting shares the underlying `QTextDocument` between both views
    (see `SourceEditorWidget.become_split_view_of`), so edits in either
    are visible in both immediately. Which view is "active" -- the one
    active-tab operations act on -- is whichever last had keyboard focus.
    """

    def __init__(
        self,
        primary_editor: SourceEditorWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
        )

        self.primary_editor = primary_editor
        self.secondary_editor: SourceEditorWidget | None = None
        self._active_editor = primary_editor

        self._splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )
        self._splitter.addWidget(
            primary_editor,
        )

        layout = QHBoxLayout(
            self,
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.addWidget(
            self._splitter,
        )

        primary_editor.focused.connect(
            lambda: self.set_active_editor(
                primary_editor,
            )
        )

    @property
    def is_split(
        self,
    ) -> bool:
        """Return whether a second view is currently open."""

        return self.secondary_editor is not None

    def editors(
        self,
    ) -> tuple[SourceEditorWidget, ...]:
        """Return every open view, primary first."""

        if self.secondary_editor is None:
            return (
                self.primary_editor,
            )

        return (
            self.primary_editor,
            self.secondary_editor,
        )

    def active_editor(
        self,
    ) -> SourceEditorWidget:
        """Return whichever view last had keyboard focus."""

        return self._active_editor

    def set_active_editor(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        self._active_editor = editor

    def add_secondary(
        self,
        editor: SourceEditorWidget,
    ) -> None:
        """Add a second view, focusing it immediately."""

        self.secondary_editor = editor
        self._splitter.addWidget(
            editor,
        )
        editor.focused.connect(
            lambda: self.set_active_editor(
                editor,
            )
        )
        self.set_active_editor(
            editor,
        )
        editor.setFocus()

    def remove_secondary(
        self,
    ) -> None:
        """Close the second view, if one is open."""

        if self.secondary_editor is None:
            return

        editor = self.secondary_editor
        self.secondary_editor = None
        self.set_active_editor(
            self.primary_editor,
        )
        editor.setParent(
            None,
        )
        editor.deleteLater()
        self.primary_editor.setFocus()


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
        source_format: CobolSourceFormat = (
            CobolSourceFormat.FIXED
        ),
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
        self._source_format = source_format

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
            for editor in self._all_editors_at(
                index,
            ):
                editor.apply_theme(
                    theme,
                )

    def apply_editor_settings(
        self,
        editor_settings: EditorSettings,
    ) -> None:
        """Apply the configured font and tab width to every open tab."""

        self._editor_settings = editor_settings

        for index in range(self.count()):
            for editor in self._all_editors_at(
                index,
            ):
                editor.apply_editor_settings(
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
            for editor in self._all_editors_at(
                index,
            ):
                editor.apply_guide_settings(
                    guide_settings,
                )

    def apply_source_format(
        self,
        source_format: CobolSourceFormat,
    ) -> None:
        """Change every open tab's assumed COBOL column convention."""

        self._source_format = source_format

        for index in range(self.count()):
            for editor in self._all_editors_at(
                index,
            ):
                editor.apply_source_format(
                    source_format,
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
        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

        if editor is not None:
            editor.show_find_bar()

    def show_replace(
        self,
    ) -> None:
        """Show the find-and-replace bar on the active tab, if any."""

        editor = self._active_editor_widget()

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
            source_format=self._source_format,
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

        if (
            self._index_for(
                document_id,
            )
            == self.currentIndex()
        ):
            self.active_document_changed.emit()

    def current_outline(
        self,
    ) -> tuple[OutlineNode, ...]:
        """Return the active tab's COBOL outline, or `()` if none applies."""

        editor = self._active_editor_widget()

        if (
            isinstance(
                editor,
                SourceEditorWidget,
            )
            and editor.is_cobol_source
        ):
            return compute_outline(
                editor.toPlainText(),
                source_format=editor._source_format,
            )

        return ()

    def current_diagnostics(
        self,
    ) -> tuple[CompilerDiagnostic, ...]:
        """Return the active tab's live diagnostics, converted for display.

        Scoped to the active tab only, same as `current_outline()` --
        background tabs' diagnostics aren't tracked.
        """

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return False

        editor.trigger_suggest()
        return True

    def add_cursor_above_on_active_tab(
        self,
    ) -> None:
        """Add a secondary cursor above the active tab's, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.add_cursor_above()

    def add_cursor_below_on_active_tab(
        self,
    ) -> None:
        """Add a secondary cursor below the active tab's, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.add_cursor_below()

    def undo_active_tab(
        self,
    ) -> None:
        """Undo the active tab's last edit, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.undo()

    def redo_active_tab(
        self,
    ) -> None:
        """Redo the active tab's last undone edit, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.redo()

    def cut_active_tab(
        self,
    ) -> None:
        """Cut the active tab's selection to the clipboard, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.cut()

    def copy_active_tab(
        self,
    ) -> None:
        """Copy the active tab's selection to the clipboard, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.copy()

    def paste_active_tab(
        self,
    ) -> None:
        """Paste the clipboard into the active tab, if one is open."""

        editor = self._active_editor_widget()

        if isinstance(
            editor,
            SourceEditorWidget,
        ):
            editor.paste()

    def delete_selection_on_active_tab(
        self,
    ) -> None:
        """Delete the active tab's selection (or the next character), if open."""

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        editor = self._active_editor_widget()

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

        pane = self.widget(
            index,
        )
        secondary = (
            pane.secondary_editor
            if isinstance(
                pane,
                _SplitEditorPane,
            )
            else None
        )

        if secondary is not None:
            # The secondary view never has its own highlighter (see
            # `become_split_view_of`) -- it just needs its own
            # `is_cobol_source` flag and folding gate re-evaluated to
            # match, not a fresh `refresh_cobol_support` call.
            secondary.is_cobol_source = editor.is_cobol_source
            secondary.apply_editor_settings(
                self._editor_settings,
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
        """Return a tab index's primary editor view.

        Most tabs' page widget IS their `SourceEditorWidget` directly --
        only a split tab's page widget is a `_SplitEditorPane` wrapping
        two of them (see `toggle_split_on_active_tab`), so unwrapping is
        the exception here, not the rule.
        """

        widget = self.widget(
            index,
        )

        if isinstance(
            widget,
            _SplitEditorPane,
        ):
            return widget.primary_editor

        return widget

    def _all_editors_at(
        self,
        index: int,
    ) -> tuple[SourceEditorWidget, ...]:
        """Return every open view at a tab index (both, if split)."""

        widget = self.widget(
            index,
        )

        if isinstance(
            widget,
            _SplitEditorPane,
        ):
            return widget.editors()

        return (
            widget,
        )

    def _active_editor_widget(
        self,
    ) -> SourceEditorWidget | None:
        """Return whichever view last had focus in the active tab, if any."""

        pane = self.currentWidget()

        if isinstance(
            pane,
            _SplitEditorPane,
        ):
            return pane.active_editor()

        return pane

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

            if isinstance(
                widget,
                _SplitEditorPane,
            ):
                if any(
                    editor.document_id == document_id
                    for editor in widget.editors()
                ):
                    return index
            elif (
                isinstance(
                    widget,
                    SourceEditorWidget,
                )
                and widget.document_id == document_id
            ):
                return index

        return -1

    def toggle_split_on_active_tab(
        self,
    ) -> None:
        """Split the active tab into two views of one document, or unsplit it.

        Both views share one Qt `QTextDocument` (see
        `SourceEditorWidget.become_split_view_of`), so edits in either are
        visible in both immediately. The new view starts with none of the
        first view's fold ranges, bookmarks, or breakpoints -- those are
        each view's own state, and can diverge from here as each is
        worked in independently.

        Only a split tab's page widget is ever a `_SplitEditorPane` --
        every other tab's page widget IS its `SourceEditorWidget`
        directly, unchanged from before this feature existed, so
        splitting/unsplitting replaces the tab's page widget in place
        (remove, then reinsert at the same index) rather than always
        paying for a wrapper only one tab in many will ever use.
        """

        index = self.currentIndex()

        if index < 0:
            return

        widget = self.widget(
            index,
        )
        title = self.tabText(
            index,
        )
        tooltip = self.tabToolTip(
            index,
        )

        if isinstance(
            widget,
            _SplitEditorPane,
        ):
            primary = widget.primary_editor
            widget.remove_secondary()
            self.removeTab(
                index,
            )
            primary.setParent(
                None,
            )
            self.insertTab(
                index,
                primary,
                title,
            )
            self.setTabToolTip(
                index,
                tooltip,
            )
            self.setCurrentIndex(
                index,
            )
            widget.deleteLater()
            return

        if not isinstance(
            widget,
            SourceEditorWidget,
        ):
            return

        primary = widget
        secondary = SourceEditorWidget(
            document_id=primary.document_id,
            initial_text="",
            theme=self._theme,
            editor_settings=self._editor_settings,
            guide_settings=self._guide_settings,
        )
        secondary.become_split_view_of(
            primary,
        )
        secondary.bookmarks_changed.connect(
            self.bookmarks_changed.emit,
        )
        secondary.breakpoints_changed.connect(
            self.breakpoints_changed.emit,
        )

        self.removeTab(
            index,
        )
        pane = _SplitEditorPane(
            primary,
        )
        pane.add_secondary(
            secondary,
        )
        self.insertTab(
            index,
            pane,
            title,
        )
        self.setTabToolTip(
            index,
            tooltip,
        )
        self.setCurrentIndex(
            index,
        )


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
