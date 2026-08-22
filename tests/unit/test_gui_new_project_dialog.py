"""Unit tests for the New Project dialog's own presentation."""

from __future__ import annotations

from opencobol2.gui.new_project_dialog import (
    _MINIMUM_DIALOG_WIDTH,
    NewProjectDialog,
)


def test_new_project_dialog_has_a_readable_minimum_width(
    qapp,
) -> None:
    dialog = NewProjectDialog()

    assert dialog.minimumWidth() == _MINIMUM_DIALOG_WIDTH
