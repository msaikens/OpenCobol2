"""Unit tests for COBOL syntax highlighting, against the real lexer."""

from __future__ import annotations

from PySide6.QtGui import QTextCharFormat
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


def _underlined_substrings(
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
        ]: format_range.format.underlineColor().name()
        for format_range in block.layout().formats()
        if format_range.format.underlineStyle()
        != QTextCharFormat.UnderlineStyle.NoUnderline
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


def test_continuation_literal_is_left_uncolored_on_both_lines(
    qapp,
) -> None:
    """A string literal continued across two physical lines (fixed
    format, `-` in the indicator column) is a documented, deliberate
    gap: `_retokenize` skips any token whose span crosses a line
    boundary rather than highlighting it against the wrong single
    line. This was previously entirely untested -- confirm the
    skip actually happens, on both lines, rather than one of them
    picking up an incorrect partial color."""

    editor, _ = _build_editor_and_highlighter(
        "       01  X VALUE 'THIS IS A LONG STRING\n"
        "      -    'AGE THAT CONTINUES'.\n",
    )

    line_0_colors = _colored_substrings(
        editor,
        0,
    )
    line_1_colors = _colored_substrings(
        editor,
        1,
    )

    assert not any(
        "STRING" in substring
        for substring in line_0_colors
    )
    assert line_1_colors == {}


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


def test_editing_one_line_refreshes_a_different_untouched_line(
    qapp,
) -> None:
    """A continuation string literal spanning two lines is (correctly,
    deliberately) left uncolored on both, since it's a cross-line
    token. Terminating it early on line 0 turns line 1's own content
    into a brand new, self-contained, colorable literal -- even though
    line 1's *text* never changed. Qt only calls highlightBlock() for
    the block whose own text changed, so without a deferred full
    rehighlight after retokenizing, line 1 stays stale until it's
    separately edited."""

    from PySide6.QtGui import QTextCursor

    # Keep an explicit reference to the highlighter (unlike the `_`
    # discard other tests in this file use) -- the deferred
    # QTimer.singleShot() this fix schedules only fires on a later
    # event-loop tick, and needs the Python wrapper to still be alive
    # then.
    editor, highlighter = _build_editor_and_highlighter(
        "       01  X VALUE 'THIS IS A LONG STRING\n"
        "      -    'AGE THAT CONTINUES'.\n",
    )

    # Baseline: the (cross-line) literal itself isn't colored on
    # either line yet -- the documented skip -- though other tokens
    # on line 0 (01, VALUE) are colored as usual.
    assert not any(
        "STRING" in substring
        for substring in _colored_substrings(editor, 0)
    )
    assert _colored_substrings(editor, 1) == {}

    # Append a single closing quote to the end of line 0 ONLY --
    # line 1's text is untouched.
    cursor = QTextCursor(
        editor.document().findBlockByNumber(0),
    )
    cursor.movePosition(
        QTextCursor.MoveOperation.EndOfBlock,
    )
    cursor.insertText(
        "'",
    )

    qapp.processEvents()

    line_0_colors = _colored_substrings(editor, 0)
    line_1_colors = _colored_substrings(editor, 1)

    assert (
        "'THIS IS A LONG STRING'" in line_0_colors
    )
    assert (
        "'AGE THAT CONTINUES'" in line_1_colors
    )


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


def test_clean_source_has_no_diagnostic_underlines(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        '           DISPLAY "HELLO".\n'
        "           STOP RUN.\n",
    )

    for line_number in range(6):
        assert (
            _underlined_substrings(
                editor,
                line_number,
            )
            == {}
        )


def test_a_lex_diagnostic_is_underlined_in_red(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "       DISPLAY 'UNCLOSED",
    )

    underlines = _underlined_substrings(
        editor,
        0,
    )

    assert any(
        color == "#e03c3c"
        for color in underlines.values()
    )


def test_a_semantic_diagnostic_is_underlined(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 1 TO WS-MISSING\n"
        "           STOP RUN.\n",
    )

    underlines = _underlined_substrings(
        editor,
        4,
    )

    # The AST's MoveStatement only carries its target names as plain
    # strings (no per-name span), so the diagnostic points at the
    # statement's own start ("MOVE") rather than at "WS-MISSING" itself --
    # an inherent precision limit of today's AST, not a highlighter bug.
    assert "MOVE" in underlines


def test_editing_away_a_diagnostic_removes_its_underline(
    qapp,
) -> None:
    editor, _ = _build_editor_and_highlighter(
        "       DISPLAY 'UNCLOSED",
    )
    assert (
        _underlined_substrings(
            editor,
            0,
        )
        != {}
    )

    editor.setPlainText(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY 'CLOSED'.\n"
        "           STOP RUN.\n",
    )

    for line_number in range(5):
        assert (
            _underlined_substrings(
                editor,
                line_number,
            )
            == {}
        )
