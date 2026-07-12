"""Unit tests for the tabbed source editor, against a real DocumentService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QMessageBox

from opencobol2.documents import DocumentService
from opencobol2.gui.editor import EditorTabsWidget
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
