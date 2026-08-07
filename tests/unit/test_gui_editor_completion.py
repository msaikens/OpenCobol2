"""Unit tests for the completion popup and snippet tab-stop wiring."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent, QTextCursor

from opencobol2.documents import DocumentService
from opencobol2.gui.editor import EditorTabsWidget, SourceEditorWidget
from opencobol2.language import CompletionItem, CompletionItemKind
from opencobol2.theming import create_builtin_theme_registry, DARK_THEME_ID


def _build_tabs() -> EditorTabsWidget:
    # `QWidget.isVisible()` reflects the whole ancestor chain, not just
    # a widget's own show()/hide() calls -- the completion popup is
    # parented deep inside this hierarchy, so its own isVisible() only
    # means anything once the tab strip itself is actually shown, the
    # same as it would be once docked into a real running MainWindow.
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
        theme=create_builtin_theme_registry().get(DARK_THEME_ID),
    )
    tabs.show()

    return tabs


def _open_cobol_source(
    tabs: EditorTabsWidget,
    tmp_path: Path,
    text: str,
) -> SourceEditorWidget:
    file_path = tmp_path / "demo.cbl"
    file_path.write_text(text)
    tabs.open_path(file_path)

    return tabs.widget(0)


def _move_cursor_to_end(
    editor: SourceEditorWidget,
) -> None:
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)


def _press_key(
    editor: SourceEditorWidget,
    key: Qt.Key,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> None:
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        modifiers,
        text,
    )
    editor.keyPressEvent(event)


def test_ctrl_space_shows_completion_popup_with_the_matching_keyword(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)

    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert editor._completion_popup.isVisible()
    item = editor._completion_popup.selected_item()
    assert item is not None
    assert item.label == "PROCEDURE"
    assert item.kind is CompletionItemKind.KEYWORD


def test_typing_an_identifier_character_schedules_a_debounced_refresh(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PRO",
    )
    _move_cursor_to_end(editor)

    _press_key(
        editor,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.NoModifier,
        "C",
    )

    assert editor._completion_debounce_timer.isActive()

    # Simulate the debounce elapsing without a real 150ms wait.
    editor._completion_debounce_timer.stop()
    editor._refresh_completions()

    assert editor._completion_popup.isVisible()


def test_backspace_also_schedules_a_debounced_refresh(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)

    _press_key(
        editor,
        Qt.Key.Key_Backspace,
        Qt.KeyboardModifier.NoModifier,
        "\x08",
    )

    assert editor._completion_debounce_timer.isActive()


def test_escape_closes_an_open_completion_popup(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)
    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert editor._completion_popup.isVisible()

    _press_key(
        editor,
        Qt.Key.Key_Escape,
    )

    assert not editor._completion_popup.isVisible()


def test_enter_accepts_the_selected_completion_and_replaces_the_prefix(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)
    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )

    _press_key(
        editor,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
        "\r",
    )

    assert not editor._completion_popup.isVisible()
    last_line = editor.toPlainText().splitlines()[-1]
    assert last_line.strip() == "PROCEDURE"


def test_down_arrow_moves_the_popup_selection(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n",
    )

    editor._completion_popup.set_items(
        (
            CompletionItem(
                label="AAA",
                kind=CompletionItemKind.KEYWORD,
                insert_text="AAA",
            ),
            CompletionItem(
                label="BBB",
                kind=CompletionItemKind.KEYWORD,
                insert_text="BBB",
            ),
        )
    )
    editor._completion_popup.show()
    assert editor._completion_popup.selected_item().label == "AAA"

    _press_key(
        editor,
        Qt.Key.Key_Down,
    )

    assert editor._completion_popup.selected_item().label == "BBB"

    _press_key(
        editor,
        Qt.Key.Key_Up,
    )

    assert editor._completion_popup.selected_item().label == "AAA"


def test_accepting_a_snippet_starts_a_tab_stop_session_and_tab_advances(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       eval",
    )
    _move_cursor_to_end(editor)
    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )

    # "EVALUATE" is both a real reserved word and this snippet's
    # trigger -- snippets are sorted ahead of plain keywords, so the
    # snippet candidate is the one selected by default.
    item = editor._completion_popup.selected_item()
    assert item.kind is CompletionItemKind.SNIPPET
    assert item.label == "evaluate"

    _press_key(
        editor,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
        "\r",
    )

    assert "EVALUATE" in editor.toPlainText()
    assert editor._active_snippet_stops is not None
    assert editor._active_snippet_index == 0
    assert editor.textCursor().selectedText() == "subject"

    _press_key(
        editor,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
        "\t",
    )

    assert editor._active_snippet_index == 1
    assert editor.textCursor().selectedText() == "value"


def test_escape_ends_an_active_snippet_session(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n",
    )
    _move_cursor_to_end(editor)

    editor.insert_snippet(
        "IF ${1:condition}\n    ${2}\nEND-IF",
    )
    assert editor._active_snippet_stops is not None

    _press_key(
        editor,
        Qt.Key.Key_Escape,
    )

    assert editor._active_snippet_stops is None


def test_tab_past_the_last_stop_ends_the_snippet_session(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n",
    )
    _move_cursor_to_end(editor)

    editor.insert_snippet(
        "IF ${1:condition}\n    ${2}\nEND-IF",
    )
    assert editor._active_snippet_index == 0

    _press_key(
        editor,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
        "\t",
    )
    assert editor._active_snippet_stops is not None
    assert editor._active_snippet_index == 1

    _press_key(
        editor,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
        "\t",
    )
    assert editor._active_snippet_stops is None


def test_mouse_click_closes_the_completion_popup(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)
    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert editor._completion_popup.isVisible()

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(2, 2),
        QPointF(2, 2),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.mousePressEvent(event)

    assert not editor._completion_popup.isVisible()


def test_focus_out_closes_the_completion_popup(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    editor = _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(editor)
    _press_key(
        editor,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert editor._completion_popup.isVisible()

    event = QFocusEvent(
        QEvent.Type.FocusOut,
        Qt.FocusReason.OtherFocusReason,
    )
    editor.focusOutEvent(event)

    assert not editor._completion_popup.isVisible()


def test_trigger_suggest_on_active_tab_delegates_to_the_active_editor(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = _build_tabs()
    _open_cobol_source(
        tabs,
        tmp_path,
        "       IDENTIFICATION DIVISION.\n       PROC",
    )
    _move_cursor_to_end(
        tabs.widget(0),
    )

    handled = tabs.trigger_suggest_on_active_tab()

    assert handled is True
    assert tabs.widget(0)._completion_popup.isVisible()


def test_trigger_suggest_on_active_tab_is_a_noop_with_no_tabs(
    qapp,
) -> None:
    tabs = _build_tabs()

    assert tabs.trigger_suggest_on_active_tab() is False
