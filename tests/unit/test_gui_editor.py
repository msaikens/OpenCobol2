"""Unit tests for the tabbed source editor, against a real DocumentService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QHelpEvent,
    QKeyEvent,
    QMouseEvent,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox

from opencobol2.compiler import CobolSourceFormat
from opencobol2.documents import DocumentService
from opencobol2.gui.editor import (
    _BREAKPOINT_MARKER_WIDTH,
    _SplitEditorPane,
    EditorTabsWidget,
    SourceEditorWidget,
)
from opencobol2.settings import CobolGuideSettings, EditorSettings
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    LIGHT_THEME_ID,
    Theme,
)


def _build_theme(
    theme_id: str = DARK_THEME_ID,
) -> Theme:
    return create_builtin_theme_registry().get(
        theme_id,
    )


def _build_tabs(
    document_service: DocumentService | None = None,
) -> EditorTabsWidget:
    return EditorTabsWidget(
        document_service=(
            DocumentService()
            if document_service is None
            else document_service
        ),
        theme=_build_theme(),
    )


def test_open_path_creates_a_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert tabs.count() == 1
    assert tabs.tabText(0) == "main.cbl"
    assert (
        tabs.widget(0).toPlainText()
        == "IDENTIFICATION DIVISION.\n"
    )
    assert (
        tabs.tabToolTip(0)
        == str(file_path)
    )


def test_open_path_twice_reuses_the_existing_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )
    tabs.new_file()
    tabs.open_path(
        file_path,
    )

    assert tabs.count() == 2
    assert tabs.currentIndex() == 0


def test_open_path_shows_error_dialog_on_undecodable_file(
    qapp,
    tmp_path: Path,
) -> None:
    """A file that can't be decoded as UTF-8 must show a clear error
    dialog and leave the tab bar untouched, not crash the double-click
    handler it's wired to."""

    file_path = tmp_path / "legacy.cbl"
    file_path.write_bytes(
        "café\r\n".encode(
            "cp1252",
        )
    )
    tabs = _build_tabs()

    with patch.object(
        QMessageBox,
        "critical",
    ) as mock_critical:
        tabs.open_path(
            file_path,
        )

    mock_critical.assert_called_once()
    assert tabs.count() == 0


def test_editing_text_marks_the_tab_dirty_and_syncs_the_document(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    document_service = DocumentService()
    tabs = _build_tabs(
        document_service,
    )
    tabs.open_path(
        file_path,
    )

    tabs.widget(0).setPlainText(
        "changed",
    )

    assert tabs.tabText(0) == "main.cbl *"
    active_document = (
        document_service.workspace
        .active_document
        .document
    )
    assert active_document.text == "changed"
    assert active_document.is_modified


def test_new_file_creates_an_untitled_tab(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.new_file()

    assert tabs.count() == 1
    assert tabs.tabText(0) == "Untitled"
    assert tabs.tabToolTip(0) == "Untitled"


def test_open_file_dialog_opens_the_chosen_path(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()

    with patch(
        "opencobol2.gui.editor.QFileDialog.getOpenFileName",
        return_value=(
            str(file_path),
            "",
        ),
    ):
        tabs.open_file_dialog()

    assert tabs.count() == 1
    assert tabs.tabText(0) == "main.cbl"


def test_open_file_dialog_does_nothing_when_cancelled(
    qapp,
) -> None:
    tabs = _build_tabs()

    with patch(
        "opencobol2.gui.editor.QFileDialog.getOpenFileName",
        return_value=(
            "",
            "",
        ),
    ):
        tabs.open_file_dialog()

    assert tabs.count() == 0


def test_save_active_document_persists_changes(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).setPlainText(
        "changed",
    )

    tabs.save_active_document()

    assert tabs.tabText(0) == "main.cbl"
    assert file_path.read_text() == "changed"


def test_save_active_document_redirects_untitled_to_save_as(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "hello",
    )
    save_path = tmp_path / "new.cbl"

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(save_path),
            "",
        ),
    ):
        tabs.save_active_document()

    assert tabs.tabText(0) == "new.cbl"
    assert save_path.read_text() == "hello"


def test_save_active_document_as_prompts_even_for_titled_documents(
    qapp,
    tmp_path: Path,
) -> None:
    original_path = tmp_path / "main.cbl"
    original_path.write_text(
        "x",
    )
    other_path = tmp_path / "copy.cbl"
    tabs = _build_tabs()
    tabs.open_path(
        original_path,
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(other_path),
            "",
        ),
    ) as mock_dialog:
        tabs.save_active_document_as()

    mock_dialog.assert_called_once()
    assert other_path.read_text() == "x"
    assert tabs.tabText(0) == "copy.cbl"


def test_save_active_document_as_does_nothing_when_cancelled(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "hello",
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            "",
            "",
        ),
    ):
        tabs.save_active_document_as()

    assert tabs.tabText(0) == "Untitled *"


def test_save_all_documents_skips_untitled_and_saves_the_rest(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).setPlainText(
        "changed",
    )
    tabs.new_file()
    tabs.widget(1).setPlainText(
        "untitled text",
    )

    tabs.save_all_documents()

    assert file_path.read_text() == "changed"
    assert tabs.tabText(0) == "main.cbl"
    assert tabs.tabText(1) == "Untitled *"


def test_close_active_document_without_changes_removes_the_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    tabs.close_active_document()

    assert tabs.count() == 0


def test_closing_a_tab_emits_bookmarks_and_breakpoints_changed(
    qapp,
) -> None:
    """The Bookmarks/Breakpoints panels only refresh on these two
    signals -- without emitting them on close, a closed tab's markers
    would keep showing in those panels until some unrelated toggle
    elsewhere happened to trigger a refresh."""

    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).toggle_bookmark_at_cursor()
    tabs.widget(0).toggle_breakpoint_at_cursor()

    bookmarks_received = []
    breakpoints_received = []
    tabs.bookmarks_changed.connect(
        lambda: bookmarks_received.append(
            True,
        )
    )
    tabs.breakpoints_changed.connect(
        lambda: breakpoints_received.append(
            True,
        )
    )

    tabs.close_active_document()

    assert tabs.count() == 0
    assert bookmarks_received == [True]
    assert breakpoints_received == [True]


def test_closing_a_modified_document_prompts_and_respects_cancel(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Cancel
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 1


def test_closing_a_modified_document_can_discard_changes(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Discard
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 0


def test_closing_a_modified_document_can_save_first(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )
    save_path = tmp_path / "new.cbl"

    with (
        patch(
            "opencobol2.gui.editor.QMessageBox.question",
            return_value=(
                QMessageBox.StandardButton.Save
            ),
        ),
        patch(
            "opencobol2.gui.editor.QFileDialog.getSaveFileName",
            return_value=(
                str(save_path),
                "",
            ),
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 0
    assert save_path.read_text() == "unsaved"


def test_closing_a_modified_untitled_document_save_choice_cancelled_keeps_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with (
        patch(
            "opencobol2.gui.editor.QMessageBox.question",
            return_value=(
                QMessageBox.StandardButton.Save
            ),
        ),
        patch(
            "opencobol2.gui.editor.QFileDialog.getSaveFileName",
            return_value=(
                "",
                "",
            ),
        ),
    ):
        tabs.close_active_document()

    # Save As was cancelled mid-close, so the tab must remain open with
    # its unsaved changes intact rather than being silently discarded.
    assert tabs.count() == 1
    assert tabs.tabText(0) == "Untitled *"


def test_close_all_documents_closes_every_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    tabs.new_file()

    tabs.close_all_documents()

    assert tabs.count() == 0


def test_rejects_non_document_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Editor tabs document service must be DocumentService"
        ),
    ):
        EditorTabsWidget(
            document_service=object(),  # type: ignore[arg-type]
            theme=_build_theme(),
        )


def test_rejects_non_theme(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match="Editor tabs theme must be Theme",
    ):
        EditorTabsWidget(
            document_service=DocumentService(),
            theme=object(),  # type: ignore[arg-type]
        )


def test_new_tab_uses_the_constructor_theme_colors(
    qapp,
) -> None:
    theme = _build_theme(
        DARK_THEME_ID,
    )
    tabs = _build_tabs()
    tabs.new_file()

    editor = tabs.widget(0)

    assert (
        editor._line_number_color.name().upper()
        == theme.colors.line_number_foreground
    )
    assert (
        editor._current_line_color.name().upper()
        == theme.colors.current_line_highlight
    )


def test_apply_theme_recolors_every_open_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    light_theme = _build_theme(
        LIGHT_THEME_ID,
    )

    tabs.apply_theme(
        light_theme,
    )

    for index in range(tabs.count()):
        editor = tabs.widget(index)
        assert (
            editor._line_number_color.name().upper()
            == light_theme.colors.line_number_foreground
        )
        assert (
            editor._current_line_color.name().upper()
            == light_theme.colors.current_line_highlight
        )


def test_apply_theme_colors_new_tabs_opened_afterward(
    qapp,
) -> None:
    tabs = _build_tabs()
    light_theme = _build_theme(
        LIGHT_THEME_ID,
    )

    tabs.apply_theme(
        light_theme,
    )
    tabs.new_file()

    editor = tabs.widget(0)
    assert (
        editor._line_number_color.name().upper()
        == light_theme.colors.line_number_foreground
    )


def test_apply_theme_rejects_non_theme(
    qapp,
) -> None:
    tabs = _build_tabs()

    with pytest.raises(
        TypeError,
        match="Editor tabs theme must be Theme",
    ):
        tabs.apply_theme(
            object(),  # type: ignore[arg-type]
        )


def test_line_number_area_width_grows_with_line_count(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    editor.setPlainText(
        "one line",
    )
    narrow_width = editor.line_number_area_width()

    editor.setPlainText(
        "\n".join(
            f"line {i}"
            for i in range(500)
        ),
    )
    wide_width = editor.line_number_area_width()

    assert wide_width > narrow_width


def test_current_line_highlight_uses_full_width_selection(
    qapp,
) -> None:
    from PySide6.QtGui import QTextFormat

    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    selections = editor.extraSelections()

    assert len(selections) == 1
    assert (
        selections[0].format.background().color()
        == editor._current_line_color
    )
    assert (
        selections[0].format.property(
            QTextFormat.Property.FullWidthSelection,
        )
        is True
    )


def test_show_find_bar_reveals_and_prefills_from_selection(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "hello world",
    )
    cursor = editor.textCursor()
    cursor.setPosition(
        0,
    )
    cursor.setPosition(
        5,
        cursor.MoveMode.KeepAnchor,
    )
    editor.setTextCursor(
        cursor,
    )

    assert editor._find_bar.isHidden()

    editor.show_find_bar()

    assert not editor._find_bar.isHidden()
    assert (
        editor._find_bar.find_edit.text()
        == "hello"
    )
    assert (
        editor._find_bar._replace_row_widget.isHidden()
    )


def test_show_replace_bar_reveals_replace_row(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    editor.show_replace_bar()

    assert not editor._find_bar.isHidden()
    assert (
        not editor._find_bar._replace_row_widget.isHidden()
    )


def test_hide_find_bar_hides_it(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.show_find_bar()

    editor.hide_find_bar()

    assert editor._find_bar.isHidden()


def test_find_text_is_case_insensitive_by_default(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "Needle in a haystack",
    )

    found = editor.find_text(
        "needle",
        backwards=False,
    )

    assert found
    assert (
        editor.textCursor().selectedText()
        == "Needle"
    )


def test_find_text_case_sensitive_flag_requires_exact_case(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "Needle needle",
    )

    found = editor.find_text(
        "needle",
        backwards=False,
        flags=(
            QTextDocument.FindFlag.FindCaseSensitively
        ),
    )

    assert found
    assert (
        editor.textCursor().selectionStart()
        == 7
    )


def test_find_text_wraps_around_the_document(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "apple banana apple",
    )
    cursor = editor.textCursor()
    cursor.movePosition(
        cursor.MoveOperation.End,
    )
    editor.setTextCursor(
        cursor,
    )

    found = editor.find_text(
        "apple",
        backwards=False,
    )

    assert found
    assert (
        editor.textCursor().selectionStart()
        == 0
    )


def test_find_text_returns_false_when_search_text_is_blank(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "hello",
    )

    assert not editor.find_text(
        "",
        backwards=False,
    )


def test_find_text_returns_false_when_not_present(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "hello world",
    )

    assert not editor.find_text(
        "zzz",
        backwards=False,
    )


def test_find_text_backwards_searches_toward_the_start(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "apple banana apple",
    )
    cursor = editor.textCursor()
    cursor.movePosition(
        cursor.MoveOperation.End,
    )
    editor.setTextCursor(
        cursor,
    )

    found = editor.find_text(
        "apple",
        backwards=True,
    )

    assert found
    assert (
        editor.textCursor().selectionStart()
        == 13
    )


def test_replace_current_replaces_selected_match_and_finds_next(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "apple banana apple",
    )
    editor.find_text(
        "apple",
        backwards=False,
    )

    found_next = editor.replace_current(
        "apple",
        "ORANGE",
    )

    assert editor.toPlainText() == (
        "ORANGE banana apple"
    )
    assert found_next
    assert (
        editor.textCursor().selectedText()
        == "apple"
    )


def test_replace_current_without_a_matching_selection_only_finds(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "apple banana",
    )
    cursor = editor.textCursor()
    cursor.movePosition(
        cursor.MoveOperation.Start,
    )
    editor.setTextCursor(
        cursor,
    )

    editor.replace_current(
        "apple",
        "ORANGE",
    )

    # No prior selection matched "apple", so nothing was replaced -- the
    # call only performed a find.
    assert (
        editor.toPlainText()
        == "apple banana"
    )
    assert (
        editor.textCursor().selectedText()
        == "apple"
    )


def test_replace_all_replaces_every_occurrence_and_returns_count(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "apple banana Apple BANANA",
    )

    count = editor.replace_all(
        "apple",
        "grape",
    )

    assert count == 2
    assert (
        editor.toPlainText()
        == "grape banana grape BANANA"
    )


def test_replace_all_returns_zero_for_blank_search_text(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "hello",
    )

    count = editor.replace_all(
        "",
        "x",
    )

    assert count == 0
    assert editor.toPlainText() == "hello"


def test_editor_tabs_show_find_delegates_to_active_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()

    tabs.show_find()

    assert not tabs.widget(
        1,
    )._find_bar.isHidden()
    assert tabs.widget(
        0,
    )._find_bar.isHidden()


def test_editor_tabs_show_replace_delegates_to_active_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()

    tabs.show_replace()

    editor = tabs.widget(
        0,
    )
    assert not editor._find_bar.isHidden()
    assert (
        not editor._find_bar._replace_row_widget.isHidden()
    )


def test_editor_tabs_show_find_is_a_no_op_without_open_tabs(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.show_find()

    assert tabs.count() == 0


def test_find_bar_next_button_reports_status_when_not_found(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "hello world",
    )
    editor.show_find_bar()

    editor._find_bar.find_edit.setText(
        "zzz",
    )
    editor._find_bar._handle_find_next()

    assert (
        editor._find_bar.status_label.text()
        == "No occurrences found."
    )


def test_find_bar_replace_all_button_reports_count(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "one one one",
    )
    editor.show_replace_bar()

    editor._find_bar.find_edit.setText(
        "one",
    )
    editor._find_bar.replace_edit.setText(
        "two",
    )
    editor._find_bar._handle_replace_all()

    assert (
        editor._find_bar.status_label.text()
        == "Replaced 3 occurrence(s)."
    )
    assert (
        editor.toPlainText()
        == "two two two"
    )


def test_opening_a_cbl_file_attaches_a_syntax_highlighter(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert (
        tabs.widget(0)._highlighter
        is not None
    )


def test_opening_a_cob_file_attaches_a_syntax_highlighter(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cob"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert (
        tabs.widget(0)._highlighter
        is not None
    )


def test_opening_a_non_cobol_file_has_no_syntax_highlighter(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "DISPLAY this is not cobol",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert tabs.widget(0)._highlighter is None


def test_new_untitled_file_attaches_a_syntax_highlighter(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.new_file()

    assert (
        tabs.widget(0)._highlighter
        is not None
    )


def test_apply_theme_recolors_the_syntax_highlighter(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "       DISPLAY X.",
    )

    light_theme = _build_theme(
        LIGHT_THEME_ID,
    )
    tabs.apply_theme(
        light_theme,
    )

    block = editor.document().findBlockByNumber(
        0,
    )
    colors = {
        block.text()[
            format_range.start:format_range.start
            + format_range.length
        ]: format_range.format.foreground()
        .color()
        .name()
        for format_range in block.layout().formats()
    }
    assert colors["DISPLAY"] == "#0000ff"


def test_new_tab_uses_a_monospace_font_by_default(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    assert editor.font().fixedPitch()
    assert editor.font().pointSize() == 11


def test_new_tab_never_word_wraps(
    qapp,
) -> None:
    """Coding-area column guides (and printing) are painted assuming
    one visual row == one logical line starting at column 1 -- true
    only without word-wrap. A wrapped fixed-format line desyncs every
    guide line past its first visual row."""

    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    assert (
        editor.lineWrapMode()
        == editor.LineWrapMode.NoWrap
    )


def test_new_tab_applies_configured_font_and_tab_width(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            font_family="Courier New",
            font_size=18,
            tab_width=8,
        ),
    )

    tabs.new_file()
    editor = tabs.widget(0)

    assert editor.font().family() == "Courier New"
    assert editor.font().pointSize() == 18
    char_width = editor.fontMetrics().horizontalAdvance(
        " ",
    )
    assert editor.tabStopDistance() == (
        char_width * 8
    )


def _press_tab(editor: SourceEditorWidget) -> None:
    """Simulate a Tab keypress directly against one editor widget."""

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
        "\t",
    )
    editor.keyPressEvent(event)


def test_tab_key_inserts_spaces_when_insert_spaces_enabled(
    qapp,
) -> None:
    """A literal tab character shifts the lexer's tab-expanded column
    positions out from under the raw document text it's applied
    against (see syntax_highlighter.py's highlightBlock) -- expanding
    Tab to spaces at the point of insertion sidesteps that mismatch
    instead of requiring every column-consuming feature to translate
    back through tab expansion."""

    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            tab_width=4,
            insert_spaces=True,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(0)

    _press_tab(editor)

    assert editor.toPlainText() == "    "
    assert "\t" not in editor.toPlainText()


def test_tab_key_inserts_literal_tab_when_insert_spaces_disabled(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            insert_spaces=False,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(0)

    _press_tab(editor)

    assert editor.toPlainText() == "\t"


def test_tab_key_rounds_up_to_next_tab_stop(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            tab_width=4,
            insert_spaces=True,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(0)

    editor.setPlainText("ab")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    _press_tab(editor)

    # Already 2 columns in; a 4-wide tab stop needs 2 more spaces to
    # reach column 4, not a fixed 4-space insertion.
    assert editor.toPlainText() == "ab  "


def test_new_tab_uses_configured_guide_settings(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        guide_settings=CobolGuideSettings(
            show_area_a=False,
        ),
    )

    tabs.new_file()
    editor = tabs.widget(0)

    assert (
        editor._guides._guide_settings.show_area_a
        is False
    )


def test_apply_editor_settings_updates_every_open_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()

    tabs.apply_editor_settings(
        EditorSettings(
            font_family="Consolas",
            font_size=20,
            tab_width=2,
        )
    )

    for index in range(tabs.count()):
        editor = tabs.widget(
            index,
        )
        assert editor.font().family() == "Consolas"
        assert editor.font().pointSize() == 20


def test_apply_editor_settings_affects_tabs_opened_afterward(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.apply_editor_settings(
        EditorSettings(
            font_family="Consolas",
            font_size=20,
            tab_width=2,
        )
    )
    tabs.new_file()

    editor = tabs.widget(0)
    assert editor.font().family() == "Consolas"
    assert editor.font().pointSize() == 20


def test_apply_guide_settings_updates_every_open_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()

    tabs.apply_guide_settings(
        CobolGuideSettings(
            show_reference_area=False,
        )
    )

    for index in range(tabs.count()):
        editor = tabs.widget(
            index,
        )
        assert (
            editor._guides._guide_settings
            .show_reference_area
            is False
        )


def test_source_editor_widget_apply_guide_settings_delegates(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    editor.apply_guide_settings(
        CobolGuideSettings(
            show_indicator_column=False,
        )
    )

    assert (
        editor._guides._guide_settings
        .show_indicator_column
        is False
    )


def test_welcome_page_is_visible_when_no_tabs_are_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert not tabs.welcome_page.isHidden()


def test_welcome_page_hides_once_a_tab_is_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.new_file()

    assert tabs.welcome_page.isHidden()


def test_welcome_page_reappears_once_the_last_tab_closes(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()

    tabs.close_active_document()

    assert tabs.count() == 0
    assert not tabs.welcome_page.isHidden()


def test_welcome_page_stays_hidden_while_other_tabs_remain_open(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()

    tabs.setCurrentIndex(
        0,
    )
    tabs.close_active_document()

    assert tabs.count() == 1
    assert tabs.welcome_page.isHidden()


def test_resizing_the_tabs_widget_resizes_the_welcome_page(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.show()

    tabs.resize(
        640,
        480,
    )

    assert tabs.welcome_page.size() == tabs.size()


def test_open_path_at_line_opens_the_file_and_moves_the_cursor(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "line one\n"
        "line two\n"
        "line three\n"
    )
    tabs = _build_tabs()

    tabs.open_path_at_line(
        file_path,
        2,
        6,
    )

    assert tabs.count() == 1
    cursor = tabs.widget(0).textCursor()
    assert cursor.blockNumber() == 1
    assert cursor.columnNumber() == 5


def test_open_path_at_line_reuses_an_already_open_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "line one\n"
        "line two\n"
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    tabs.new_file()

    tabs.open_path_at_line(
        file_path,
        2,
        1,
    )

    assert tabs.count() == 2
    assert tabs.currentIndex() == 0


def test_go_to_line_with_an_out_of_range_line_does_nothing(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    editor.go_to_line(
        999,
    )

    assert editor.textCursor().blockNumber() == 0


def test_is_cobol_source_true_for_a_cbl_file(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert tabs.widget(0).is_cobol_source is True


def test_is_cobol_source_false_for_a_non_cobol_file(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()

    tabs.open_path(
        file_path,
    )

    assert tabs.widget(0).is_cobol_source is False


def test_save_as_activates_cobol_support_for_a_newly_cobol_named_file(
    qapp,
    tmp_path: Path,
) -> None:
    """is_cobol_source/the highlighter/folding are otherwise only set
    up once at tab-creation time from the initial path -- Save-As-ing
    a plain-text tab to a .cbl name must still activate COBOL support
    on that same tab, not require closing and reopening it."""

    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    editor = tabs.widget(0)
    assert editor.is_cobol_source is False
    assert editor._highlighter is None

    new_path = tmp_path / "main.cbl"

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(new_path),
            "",
        ),
    ):
        tabs.save_active_document_as()

    assert editor.is_cobol_source is True
    assert editor._highlighter is not None


def test_save_as_deactivates_cobol_support_for_a_newly_non_cobol_file(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    editor = tabs.widget(0)
    assert editor.is_cobol_source is True
    assert editor._highlighter is not None

    new_path = tmp_path / "notes.txt"

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(new_path),
            "",
        ),
    ):
        tabs.save_active_document_as()

    assert editor.is_cobol_source is False
    assert editor._highlighter is None
    assert editor._folding_enabled is False


def test_current_outline_returns_outline_for_the_active_cobol_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
    )

    outline = tabs.current_outline()

    assert [
        node.name
        for node in outline
    ] == ["IDENTIFICATION DIVISION (DEMO)"]


def test_current_outline_is_empty_for_a_non_cobol_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    assert tabs.current_outline() == ()


def test_current_outline_is_empty_when_no_tabs_are_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.current_outline() == ()


def test_go_to_active_line_moves_the_cursor_in_the_current_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "line one\n"
        "line two\n"
    )

    tabs.go_to_active_line(
        2,
        6,
    )

    cursor = tabs.widget(0).textCursor()
    assert cursor.blockNumber() == 1
    assert cursor.columnNumber() == 5


def test_go_to_active_line_does_nothing_when_no_tabs_are_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.go_to_active_line(
        1,
    )


def test_active_document_changed_emits_on_tab_switch(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    received = []
    tabs.active_document_changed.connect(
        lambda: received.append(
            True,
        )
    )

    tabs.setCurrentIndex(
        0,
    )

    assert received == [True]


def test_active_document_changed_emits_when_the_active_tab_is_edited(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    received = []
    tabs.active_document_changed.connect(
        lambda: received.append(
            True,
        )
    )

    tabs.widget(0).setPlainText(
        "changed",
    )

    assert received == [True]


def test_active_document_changed_does_not_emit_for_a_background_tab_edit(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    background_editor = tabs.widget(0)
    assert tabs.currentIndex() == 1
    received = []
    tabs.active_document_changed.connect(
        lambda: received.append(
            True,
        )
    )

    background_editor.setPlainText(
        "changed in the background",
    )

    assert received == []


def test_toggle_bookmark_adds_a_bookmark_at_the_cursor_line(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
        "line three\n"
    )
    editor.go_to_line(
        2,
    )

    editor.toggle_bookmark_at_cursor()

    assert editor.bookmarked_lines == (2,)


def test_toggle_bookmark_twice_removes_it(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
    )
    editor.go_to_line(
        1,
    )

    editor.toggle_bookmark_at_cursor()
    editor.toggle_bookmark_at_cursor()

    assert editor.bookmarked_lines == ()


def test_bookmarked_lines_are_sorted(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "one\n"
        "two\n"
        "three\n"
    )

    editor.go_to_line(
        3,
    )
    editor.toggle_bookmark_at_cursor()
    editor.go_to_line(
        1,
    )
    editor.toggle_bookmark_at_cursor()

    assert editor.bookmarked_lines == (
        1,
        3,
    )


def test_toggle_bookmark_emits_bookmarks_changed(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    received = []
    editor.bookmarks_changed.connect(
        lambda: received.append(
            True,
        )
    )

    editor.toggle_bookmark_at_cursor()

    assert received == [True]


def test_bookmark_follows_its_line_when_lines_shift_above_it(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
        "line three\n"
    )
    editor.go_to_line(
        3,
    )
    editor.toggle_bookmark_at_cursor()
    assert editor.bookmarked_lines == (3,)

    cursor = editor.textCursor()
    cursor.movePosition(
        QTextCursor.MoveOperation.Start,
    )
    cursor.insertText(
        "a new line\nanother new line\n",
    )

    # The bookmark stays attached to "line three" itself, which has now
    # shifted down to line 5 -- not to whatever text now occupies line 3.
    assert editor.bookmarked_lines == (5,)
    assert (
        "line three"
        in editor.document()
        .findBlockByNumber(
            4,
        )
        .text()
    )


def test_bookmarked_line_paints_a_marker_in_the_gutter(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=(
            "line one\n"
            "line two\n"
            "line three\n"
        ),
        theme=_build_theme(),
    )
    editor.resize(
        600,
        400,
    )
    editor.show()

    editor.go_to_line(
        2,
    )
    editor.toggle_bookmark_at_cursor()

    image = (
        editor._line_number_area.grab().toImage()
    )
    block = editor.document().findBlockByNumber(
        1,
    )
    marker_rect = editor.blockBoundingGeometry(
        block,
    ).translated(
        editor.contentOffset(),
    )
    y = int(
        marker_rect.center().y(),
    )

    assert (
        image.pixelColor(
            _BREAKPOINT_MARKER_WIDTH + 2,
            y,
        )
        == editor._bookmark_color
    )


def test_toggle_bookmark_on_active_tab_toggles_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "should not be bookmarked\n",
    )
    tabs.setCurrentIndex(
        1,
    )
    tabs.widget(1).setPlainText(
        "line one\n"
        "line two\n",
    )
    tabs.widget(1).go_to_line(
        2,
    )

    tabs.toggle_bookmark_on_active_tab()

    assert tabs.widget(1).bookmarked_lines == (2,)
    assert tabs.widget(0).bookmarked_lines == ()


def test_toggle_bookmark_on_active_tab_does_nothing_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.toggle_bookmark_on_active_tab()


def test_all_bookmarks_aggregates_across_open_tabs(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "one\n"
        "two\n"
        "three\n",
    )
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).go_to_line(
        2,
    )
    tabs.widget(0).toggle_bookmark_at_cursor()

    tabs.new_file()
    tabs.widget(1).setPlainText(
        "alpha\n"
        "beta\n",
    )
    tabs.widget(1).go_to_line(
        1,
    )
    tabs.widget(1).toggle_bookmark_at_cursor()

    entries = tabs.all_bookmarks()

    assert len(
        entries,
    ) == 2
    named_entry = next(
        entry
        for entry in entries
        if entry.display_name == "main.cbl"
    )
    assert named_entry.line == 2
    assert named_entry.text == "two"
    untitled_entry = next(
        entry
        for entry in entries
        if entry.display_name == "Untitled"
    )
    assert untitled_entry.line == 1
    assert untitled_entry.text == "alpha"


def test_all_bookmarks_is_empty_with_no_bookmarks(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()

    assert tabs.all_bookmarks() == ()


def test_reveal_bookmark_activates_the_tab_and_moves_the_cursor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    document_id = tabs.widget(0).document_id
    tabs.widget(0).setPlainText(
        "line one\n"
        "line two\n",
    )
    tabs.new_file()
    assert tabs.currentIndex() == 1

    tabs.reveal_bookmark(
        document_id,
        2,
        3,
    )

    assert tabs.currentIndex() == 0
    cursor = tabs.widget(0).textCursor()
    assert cursor.blockNumber() == 1
    assert cursor.columnNumber() == 2


def test_reveal_bookmark_with_an_unknown_document_id_does_nothing(
    qapp,
) -> None:
    from uuid import uuid4

    tabs = _build_tabs()
    tabs.new_file()

    tabs.reveal_bookmark(
        uuid4(),
        1,
    )

    assert tabs.currentIndex() == 0


def test_editor_tabs_bookmarks_changed_forwards_from_a_background_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    background_editor = tabs.widget(0)
    assert tabs.currentIndex() == 1
    received = []
    tabs.bookmarks_changed.connect(
        lambda: received.append(
            True,
        )
    )

    background_editor.toggle_bookmark_at_cursor()

    assert received == [True]


def test_autosave_disabled_by_default_does_not_start_the_timer(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert not tabs._autosave_timer.isActive()


def test_autosave_enabled_starts_the_timer_with_the_configured_interval(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            autosave_enabled=True,
            autosave_interval_seconds=30,
        ),
    )

    assert tabs._autosave_timer.isActive()
    assert tabs._autosave_timer.interval() == 30000


def test_apply_editor_settings_reconfigures_the_autosave_timer(
    qapp,
) -> None:
    tabs = _build_tabs()
    assert not tabs._autosave_timer.isActive()

    tabs.apply_editor_settings(
        EditorSettings(
            autosave_enabled=True,
            autosave_interval_seconds=15,
        )
    )

    assert tabs._autosave_timer.isActive()
    assert tabs._autosave_timer.interval() == 15000

    tabs.apply_editor_settings(
        EditorSettings(
            autosave_enabled=False,
        )
    )

    assert not tabs._autosave_timer.isActive()


def test_autosave_timeout_saves_a_modified_named_document(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).setPlainText(
        "changed",
    )

    tabs._handle_autosave_timeout()

    assert file_path.read_text() == "changed"
    assert tabs.tabText(0) == "main.cbl"


def test_autosave_timeout_skips_an_untitled_document(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "some text",
    )

    tabs._handle_autosave_timeout()


def test_autosave_timeout_skips_an_unmodified_document(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    tabs._handle_autosave_timeout()

    assert file_path.read_text() == "original"


def test_autosave_timeout_continues_past_a_save_failure(
    qapp,
    tmp_path: Path,
) -> None:
    document_service = DocumentService()
    tabs = _build_tabs(
        document_service,
    )
    first_path = tmp_path / "first.cbl"
    first_path.write_text(
        "one",
    )
    second_path = tmp_path / "second.cbl"
    second_path.write_text(
        "two",
    )
    tabs.open_path(
        first_path,
    )
    tabs.open_path(
        second_path,
    )
    tabs.widget(0).setPlainText(
        "one changed",
    )
    tabs.widget(1).setPlainText(
        "two changed",
    )

    with patch.object(
        DocumentService,
        "save_document",
        side_effect=[
            OSError(
                "boom",
            ),
            None,
        ],
    ) as mock_save_document:
        tabs._handle_autosave_timeout()

    assert mock_save_document.call_count == 2
    assert mock_save_document.call_args_list[0].args == (
        tabs.widget(0).document_id,
    )
    assert mock_save_document.call_args_list[1].args == (
        tabs.widget(1).document_id,
    )


def test_diagnostics_reports_a_lex_diagnostic_for_cobol_files(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)

    editor.setPlainText(
        "       DISPLAY 'UNCLOSED",
    )

    assert editor.is_cobol_source
    assert any(
        "not terminated" in diagnostic.message
        for diagnostic in editor.diagnostics
    )


def test_diagnostics_is_empty_for_a_non_cobol_file(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "       DISPLAY 'UNCLOSED",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    assert tabs.widget(0).diagnostics == ()


def test_current_diagnostics_converts_to_compiler_diagnostic(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "       DISPLAY 'UNCLOSED",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    diagnostics = tabs.current_diagnostics()

    # This source is missing IDENTIFICATION DIVISION entirely, so a
    # parse-level diagnostic at column 8 now correctly sorts before
    # the lex-level "not terminated" diagnostic at a later column on
    # the same line (Editor Phase 4 tracker finding Editor-Facing-8) --
    # assert every diagnostic carries the source path, and that the
    # lex diagnostic is present somewhere, rather than assuming index 0.
    assert len(diagnostics) >= 1
    assert all(
        diagnostic.source_path == file_path
        for diagnostic in diagnostics
    )
    assert any(
        "not terminated" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_current_diagnostics_uses_no_path_for_untitled_documents(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "       DISPLAY 'UNCLOSED",
    )

    diagnostics = tabs.current_diagnostics()

    assert len(diagnostics) >= 1
    assert diagnostics[0].source_path is None


def test_current_diagnostics_is_empty_when_no_tabs_are_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.current_diagnostics() == ()


def test_current_diagnostics_is_empty_for_clean_source(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        '           DISPLAY "HELLO".\n'
        "           STOP RUN.\n",
    )

    assert tabs.current_diagnostics() == ()


_NAVIGATION_SAMPLE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-COUNT PIC 9(3).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 1 TO WS-COUNT\n"
    "           STOP RUN.\n"
)


def _go_to_usage(
    editor,
    line: int,
    name: str,
) -> None:
    column = (
        editor.document()
        .findBlockByNumber(
            line - 1,
        )
        .text()
        .index(
            name,
        )
        + 1
    )
    editor.go_to_line(
        line,
        column,
    )


def test_go_to_definition_moves_the_cursor_to_the_definition(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    found = editor.go_to_definition()

    assert found is True
    assert editor.textCursor().blockNumber() == 4


def test_go_to_definition_returns_false_when_nothing_is_found(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    # Column 1 of line 1 is inside a reserved word, not an identifier.
    editor.go_to_line(
        1,
        8,
    )

    assert editor.go_to_definition() is False


def test_references_at_cursor_finds_every_usage(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    locations = editor.references_at_cursor()

    assert {
        location.line
        for location in locations
    } == {5, 8}


def test_go_to_definition_on_active_tab_delegates_to_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    found = tabs.go_to_definition_on_active_tab()

    assert found is True
    assert editor.textCursor().blockNumber() == 4


def test_go_to_definition_on_active_tab_is_false_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.go_to_definition_on_active_tab() is False


def test_find_references_for_active_tab_returns_find_results(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        _NAVIGATION_SAMPLE,
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    _go_to_usage(
        tabs.widget(0),
        8,
        "WS-COUNT",
    )

    results = tabs.find_references_for_active_tab()

    assert {
        result.line
        for result in results
    } == {5, 8}
    assert all(
        result.path == file_path
        for result in results
    )


def test_find_references_for_active_tab_is_empty_for_untitled_documents(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    assert tabs.find_references_for_active_tab() == ()


def test_find_references_for_active_tab_is_empty_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.find_references_for_active_tab() == ()


def _point_for_usage(
    editor,
    line: int,
    name: str,
) -> QPoint:
    text = (
        editor.document()
        .findBlockByNumber(
            line - 1,
        )
        .text()
    )
    start_column = text.index(name) + 1
    middle_column = start_column + len(name) // 2
    editor.go_to_line(
        line,
        middle_column,
    )

    return editor.cursorRect().center()


def test_hover_info_at_describes_a_data_item_under_the_cursor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    point = _point_for_usage(
        editor,
        8,
        "WS-COUNT",
    )

    info = editor.hover_info_at(
        point,
    )

    assert info is not None
    assert info.kind == "data-item"
    assert "WS-COUNT" in info.detail


_SIGNATURE_HELP_SAMPLE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-NAME PIC X(20).\n"
    "       01 WS-RESULT PIC X(20).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE FUNCTION UPPER-CASE(WS-NAME) TO WS-RESULT\n"
    "           STOP RUN.\n"
)


def test_hover_info_at_describes_a_function_call_argument_list(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _SIGNATURE_HELP_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    point = _point_for_usage(
        editor,
        9,
        "WS-NAME",
    )

    info = editor.hover_info_at(
        point,
    )

    assert info is not None
    assert info.kind == "function-signature"
    assert info.name == "UPPER-CASE"
    assert "UPPER-CASE" in info.detail


def test_hover_info_at_returns_none_off_an_identifier(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    # The period ending "STOP RUN." on line 9 is neither an identifier
    # nor a documented reserved word.
    editor.go_to_line(
        9,
        editor.document()
        .findBlockByNumber(8)
        .text()
        .index(".")
        + 1,
    )

    assert (
        editor.hover_info_at(
            editor.cursorRect().center(),
        )
        is None
    )


def test_hover_info_at_returns_none_for_non_cobol_files(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        _NAVIGATION_SAMPLE,
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    editor = tabs.widget(0)
    editor.resize(
        600,
        400,
    )
    editor.show()

    assert editor.is_cobol_source is False
    assert (
        editor.hover_info_at(
            _point_for_usage(
                editor,
                8,
                "WS-COUNT",
            ),
        )
        is None
    )


def test_tooltip_event_shows_hover_info_for_a_recognized_symbol(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    point = _point_for_usage(
        editor,
        8,
        "WS-COUNT",
    )

    with patch(
        "opencobol2.gui.editor.QToolTip.showText",
    ) as mock_show_text:
        handled = editor.event(
            QHelpEvent(
                QEvent.Type.ToolTip,
                point,
                editor.mapToGlobal(
                    point,
                ),
            )
        )

    assert handled is True
    assert mock_show_text.called
    shown_text = mock_show_text.call_args.args[1]
    assert "WS-COUNT" in shown_text


def test_tooltip_event_shows_hover_info_for_a_documented_reserved_word(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    point = _point_for_usage(
        editor,
        8,
        "MOVE",
    )

    with patch(
        "opencobol2.gui.editor.QToolTip.showText",
    ) as mock_show_text:
        handled = editor.event(
            QHelpEvent(
                QEvent.Type.ToolTip,
                point,
                editor.mapToGlobal(
                    point,
                ),
            )
        )

    assert handled is True
    assert mock_show_text.called
    shown_text = mock_show_text.call_args.args[1]
    assert "MOVE" in shown_text


def test_tooltip_event_hides_the_tooltip_when_nothing_is_found(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    # The period ending "STOP RUN." on line 9 is neither an identifier
    # nor a documented reserved word.
    editor.go_to_line(
        9,
        editor.document()
        .findBlockByNumber(8)
        .text()
        .index(".")
        + 1,
    )
    point = editor.cursorRect().center()

    with patch(
        "opencobol2.gui.editor.QToolTip.hideText",
    ) as mock_hide_text:
        handled = editor.event(
            QHelpEvent(
                QEvent.Type.ToolTip,
                point,
                editor.mapToGlobal(
                    point,
                ),
            )
        )

    assert handled is True
    assert mock_hide_text.called


def _build_editor_with_lines(
    line_count: int,
) -> SourceEditorWidget:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="\n".join(
            f"line {index}"
            for index in range(line_count)
        ),
        theme=_build_theme(),
    )
    editor.resize(
        600,
        400,
    )
    editor.show()

    return editor


def test_minimap_is_visible_and_sized_by_default(
    qapp,
) -> None:
    editor = _build_editor_with_lines(50)

    assert editor._minimap_area.isVisible()
    assert editor.minimap_area_width() > 0


def test_minimap_reserves_space_on_the_viewport_right_edge(
    qapp,
) -> None:
    editor = _build_editor_with_lines(50)

    margins = editor.viewportMargins()

    assert margins.right() == editor.minimap_area_width()


def test_minimap_is_hidden_when_disabled_via_settings(
    qapp,
) -> None:
    editor = _build_editor_with_lines(50)

    editor.apply_editor_settings(
        EditorSettings(
            show_minimap=False,
        )
    )

    assert editor._minimap_area.isVisible() is False
    assert editor.minimap_area_width() == 0


def test_minimap_line_for_position_maps_top_and_bottom(
    qapp,
) -> None:
    editor = _build_editor_with_lines(100)

    top_line = editor.minimap_line_for_position(0)
    bottom_line = editor.minimap_line_for_position(
        editor._minimap_area.height() - 1,
    )

    assert top_line == 0
    assert bottom_line == 99


def test_minimap_line_for_position_clamps_out_of_range_input(
    qapp,
) -> None:
    editor = _build_editor_with_lines(10)

    assert editor.minimap_line_for_position(-5) == 0
    assert (
        editor.minimap_line_for_position(
            100_000,
        )
        == 9
    )


def test_handle_minimap_click_moves_the_cursor_to_that_line(
    qapp,
) -> None:
    editor = _build_editor_with_lines(100)

    editor.handle_minimap_click(
        QPoint(
            10,
            editor._minimap_area.height() - 1,
        )
    )

    assert editor.textCursor().blockNumber() == 99


def test_minimap_paints_without_raising_on_an_empty_document(
    qapp,
) -> None:
    editor = _build_editor_with_lines(0)

    editor._minimap_area.update()
    qapp.processEvents()


def test_last_visible_block_number_accounts_for_hidden_folded_blocks(
    qapp,
) -> None:
    """The old calculation multiplied the on-screen *rendered row*
    count by the minimap's per-block-index pixel height -- correct
    only when one row equals one block. Once a fold hides a large
    span, a handful of rendered rows can cover a much wider range of
    block indices, and the indicator must reflect that wider span."""

    from uuid import uuid4

    folded_body = "".join(
        f'               DISPLAY "X"\n'
        for _ in range(500)
    )
    filler_after = "".join(
        f'       DISPLAY "FILLER {index}".\n'
        for index in range(500)
    )
    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=(
            "       IDENTIFICATION DIVISION.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           IF 1 > 0\n"
            + folded_body
            + "           END-IF\n"
            "           STOP RUN.\n"
            + filler_after
        ),
        theme=_build_theme(),
    )
    editor.resize(
        600,
        100,
    )
    editor.show()

    editor.toggle_fold(
        4,
    )
    assert editor._collapsed_start_lines

    last_visible = editor._last_visible_block_number()

    # The 500-line IF body occupies block indices ~4-503, all hidden.
    # Visible content resumes at END-IF (~504); the viewport's row
    # budget consumed from there must land well past that point, not
    # underneath the folded body as the old formula would.
    assert last_visible > 503


def test_minimap_setting_round_trips_through_apply_editor_settings(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.apply_editor_settings(
        EditorSettings(
            show_minimap=False,
        )
    )
    tabs.new_file()

    editor = tabs.widget(0)

    assert editor._minimap_area.isVisible() is False


_RENAME_COLLISION_SAMPLE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-COUNT PIC 9(3).\n"
    "       01 WS-COUNT-TOTAL PIC 9(5).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 1 TO WS-COUNT\n"
    "           MOVE WS-COUNT TO WS-COUNT-TOTAL\n"
    "           STOP RUN.\n"
)


def test_rename_symbol_at_cursor_renames_every_occurrence(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    count = editor.rename_symbol_at_cursor(
        "WS-TOTAL",
    )

    assert count == 2
    assert "WS-COUNT" not in editor.toPlainText()
    assert (
        editor.toPlainText().count(
            "WS-TOTAL",
        )
        == 2
    )


def test_rename_symbol_at_cursor_does_not_touch_a_longer_identifier_sharing_a_prefix(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _RENAME_COLLISION_SAMPLE,
    )
    _go_to_usage(
        editor,
        9,
        "WS-COUNT",
    )

    count = editor.rename_symbol_at_cursor(
        "WS-TOTAL",
    )

    assert count == 3
    text = editor.toPlainText()
    assert "WS-COUNT-TOTAL" in text
    assert "WS-COUNT " not in text
    assert "WS-COUNT\n" not in text
    assert text.count("WS-TOTAL") == 3


def test_rename_symbol_at_cursor_is_undoable_as_one_step(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    original_text = editor.toPlainText()
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    editor.rename_symbol_at_cursor(
        "WS-TOTAL",
    )
    editor.undo()

    assert editor.toPlainText() == original_text


def test_rename_symbol_at_cursor_returns_zero_off_an_identifier(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    # Column 1 of line 1 is inside a reserved word, not an identifier.
    editor.go_to_line(
        1,
        8,
    )

    assert (
        editor.rename_symbol_at_cursor(
            "WS-TOTAL",
        )
        == 0
    )


def test_rename_symbol_on_active_tab_delegates_to_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NAVIGATION_SAMPLE,
    )
    _go_to_usage(
        editor,
        8,
        "WS-COUNT",
    )

    count = tabs.rename_symbol_on_active_tab(
        "WS-TOTAL",
    )

    assert count == 2
    assert "WS-COUNT" not in editor.toPlainText()


def test_rename_symbol_on_active_tab_is_zero_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert (
        tabs.rename_symbol_on_active_tab(
            "WS-TOTAL",
        )
        == 0
    )


def test_print_active_tab_is_false_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.print_active_tab(QPrinter()) is False


def test_print_active_tab_prints_the_active_document(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
    )

    assert tabs.print_active_tab(QPrinter()) is True


def _build_foldable_tab_with_a_collapsed_fold(tabs) -> None:
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           IF 1 > 0\n"
        '               DISPLAY "POSITIVE"\n'
        "           END-IF\n"
        "           STOP RUN.\n"
    )
    # Fold-range recompute is debounced (see
    # `_FOLD_RANGE_DEBOUNCE_MILLISECONDS`) -- simulate it elapsing
    # without a real wait, the same way the completion debounce tests
    # already do.
    editor._fold_range_debounce_timer.stop()
    editor._update_fold_ranges()
    editor.toggle_fold(
        5,
    )
    assert editor._collapsed_start_lines


def test_print_active_tab_warns_before_printing_folded_content(
    qapp,
) -> None:
    """QPlainTextEdit.print_() prints folded-away content in full
    regardless of what's visible on screen -- with an active fold,
    printing must ask before doing that rather than silently
    surprising the user."""

    tabs = _build_tabs()
    _build_foldable_tab_with_a_collapsed_fold(
        tabs,
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ) as mock_question:
        result = tabs.print_active_tab(
            QPrinter(),
        )

    mock_question.assert_called_once()
    assert result is False


def test_print_active_tab_proceeds_when_fold_warning_is_confirmed(
    qapp,
) -> None:
    tabs = _build_tabs()
    _build_foldable_tab_with_a_collapsed_fold(
        tabs,
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        result = tabs.print_active_tab(
            QPrinter(),
        )

    assert result is True


def test_print_active_tab_does_not_warn_without_any_folds(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "       IDENTIFICATION DIVISION.\n"
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
    ) as mock_question:
        result = tabs.print_active_tab(
            QPrinter(),
        )

    mock_question.assert_not_called()
    assert result is True


def test_toggle_breakpoint_adds_a_breakpoint_at_the_cursor_line(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
        "line three\n"
    )
    editor.go_to_line(
        2,
    )

    editor.toggle_breakpoint_at_cursor()

    assert editor.breakpoint_lines == (2,)


def test_toggle_breakpoint_twice_removes_it(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
    )
    editor.go_to_line(
        1,
    )

    editor.toggle_breakpoint_at_cursor()
    editor.toggle_breakpoint_at_cursor()

    assert editor.breakpoint_lines == ()


def test_breakpointed_lines_are_sorted(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "one\n"
        "two\n"
        "three\n"
    )

    editor.go_to_line(
        3,
    )
    editor.toggle_breakpoint_at_cursor()
    editor.go_to_line(
        1,
    )
    editor.toggle_breakpoint_at_cursor()

    assert editor.breakpoint_lines == (
        1,
        3,
    )


def test_toggle_breakpoint_emits_breakpoints_changed(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    received = []
    editor.breakpoints_changed.connect(
        lambda: received.append(
            True,
        )
    )

    editor.toggle_breakpoint_at_cursor()

    assert received == [True]


def test_breakpoint_follows_its_line_when_lines_shift_above_it(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one\n"
        "line two\n"
        "line three\n"
    )
    editor.go_to_line(
        3,
    )
    editor.toggle_breakpoint_at_cursor()
    assert editor.breakpoint_lines == (3,)

    cursor = editor.textCursor()
    cursor.movePosition(
        QTextCursor.MoveOperation.Start,
    )
    cursor.insertText(
        "a new line\nanother new line\n",
    )

    # The breakpoint stays attached to "line three" itself, which has
    # now shifted down to line 5 -- not to whatever text now occupies
    # line 3.
    assert editor.breakpoint_lines == (5,)
    assert (
        "line three"
        in editor.document()
        .findBlockByNumber(
            4,
        )
        .text()
    )


def test_breakpointed_line_paints_a_marker_in_the_gutter(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=(
            "line one\n"
            "line two\n"
            "line three\n"
        ),
        theme=_build_theme(),
    )
    editor.resize(
        600,
        400,
    )
    editor.show()

    editor.go_to_line(
        2,
    )
    editor.toggle_breakpoint_at_cursor()

    image = (
        editor._line_number_area.grab().toImage()
    )
    block = editor.document().findBlockByNumber(
        1,
    )
    marker_rect = editor.blockBoundingGeometry(
        block,
    ).translated(
        editor.contentOffset(),
    )
    y = int(
        marker_rect.center().y(),
    )

    assert (
        image.pixelColor(
            _BREAKPOINT_MARKER_WIDTH // 2,
            y,
        )
        == editor._breakpoint_color
    )


def test_toggle_breakpoint_on_active_tab_toggles_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "should not have a breakpoint\n",
    )
    tabs.setCurrentIndex(
        1,
    )
    tabs.widget(1).setPlainText(
        "line one\n"
        "line two\n",
    )
    tabs.widget(1).go_to_line(
        2,
    )

    tabs.toggle_breakpoint_on_active_tab()

    assert tabs.widget(1).breakpoint_lines == (2,)
    assert tabs.widget(0).breakpoint_lines == ()


def test_toggle_breakpoint_on_active_tab_does_nothing_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.toggle_breakpoint_on_active_tab()


def test_all_breakpoints_aggregates_across_open_tabs(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "alpha one\n"
        "alpha two\n",
    )
    tabs.widget(0).go_to_line(
        2,
    )
    tabs.widget(0).toggle_breakpoint_at_cursor()
    tabs.widget(1).setPlainText(
        "beta one\n"
        "beta two\n",
    )
    tabs.widget(1).go_to_line(
        1,
    )
    tabs.widget(1).toggle_breakpoint_at_cursor()

    entries = tabs.all_breakpoints()

    assert {
        (entry.line, entry.text)
        for entry in entries
    } == {
        (2, "alpha two"),
        (1, "beta one"),
    }


def test_reveal_breakpoint_activates_the_tab_and_moves_the_cursor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.new_file()
    tabs.widget(1).setPlainText(
        "line one\n"
        "line two\n"
        "line three\n",
    )
    tabs.setCurrentIndex(
        0,
    )
    document_id = tabs.widget(1).document_id

    tabs.reveal_breakpoint(
        document_id,
        3,
    )

    assert tabs.currentIndex() == 1
    assert tabs.widget(1).textCursor().blockNumber() == 2


def test_format_document_trims_trailing_whitespace(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one   \n"
        "line two\n"
        "line three\t\t\n",
    )

    changed = editor.format_document()

    assert changed is True
    assert editor.toPlainText() == (
        "line one\n"
        "line two\n"
        "line three\n"
    )


def test_format_document_expands_tabs_when_insert_spaces_is_enabled(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            insert_spaces=True,
            tab_width=4,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "\tindented\n",
    )

    editor.format_document()

    assert editor.toPlainText() == (
        "    indented\n"
    )


def test_format_document_leaves_tabs_alone_when_insert_spaces_is_disabled(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            insert_spaces=False,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "\tindented   \n",
    )

    changed = editor.format_document()

    assert changed is True
    assert editor.toPlainText() == (
        "\tindented\n"
    )


def test_format_document_returns_false_when_nothing_changes(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "already clean\n"
        "no trailing space\n",
    )

    assert editor.format_document() is False


def test_format_document_is_undoable_as_one_step(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one   \n"
        "line two\t\n",
    )
    original_text = editor.toPlainText()

    editor.format_document()
    editor.undo()

    assert editor.toPlainText() == original_text


def test_format_active_tab_delegates_to_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line one   \n",
    )

    changed = tabs.format_active_tab()

    assert changed is True
    assert editor.toPlainText() == "line one\n"


def test_format_active_tab_is_false_with_no_tabs_open(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.format_active_tab() is False


_UNTERMINATED_LITERAL_SAMPLE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       PROCEDURE DIVISION.\n"
    "           DISPLAY 'unterminated literal here\n"
    "           STOP RUN.\n"
)


def test_quick_fix_at_finds_a_fix_for_an_unterminated_literal(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    editor.go_to_line(
        4,
        5,
    )
    point = editor.cursorRect().center()

    fix = editor.quick_fix_at(
        point,
    )

    assert fix is not None
    assert fix.insert_text == "'"
    assert fix.line == 4


def test_quick_fix_at_returns_none_without_a_diagnostic_on_the_line(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    editor.go_to_line(
        1,
        1,
    )
    point = editor.cursorRect().center()

    assert (
        editor.quick_fix_at(
            point,
        )
        is None
    )


def test_apply_quick_fix_inserts_text_and_resolves_the_diagnostic(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    editor.go_to_line(
        4,
        5,
    )
    fix = editor.quick_fix_at(
        editor.cursorRect().center(),
    )
    assert fix is not None

    editor.apply_quick_fix(
        fix,
    )

    assert (
        "unterminated literal here'"
        in editor.toPlainText()
    )
    assert editor.diagnostics == ()


def test_apply_quick_fix_is_undoable(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    original_text = editor.toPlainText()
    editor.go_to_line(
        4,
        5,
    )
    fix = editor.quick_fix_at(
        editor.cursorRect().center(),
    )
    assert fix is not None

    editor.apply_quick_fix(
        fix,
    )
    editor.undo()

    assert editor.toPlainText() == original_text


def test_build_context_menu_includes_a_quick_fix_action_on_a_diagnostic_line(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    editor.go_to_line(
        4,
        5,
    )
    point = editor.cursorRect().center()

    menu = editor.build_context_menu(
        point,
    )

    action_texts = [
        action.text()
        for action in menu.actions()
    ]
    assert any(
        "Insert missing closing" in text
        for text in action_texts
    )


def test_build_context_menu_has_no_quick_fix_action_without_a_diagnostic(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _UNTERMINATED_LITERAL_SAMPLE,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()
    editor.go_to_line(
        1,
        1,
    )
    point = editor.cursorRect().center()

    menu = editor.build_context_menu(
        point,
    )

    action_texts = [
        action.text()
        for action in menu.actions()
    ]
    assert not any(
        "Insert missing closing" in text
        for text in action_texts
    )


# --- Split editors -----------------------------------------------------


def test_toggle_split_wraps_the_tab_in_a_split_pane(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()

    tabs.toggle_split_on_active_tab()

    pane = tabs.widget(0)
    assert isinstance(pane, _SplitEditorPane)
    assert pane.is_split
    assert len(pane.editors()) == 2


def test_split_views_share_the_same_document(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()

    pane = tabs.widget(0)
    pane.primary_editor.setPlainText(
        "shared text",
    )

    assert (
        pane.secondary_editor.toPlainText()
        == "shared text"
    )


def test_split_view_has_no_highlighter_of_its_own(
    qapp,
    tmp_path: Path,
) -> None:
    """Highlighting for a split's second view comes from the primary
    view's highlighter running against their shared document -- a
    second highlighter attached to the same document would double up
    and fight the first one over the same character formats."""

    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )

    tabs.toggle_split_on_active_tab()

    pane = tabs.widget(0)
    assert pane.primary_editor._highlighter is not None
    assert pane.secondary_editor._highlighter is None


def test_toggle_split_again_closes_the_split(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()

    tabs.toggle_split_on_active_tab()

    editor = tabs.widget(0)
    assert isinstance(editor, SourceEditorWidget)
    assert not isinstance(editor, _SplitEditorPane)


def test_split_preserves_tab_title_and_tooltip(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = _build_tabs()
    tabs.open_path(
        file_path,
    )
    title_before = tabs.tabText(0)
    tooltip_before = tabs.tabToolTip(0)

    tabs.toggle_split_on_active_tab()

    assert tabs.tabText(0) == title_before
    assert tabs.tabToolTip(0) == tooltip_before


def test_toggle_split_on_active_tab_does_nothing_without_an_open_tab(
    qapp,
) -> None:
    tabs = _build_tabs()

    tabs.toggle_split_on_active_tab()

    assert tabs.count() == 0


def test_active_editor_widget_tracks_focus_between_split_views(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)

    pane.secondary_editor.setFocus()
    pane.secondary_editor.focused.emit()

    assert tabs._active_editor_widget() is pane.secondary_editor

    pane.primary_editor.setFocus()
    pane.primary_editor.focused.emit()

    assert tabs._active_editor_widget() is pane.primary_editor


def test_apply_theme_recolors_both_split_views(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)

    tabs.apply_theme(
        _build_theme(
            LIGHT_THEME_ID,
        )
    )

    assert (
        pane.primary_editor._current_line_color
        == pane.secondary_editor._current_line_color
    )


def test_apply_editor_settings_updates_both_split_views(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)

    tabs.apply_editor_settings(
        EditorSettings(
            font_family="Courier New",
            font_size=20,
        )
    )

    assert (
        pane.primary_editor.font().family()
        == "Courier New"
    )
    assert (
        pane.secondary_editor.font().family()
        == "Courier New"
    )


def test_edit_in_secondary_view_marks_the_document_modified(
    qapp,
) -> None:
    """A same-document edit from either view must reach the domain
    document model and refresh tab chrome, not just the primary view's
    own `textChanged` connection made at tab-creation time."""

    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
    )
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)

    pane.secondary_editor.setPlainText(
        "typed in the second view",
    )

    workspace_document = document_service.workspace.get_document(
        pane.primary_editor.document_id,
    )
    assert workspace_document.document.is_modified
    assert (
        workspace_document.document.text
        == "typed in the second view"
    )
    assert tabs.tabText(0).endswith("*")


def test_save_as_syncs_cobol_support_to_the_secondary_view(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)
    assert pane.secondary_editor.is_cobol_source

    with patch.object(
        QFileDialog,
        "getSaveFileName",
        return_value=(
            str(
                tmp_path / "plain.txt",
            ),
            "",
        ),
    ):
        tabs.save_active_document_as()

    assert not pane.primary_editor.is_cobol_source
    assert not pane.secondary_editor.is_cobol_source


# --- Multiple cursors ----------------------------------------------------


def _press_key(
    editor: SourceEditorWidget,
    key: Qt.Key,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> None:
    """Simulate a keypress directly against one editor widget."""

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        modifiers,
        text,
    )
    editor.keyPressEvent(event)


def test_add_cursor_below_adds_a_secondary_cursor(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)

    editor.add_cursor_below()

    assert editor.has_secondary_cursors
    assert (
        editor._secondary_cursors[0].blockNumber()
        == 1
    )
    assert (
        editor._secondary_cursors[0].positionInBlock()
        == 2
    )


def test_add_cursor_above_adds_a_secondary_cursor(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(2, 3)

    editor.add_cursor_above()

    assert (
        editor._secondary_cursors[0].blockNumber()
        == 0
    )


def test_add_cursor_below_clamps_to_a_shorter_line(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="line one\nx\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 9)

    editor.add_cursor_below()

    assert (
        editor._secondary_cursors[0].positionInBlock()
        == 1
    )


def test_add_cursor_below_does_nothing_past_the_last_line(
    qapp,
) -> None:
    editor = _build_editor_with_lines(2)
    editor.go_to_line(2, 1)

    editor.add_cursor_below()

    assert not editor.has_secondary_cursors


def test_typing_replicates_at_every_cursor(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="line0\nline1\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 6)
    editor.add_cursor_below()

    _press_key(
        editor,
        Qt.Key.Key_X,
        text="X",
    )

    assert (
        editor.toPlainText()
        == "line0X\nline1X\n"
    )


def test_typing_is_undoable_as_one_step(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="line0\nline1\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 6)
    editor.add_cursor_below()

    _press_key(
        editor,
        Qt.Key.Key_X,
        text="X",
    )
    editor.undo()

    assert editor.toPlainText() == "line0\nline1\n"


def test_backspace_replicates_at_every_cursor(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="line0\nline1\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 6)
    editor.add_cursor_below()

    _press_key(
        editor,
        Qt.Key.Key_Backspace,
    )

    assert (
        editor.toPlainText()
        == "line\nline\n"
    )


def test_escape_clears_secondary_cursors(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)
    editor.add_cursor_below()

    _press_key(
        editor,
        Qt.Key.Key_Escape,
    )

    assert not editor.has_secondary_cursors


def test_plain_click_clears_secondary_cursors(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)
    editor.add_cursor_below()

    click = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.mousePressEvent(click)

    assert not editor.has_secondary_cursors


def test_alt_click_adds_a_secondary_cursor(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 1)
    point = editor.cursorRect().center()
    position = QPointF(
        point,
    )

    click = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
        ),
    )
    editor.mousePressEvent(click)

    assert editor.has_secondary_cursors


def test_movement_key_moves_every_cursor(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)
    editor.add_cursor_below()

    _press_key(
        editor,
        Qt.Key.Key_Right,
    )

    assert (
        editor._secondary_cursors[0].positionInBlock()
        == 3
    )


def test_add_cursor_above_on_active_tab_delegates_to_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.go_to_line(1, 1)
    editor.setPlainText(
        "line0\nline1\n",
    )
    editor.go_to_line(2, 1)

    tabs.add_cursor_above_on_active_tab()

    assert editor.has_secondary_cursors


def test_add_cursor_below_on_active_tab_delegates_to_the_active_editor(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        "line0\nline1\n",
    )
    editor.go_to_line(1, 1)

    tabs.add_cursor_below_on_active_tab()

    assert editor.has_secondary_cursors


# --- Column (box) selection ------------------------------------------


_ALT_SHIFT = (
    Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.ShiftModifier
)


def test_alt_shift_down_starts_and_extends_a_column_selection(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)

    _press_key(
        editor,
        Qt.Key.Key_Down,
        _ALT_SHIFT,
    )

    assert editor._column_selection is not None
    assert editor._column_selection.anchor_line == 0
    assert editor._column_selection.active_line == 1


def test_typing_inserts_at_every_line_in_the_column_selection(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\ncccc\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 2)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_X,
        text="X",
    )

    assert (
        editor.toPlainText()
        == "aXaaa\nbXbbb\ncXccc\n"
    )


def test_consecutive_typing_does_not_reverse_order(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 2)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(editor, Qt.Key.Key_X, text="X")
    _press_key(editor, Qt.Key.Key_Y, text="Y")

    assert (
        editor.toPlainText()
        == "aXYaaa\nbXYbbb\n"
    )


def test_backspace_at_column_zero_does_not_merge_lines(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\ncccc\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 1)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Backspace,
    )

    assert editor.toPlainText() == "aaaa\nbbbb\ncccc\n"
    assert editor.document().blockCount() == 4


def test_delete_at_end_of_line_does_not_merge_lines(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\ncccc\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 5)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Delete,
    )

    assert editor.toPlainText() == "aaaa\nbbbb\ncccc\n"
    assert editor.document().blockCount() == 4


def test_backspace_within_a_line_deletes_one_character_per_line(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 3)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Backspace,
    )

    assert (
        editor.toPlainText()
        == "aaa\nbbb\n"
    )


def test_column_selection_skips_lines_shorter_than_the_range(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nx\ncccc\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 3)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Z,
        text="Z",
    )

    assert (
        editor.toPlainText()
        == "aaZaa\nx\nccZcc\n"
    )


def test_plain_arrow_exits_column_selection_mode(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Right,
    )

    assert editor._column_selection is None


def test_escape_clears_column_selection(
    qapp,
) -> None:
    editor = _build_editor_with_lines(3)
    editor.go_to_line(1, 3)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Escape,
    )

    assert editor._column_selection is None


def test_column_selection_with_a_range_replaces_selected_text(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text="aaaa\nbbbb\n",
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    editor.go_to_line(1, 1)
    _press_key(editor, Qt.Key.Key_Down, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Right, _ALT_SHIFT)
    _press_key(editor, Qt.Key.Key_Right, _ALT_SHIFT)

    _press_key(
        editor,
        Qt.Key.Key_Z,
        text="Z",
    )

    assert (
        editor.toPlainText()
        == "Zaa\nZbb\n"
    )


# --- Source format (Fixed vs. Free column convention) -----------------


_NOT_COLUMN_CONFORMING_SOURCE = (
    "IDENTIFICATION DIVISION.\n"
    "PROGRAM-ID. DEMO.\n"
    "PROCEDURE DIVISION.\n"
    "STOP RUN.\n"
)


def test_fixed_format_default_reports_spurious_column_diagnostics(
    qapp,
) -> None:
    """Documents the exact bug being fixed: Fixed format (the
    unconditional default before `apply_source_format` existed) treats
    columns 1-6 of every line as the sequence area and column 7 as the
    indicator column, so source that doesn't start its code at column 8
    gets its first several characters silently swallowed -- mangling
    `IDENTIFICATION` into `ICATION` here and raising a bogus "Expected
    IDENTIFICATION DIVISION" error despite the line being entirely
    correct COBOL."""

    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=_NOT_COLUMN_CONFORMING_SOURCE,
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()

    assert len(editor.diagnostics) > 0


def test_free_format_reports_no_spurious_column_diagnostics(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=_NOT_COLUMN_CONFORMING_SOURCE,
        theme=_build_theme(),
        source_format=CobolSourceFormat.FREE,
    )
    editor.resize(600, 400)
    editor.show()

    assert editor.diagnostics == ()


def test_free_format_highlights_the_first_word_on_a_line(
    qapp,
) -> None:
    """Fixed format's sequence-area stripping is also why `IDENTIFICATION`
    doesn't get colored while `DIVISION` does on the same line when the
    source isn't column-conforming -- Free format doesn't strip anything."""

    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=_NOT_COLUMN_CONFORMING_SOURCE,
        theme=_build_theme(),
        source_format=CobolSourceFormat.FREE,
    )
    editor.resize(600, 400)
    editor.show()

    highlighted = {
        token.text
        for tokens in editor._highlighter._tokens_by_line.values()
        for token in tokens
    }
    assert "IDENTIFICATION" in highlighted
    assert "DIVISION" in highlighted


def test_apply_source_format_updates_diagnostics_live(
    qapp,
) -> None:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=_NOT_COLUMN_CONFORMING_SOURCE,
        theme=_build_theme(),
    )
    editor.resize(600, 400)
    editor.show()
    assert len(editor.diagnostics) > 0

    editor.apply_source_format(
        CobolSourceFormat.FREE,
    )

    assert editor.diagnostics == ()


def test_split_secondary_view_inherits_the_primary_source_format(
    qapp,
) -> None:
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
        theme=_build_theme(),
        source_format=CobolSourceFormat.FREE,
    )
    tabs.new_file()
    tabs.toggle_split_on_active_tab()

    pane = tabs.widget(0)
    assert (
        pane.secondary_editor._source_format
        == CobolSourceFormat.FREE
    )


def test_editor_tabs_apply_source_format_updates_every_open_tab(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    editor = tabs.widget(0)
    editor.setPlainText(
        _NOT_COLUMN_CONFORMING_SOURCE,
    )
    assert len(editor.diagnostics) > 0

    tabs.apply_source_format(
        CobolSourceFormat.FREE,
    )

    assert editor.diagnostics == ()


def test_editor_tabs_apply_source_format_updates_both_split_views(
    qapp,
) -> None:
    tabs = _build_tabs()
    tabs.new_file()
    tabs.toggle_split_on_active_tab()
    pane = tabs.widget(0)

    tabs.apply_source_format(
        CobolSourceFormat.FREE,
    )

    assert (
        pane.primary_editor._source_format
        == CobolSourceFormat.FREE
    )
    assert (
        pane.secondary_editor._source_format
        == CobolSourceFormat.FREE
    )
