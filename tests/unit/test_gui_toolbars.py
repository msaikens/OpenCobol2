"""Unit tests for the command-contribution toolbar renderer."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QToolBar

from opencobol2.commands import (
    Command,
    CommandContribution,
    CommandContributionRegistry,
    CommandRegistry,
    CommandState,
    CommandSurfaceKind,
    DynamicMenuContribution,
)
from opencobol2.gui.toolbars import build_toolbar
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import CommandService


def _build_service() -> CommandContributionService:
    command_registry = CommandRegistry()
    command_registry.register(
        Command(
            command_id="test.build",
            title="Build",
            handler=lambda context: "build",
            description="Build the project.",
        )
    )
    command_registry.register(
        Command(
            command_id="test.stop",
            title="Stop",
            handler=lambda context: "stop",
            state_provider=(
                lambda context: CommandState(
                    enabled=False,
                )
            ),
        )
    )

    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        CommandContribution(
            contribution_id="toolbar.build",
            command_id="test.build",
            surface_kind=CommandSurfaceKind.TOOLBAR,
            surface_id="main",
            order=10,
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id="toolbar.stop",
            command_id="test.stop",
            surface_kind=CommandSurfaceKind.TOOLBAR,
            surface_id="main",
            order=20,
            separator_before=True,
        )
    )

    return CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )


def test_build_toolbar_creates_actions(
    qapp,
) -> None:
    service = _build_service()
    toolbar = QToolBar()

    build_toolbar(
        toolbar,
        "main",
        service,
    )

    titles = [
        action.text()
        for action in toolbar.actions()
        if not action.isSeparator()
    ]
    assert titles == [
        "Build",
        "Stop",
    ]

    build_action = next(
        action
        for action in toolbar.actions()
        if action.text() == "Build"
    )
    assert (
        build_action.toolTip()
        == "Build the project."
    )

    stop_action = next(
        action
        for action in toolbar.actions()
        if action.text() == "Stop"
    )
    assert stop_action.isEnabled() is False


def test_build_toolbar_adds_separator(
    qapp,
) -> None:
    service = _build_service()
    toolbar = QToolBar()

    build_toolbar(
        toolbar,
        "main",
        service,
    )

    assert any(
        action.isSeparator()
        for action in toolbar.actions()
    )


def test_build_toolbar_rejects_submenu_contribution(
    qapp,
) -> None:
    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        DynamicMenuContribution(
            contribution_id="toolbar.dynamic",
            title="Dynamic",
            surface_kind=CommandSurfaceKind.TOOLBAR,
            surface_id="main",
            provider=lambda context: (),
        )
    )
    service = CommandContributionService(
        command_service=CommandService(
            registry=CommandRegistry(),
        ),
        contribution_registry=contribution_registry,
    )
    toolbar = QToolBar()

    with pytest.raises(
        TypeError,
        match=(
            "Toolbar surfaces only support direct "
            "command contributions"
        ),
    ):
        build_toolbar(
            toolbar,
            "main",
            service,
        )


def test_build_toolbar_is_idempotent_on_rebuild(
    qapp,
) -> None:
    service = _build_service()
    toolbar = QToolBar()

    build_toolbar(
        toolbar,
        "main",
        service,
    )
    build_toolbar(
        toolbar,
        "main",
        service,
    )

    titles = [
        action.text()
        for action in toolbar.actions()
        if not action.isSeparator()
    ]
    assert titles == [
        "Build",
        "Stop",
    ]
