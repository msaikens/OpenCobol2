"""Unit tests for the tabbed source editor, against a real DocumentService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
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
