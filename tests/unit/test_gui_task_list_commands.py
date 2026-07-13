"""Unit tests for scanning a project's files for TODO/FIXME task markers."""

from __future__ import annotations

from pathlib import Path

from opencobol2.gui.task_list_commands import scan_project_for_tasks
from opencobol2.project import create_project


def test_scan_finds_tasks_across_multiple_files(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "one.cbl"
    ).write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. ONE.\n"
        "      * TODO first file\n"
    )
    (
        tmp_path / "two.cbl"
    ).write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TWO.\n"
        "      * FIXME second file\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    entries = scan_project_for_tasks(
        project,
    )

    assert {
        (
            entry.path.name,
            entry.tag,
        )
        for entry in entries
    } == {
        (
            "one.cbl",
            "TODO",
        ),
        (
            "two.cbl",
            "FIXME",
        ),
    }


def test_scan_with_no_matching_files_returns_nothing(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Empty",
        root_path=tmp_path,
    )

    assert scan_project_for_tasks(
        project,
    ) == ()


def test_scan_skips_unreadable_files(
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "      * TODO unreadable\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    from pathlib import Path as PathClass

    original_read_text = PathClass.read_text

    def _boom(self, *args, **kwargs):
        if self.name == "main.cbl":
            raise OSError(
                "boom",
            )
        return original_read_text(
            self,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        PathClass,
        "read_text",
        _boom,
    )

    assert scan_project_for_tasks(
        project,
    ) == ()
