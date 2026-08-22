"""A single-form dialog for creating a new project.

Replaces what used to be a sequence of three separate stock prompts (a
project-name `QInputDialog`, a root-directory `QFileDialog`, and a
project-*file* `QFileDialog`) with one form that asks only for what the
user actually decides: the project's name and where it should live. The
project's own metadata file is placed automatically -- see
`opencobol2.gui.project_commands.create_project_from_details` -- rather
than asked about, since it is an internal artifact the user editing or
relocating by hand would only risk breaking the project.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_DEFAULT_PROJECTS_DIRECTORY_NAME = "OpenCobol2 Projects"


def default_projects_root() -> Path:
    """Return the default parent directory new projects are suggested under.

    :returns: `~/OpenCobol2 Projects`, mirroring the same
        "a sensible default the user can override" convention other
        IDEs use for a new project's suggested location.
    """

    return Path.home() / _DEFAULT_PROJECTS_DIRECTORY_NAME


class NewProjectDialog(QDialog):
    """Prompts for a new project's name and root directory in one form.

    The root-directory field auto-fills from the project name as it's
    typed (`default_projects_root() / name`) until the user either
    edits that field directly or browses to a different one -- at that
    point their choice is treated as deliberate and no longer
    overwritten by further name edits, the same "stop auto-filling once
    the user takes over" behavior most name+location dialogs use.

    :ivar project_name: The entered project name, valid only after
        :meth:`exec` returns `QDialog.DialogCode.Accepted`.
    :ivar project_root: The entered project root directory, valid only
        after :meth:`exec` returns `QDialog.DialogCode.Accepted`.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        """Build the dialog, with the root directory field already
        showing a sensible default.

        :param parent: The optional parent widget.
        :returns: None.
        """

        super().__init__(
            parent,
        )

        self.setWindowTitle(
            "New Project",
        )

        self._root_manually_set = False

        self._name_edit = QLineEdit()
        self._name_edit.textEdited.connect(
            self._update_default_root,
        )

        self._root_edit = QLineEdit()
        self._root_edit.textEdited.connect(
            self._mark_root_manually_set,
        )

        browse_button = QPushButton(
            "...",
        )
        browse_button.setFixedWidth(
            32,
        )
        browse_button.setToolTip(
            "Browse for an existing folder",
        )
        browse_button.clicked.connect(
            self._browse_for_root,
        )

        root_row = QHBoxLayout()
        root_row.addWidget(
            self._root_edit,
        )
        root_row.addWidget(
            browse_button,
        )

        form = QFormLayout()
        form.addRow(
            "Project name:",
            self._name_edit,
        )
        form.addRow(
            "Project root directory:",
            root_row,
        )

        layout = QVBoxLayout(
            self,
        )
        layout.addLayout(
            form,
        )

        button_row = QHBoxLayout()
        button_row.addStretch()

        ok_button = QPushButton(
            "OK",
        )
        ok_button.clicked.connect(
            self._validate_and_accept,
        )
        button_row.addWidget(
            ok_button,
        )

        cancel_button = QPushButton(
            "Cancel",
        )
        cancel_button.clicked.connect(
            self.reject,
        )
        button_row.addWidget(
            cancel_button,
        )

        layout.addLayout(
            button_row,
        )

        self._update_default_root()

    def _default_root_for(
        self,
        name: str,
    ) -> Path:
        """Return the suggested root directory for a given project name.

        :param name: The project name typed so far, possibly empty or
            whitespace-only.
        :returns: `default_projects_root() / name`, falling back to
            the literal name `"NewProject"` when `name` has no
            non-whitespace content yet.
        """

        stripped_name = name.strip()

        return default_projects_root() / (
            stripped_name
            if stripped_name
            else "NewProject"
        )

    def _update_default_root(
        self,
    ) -> None:
        """Refresh the root-directory field's auto-filled suggestion.

        :returns: None. A no-op once the user has manually set the
            root directory field themselves (see `_root_manually_set`).
        """

        if self._root_manually_set:
            return

        self._root_edit.setText(
            str(
                self._default_root_for(
                    self._name_edit.text(),
                ),
            ),
        )

    def _mark_root_manually_set(
        self,
    ) -> None:
        """Stop auto-filling the root directory from the project name.

        :returns: None.
        """

        self._root_manually_set = True

    def _browse_for_root(
        self,
    ) -> None:
        """Open a folder-picker to choose an existing root directory.

        :returns: None. Updates the root-directory field (and marks it
            manually set) only if a folder was actually chosen.
        """

        chosen_directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Root Directory",
            self._root_edit.text(),
        )

        if not chosen_directory:
            return

        self._root_edit.setText(
            chosen_directory,
        )
        self._mark_root_manually_set()

    def _validate_and_accept(
        self,
    ) -> None:
        """Validate the form, then close the dialog as accepted.

        :returns: None. Shows a warning and leaves the dialog open if
            either field is blank; otherwise records
            :attr:`project_name`/:attr:`project_root` and accepts.
        """

        name = self._name_edit.text().strip()
        root_text = self._root_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "New Project",
                "Enter a project name.",
            )
            return

        if not root_text:
            QMessageBox.warning(
                self,
                "New Project",
                "Choose a project root directory.",
            )
            return

        self.project_name = name
        self.project_root = Path(
            root_text,
        )
        self.accept()
