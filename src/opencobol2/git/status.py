"""Parsing of Git porcelain version 2 repository status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opencobol2.git.models import (
    GitChange,
    GitChangeStatus,
    GitRepositoryStatus,
)


@dataclass(
    slots=True,
)
class _StatusHeaders:
    """Mutable porcelain-v2 branch header collection."""

    head_oid: str | None = None
    branch_name: str | None = None
    detached: bool = False
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0


def parse_git_status_porcelain_v2(
    *,
    repository_root: Path | str,
    output: str,
) -> GitRepositoryStatus:
    """Parse NUL-delimited Git porcelain-v2 branch status."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git status output must be a string."
        )

    headers = _StatusHeaders()
    changes: list[GitChange] = []

    records = output.split(
        "\0",
    )
    index = 0

    while index < len(
        records,
    ):
        record = records[
            index
        ]
        index += 1

        if not record:
            continue

        if record.startswith(
            "# ",
        ):
            _parse_header(
                headers,
                record,
            )
            continue

        record_kind = record[
            0
        ]

        if record_kind == "1":
            changes.append(
                _parse_ordinary_change(
                    record,
                )
            )
            continue

        if record_kind == "2":
            if index >= len(
                records,
            ):
                raise ValueError(
                    "Git rename or copy status record is missing "
                    "its original path."
                )

            original_path = records[
                index
            ]
            index += 1

            if not original_path:
                raise ValueError(
                    "Git rename or copy status record is missing "
                    "its original path."
                )

            changes.append(
                _parse_renamed_or_copied_change(
                    record,
                    original_path,
                )
            )
            continue

        if record_kind == "u":
            changes.append(
                _parse_unmerged_change(
                    record,
                )
            )
            continue

        if record_kind == "?":
            changes.append(
                _parse_untracked_change(
                    record,
                )
            )
            continue

        if record_kind == "!":
            changes.append(
                _parse_ignored_change(
                    record,
                )
            )
            continue

        raise ValueError(
            "Unsupported Git porcelain-v2 status record: "
            f"{record!r}."
        )

    return GitRepositoryStatus(
        repository_root=repository_root,
        head_oid=headers.head_oid,
        branch_name=headers.branch_name,
        detached=headers.detached,
        upstream=headers.upstream,
        ahead=headers.ahead,
        behind=headers.behind,
        changes=tuple(
            changes,
        ),
    )


def _parse_header(
    headers: _StatusHeaders,
    record: str,
) -> None:
    """Parse one porcelain-v2 branch header."""

    if record.startswith(
        "# branch.oid ",
    ):
        oid = record.removeprefix(
            "# branch.oid ",
        )

        headers.head_oid = (
            None
            if oid == "(initial)"
            else oid
        )
        return

    if record.startswith(
        "# branch.head ",
    ):
        head = record.removeprefix(
            "# branch.head ",
        )

        if head == "(detached)":
            headers.branch_name = None
            headers.detached = True
        else:
            headers.branch_name = head
            headers.detached = False

        return

    if record.startswith(
        "# branch.upstream ",
    ):
        headers.upstream = record.removeprefix(
            "# branch.upstream ",
        )
        return

    if record.startswith(
        "# branch.ab ",
    ):
        ahead_text, behind_text = record.removeprefix(
            "# branch.ab ",
        ).split(
            " ",
            maxsplit=1,
        )

        if not ahead_text.startswith(
            "+",
        ):
            raise ValueError(
                "Git branch ahead count must start with '+'."
            )

        if not behind_text.startswith(
            "-",
        ):
            raise ValueError(
                "Git branch behind count must start with '-'."
            )

        headers.ahead = int(
            ahead_text[
                1:
            ],
        )
        headers.behind = int(
            behind_text[
                1:
            ],
        )


def _parse_ordinary_change(
    record: str,
) -> GitChange:
    """Parse one ordinary changed-entry record."""

    fields = record.split(
        " ",
        maxsplit=8,
    )

    if len(
        fields,
    ) != 9:
        raise ValueError(
            "Invalid ordinary Git porcelain-v2 status record."
        )

    xy = fields[
        1
    ]
    path = fields[
        8
    ]

    return _create_change(
        path=path,
        xy=xy,
    )


def _parse_renamed_or_copied_change(
    record: str,
    original_path: str,
) -> GitChange:
    """Parse one rename or copy status record."""

    fields = record.split(
        " ",
        maxsplit=9,
    )

    if len(
        fields,
    ) != 10:
        raise ValueError(
            "Invalid rename or copy Git porcelain-v2 status record."
        )

    if not original_path:
        raise ValueError(
            "Git rename or copy status record is missing "
            "its original path."
        )

    xy = fields[
        1
    ]
    path = fields[
        9
    ]

    return _create_change(
        path=path,
        xy=xy,
        original_path=original_path,
    )


def _parse_unmerged_change(
    record: str,
) -> GitChange:
    """Parse one unmerged status record."""

    fields = record.split(
        " ",
        maxsplit=10,
    )

    if len(
        fields,
    ) != 11:
        raise ValueError(
            "Invalid unmerged Git porcelain-v2 status record."
        )

    return GitChange(
        path=fields[
            10
        ],
        index_status=GitChangeStatus.UNMERGED,
        worktree_status=GitChangeStatus.UNMERGED,
    )


def _parse_untracked_change(
    record: str,
) -> GitChange:
    """Parse one untracked path record."""

    path = _parse_simple_path_record(
        record,
        "? ",
        "untracked",
    )

    return GitChange(
        path=path,
        index_status=GitChangeStatus.UNTRACKED,
        worktree_status=GitChangeStatus.UNTRACKED,
    )


def _parse_ignored_change(
    record: str,
) -> GitChange:
    """Parse one ignored path record."""

    path = _parse_simple_path_record(
        record,
        "! ",
        "ignored",
    )

    return GitChange(
        path=path,
        index_status=GitChangeStatus.IGNORED,
        worktree_status=GitChangeStatus.IGNORED,
    )


def _parse_simple_path_record(
    record: str,
    prefix: str,
    kind: str,
) -> str:
    """Parse a porcelain record containing only a kind and path."""

    if not record.startswith(
        prefix,
    ):
        raise ValueError(
            f"Invalid {kind} Git porcelain-v2 status record."
        )

    path = record.removeprefix(
        prefix,
    )

    if not path:
        raise ValueError(
            f"Git {kind} path must not be empty."
        )

    return path


def _create_change(
    *,
    path: str,
    xy: str,
    original_path: str | None = None,
) -> GitChange:
    """Create one normalized changed-path model."""

    if len(
        xy,
    ) != 2:
        raise ValueError(
            "Git porcelain-v2 XY status must contain two characters."
        )

    return GitChange(
        path=path,
        index_status=_parse_status_character(
            xy[
                0
            ],
        ),
        worktree_status=_parse_status_character(
            xy[
                1
            ],
        ),
        original_path=original_path,
    )


def _parse_status_character(
    value: str,
) -> GitChangeStatus:
    """Normalize one Git XY status character."""

    statuses = {
        ".": GitChangeStatus.UNMODIFIED,
        "M": GitChangeStatus.MODIFIED,
        "T": GitChangeStatus.TYPE_CHANGED,
        "A": GitChangeStatus.ADDED,
        "D": GitChangeStatus.DELETED,
        "R": GitChangeStatus.RENAMED,
        "C": GitChangeStatus.COPIED,
        "U": GitChangeStatus.UNMERGED,
        "?": GitChangeStatus.UNTRACKED,
        "!": GitChangeStatus.IGNORED,
    }

    return statuses.get(
        value,
        GitChangeStatus.UNKNOWN,
    )