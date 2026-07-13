"""Unit tests for the tabbed source editor, against a real DocumentService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent, QTextCursor, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QMessageBox

from opencobol2.documents import DocumentService
from opencobol2.gui.editor import EditorTabsWidget, SourceEditorWidget
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
            2,
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

    assert len(diagnostics) >= 1
    assert diagnostics[0].source_path == file_path
    assert "not terminated" in diagnostics[0].message


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
    # Column 8 of line 1 is inside a reserved word, not an identifier.
    editor.go_to_line(
        1,
        8,
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
    editor.go_to_line(
        1,
        8,
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
