"""Unit tests for COBOL syntax highlighting, against the real lexer."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit

from opencobol2.gui.syntax_highlighter import CobolSyntaxHighlighter
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    LIGHT_THEME_ID,
)


def _build_editor_and_highlighter(
    text: str,
    theme_id: str = DARK_THEME_ID,
):
    theme = create_builtin_theme_registry().get(
        theme_id,
    )
    editor = QPlainTextEdit()
    editor.setPlainText(
        text,
    )
    highlighter = CobolSyntaxHighlighter(
        editor.document(),
        theme=theme,
    )

    return editor, highlighter


def _colored_substrings(
    editor: QPlainTextEdit,
    line_number: int,
) -> dict[str, str]:
    block = editor.document().findBlockByNumber(
        line_number,
    )
    text = block.text()

    return {
        text[
            format_range.start:format_range.start
            + format_range.length
        ]: format_range.format.foreground()
        .color()
        .name()
        for format_range in block.layout().formats()
    }


def test_reserved_words_get_the_keyword_color(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "       IDENTIFICATION DIVISION.",
    )

    colors = _colored_substrings(
        editor,
        0,
    )

    assert colors["IDENTIFICATION"] == "#569cd6"
    assert colors["DIVISION"] == "#569cd6"


def test_string_literals_get_the_string_color(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        '           DISPLAY "HELLO".',
    )

    colors = _colored_substrings(
        editor,
        0,
    )

    assert colors['"HELLO"'] == "#ce9178"


def test_numeric_literals_get_the_number_color(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "           MOVE 42 TO X.",
    )

    colors = _colored_substrings(
        editor,
        0,
    )

    assert colors["42"] == "#b5cea8"


def test_comments_get_the_comment_color(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "      * a full-line comment",
    )

    colors = _colored_substrings(
        editor,
        0,
    )

    assert (
        colors[" a full-line comment"]
        == "#6a9955"
    )


def test_non_reserved_identifiers_are_not_recolored(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "           MOVE X TO Y.",
    )

    colors = _colored_substrings(
        editor,
        0,
    )

    assert "X" not in colors
    assert "Y" not in colors


def test_apply_theme_recolors_existing_tokens(
    qapp,
) -> None:
    editor, highlighter = (
        _build_editor_and_highlighter(
            "           DISPLAY X.",
        )
    )
    dark_colors = _colored_substrings(
        editor,
        0,
    )
    assert dark_colors["DISPLAY"] == "#569cd6"

    light_theme = create_builtin_theme_registry().get(
        LIGHT_THEME_ID,
    )
    highlighter.apply_theme(
        light_theme,
    )

    light_colors = _colored_substrings(
        editor,
        0,
    )
    assert light_colors["DISPLAY"] == "#0000ff"


def test_editing_text_retokenizes_and_highlights_new_tokens(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "           DISPLAY X.",
    )

    editor.setPlainText(
        "           DISPLAY X.\n"
        "           MOVE 5 TO Y.",
    )

    colors = _colored_substrings(
        editor,
        1,
    )

    assert colors["MOVE"] == "#569cd6"
    assert colors["5"] == "#b5cea8"


def test_malformed_source_does_not_crash(
    qapp,
) -> None:
    editor, highlighter = (
        _build_editor_and_highlighter(
            '           DISPLAY "unterminated',
        )
    )

    # Constructing and rendering against unterminated/invalid source must
    # not raise -- if it did, the test itself would fail with an error.
    editor.setPlainText(
        '           DISPLAY "still unterminated',
    )
    assert highlighter is not None
