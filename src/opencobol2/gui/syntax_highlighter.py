"""COBOL syntax highlighting for the editor, driven by the real lexer.

Tokenizes the *whole* document (there is no incremental/per-line lexer API
yet) and caches the result until the document's text actually changes, so a
single keystroke re-lexes the buffer once rather than once per visible line.
This is an honest first-cut trade-off: fine for typical COBOL source files,
but would need real incremental lexing to scale to very large documents.

Also underlines lex/parse/semantic diagnostics (`compute_source_diagnostics`)
in the same pass. A diagnostic only carries a single point position, not a
span, so the underline covers the run of non-whitespace characters starting
there -- an approximation of "the token that's wrong," not an exact range
from the language service.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QTimer
from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)

from opencobol2.compiler import CobolSourceFormat, DiagnosticSeverity
from opencobol2.language import (
    compute_source_diagnostics,
    LexDiagnostic,
    ParseDiagnostic,
    Token,
    TokenKind,
    tokenize_cobol_source,
)
from opencobol2.theming import Theme


_HIGHLIGHTED_TOKEN_KINDS = (
    TokenKind.RESERVED_WORD,
    TokenKind.ALPHANUMERIC_LITERAL,
    TokenKind.NUMERIC_LITERAL,
    TokenKind.COMMENT,
)

_DIAGNOSTIC_UNDERLINE_COLORS = {
    DiagnosticSeverity.ERROR: QColor(
        224,
        60,
        60,
    ),
    DiagnosticSeverity.WARNING: QColor(
        212,
        166,
        48,
    ),
    DiagnosticSeverity.NOTE: QColor(
        130,
        130,
        130,
    ),
}


class CobolSyntaxHighlighter(QSyntaxHighlighter):
    """Colors COBOL reserved words, literals, and comments in an editor.

    Also underlines lex/parse/semantic diagnostics found on the same
    tokenizing pass.

    :ivar _source_format: The column convention (fixed or free format)
        used the last time the document was tokenized.
    :ivar _tokens_by_line: Highlightable tokens from the last
        successful tokenize pass, keyed by 0-based line number.
    :ivar _diagnostics_by_line: Lex/parse/semantic diagnostics from the
        last successful tokenize-and-analyze pass, keyed by 0-based
        line number.
    :ivar _cached_text: The full document text the caches above were
        built from, or ``None`` before the first pass. Used to detect
        whether the document actually changed since the last
        `highlightBlock` call.
    :ivar _formats: The text format to apply for each highlighted
        :class:`TokenKind`, rebuilt whenever the theme changes.
    :ivar _rehighlight_timer: Single-shot, zero-interval timer used to
        defer a full document rehighlight until after the current
        `highlightBlock` call returns.
    """

    def __init__(
        self,
        document: QTextDocument,
        *,
        theme: Theme,
        source_format: CobolSourceFormat = (
            CobolSourceFormat.FIXED
        ),
    ) -> None:
        """Attach a highlighter to a document, colored from a theme.

        The rehighlight timer is parented to `self` so Qt destroys it
        (and cancels any pending timeout) if the highlighter itself is
        destroyed first. A bare ``QTimer.singleShot(0, self.rehighlight)``
        keeps no such link and can fire after `self`'s underlying C++
        object is already gone.

        :param document: The Qt text document to attach highlighting
            to.
        :param theme: The color theme to build the initial token
            formats from.
        :param source_format: Whether `document` holds fixed-format or
            free-format COBOL source. Defaults to
            :attr:`CobolSourceFormat.FIXED`.
        :returns: None. Initializes the token/diagnostic caches, builds
            the color formats from `theme`, and arms the deferred
            rehighlight timer.
        """

        super().__init__(
            document,
        )

        self._source_format = source_format
        self._tokens_by_line: dict[
            int,
            tuple[Token, ...],
        ] = {}
        self._diagnostics_by_line: dict[
            int,
            tuple[
                LexDiagnostic | ParseDiagnostic,
                ...,
            ],
        ] = {}
        self._cached_text: str | None = None
        self._formats: dict[
            TokenKind,
            QTextCharFormat,
        ] = {}

        self._rehighlight_timer = QTimer(
            self,
        )
        self._rehighlight_timer.setSingleShot(
            True,
        )
        self._rehighlight_timer.setInterval(
            0,
        )
        self._rehighlight_timer.timeout.connect(
            self.rehighlight,
        )

        self.apply_theme(
            theme,
        )

    def diagnostics(
        self,
    ) -> tuple[LexDiagnostic | ParseDiagnostic, ...]:
        """Return every lex/parse/semantic diagnostic found on the last pass.

        :returns: All diagnostics accumulated across every line of the
            document during the most recent `_retokenize` call, in no
            particular order.
        """

        return tuple(
            diagnostic
            for diagnostics in self._diagnostics_by_line.values()
            for diagnostic in diagnostics
        )

    def apply_theme(
        self,
        theme: Theme,
    ) -> None:
        """Recolor every highlighted token kind and rehighlight the document.

        Clears `_cached_text` before rehighlighting so the next
        `highlightBlock` call is forced to re-tokenize even though the
        document text itself hasn't changed -- only the colors did, and
        `highlightBlock` only re-tokenizes when the cached text is
        stale.

        :param theme: The color theme to rebuild the token formats
            from.
        :returns: None. Replaces `_formats` and triggers an immediate
            full rehighlight.
        """

        self._formats = {
            TokenKind.RESERVED_WORD: _build_format(
                theme.colors.syntax_keyword,
            ),
            TokenKind.ALPHANUMERIC_LITERAL: _build_format(
                theme.colors.syntax_string,
            ),
            TokenKind.NUMERIC_LITERAL: _build_format(
                theme.colors.syntax_number,
            ),
            TokenKind.COMMENT: _build_format(
                theme.colors.syntax_comment,
            ),
        }
        self._cached_text = None
        self.rehighlight()

    def apply_source_format(
        self,
        source_format: CobolSourceFormat,
    ) -> None:
        """Change the assumed column convention and rehighlight.

        Fixed enforces the traditional sequence-area/indicator-column/
        Area-A column positions; Free does not, treating every column as
        ordinary code. Retokenizing against the wrong assumption is
        exactly what mangles a line that doesn't conform to the one
        currently in effect (its first several characters silently
        swallowed as if they were the sequence area), so switching
        formats needs a real retokenize, not just a repaint.

        :param source_format: The new column convention to assume for
            the document.
        :returns: None. Discards the cached text so the next
            `highlightBlock` call retokenizes, then triggers an
            immediate full rehighlight.
        """

        self._source_format = source_format
        self._cached_text = None
        self.rehighlight()

    def highlightBlock(
        self,
        text: str,
    ) -> None:
        """Apply cached token formatting to one visible line block.

        Overrides :meth:`QSyntaxHighlighter.highlightBlock`; Qt invokes
        this once per text block that needs (re)painting. Re-tokenizes
        the whole document first if the cached text is stale, then
        looks up and applies the formats and diagnostic underlines that
        belong to the current block's line number.

        :param text: The plain text of the block currently being
            highlighted, as provided by Qt.
        :returns: None. Formats are applied to the current block via
            `setFormat`.
        """

        full_text = self.document().toPlainText()

        if full_text != self._cached_text:
            self._retokenize(
                full_text,
            )
            self._schedule_full_rehighlight()

        block_number = self.currentBlock().blockNumber()

        for token in self._tokens_by_line.get(
            block_number,
            (),
        ):
            format_ = self._formats.get(
                token.kind,
            )

            if format_ is None:
                continue

            self.setFormat(
                token.span.start.column - 1,
                len(
                    token.text,
                ),
                format_,
            )

        for diagnostic in self._diagnostics_by_line.get(
            block_number,
            (),
        ):
            start = max(
                diagnostic.position.column - 1,
                0,
            )

            if start >= len(
                text,
            ):
                continue

            word_match = re.match(
                r"\S+",
                text[start:],
            )
            length = (
                len(
                    word_match.group(),
                )
                if word_match is not None
                else 1
            )

            merged_format = QTextCharFormat(
                self.format(
                    start,
                ),
            )
            merged_format.setUnderlineStyle(
                QTextCharFormat.UnderlineStyle.SpellCheckUnderline,
            )
            merged_format.setUnderlineColor(
                _DIAGNOSTIC_UNDERLINE_COLORS.get(
                    diagnostic.severity,
                    _DIAGNOSTIC_UNDERLINE_COLORS[
                        DiagnosticSeverity.ERROR
                    ],
                ),
            )
            self.setFormat(
                start,
                length,
                merged_format,
            )

    def _schedule_full_rehighlight(
        self,
    ) -> None:
        """Queue a full rehighlight after retokenizing on this pass.

        Qt only calls `highlightBlock()` for the block(s) whose own
        text just changed -- but retokenizing the whole document can
        change what tokens an *untouched* block should have (e.g. a
        continuation string literal spanning two lines: editing line N
        can turn line N+1 from "mid-literal" into "plain code" without
        line N+1's own text changing at all). Without this, that
        other block keeps its stale formatting until it happens to be
        edited directly. Deferred via a queued call, not called
        synchronously, since `rehighlight()` re-invokes
        `highlightBlock()` for every block and would recurse into this
        same method while it's still on the stack.

        Calling `start()` on the timer is itself the re-entrancy
        guard: per `QTimer.isActive()` semantics, starting an
        already-running single-shot timer just resets its remaining
        time rather than scheduling a second firing, so a burst of
        edits arriving before the queued call fires still results in
        only one `rehighlight()` pass.

        :returns: None. (Re-)arms `_rehighlight_timer`.
        """

        self._rehighlight_timer.start()

    def _retokenize(
        self,
        full_text: str,
    ) -> None:
        """Re-lex/parse/analyze the document, indexing results by line number.

        Tokenizing errors are swallowed rather than propagated: a live
        editor must never crash from a highlighting pass over
        transient, mid-edit invalid source, so any exception simply
        clears the caches (skipping highlighting for this pass) rather
        than taking the whole editor down with it.

        A token whose span crosses source lines (a string literal
        continued across two lines) is skipped rather than
        highlighted, since it is not yet supported to highlight such a
        token correctly on a single line.

        :param full_text: The complete current document text to
            tokenize and analyze.
        :returns: None. Replaces `_cached_text`, `_tokens_by_line`, and
            `_diagnostics_by_line` with the results of this pass.
        """

        self._cached_text = full_text
        tokens_by_line: dict[
            int,
            list[Token],
        ] = {}

        try:
            result = tokenize_cobol_source(
                full_text,
                source_format=self._source_format,
            )
        except Exception:
            self._tokens_by_line = {}
            self._diagnostics_by_line = {}
            return

        for token in result.tokens:
            if token.kind not in _HIGHLIGHTED_TOKEN_KINDS:
                continue

            if token.span.start.line != token.span.end.line:
                continue

            line_number = token.span.start.line - 1
            tokens_by_line.setdefault(
                line_number,
                [],
            ).append(
                token,
            )

        self._tokens_by_line = {
            line_number: tuple(
                tokens,
            )
            for line_number, tokens in tokens_by_line.items()
        }

        diagnostics_by_line: dict[
            int,
            list[LexDiagnostic | ParseDiagnostic],
        ] = {}

        for diagnostic in compute_source_diagnostics(
            full_text,
            source_format=self._source_format,
            lex_result=result,
        ):
            line_number = diagnostic.position.line - 1
            diagnostics_by_line.setdefault(
                line_number,
                [],
            ).append(
                diagnostic,
            )

        self._diagnostics_by_line = {
            line_number: tuple(
                diagnostics,
            )
            for line_number, diagnostics in diagnostics_by_line.items()
        }


def _build_format(
    hex_color: str,
) -> QTextCharFormat:
    """Build a text format that only overrides the foreground color.

    :param hex_color: The foreground color to set, in a format
        accepted by :class:`QColor` (e.g. ``"#RRGGBB"``).
    :returns: A new :class:`QTextCharFormat` with only its foreground
        color set to `hex_color`.
    """

    text_format = QTextCharFormat()
    text_format.setForeground(
        QColor(
            hex_color,
        ),
    )

    return text_format
