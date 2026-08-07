"""Renders command-contribution menu surfaces as live Qt menus."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QMenuBar,
)

from opencobol2.commands import (
    CommandSurfaceKind,
    ResolvedCommandContribution,
    ResolvedDynamicMenuContribution,
    ResolvedDynamicMenuItem,
    ResolvedSubmenuContribution,
)
from opencobol2.services.command_contributions import (
    CommandContributionService,
)


def build_menu_bar(
    menu_bar: QMenuBar,
    top_level_menus: Sequence[tuple[str, str]],
    contribution_service: CommandContributionService,
) -> dict[str, QMenu]:
    """Build a menu bar's top-level menus from ordered (surface ID, title) pairs."""

    menus: dict[str, QMenu] = {}

    for surface_id, title in top_level_menus:
        menu = menu_bar.addMenu(
            title,
        )
        connect_menu(
            menu,
            surface_id,
            contribution_service,
        )
        menus[surface_id] = menu

    return menus


def connect_menu(
    menu: QMenu,
    surface_id: str,
    contribution_service: CommandContributionService,
    *,
    _ancestor_surface_ids: frozenset[str] = frozenset(),
) -> None:
    """Wire a menu to rebuild its contents from live state on every open."""

    menu.aboutToShow.connect(
        lambda: populate_menu(
            menu,
            surface_id,
            contribution_service,
            _ancestor_surface_ids=_ancestor_surface_ids,
        )
    )
    populate_menu(
        menu,
        surface_id,
        contribution_service,
        _ancestor_surface_ids=_ancestor_surface_ids,
    )


def populate_menu(
    menu: QMenu,
    surface_id: str,
    contribution_service: CommandContributionService,
    *,
    _ancestor_surface_ids: frozenset[str] = frozenset(),
) -> None:
    """Clear and repopulate one menu from current command contribution state."""

    # Editor §UIShell-2: `menu.clear()` below only empties the menu's own
    # action list -- a submenu `QMenu` created by a *previous*
    # populate_menu() call (via addMenu() further down) stays alive as an
    # orphaned QObject child of `menu` forever, since nothing else ever
    # deletes it, and this whole function reruns on every `aboutToShow`.
    # Explicitly deleting every direct-child submenu before rebuilding is
    # what actually reclaims it; nested descendants are cleaned up
    # automatically by Qt once their own direct parent is deleted.
    for stale_submenu in menu.findChildren(
        QMenu,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    ):
        stale_submenu.deleteLater()

    menu.clear()
    # A submenu contribution whose submenu_id points back to one of its
    # own ancestors would otherwise recurse into connect_menu forever
    # (stack overflow) the moment this menu is shown. Checked against
    # the ancestors *above* this level (not including surface_id
    # itself) so a direct self-reference still renders once -- as an
    # entry whose own submenu comes up empty -- rather than vanishing
    # outright, matching how a longer A -> B -> A cycle is broken one
    # level in rather than by hiding the outer entry.
    child_ancestor_surface_ids = (
        _ancestor_surface_ids | {surface_id}
    )

    for resolved in contribution_service.resolve_surface(
        CommandSurfaceKind.MENU,
        surface_id,
        # A hidden contribution's own action must not render, but its
        # separator_before/after still marks a real boundary between
        # its visible neighbors -- resolving with include_hidden=True
        # and gating just the addAction() call keeps that boundary
        # intact instead of silently dropping it along with the item.
        include_hidden=True,
    ):
        if isinstance(
            resolved,
            ResolvedCommandContribution,
        ):
            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_before,
            )

            if resolved.state.visible:
                menu.addAction(
                    _create_command_action(
                        menu,
                        resolved,
                        contribution_service,
                    )
                )

            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_after,
            )
            continue

        if isinstance(
            resolved,
            ResolvedSubmenuContribution,
        ):
            if (
                resolved.contribution.submenu_id
                in _ancestor_surface_ids
            ):
                continue

            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_before,
            )
            submenu = menu.addMenu(
                resolved.contribution.title,
            )
            connect_menu(
                submenu,
                resolved.contribution.submenu_id,
                contribution_service,
                _ancestor_surface_ids=child_ancestor_surface_ids,
            )
            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_after,
            )
            continue

        if isinstance(
            resolved,
            ResolvedDynamicMenuContribution,
        ):
            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_before,
            )
            for resolved_item in resolved.items:
                if not resolved_item.state.visible:
                    continue

                menu.addAction(
                    _create_dynamic_action(
                        menu,
                        resolved_item,
                        contribution_service,
                    )
                )
            _add_separator_if_requested(
                menu,
                resolved.contribution.separator_after,
            )
            continue

        raise TypeError(
            "Unsupported resolved menu contribution: "
            f"{type(resolved).__name__}."
        )


def _add_separator_if_requested(
    menu: QMenu,
    requested: bool,
) -> None:
    """Add a separator to a menu when requested by a contribution."""

    if requested:
        menu.addSeparator()


def _create_command_action(
    menu: QMenu,
    resolved: ResolvedCommandContribution,
    contribution_service: CommandContributionService,
) -> QAction:
    """Create a menu action for one resolved direct command contribution."""

    action = QAction(
        resolved.command.title,
        menu,
    )
    action.setEnabled(
        resolved.state.enabled,
    )

    if resolved.state.checked:
        action.setCheckable(
            True,
        )
        action.setChecked(
            True,
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


def _create_dynamic_action(
    menu: QMenu,
    resolved_item: ResolvedDynamicMenuItem,
    contribution_service: CommandContributionService,
) -> QAction:
    """Create a menu action for one resolved dynamic menu item."""

    action = QAction(
        resolved_item.item.title,
        menu,
    )
    action.setEnabled(
        resolved_item.state.enabled,
    )

    if resolved_item.state.checked:
        action.setCheckable(
            True,
        )
        action.setChecked(
            True,
        )

    action.triggered.connect(
        lambda: contribution_service.execute_dynamic_item(
            resolved_item,
        )
    )

    return action
