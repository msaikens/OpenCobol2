"""Unit tests for code folding in the source editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint

from opencobol2.documents import DocumentService
from opencobol2.gui.editor import EditorTabsWidget, SourceEditorWidget
from opencobol2.settings import EditorSettings
from opencobol2.theming import create_builtin_theme_registry, DARK_THEME_ID


_SAMPLE_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF 1 > 0
               DISPLAY "POSITIVE"
           END-IF
           STOP RUN.
       CLEANUP-PARA.
           DISPLAY "DONE".
"""


def _build_theme():
    return create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )


def _build_folding_editor(
    text: str = _SAMPLE_PROGRAM,
    *,
    code_folding: bool = True,
    path=None,
) -> SourceEditorWidget:
    from uuid import uuid4

    editor = SourceEditorWidget(
        document_id=uuid4(),
        initial_text=text,
        theme=_build_theme(),
        editor_settings=EditorSettings(
            code_folding=code_folding,
        ),
        path=path,
    )
    editor.resize(
        600,
        400,
    )
    editor.show()

    return editor


def _visible_lines(
    editor: SourceEditorWidget,
) -> list[int]:
    document = editor.document()

    return [
        line_number + 1
        for line_number in range(
            document.blockCount(),
        )
        if document.findBlockByNumber(
            line_number,
        ).isVisible()
    ]


def test_fold_ranges_computed_on_construction(
    qapp,
) -> None:
    editor = _build_folding_editor()

    starts = {
        fold_range.start_line
        for fold_range in editor._fold_ranges
    }

    assert starts == {
        1,
        3,
        4,
        5,
        9,
    }


def test_folding_disabled_computes_no_ranges(
    qapp,
) -> None:
    editor = _build_folding_editor(
        code_folding=False,
    )

    assert editor._fold_ranges == ()
    assert editor._folding_enabled is False


def test_non_cobol_file_never_enables_folding(
    qapp,
) -> None:
    editor = _build_folding_editor(
        code_folding=True,
        path=Path(
            "notes.txt",
        ),
    )

    assert editor._folding_enabled is False
    assert editor._fold_ranges == ()


def test_toggle_fold_hides_and_restores_lines(
    qapp,
) -> None:
    editor = _build_folding_editor()

    editor.toggle_fold(
        4,
    )

    assert 4 in editor._collapsed_start_lines
    assert _visible_lines(
        editor,
    ) == [
        1,
        2,
        3,
        4,
        9,
        10,
        11,
    ]

    editor.toggle_fold(
        4,
    )

    assert editor._collapsed_start_lines == set()
    assert _visible_lines(
        editor,
    ) == list(
        range(
            1,
            12,
        )
    )


def test_toggle_fold_on_non_foldable_line_is_a_no_op(
    qapp,
) -> None:
    editor = _build_folding_editor()

    editor.toggle_fold(
        2,
    )

    assert editor._collapsed_start_lines == set()


def test_expanding_a_parent_preserves_a_nested_collapsed_fold(
    qapp,
) -> None:
    editor = _build_folding_editor()

    editor.toggle_fold(
        5,
    )  # collapse the IF statement (nested inside MAIN-PARA)
    editor.toggle_fold(
        4,
    )  # collapse MAIN-PARA (hides the already-collapsed IF too)
    editor.toggle_fold(
        4,
    )  # expand MAIN-PARA again

    assert editor._collapsed_start_lines == {
        5,
    }
    # Line 6 (inside the IF) must stay hidden; the IF is still collapsed.
    assert 6 not in _visible_lines(
        editor,
    )
    assert 4 in _visible_lines(
        editor,
    )
    assert 5 in _visible_lines(
        editor,
    )


def test_disabling_folding_expands_everything(
    qapp,
) -> None:
    editor = _build_folding_editor()
    editor.toggle_fold(
        4,
    )
    assert editor._collapsed_start_lines == {
        4,
    }

    editor.apply_editor_settings(
        EditorSettings(
            code_folding=False,
        )
    )

    assert editor._folding_enabled is False
    assert editor._collapsed_start_lines == set()
    assert _visible_lines(
        editor,
    ) == list(
        range(
            1,
            12,
        )
    )


def test_gutter_width_grows_when_folding_enabled(
    qapp,
) -> None:
    folding_editor = _build_folding_editor(
        code_folding=True,
    )
    plain_editor = _build_folding_editor(
        code_folding=False,
    )

    assert (
        folding_editor.line_number_area_width()
        > plain_editor.line_number_area_width()
    )


def test_gutter_click_toggles_the_fold_under_it(
    qapp,
) -> None:
    editor = _build_folding_editor()

    block = editor.document().findBlockByNumber(
        3,
    )  # 0-based -> line 4, MAIN-PARA
    rect = editor.blockBoundingGeometry(
        block,
    ).translated(
        editor.contentOffset(),
    )
    midpoint_y = int(
        (rect.top() + rect.bottom()) / 2,
    )

    editor.handle_line_number_area_click(
        QPoint(
            5,
            midpoint_y,
        )
    )

    assert 4 in editor._collapsed_start_lines


def test_in_place_edit_with_no_line_count_change_refreshes_fold_ranges(
    qapp,
) -> None:
    """blockCountChanged alone must not be the only trigger for
    recomputing fold ranges -- an edit that replaces a fold-start
    line's text with something no longer foldable, keeping the same
    number of lines, must still drop that stale fold range."""

    editor = _build_folding_editor()

    starts_before = {
        fold_range.start_line
        for fold_range in editor._fold_ranges
    }
    # fold_range.start_line is 1-based; 1-based line 5 is "IF 1 > 0"
    # (0-based document block 4).
    assert 5 in starts_before

    # Replace that line's text in place with a plain DISPLAY statement
    # -- same physical line, same line count, no longer an IF at all.
    block = editor.document().findBlockByNumber(
        4,
    )
    cursor = editor.textCursor()
    cursor.setPosition(
        block.position(),
    )
    cursor.movePosition(
        cursor.MoveOperation.EndOfBlock,
        cursor.MoveMode.KeepAnchor,
    )
    cursor.insertText(
        "           DISPLAY 1",
    )

    # Fold-range recompute is debounced (see
    # `_FOLD_RANGE_DEBOUNCE_MILLISECONDS`) -- simulate it elapsing
    # without a real wait, the same way the completion debounce tests
    # already do.
    editor._fold_range_debounce_timer.stop()
    editor._update_fold_ranges()

    starts_after = {
        fold_range.start_line
        for fold_range in editor._fold_ranges
    }
    assert 5 not in starts_after


def test_editing_that_shifts_fold_lines_expands_everything_safely(
    qapp,
) -> None:
    editor = _build_folding_editor()
    editor.toggle_fold(
        4,
    )
    assert editor._collapsed_start_lines == {
        4,
    }

    # Insert a new paragraph before MAIN-PARA, shifting every subsequent
    # line number -- the previously-collapsed start line (4) is no longer
    # a valid fold start, so the safety net must expand everything.
    cursor = editor.textCursor()
    cursor.movePosition(
        cursor.MoveOperation.Start,
    )
    editor.setTextCursor(
        cursor,
    )
    editor.insertPlainText(
        "       NEW-PARA.\n"
        '           DISPLAY "NEW".\n',
    )

    # Fold-range recompute is debounced (see
    # `_FOLD_RANGE_DEBOUNCE_MILLISECONDS`) -- simulate it elapsing
    # without a real wait, the same way the completion debounce tests
    # already do.
    editor._fold_range_debounce_timer.stop()
    editor._update_fold_ranges()

    assert editor._collapsed_start_lines == set()
    assert _visible_lines(
        editor,
    ) == list(
        range(
            1,
            editor.document().blockCount()
            + 1,
        )
    )


def test_editor_tabs_thread_code_folding_setting(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
        theme=_build_theme(),
        editor_settings=EditorSettings(
            code_folding=True,
        ),
    )
    tabs.new_file()
    editor = tabs.widget(
        0,
    )
    editor.setPlainText(
        _SAMPLE_PROGRAM,
    )

    assert editor._folding_enabled is True

    tabs.apply_editor_settings(
        EditorSettings(
            code_folding=False,
        )
    )

    assert editor._folding_enabled is False
