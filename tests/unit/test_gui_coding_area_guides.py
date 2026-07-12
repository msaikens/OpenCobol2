"""Unit tests for the COBOL fixed-format coding-area guide renderer."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFontDatabase, QPainter
from PySide6.QtWidgets import QPlainTextEdit

from opencobol2.gui.coding_area_guides import CodingAreaGuides
from opencobol2.settings import CobolGuideSettings
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
)


class _GuidesTestEditor(QPlainTextEdit):
    """A minimal editor whose real paintEvent renders guides on top of text.

    `CodingAreaGuides.paint()` must run inside an actual Qt paint cycle to
    show up in a `.grab()` image -- calling it through a manually created
    `QPainter` outside of `paintEvent` gets discarded by the repaint that
    `.grab()` itself triggers.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.guides = CodingAreaGuides(
            self,
        )

    def paintEvent(
        self,
        event,
    ) -> None:
        super().paintEvent(
            event,
        )

        painter = QPainter(
            self.viewport(),
        )
        self.guides.paint(
            painter,
        )
        painter.end()


def _build_editor() -> _GuidesTestEditor:
    editor = _GuidesTestEditor()
    font = QFontDatabase.systemFont(
        QFontDatabase.SystemFont.FixedFont,
    )
    font.setPointSize(
        12,
    )
    editor.setFont(
        font,
    )
    editor.setPlainText(
        "\n".join(
            [
                " " * 100,
            ]
            * 5
        ),
    )
    editor.resize(
        900,
        200,
    )
    editor.show()
    editor.guides.apply_theme(
        create_builtin_theme_registry().get(
            DARK_THEME_ID,
        )
    )

    return editor


def test_default_guide_settings_show_every_area(
    qapp,
) -> None:
    editor = _build_editor()

    image = editor.viewport().grab().toImage()

    boundary_x = int(
        editor.guides._x_for_column(
            7,
        )
    )
    background_x = int(
        editor.guides._x_for_column(
            40,
        )
    )

    assert image.pixelColor(
        boundary_x,
        50,
    ) != image.pixelColor(
        background_x,
        50,
    )


def test_disabling_a_guide_removes_its_boundary_line(
    qapp,
) -> None:
    editor = _build_editor()
    editor.guides.apply_guide_settings(
        CobolGuideSettings(
            show_sequence_area=False,
            show_indicator_column=False,
            show_area_a=False,
            show_area_b_boundary=False,
            show_reference_area=False,
            shade_areas=False,
        )
    )

    image = editor.viewport().grab().toImage()

    boundary_x = int(
        editor.guides._x_for_column(
            7,
        )
    )
    background_x = int(
        editor.guides._x_for_column(
            40,
        )
    )

    assert image.pixelColor(
        boundary_x,
        50,
    ) == image.pixelColor(
        background_x,
        50,
    )


def test_shade_areas_shades_the_sequence_area_region(
    qapp,
) -> None:
    editor = _build_editor()
    editor.guides.apply_guide_settings(
        CobolGuideSettings(
            show_sequence_area=True,
            show_indicator_column=False,
            show_area_a=False,
            show_area_b_boundary=False,
            show_reference_area=False,
            shade_areas=True,
        )
    )

    image = editor.viewport().grab().toImage()

    sequence_area_x = int(
        editor.guides._x_for_column(
            3,
        )
    )
    unshaded_x = int(
        editor.guides._x_for_column(
            40,
        )
    )

    assert image.pixelColor(
        sequence_area_x,
        50,
    ) != image.pixelColor(
        unshaded_x,
        50,
    )


def test_x_for_column_scales_with_character_width(
    qapp,
) -> None:
    editor = _build_editor()

    char_width = editor.fontMetrics().horizontalAdvance(
        " ",
    )
    margin = editor.document().documentMargin()

    assert editor.guides._x_for_column(
        1,
    ) == pytest.approx(
        margin,
    )
    assert editor.guides._x_for_column(
        8,
    ) == pytest.approx(
        margin + 7 * char_width,
    )


def test_apply_guide_settings_rejects_wrong_type(
    qapp,
) -> None:
    editor = _build_editor()

    with pytest.raises(
        TypeError,
        match=(
            "Coding area guide settings must be "
            "CobolGuideSettings"
        ),
    ):
        editor.guides.apply_guide_settings(
            object(),  # type: ignore[arg-type]
        )


def test_apply_theme_rejects_wrong_type(
    qapp,
) -> None:
    editor = _build_editor()

    with pytest.raises(
        TypeError,
        match="Coding area guide theme must be Theme",
    ):
        editor.guides.apply_theme(
            object(),  # type: ignore[arg-type]
        )
