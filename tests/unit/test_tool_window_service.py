"""Unit tests for IDE tool-window shell state orchestration."""

from __future__ import annotations

import pytest

from opencobol2.services.tool_windows import (
    ToolWindowAccentNotSupportedError,
    ToolWindowAreaNotAllowedError,
    ToolWindowService,
)
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowGeometry,
    ToolWindowRegistry,
)


def _create_service(
    *definitions: ToolWindowDefinition,
) -> ToolWindowService:
    """Create a tool-window service."""

    registry = ToolWindowRegistry()

    for definition in definitions:
        registry.register(
            definition,
        )

    return ToolWindowService(
        registry=registry,
    )


def _create_definition(
    *,
    tool_window_id: str = "output",
    default_visible: bool = False,
    default_pinned: bool = True,
    supports_accent_color: bool = True,
) -> ToolWindowDefinition:
    """Create a representative tool-window definition."""

    return ToolWindowDefinition(
        tool_window_id=tool_window_id,
        title=tool_window_id,
        default_area=ToolWindowArea.BOTTOM,
        allowed_areas=(
            ToolWindowArea.LEFT,
            ToolWindowArea.RIGHT,
            ToolWindowArea.BOTTOM,
            ToolWindowArea.DOCUMENT,
        ),
        default_visible=default_visible,
        default_pinned=default_pinned,
        supports_accent_color=supports_accent_color,
    )


def test_service_materializes_default_state() -> None:
    service = _create_service(
        _create_definition(
            default_visible=True,
            default_pinned=False,
        ),
    )

    state = service.get_state(
        "output",
    )

    assert state.area is ToolWindowArea.BOTTOM
    assert state.visible is True
    assert state.pinned is False
    assert state.auto_hide is True


def test_show_and_hide_update_visibility() -> None:
    service = _create_service(
        _create_definition(),
    )

    shown = service.show(
        "output",
    )
    hidden = service.hide(
        "output",
    )

    assert shown.visible is True
    assert hidden.visible is False
    assert hidden.active is False


def test_activate_shows_target_and_deactivates_previous_window() -> None:
    service = _create_service(
        _create_definition(
            tool_window_id="output",
        ),
        _create_definition(
            tool_window_id="problems",
        ),
    )

    service.activate(
        "output",
    )
    problems = service.activate(
        "problems",
    )

    assert service.get_state(
        "output",
    ).active is False
    assert problems.visible is True
    assert problems.active is True


def test_unpinning_docked_window_enables_auto_hide() -> None:
    service = _create_service(
        _create_definition(),
    )

    state = service.set_pinned(
        "output",
        False,
    )

    assert state.pinned is False
    assert state.auto_hide is True


def test_floating_window_is_automatically_pinned() -> None:
    service = _create_service(
        _create_definition(
            default_pinned=False,
        ),
    )

    state = service.set_floating(
        "output",
        True,
    )

    assert state.floating is True
    assert state.pinned is True
    assert state.auto_hide is False


def test_floating_window_cannot_be_unpinned() -> None:
    service = _create_service(
        _create_definition(),
    )

    service.set_floating(
        "output",
        True,
    )

    with pytest.raises(
        ValueError,
        match="cannot use auto-hide",
    ):
        service.set_pinned(
            "output",
            False,
        )


def test_move_to_document_area_forces_pinned_state() -> None:
    service = _create_service(
        _create_definition(
            default_pinned=False,
        ),
    )

    state = service.move_to_area(
        "output",
        ToolWindowArea.DOCUMENT,
    )

    assert state.area is ToolWindowArea.DOCUMENT
    assert state.pinned is True


def test_document_area_window_cannot_be_made_floating() -> None:
    """DOCUMENT area means pinned like an editor tab; floating means
    detached into its own top-level window -- a tool window must not
    end up in both states at once."""

    service = _create_service(
        _create_definition(),
    )

    service.move_to_area(
        "output",
        ToolWindowArea.DOCUMENT,
    )

    with pytest.raises(
        ValueError,
        match="cannot be made floating",
    ):
        service.set_floating(
            "output",
            True,
        )


def test_floating_window_cannot_be_moved_to_document_area() -> None:
    service = _create_service(
        _create_definition(),
    )

    service.set_floating(
        "output",
        True,
    )

    with pytest.raises(
        ValueError,
        match="cannot be moved to the document area",
    ):
        service.move_to_area(
            "output",
            ToolWindowArea.DOCUMENT,
        )


def test_move_rejects_disallowed_area() -> None:
    definition = ToolWindowDefinition(
        tool_window_id="output",
        title="Output",
        default_area=ToolWindowArea.BOTTOM,
        allowed_areas=(
            ToolWindowArea.BOTTOM,
        ),
    )

    service = _create_service(
        definition,
    )

    with pytest.raises(
        ToolWindowAreaNotAllowedError,
        match="does not allow area",
    ):
        service.move_to_area(
            "output",
            ToolWindowArea.LEFT,
        )


def test_service_sets_and_resets_accent_color() -> None:
    service = _create_service(
        _create_definition(),
    )

    accented = service.set_accent_color(
        "output",
        "#12abef",
    )

    reset = service.reset_accent_color(
        "output",
    )

    assert accented.appearance.accent_color == "#12ABEF"
    assert reset.appearance.uses_default_accent is True


def test_service_rejects_accent_for_unsupported_window() -> None:
    service = _create_service(
        _create_definition(
            supports_accent_color=False,
        ),
    )

    with pytest.raises(
        ToolWindowAccentNotSupportedError,
        match="does not support a custom accent",
    ):
        service.set_accent_color(
            "output",
            "#112233",
        )


def test_service_persists_geometry_in_live_state() -> None:
    service = _create_service(
        _create_definition(),
    )

    geometry = ToolWindowGeometry(
        x=100,
        y=200,
        width=900,
        height=600,
    )

    state = service.set_geometry(
        "output",
        geometry,
    )

    assert state.geometry is geometry


def test_service_sets_tab_group() -> None:
    service = _create_service(
        _create_definition(),
    )

    state = service.set_tab_group(
        "output",
        "bottom-results",
    )

    assert state.tab_group_id == "bottom-results"


def test_listener_is_notified_of_every_state_change() -> None:
    service = _create_service(
        _create_definition(),
    )
    seen_states = []
    service.add_listener(
        seen_states.append,
    )

    service.show(
        "output",
    )
    service.hide(
        "output",
    )

    assert [
        state.visible
        for state in seen_states
    ] == [
        True,
        False,
    ]


def test_a_raising_listener_does_not_break_the_state_change_or_other_listeners() -> (
    None
):
    service = _create_service(
        _create_definition(),
    )
    seen_states = []

    def raising_listener(
        state,
    ) -> None:
        raise RuntimeError(
            "a broken listener",
        )

    service.add_listener(
        raising_listener,
    )
    service.add_listener(
        seen_states.append,
    )

    state = service.show(
        "output",
    )

    assert state.visible is True
    assert len(seen_states) == 1
    assert seen_states[0].visible is True