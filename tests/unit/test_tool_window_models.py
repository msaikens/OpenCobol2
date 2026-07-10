"""Unit tests for IDE tool-window domain models."""

from __future__ import annotations

import pytest

from opencobol2.tool_windows import (
    ToolWindowAppearance,
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowGeometry,
    ToolWindowState,
    normalize_tool_window_accent_color,
)


def test_definition_normalizes_identity_and_accessibility_name() -> None:
    definition = ToolWindowDefinition(
        tool_window_id="  output  ",
        title="  Output  ",
        default_area=ToolWindowArea.BOTTOM,
        allowed_areas=(
            ToolWindowArea.BOTTOM,
        ),
    )

    assert definition.tool_window_id == "output"
    assert definition.title == "Output"
    assert definition.accessibility_name == "Output"


def test_definition_requires_default_area_to_be_allowed() -> None:
    with pytest.raises(
        ValueError,
        match="default area must be one of the allowed areas",
    ):
        ToolWindowDefinition(
            tool_window_id="output",
            title="Output",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
            ),
        )


def test_definition_requires_unique_allowed_areas() -> None:
    with pytest.raises(
        ValueError,
        match="allowed areas must be unique",
    ):
        ToolWindowDefinition(
            tool_window_id="output",
            title="Output",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.BOTTOM,
                ToolWindowArea.BOTTOM,
            ),
        )


def test_document_area_definition_must_be_pinned() -> None:
    with pytest.raises(
        ValueError,
        match="Document-area tool windows must be pinned",
    ):
        ToolWindowDefinition(
            tool_window_id="history",
            title="History",
            default_area=ToolWindowArea.DOCUMENT,
            allowed_areas=(
                ToolWindowArea.DOCUMENT,
            ),
            default_pinned=False,
        )


def test_accent_color_is_normalized() -> None:
    appearance = ToolWindowAppearance(
        accent_color="  #ab12ef  ",
    )

    assert appearance.accent_color == "#AB12EF"
    assert appearance.uses_default_accent is False


def test_default_appearance_uses_application_accent() -> None:
    appearance = ToolWindowAppearance()

    assert appearance.accent_color is None
    assert appearance.uses_default_accent is True


@pytest.mark.parametrize(
    "accent_color",
    [
        "red",
        "#FFF",
        "#GG0000",
        "112233",
    ],
)
def test_invalid_accent_color_is_rejected(
    accent_color: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="#RRGGBB",
    ):
        normalize_tool_window_accent_color(
            accent_color,
        )


def test_geometry_requires_positive_dimensions() -> None:
    with pytest.raises(
        ValueError,
        match="width must be greater than zero",
    ):
        ToolWindowGeometry(
            x=0,
            y=0,
            width=0,
            height=400,
        )


def test_active_tool_window_must_be_visible() -> None:
    with pytest.raises(
        ValueError,
        match="active tool window must be visible",
    ):
        ToolWindowState(
            tool_window_id="output",
            area=ToolWindowArea.BOTTOM,
            visible=False,
            active=True,
        )


def test_floating_tool_window_must_be_pinned() -> None:
    with pytest.raises(
        ValueError,
        match="floating tool window must be pinned",
    ):
        ToolWindowState(
            tool_window_id="output",
            area=ToolWindowArea.BOTTOM,
            floating=True,
            pinned=False,
        )


def test_unpinned_docked_window_is_auto_hide() -> None:
    state = ToolWindowState(
        tool_window_id="output",
        area=ToolWindowArea.BOTTOM,
        visible=True,
        pinned=False,
    )

    assert state.auto_hide is True