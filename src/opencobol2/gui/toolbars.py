"""Renders command-contribution toolbar surfaces as live Qt toolbars.

Only direct command contributions are supported on toolbar surfaces today —
no built-in toolbar contributions register submenus or dynamic menus, so
those contribution kinds are rejected here rather than silently ignored.
"""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar

from opencobol2.commands import (
    CommandSurfaceKind,
    ResolvedCommandContribution,
)
from opencobol2.services.command_contributions import (
    CommandContributionService,
)


def build_toolbar(
    toolbar: QToolBar,
    surface_id: str,
    contribution_service: CommandContributionService,
) -> None:
    """Clear and repopulate one toolbar from current contribution state."""

    toolbar.clear()

    for resolved in contribution_service.resolve_surface(
        CommandSurfaceKind.TOOLBAR,
        surface_id,
        # A hidden contribution's own action must not render, but its
        # separator_before/after still marks a real boundary between
        # its visible neighbors -- see the matching comment in
        # gui/command_menus.py for the full rationale.
        include_hidden=True,
    ):
        if not isinstance(
            resolved,
            ResolvedCommandContribution,
        ):
            raise TypeError(
                "Toolbar surfaces only support direct command "
                "contributions, not "
                f"{type(resolved).__name__}."
            )

        if resolved.contribution.separator_before:
            toolbar.addSeparator()

        if resolved.state.visible:
            toolbar.addAction(
                _create_toolbar_action(
                    toolbar,
                    resolved,
                    contribution_service,
                )
            )

        if resolved.contribution.separator_after:
            toolbar.addSeparator()


def _create_toolbar_action(
    toolbar: QToolBar,
    resolved: ResolvedCommandContribution,
    contribution_service: CommandContributionService,
) -> QAction:
    """Create a toolbar action for one resolved command contribution."""

    action = QAction(
        resolved.command.title,
        toolbar,
    )
    action.setEnabled(
        resolved.state.enabled,
    )

    if resolved.command.description:
        action.setToolTip(
            resolved.command.description,
        )

    contribution_id = (
        resolved.contribution.contribution_id
    )
    action.triggered.connect(
        lambda: contribution_service.execute_contribution(
            contribution_id,
        )
    )

    return action
