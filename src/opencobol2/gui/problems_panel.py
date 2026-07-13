"""A table view of compiler diagnostics and live editor diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from opencobol2.compiler import CompilerDiagnostic


_COLUMN_HEADERS = (
    "Severity",
    "File",
    "Line",
    "Column",
    "Message",
)


class ProblemsWidget(QTableWidget):
    """Shows build diagnostics alongside the active editor's live ones.

    The two sources are tracked separately so neither wipes out the
    other: running a build doesn't erase what the active editor is
    currently flagging, and switching/editing tabs doesn't erase the
    last build's results. "Live" is scoped to the active editor tab
    only, not every open tab or the whole project -- the same scope
    Outline uses.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty, read-only diagnostics table."""

        super().__init__(
            0,
            len(
                _COLUMN_HEADERS,
            ),
            parent,
        )

        self.setHorizontalHeaderLabels(
            _COLUMN_HEADERS,
        )
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.verticalHeader().setVisible(
            False,
        )

        self._build_diagnostics: tuple[
            CompilerDiagnostic,
            ...,
        ] = ()
        self._live_diagnostics: tuple[
            CompilerDiagnostic,
            ...,
        ] = ()

    def set_diagnostics(
        self,
        diagnostics: Sequence[CompilerDiagnostic],
    ) -> None:
        """Replace the build diagnostics shown (from the most recent build)."""

        self._build_diagnostics = tuple(
            diagnostics,
        )
        self._render_rows()

    def clear_diagnostics(
        self,
    ) -> None:
        """Remove every build diagnostic from the table."""

        self._build_diagnostics = ()
        self._render_rows()

    def set_live_diagnostics(
        self,
        diagnostics: Sequence[CompilerDiagnostic],
    ) -> None:
        """Replace the active editor tab's live diagnostics."""

        self._live_diagnostics = tuple(
            diagnostics,
        )
        self._render_rows()

    def _render_rows(
        self,
    ) -> None:
        all_diagnostics = (
            self._build_diagnostics
            + self._live_diagnostics
        )
        self.setRowCount(
            len(
                all_diagnostics,
            ),
        )

        for row, diagnostic in enumerate(
            all_diagnostics,
        ):
            self.setItem(
                row,
                0,
                QTableWidgetItem(
                    diagnostic.severity.value.upper(),
                ),
            )
            self.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(
                        diagnostic.source_path,
                    )
                    if diagnostic.source_path is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(
                        diagnostic.line,
                    )
                    if diagnostic.line is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                3,
                QTableWidgetItem(
                    str(
                        diagnostic.column,
                    )
                    if diagnostic.column is not None
                    else "",
                ),
            )
            self.setItem(
                row,
                4,
                QTableWidgetItem(
                    diagnostic.message,
                ),
            )
