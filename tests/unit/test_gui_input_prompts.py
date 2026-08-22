"""Unit tests for the shared readable-width single-value prompt dialogs."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QDialog, QInputDialog

from opencobol2.gui.input_prompts import (
    _MINIMUM_PROMPT_WIDTH,
    prompt_for_int,
    prompt_for_text,
)


def _fake_accepted_exec(
    dialog_self,
) -> int:
    dialog_self.accept()

    return int(
        dialog_self.result(),
    )


def _fake_cancelled_exec(
    dialog_self,
) -> int:
    dialog_self.reject()

    return int(
        dialog_self.result(),
    )


def test_prompt_for_text_returns_the_entered_text_when_accepted(
    qapp,
) -> None:
    with patch.object(
        QInputDialog,
        "exec",
        _fake_accepted_exec,
    ):
        text, accepted = prompt_for_text(
            None,
            "Title",
            "Label:",
            default_text="pre-filled",
        )

    assert accepted is True
    assert text == "pre-filled"


def test_prompt_for_text_returns_empty_and_false_when_cancelled(
    qapp,
) -> None:
    with patch.object(
        QInputDialog,
        "exec",
        _fake_cancelled_exec,
    ):
        text, accepted = prompt_for_text(
            None,
            "Title",
            "Label:",
            default_text="ignored",
        )

    assert accepted is False
    assert text == ""


def test_prompt_for_text_sets_window_title_and_label(
    qapp,
) -> None:
    seen = {}

    def fake_exec(
        dialog_self,
    ) -> int:
        seen["title"] = dialog_self.windowTitle()
        seen["label"] = dialog_self.labelText()
        seen["width"] = dialog_self.minimumWidth()
        dialog_self.accept()

        return int(
            dialog_self.result(),
        )

    with patch.object(
        QInputDialog,
        "exec",
        fake_exec,
    ):
        prompt_for_text(
            None,
            "New Branch",
            "Branch name:",
        )

    assert seen["title"] == "New Branch"
    assert seen["label"] == "Branch name:"
    assert seen["width"] == _MINIMUM_PROMPT_WIDTH


def test_prompt_for_text_defaults_to_an_empty_field(
    qapp,
) -> None:
    seen = {}

    def fake_exec(
        dialog_self,
    ) -> int:
        seen["text"] = dialog_self.textValue()
        dialog_self.accept()

        return int(
            dialog_self.result(),
        )

    with patch.object(
        QInputDialog,
        "exec",
        fake_exec,
    ):
        prompt_for_text(
            None,
            "Title",
            "Label:",
        )

    assert seen["text"] == ""


def test_prompt_for_int_returns_the_entered_value_when_accepted(
    qapp,
) -> None:
    with patch.object(
        QInputDialog,
        "exec",
        _fake_accepted_exec,
    ):
        value, accepted = prompt_for_int(
            None,
            "Go to Line",
            "Line number:",
            1,
            1,
            100,
        )

    assert accepted is True
    assert value == 1


def test_prompt_for_int_returns_zero_and_false_when_cancelled(
    qapp,
) -> None:
    with patch.object(
        QInputDialog,
        "exec",
        _fake_cancelled_exec,
    ):
        value, accepted = prompt_for_int(
            None,
            "Go to Line",
            "Line number:",
            1,
            1,
            100,
        )

    assert accepted is False
    assert value == 0


def test_prompt_for_int_sets_window_title_range_and_value(
    qapp,
) -> None:
    seen = {}

    def fake_exec(
        dialog_self,
    ) -> int:
        seen["title"] = dialog_self.windowTitle()
        seen["label"] = dialog_self.labelText()
        seen["value"] = dialog_self.intValue()
        seen["minimum"] = dialog_self.intMinimum()
        seen["maximum"] = dialog_self.intMaximum()
        seen["width"] = dialog_self.minimumWidth()
        dialog_self.accept()

        return int(
            dialog_self.result(),
        )

    with patch.object(
        QInputDialog,
        "exec",
        fake_exec,
    ):
        prompt_for_int(
            None,
            "Go to Line",
            "Line number (1-42):",
            7,
            1,
            42,
        )

    assert seen["title"] == "Go to Line"
    assert seen["label"] == "Line number (1-42):"
    assert seen["value"] == 7
    assert seen["minimum"] == 1
    assert seen["maximum"] == 42
    assert seen["width"] == _MINIMUM_PROMPT_WIDTH
