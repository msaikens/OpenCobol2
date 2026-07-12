"""Unit tests for the tabbed source editor, against a real DocumentService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from opencobol2.documents import DocumentService
from opencobol2.gui.editor import EditorTabsWidget


def test_open_path_creates_a_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )

    tabs.open_path(
        file_path,
    )

    assert tabs.count() == 1
    assert tabs.tabText(0) == "main.cbl"
    assert (
        tabs.widget(0).toPlainText()
        == "IDENTIFICATION DIVISION.\n"
    )
    assert (
        tabs.tabToolTip(0)
        == str(file_path)
    )


def test_open_path_twice_reuses_the_existing_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )

    tabs.open_path(
        file_path,
    )
    tabs.new_file()
    tabs.open_path(
        file_path,
    )

    assert tabs.count() == 2
    assert tabs.currentIndex() == 0


def test_editing_text_marks_the_tab_dirty_and_syncs_the_document(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    document_service = DocumentService()
    tabs = EditorTabsWidget(
        document_service=document_service,
    )
    tabs.open_path(
        file_path,
    )

    tabs.widget(0).setPlainText(
        "changed",
    )

    assert tabs.tabText(0) == "main.cbl *"
    active_document = (
        document_service.workspace
        .active_document
        .document
    )
    assert active_document.text == "changed"
    assert active_document.is_modified


def test_new_file_creates_an_untitled_tab(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )

    tabs.new_file()

    assert tabs.count() == 1
    assert tabs.tabText(0) == "Untitled"
    assert tabs.tabToolTip(0) == "Untitled"


def test_open_file_dialog_opens_the_chosen_path(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getOpenFileName",
        return_value=(
            str(file_path),
            "",
        ),
    ):
        tabs.open_file_dialog()

    assert tabs.count() == 1
    assert tabs.tabText(0) == "main.cbl"


def test_open_file_dialog_does_nothing_when_cancelled(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getOpenFileName",
        return_value=(
            "",
            "",
        ),
    ):
        tabs.open_file_dialog()

    assert tabs.count() == 0


def test_save_active_document_persists_changes(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).setPlainText(
        "changed",
    )

    tabs.save_active_document()

    assert tabs.tabText(0) == "main.cbl"
    assert file_path.read_text() == "changed"


def test_save_active_document_redirects_untitled_to_save_as(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "hello",
    )
    save_path = tmp_path / "new.cbl"

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(save_path),
            "",
        ),
    ):
        tabs.save_active_document()

    assert tabs.tabText(0) == "new.cbl"
    assert save_path.read_text() == "hello"


def test_save_active_document_as_prompts_even_for_titled_documents(
    qapp,
    tmp_path: Path,
) -> None:
    original_path = tmp_path / "main.cbl"
    original_path.write_text(
        "x",
    )
    other_path = tmp_path / "copy.cbl"
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.open_path(
        original_path,
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(other_path),
            "",
        ),
    ) as mock_dialog:
        tabs.save_active_document_as()

    mock_dialog.assert_called_once()
    assert other_path.read_text() == "x"
    assert tabs.tabText(0) == "copy.cbl"


def test_save_active_document_as_does_nothing_when_cancelled(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "hello",
    )

    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            "",
            "",
        ),
    ):
        tabs.save_active_document_as()

    assert tabs.tabText(0) == "Untitled *"


def test_save_all_documents_skips_untitled_and_saves_the_rest(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "original",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.open_path(
        file_path,
    )
    tabs.widget(0).setPlainText(
        "changed",
    )
    tabs.new_file()
    tabs.widget(1).setPlainText(
        "untitled text",
    )

    tabs.save_all_documents()

    assert file_path.read_text() == "changed"
    assert tabs.tabText(0) == "main.cbl"
    assert tabs.tabText(1) == "Untitled *"


def test_close_active_document_without_changes_removes_the_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.open_path(
        file_path,
    )

    tabs.close_active_document()

    assert tabs.count() == 0


def test_closing_a_modified_document_prompts_and_respects_cancel(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Cancel
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 1


def test_closing_a_modified_document_can_discard_changes(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Discard
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 0


def test_closing_a_modified_document_can_save_first(
    qapp,
    tmp_path: Path,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )
    save_path = tmp_path / "new.cbl"

    with (
        patch(
            "opencobol2.gui.editor.QMessageBox.question",
            return_value=(
                QMessageBox.StandardButton.Save
            ),
        ),
        patch(
            "opencobol2.gui.editor.QFileDialog.getSaveFileName",
            return_value=(
                str(save_path),
                "",
            ),
        ),
    ):
        tabs.close_active_document()

    assert tabs.count() == 0
    assert save_path.read_text() == "unsaved"


def test_closing_a_modified_untitled_document_save_choice_cancelled_keeps_tab(
    qapp,
) -> None:
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.new_file()
    tabs.widget(0).setPlainText(
        "unsaved",
    )

    with (
        patch(
            "opencobol2.gui.editor.QMessageBox.question",
            return_value=(
                QMessageBox.StandardButton.Save
            ),
        ),
        patch(
            "opencobol2.gui.editor.QFileDialog.getSaveFileName",
            return_value=(
                "",
                "",
            ),
        ),
    ):
        tabs.close_active_document()

    # Save As was cancelled mid-close, so the tab must remain open with
    # its unsaved changes intact rather than being silently discarded.
    assert tabs.count() == 1
    assert tabs.tabText(0) == "Untitled *"


def test_close_all_documents_closes_every_tab(
    qapp,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "main.cbl"
    file_path.write_text(
        "x",
    )
    tabs = EditorTabsWidget(
        document_service=DocumentService(),
    )
    tabs.open_path(
        file_path,
    )
    tabs.new_file()

    tabs.close_all_documents()

    assert tabs.count() == 0


def test_rejects_non_document_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Editor tabs document service must be DocumentService"
        ),
    ):
        EditorTabsWidget(
            document_service=object(),  # type: ignore[arg-type]
        )
