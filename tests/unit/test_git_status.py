"""Unit tests for Git porcelain-v2 repository status parsing."""

from pathlib import Path

import pytest

from opencobol2.git import (
    GitChangeStatus,
    parse_git_status_porcelain_v2,
)


def test_parse_clean_branch_status() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root=r"C:\source\OpenCobol2",
        output=(
            "# branch.oid abc123\0"
            "# branch.head modernization/foundation\0"
            "# branch.upstream origin/modernization/foundation\0"
            "# branch.ab +2 -1\0"
        ),
    )

    assert status.repository_root == Path(
        r"C:\source\OpenCobol2"
    )
    assert status.head_oid == "abc123"
    assert status.branch_name == "modernization/foundation"
    assert status.detached is False
    assert (
        status.upstream
        == "origin/modernization/foundation"
    )
    assert status.ahead == 2
    assert status.behind == 1
    assert status.changes == ()
    assert status.clean is True


def test_parse_detached_head_status() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "# branch.oid abc123\0"
            "# branch.head (detached)\0"
        ),
    )

    assert status.branch_name is None
    assert status.detached is True


def test_parse_initial_branch_has_no_head_oid() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "# branch.oid (initial)\0"
            "# branch.head main\0"
        ),
    )

    assert status.head_oid is None
    assert status.branch_name == "main"


def test_parse_ordinary_staged_and_unstaged_changes() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "# branch.oid abc123\0"
            "# branch.head main\0"
            "1 M. N... 100644 100644 100644 "
            "abc abc src/staged.cob\0"
            "1 .M N... 100644 100644 100644 "
            "abc abc src/unstaged.cob\0"
            "1 MM N... 100644 100644 100644 "
            "abc abc src/both.cob\0"
        ),
    )

    assert len(
        status.changes,
    ) == 3

    staged = status.changes[
        0
    ]
    assert staged.path == Path(
        "src/staged.cob"
    )
    assert staged.index_status is GitChangeStatus.MODIFIED
    assert (
        staged.worktree_status
        is GitChangeStatus.UNMODIFIED
    )
    assert staged.staged is True
    assert staged.unstaged is False

    unstaged = status.changes[
        1
    ]
    assert (
        unstaged.index_status
        is GitChangeStatus.UNMODIFIED
    )
    assert (
        unstaged.worktree_status
        is GitChangeStatus.MODIFIED
    )
    assert unstaged.staged is False
    assert unstaged.unstaged is True

    both = status.changes[
        2
    ]
    assert both.staged is True
    assert both.unstaged is True

    assert status.clean is False
    assert status.has_staged_changes is True
    assert status.has_unstaged_changes is True


def test_parse_untracked_path() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output="? new program.cob\0",
    )

    assert len(
        status.changes,
    ) == 1

    change = status.changes[
        0
    ]

    assert change.path == Path(
        "new program.cob"
    )
    assert (
        change.index_status
        is GitChangeStatus.UNTRACKED
    )
    assert (
        change.worktree_status
        is GitChangeStatus.UNTRACKED
    )
    assert change.staged is False
    assert change.unstaged is True


def test_parse_ignored_path() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output="! build/output.exe\0",
    )

    change = status.changes[
        0
    ]

    assert (
        change.index_status
        is GitChangeStatus.IGNORED
    )
    assert (
        change.worktree_status
        is GitChangeStatus.IGNORED
    )
    assert change.staged is False
    assert change.unstaged is False


def test_parse_rename_with_original_path() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "2 R. N... 100644 100644 100644 "
            "abc abc R100 src/new-name.cob\0"
            "src/old-name.cob\0"
        ),
    )

    assert len(
        status.changes,
    ) == 1

    change = status.changes[
        0
    ]

    assert change.path == Path(
        "src/new-name.cob"
    )
    assert change.original_path == Path(
        "src/old-name.cob"
    )
    assert (
        change.index_status
        is GitChangeStatus.RENAMED
    )
    assert (
        change.worktree_status
        is GitChangeStatus.UNMODIFIED
    )


def test_parse_unmerged_path() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "u UU N... 100644 100644 100644 100644 "
            "abc def ghi src/conflict.cob\0"
        ),
    )

    change = status.changes[
        0
    ]

    assert (
        change.index_status
        is GitChangeStatus.UNMERGED
    )
    assert (
        change.worktree_status
        is GitChangeStatus.UNMERGED
    )
    assert change.staged is True
    assert change.unstaged is True


def test_unknown_xy_status_is_preserved_as_unknown() -> None:
    status = parse_git_status_porcelain_v2(
        repository_root="/source/project",
        output=(
            "1 X. N... 100644 100644 100644 "
            "abc abc src/test.cob\0"
        ),
    )

    assert (
        status.changes[0].index_status
        is GitChangeStatus.UNKNOWN
    )


def test_unsupported_record_type_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported Git porcelain-v2",
    ):
        parse_git_status_porcelain_v2(
            repository_root="/source/project",
            output="x unsupported\0",
        )


def test_rename_requires_original_path_record() -> None:
    with pytest.raises(
        ValueError,
        match="missing its original path",
    ):
        parse_git_status_porcelain_v2(
            repository_root="/source/project",
            output=(
                "2 R. N... 100644 100644 100644 "
                "abc abc R100 src/new-name.cob\0"
            ),
        )