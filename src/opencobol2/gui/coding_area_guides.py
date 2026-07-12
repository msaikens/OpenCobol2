"""Paints COBOL fixed-format column guides over a source editor.

The six `CobolGuideSettings` toggles existed as real, persisted settings
(editable in the Settings dialog's COBOL tab) since before this module, but
had no visual consumer anywhere. Interpretation used here, since none of
the toggles carry documented rendering semantics of their own:

* `show_sequence_area` / `show_indicator_column` / `show_reference_area`
  each shade their own narrow column region (when `shade_areas` is on) and
  draw a boundary line at that region's trailing edge.
* `show_area_a` only shades Area A's region (columns 8-11); it has no
  boundary line of its own.
* `show_area_b_boundary` draws the one boundary line COBOL fixed-format
  code depends on most: the start of Area B (column 12), independently of
  whether Area A's shading is enabled.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter

from opencobol2.language import (
    FIXED_FORMAT_AREA_A_END_COLUMN,
    FIXED_FORMAT_CONTENT_START_COLUMN,
    FIXED_FORMAT_INDICATOR_COLUMN,
    FIXED_FORMAT_REFERENCE_AREA_START_COLUMN,
    FIXED_FORMAT_SEQUENCE_AREA_WIDTH,
)
from opencobol2.settings import CobolGuideSettings
from opencobol2.theming import Theme


class CodingAreaGuides:
    """Paints column rulers/shading for one editor's fixed-format guides."""

    def __init__(
        self,
        editor,
    ) -> None:
        """Attach a guide renderer to an editor, using its default settings."""

        self._editor = editor
        self._guide_settings = CobolGuideSettings()
        self._line_color = QColor(
            "#808080",
        )

        self._apply_colors()

    def apply_guide_settings(
        self,
        guide_settings: CobolGuideSettings,
    ) -> None:
        """Change which guides are shown, and repaint."""

        if not isinstance(
            guide_settings,
            CobolGuideSettings,
        ):
            raise TypeError(
                "Coding area guide settings must be "
                "CobolGuideSettings."
            )

        self._guide_settings = guide_settings
        self._editor.viewport().update()

    def apply_theme(
        self,
        theme: Theme,
    ) -> None:
        """Recolor the guides from a theme, and repaint."""

        if not isinstance(
            theme,
            Theme,
        ):
            raise TypeError(
                "Coding area guide theme must be Theme."
            )

        self._line_color = QColor(
            theme.colors.line_number_foreground,
        )
        self._apply_colors()
        self._editor.viewport().update()

    def paint(
        self,
        painter: QPainter,
    ) -> None:
        """Paint every enabled guide over the editor's current viewport."""

        settings = self._guide_settings
        viewport = self._editor.viewport()
        height = viewport.height()
        width = viewport.width()

        if settings.show_sequence_area:
            self._draw_region(
                painter,
                1,
                FIXED_FORMAT_SEQUENCE_AREA_WIDTH + 1,
                height,
                draw_boundary=True,
            )

        if settings.show_indicator_column:
            self._draw_region(
                painter,
                FIXED_FORMAT_INDICATOR_COLUMN,
                FIXED_FORMAT_CONTENT_START_COLUMN,
                height,
                draw_boundary=True,
            )

        if settings.show_area_a:
            self._draw_region(
                painter,
                FIXED_FORMAT_CONTENT_START_COLUMN,
                FIXED_FORMAT_AREA_A_END_COLUMN + 1,
                height,
                draw_boundary=False,
            )

        if settings.show_area_b_boundary:
            self._draw_boundary_line(
                painter,
                FIXED_FORMAT_AREA_A_END_COLUMN + 1,
                height,
            )

        if settings.show_reference_area:
            self._draw_region(
                painter,
                FIXED_FORMAT_REFERENCE_AREA_START_COLUMN,
                None,
                height,
                draw_boundary=False,
                end_x=width,
            )
            # The reference area is the last region, so its meaningful
            # boundary is at its own start (marking the end of content)
            # rather than at the viewport's far edge.
            self._draw_boundary_line(
                painter,
                FIXED_FORMAT_REFERENCE_AREA_START_COLUMN,
                height,
            )

    def _draw_region(
        self,
        painter: QPainter,
        start_column: int,
        end_column: int | None,
        height: int,
        *,
        draw_boundary: bool,
        end_x: float | None = None,
    ) -> None:
        start_x = self._x_for_column(
            start_column,
        )
        resolved_end_x = (
            end_x
            if end_column is None
            else self._x_for_column(
                end_column,
            )
        )

        if self._guide_settings.shade_areas and (
            resolved_end_x > start_x
        ):
            painter.fillRect(
                QRectF(
                    start_x,
                    0,
                    resolved_end_x - start_x,
                    height,
                ),
                self._shade_color,
            )

        if draw_boundary:
            self._draw_boundary_line_at(
                painter,
                resolved_end_x,
                height,
            )

    def _draw_boundary_line(
        self,
        painter: QPainter,
        column: int,
        height: int,
    ) -> None:
        self._draw_boundary_line_at(
            painter,
            self._x_for_column(
                column,
            ),
            height,
        )

    def _draw_boundary_line_at(
        self,
        painter: QPainter,
        x: float,
        height: int,
    ) -> None:
        painter.setPen(
            self._line_pen_color,
        )
        painter.drawLine(
            QPointF(
                x,
                0,
            ),
            QPointF(
                x,
                height,
            ),
        )

    def _x_for_column(
        self,
        column_number: int,
    ) -> float:
        """Return the pixel x-offset where a 1-based column starts."""

        char_width = (
            self._editor.fontMetrics().horizontalAdvance(
                " ",
            )
        )
        margin = self._editor.document().documentMargin()

        return margin + (
            column_number - 1
        ) * char_width

    def _apply_colors(
        self,
    ) -> None:
        line_pen_color = QColor(
            self._line_color,
        )
        line_pen_color.setAlpha(
            140,
        )
        self._line_pen_color = line_pen_color

        shade_color = QColor(
            self._line_color,
        )
        shade_color.setAlpha(
            24,
        )
        self._shade_color = shade_color
