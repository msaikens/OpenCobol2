"""Parsing of Git porcelain version 2 repository status.

Git is invoked with `--porcelain=v2 -z`, so `output` is a sequence of
NUL-delimited records rather than newline-delimited lines: a record's
own text can otherwise contain characters (such as a path with an
embedded newline) that would be ambiguous with a line-oriented format.
Each record is either a `# `-prefixed branch header, or a change
record whose first character identifies its kind (ordinary change,
rename/copy, unmerged, untracked, or ignored); a rename/copy record is
followed by a second, separate record holding the path's original
location.
"""

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
    """Mutable porcelain-v2 branch header collection.

    :ivar head_oid: The current commit's full object ID, or `None` if
        the repository has no commits yet (the `(initial)` sentinel).
    :ivar branch_name: The current branch's name, or `None` if `HEAD`
        is detached.
    :ivar detached: Whether `HEAD` is detached (not on a branch).
    :ivar upstream: The configured upstream branch's name, if any.
    :ivar ahead: The number of commits the current branch is ahead of
        its upstream.
    :ivar behind: The number of commits the current branch is behind
        its upstream.
    """

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
    """Parse NUL-delimited Git porcelain-v2 branch status.

    :param repository_root: The repository's root directory, carried
        through unchanged onto the returned status.
    :param output: The raw `git status --porcelain=v2 -z` output to
        parse.
    :returns: The fully parsed repository status, combining the branch
        headers with every changed/untracked/ignored path found.
    :raises TypeError: If `output` is not a string.
    :raises ValueError: If a record cannot be parsed as a valid
        porcelain-v2 record, or a rename/copy record is missing its
        following original-path record.
    """

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
    """Parse one porcelain-v2 branch header, mutating `headers` in place.

    :param headers: The header collection to update with whatever this
        record contributes.
    :param record: One `# `-prefixed branch header record. Records
        whose header name isn't recognized are silently ignored.
    :returns: None. `headers` is mutated in place.
    :raises ValueError: If a `# branch.ab ` record's ahead/behind
        counts don't start with the expected `+`/`-` sign characters.
    """

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
    """Parse one ordinary changed-entry record (kind `1`).

    :param record: The full ordinary-change record, space-delimited
        with the path as its final field.
    :returns: The parsed change, with its index/worktree status
        derived from the record's two-character XY field.
    :raises ValueError: If the record does not split into the nine
        fields an ordinary change record requires.
    """

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
    """Parse one rename or copy status record (kind `2`).

    :param record: The full rename/copy record, space-delimited with
        the current path as its final field.
    :param original_path: The path this entry was renamed or copied
        from, taken from the separate record that immediately follows
        a kind-`2` record in porcelain-v2 output.
    :returns: The parsed change, carrying `original_path` through onto
        the returned :class:`GitChange`.
    :raises ValueError: If the record does not split into the ten
        fields a rename/copy record requires, or if `original_path` is
        empty.
    """

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
    """Parse one unmerged status record (kind `u`).

    :param record: The full unmerged record, space-delimited with the
        path as its final field.
    :returns: The parsed change, with both index and worktree status
        set to :attr:`GitChangeStatus.UNMERGED`.
    :raises ValueError: If the record does not split into the eleven
        fields an unmerged record requires.
    """

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
    """Parse one untracked path record (kind `?`).

    :param record: The full untracked record, a `"? "` prefix followed
        by the path.
    :returns: The parsed change, with both index and worktree status
        set to :attr:`GitChangeStatus.UNTRACKED`.
    :raises ValueError: If the record is malformed or its path is
        empty.
    """

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
    """Parse one ignored path record (kind `!`).

    :param record: The full ignored record, a `"! "` prefix followed
        by the path.
    :returns: The parsed change, with both index and worktree status
        set to :attr:`GitChangeStatus.IGNORED`.
    :raises ValueError: If the record is malformed or its path is
        empty.
    """

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
    """Parse a porcelain record containing only a kind and path.

    :param record: The full record text.
    :param prefix: The expected leading kind marker (e.g. `"? "`).
    :param kind: A human-readable name for this record kind, used only
        to phrase any raised error message.
    :returns: The path with `prefix` stripped off.
    :raises ValueError: If `record` does not start with `prefix`, or
        the remaining path is empty.
    """

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
    """Create one normalized changed-path model.

    :param path: The (current) path of the changed entry.
    :param xy: The two-character XY status field from an ordinary or
        rename/copy porcelain-v2 record, whose first character is the
        index status and second character is the worktree status.
    :param original_path: The path this entry was renamed or copied
        from, if applicable.
    :returns: The parsed change, with `xy`'s two characters decoded
        into their respective :class:`GitChangeStatus` values.
    :raises ValueError: If `xy` is not exactly two characters long.
    """

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
    """Normalize one Git XY status character.

    :param value: One character from a porcelain-v2 XY status field.
    :returns: The matching :class:`GitChangeStatus`, or
        :attr:`GitChangeStatus.UNKNOWN` if `value` matches none of the
        recognized status characters.
    """

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