"""Single-value prompt dialogs sized to actually be readable.

`QInputDialog`'s static convenience methods (`getText()`, `getInt()`,
etc. -- most of this codebase used to call these directly) size their
dialog to barely fit its own content, which reads as cramped at the
font size Windows renders these dialogs at -- exactly the "tiny,
almost unreadable" complaint raised against this IDE's other stock
dialogs. Constructing the `QInputDialog` directly, rather than through
a static method, allows setting an explicit minimum width before
showing it; :func:`prompt_for_text` and :func:`prompt_for_int` wrap
that up behind the exact same return shape their respective static
method already has, so every existing call site is a drop-in
replacement.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QInputDialog, QWidget


_MINIMUM_PROMPT_WIDTH = 420


def prompt_for_text(
    parent: QWidget | None,
    title: str,
    label: str,
    *,
    default_text: str = "",
) -> tuple[str, bool]:
    """Prompt for one line of text via a dialog sized to be readable.

    :param parent: The parent widget to center the dialog over.
    :param title: The dialog's window title.
    :param label: The prompt label shown above the text field.
    :param default_text: Text to pre-fill the field with (and
        pre-select, matching `QInputDialog.getText()`'s own behavior),
        for prompts that edit an existing name rather than starting
        from blank.
    :returns: `(entered_text, True)` if the dialog was accepted, or
        `("", False)` if it was cancelled -- the same shape
        `QInputDialog.getText()` already returns.
    """

    dialog = QInputDialog(
        parent,
    )
    dialog.setWindowTitle(
        title,
    )
    dialog.setLabelText(
        label,
    )
    dialog.setTextValue(
        default_text,
    )
    dialog.setMinimumWidth(
        _MINIMUM_PROMPT_WIDTH,
    )

    if (
        dialog.exec()
        != QDialog.DialogCode.Accepted
    ):
        return "", False

    return dialog.textValue(), True


def prompt_for_int(
    parent: QWidget | None,
    title: str,
    label: str,
    value: int,
    minimum: int,
    maximum: int,
) -> tuple[int, bool]:
    """Prompt for one integer via a dialog sized to be readable.

    :param parent: The parent widget to center the dialog over.
    :param title: The dialog's window title.
    :param label: The prompt label shown above the spin box.
    :param value: The spin box's initial value.
    :param minimum: The spin box's minimum allowed value.
    :param maximum: The spin box's maximum allowed value.
    :returns: `(entered_value, True)` if the dialog was accepted, or
        `(0, False)` if it was cancelled -- the same shape
        `QInputDialog.getInt()` already returns.
    """

    dialog = QInputDialog(
        parent,
    )
    dialog.setWindowTitle(
        title,
    )
    dialog.setLabelText(
        label,
    )
    dialog.setInputMode(
        QInputDialog.InputMode.IntInput,
    )
    dialog.setIntRange(
        minimum,
        maximum,
    )
    dialog.setIntValue(
        value,
    )
    dialog.setMinimumWidth(
        _MINIMUM_PROMPT_WIDTH,
    )

    if (
        dialog.exec()
        != QDialog.DialogCode.Accepted
    ):
        return 0, False

    return dialog.intValue(), True
