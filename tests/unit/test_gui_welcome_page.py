"""Unit tests for the Welcome page overlay widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton

from opencobol2.gui.welcome_page import WelcomePageWidget


def _button(
    widget: WelcomePageWidget,
    text: str,
) -> QPushButton:
    for button in widget.findChildren(
        QPushButton,
    ):
        if button.text() == text:
            return button

    raise AssertionError(
        f"No button with text {text!r} found.",
    )


def test_initially_shows_the_empty_recent_projects_placeholder(
    qapp,
) -> None:
    widget = WelcomePageWidget()

    assert widget._recent_list.isHidden()
    assert not widget._empty_recent_label.isHidden()
    assert widget._recent_list.count() == 0


def test_set_recent_projects_populates_the_list(
    qapp,
    tmp_path: Path,
) -> None:
    widget = WelcomePageWidget()
    first_path = tmp_path / "one.ocproj"
    second_path = tmp_path / "two.ocproj"

    widget.set_recent_projects(
        (
            first_path,
            second_path,
        ),
    )

    assert widget._recent_list.count() == 2
    assert widget._recent_list.item(0).text() == str(
        first_path,
    )
    assert not widget._recent_list.isHidden()
    assert widget._empty_recent_label.isHidden()


def test_set_recent_projects_with_empty_sequence_restores_placeholder(
    qapp,
    tmp_path: Path,
) -> None:
    widget = WelcomePageWidget()
    widget.set_recent_projects(
        (tmp_path / "one.ocproj",),
    )

    widget.set_recent_projects(
        (),
    )

    assert widget._recent_list.isHidden()
    assert not widget._empty_recent_label.isHidden()


def test_new_project_button_emits_signal(
    qapp,
) -> None:
    widget = WelcomePageWidget()
    received = []
    widget.new_project_requested.connect(
        lambda: received.append(
            True,
        )
    )

    _button(
        widget,
        "New Project...",
    ).click()

    assert received == [True]


def test_open_project_button_emits_signal(
    qapp,
) -> None:
    widget = WelcomePageWidget()
    received = []
    widget.open_project_requested.connect(
        lambda: received.append(
            True,
        )
    )

    _button(
        widget,
        "Open Project...",
    ).click()

    assert received == [True]


def test_double_clicking_a_recent_project_emits_its_path(
    qapp,
    tmp_path: Path,
) -> None:
    widget = WelcomePageWidget()
    project_path = tmp_path / "sample.ocproj"
    widget.set_recent_projects(
        (project_path,),
    )
    received = []
    widget.open_recent_project_requested.connect(
        lambda path: received.append(
            path,
        )
    )

    item = widget._recent_list.item(0)
    widget._handle_recent_item_double_clicked(
        item,
    )

    assert received == [project_path]
