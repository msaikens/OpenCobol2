"""Unit tests for the command-contribution menu bar renderer."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import (
    QMenu,
    QMenuBar,
)

from opencobol2.commands import (
    Command,
    CommandContribution,
    CommandContributionRegistry,
    CommandRegistry,
    CommandState,
    CommandSurfaceKind,
    DynamicMenuContribution,
    DynamicMenuItem,
    SubmenuContribution,
)
from opencobol2.gui.command_menus import (
    build_menu_bar,
    populate_menu,
)
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import CommandService


def _build_service(
    *,
    checked: bool = False,
    enabled: bool = True,
) -> CommandContributionService:
    command_registry = CommandRegistry()
    command_registry.register(
        Command(
            command_id="test.new",
            title="New",
            handler=lambda context: "new",
        )
    )
    command_registry.register(
        Command(
            command_id="test.save",
            title="Save",
            handler=lambda context: "save",
            state_provider=(
                lambda context: CommandState(
                    enabled=enabled,
                    checked=checked,
                )
            ),
        )
    )
    command_registry.register(
        Command(
            command_id="test.nested",
            title="Nested Command",
            handler=lambda context: "nested",
        )
    )
    command_registry.register(
        Command(
            command_id="test.recent",
            title="Recent Item Template",
            handler=lambda context: context.get(
                "path",
            ),
        )
    )

    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.new",
            command_id="test.new",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            order=10,
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.save",
            command_id="test.save",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            order=20,
            separator_before=True,
        )
    )
    contribution_registry.register(
        SubmenuContribution(
            contribution_id="menu.file.recent",
            title="Open Recent",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.recent",
            order=30,
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id=(
                "menu.file.recent.nested"
            ),
            command_id="test.nested",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file.recent",
            order=10,
        )
    )
    contribution_registry.register(
        DynamicMenuContribution(
            contribution_id="menu.file.dynamic",
            title="Dynamic",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            provider=lambda context: (
                DynamicMenuItem(
                    title="Recent A",
                    command_id="test.recent",
                ),
                DynamicMenuItem(
                    title="Recent B",
                    command_id="test.recent",
                    enabled=False,
                ),
            ),
            order=40,
            separator_before=True,
        )
    )

    return CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )


def test_populate_menu_creates_actions_with_separators(
    qapp,
) -> None:
    service = _build_service()
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    titles = [
        action.text()
        for action in menu.actions()
    ]
    assert "New" in titles
    assert "Save" in titles
    assert "Open Recent" in titles
    assert "Recent A" in titles
    assert "Recent B" in titles
    assert any(
        action.isSeparator()
        for action in menu.actions()
    )


def test_populate_menu_reflects_command_state(
    qapp,
) -> None:
    service = _build_service(
        checked=True,
        enabled=False,
    )
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    save_action = next(
        action
        for action in menu.actions()
        if action.text() == "Save"
    )

    assert save_action.isEnabled() is False
    assert save_action.isCheckable() is True
    assert save_action.isChecked() is True


def test_populate_menu_disables_dynamic_item(
    qapp,
) -> None:
    service = _build_service()
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    recent_b = next(
        action
        for action in menu.actions()
        if action.text() == "Recent B"
    )

    assert recent_b.isEnabled() is False


def test_populate_menu_builds_nested_submenu(
    qapp,
) -> None:
    service = _build_service()
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    recent_action = next(
        action
        for action in menu.actions()
        if action.text() == "Open Recent"
    )
    submenu = recent_action.menu()

    assert submenu is not None

    submenu.aboutToShow.emit()

    assert [
        action.text()
        for action in submenu.actions()
    ] == ["Nested Command"]


def test_command_action_executes_contribution_on_trigger(
    qapp,
) -> None:
    service = _build_service()
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    new_action = next(
        action
        for action in menu.actions()
        if action.text() == "New"
    )

    new_action.trigger()


def test_build_menu_bar_creates_top_level_menus(
    qapp,
) -> None:
    service = _build_service()
    menu_bar = QMenuBar()

    menus = build_menu_bar(
        menu_bar,
        (
            (
                "file",
                "&File",
            ),
        ),
        service,
    )

    assert set(
        menus.keys(),
    ) == {"file"}
    assert menus["file"].title() == "&File"


def test_populate_menu_breaks_self_referencing_submenu_cycle(
    qapp,
) -> None:
    """A submenu whose submenu_id points back to its own surface must
    not recurse forever the moment the menu is shown."""

    command_registry = CommandRegistry()
    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        SubmenuContribution(
            contribution_id="menu.cyclic.self",
            title="Cyclic",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="cyclic",
            submenu_id="cyclic",
        )
    )
    service = CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )
    menu = QMenu()

    populate_menu(
        menu,
        "cyclic",
        service,
    )

    cyclic_action = next(
        action
        for action in menu.actions()
        if action.text() == "Cyclic"
    )
    submenu = cyclic_action.menu()

    assert submenu is not None
    # Showing the nested submenu must not recurse back into itself.
    submenu.aboutToShow.emit()
    assert submenu.actions() == []


def test_repeated_menu_opens_do_not_leak_submenu_objects(
    qapp,
) -> None:
    # Editor §UIShell-2: `populate_menu()` reruns on every real
    # `aboutToShow` -- `menu.clear()` alone only empties the action
    # list, leaving each previous call's submenu `QMenu` alive forever
    # as an orphaned child of `menu`. Reproduced with real repeated
    # `aboutToShow` cycles, exactly as the original finding did.
    service = _build_service()
    menu = QMenu()
    menu.aboutToShow.connect(
        lambda: populate_menu(
            menu,
            "file",
            service,
        )
    )

    for _ in range(20):
        menu.aboutToShow.emit()

    # `deleteLater()` schedules a `DeferredDelete` event that a real,
    # running `exec()` loop processes automatically while idle -- a
    # plain `processEvents()` call deliberately excludes that event
    # type (to avoid destroying objects mid-callback), so it must be
    # flushed explicitly here to prove the object is actually gone
    # rather than merely scheduled.
    QCoreApplication.sendPostedEvents(
        None,
        QEvent.Type.DeferredDelete,
    )

    assert (
        len(
            menu.findChildren(
                QMenu,
                options=(
                    Qt.FindChildOption
                    .FindDirectChildrenOnly
                ),
            )
        )
        == 1
    )


def test_populate_menu_keeps_separator_around_hidden_contribution(
    qapp,
) -> None:
    """A hidden contribution's own action must not render, but a
    separator attached to it still marks a real boundary between its
    visible neighbors and must not disappear along with the item."""

    command_registry = CommandRegistry()
    command_registry.register(
        Command(
            command_id="test.before",
            title="Before",
            handler=lambda context: None,
        )
    )
    command_registry.register(
        Command(
            command_id="test.hidden",
            title="Hidden",
            handler=lambda context: None,
            state_provider=lambda context: CommandState(
                visible=False,
            ),
        )
    )
    command_registry.register(
        Command(
            command_id="test.after",
            title="After",
            handler=lambda context: None,
        )
    )

    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.before",
            command_id="test.before",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            order=10,
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.hidden",
            command_id="test.hidden",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            order=20,
            separator_before=True,
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.after",
            command_id="test.after",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            order=30,
        )
    )

    service = CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )
    menu = QMenu()

    populate_menu(
        menu,
        "file",
        service,
    )

    titles = [
        action.text()
        for action in menu.actions()
    ]
    assert "Before" in titles
    assert "Hidden" not in titles
    assert "After" in titles
    assert any(
        action.isSeparator()
        for action in menu.actions()
    )
