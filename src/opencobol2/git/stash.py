"""Parsing of the local Git stash list."""

from __future__ import annotations

import re

from opencobol2.git.models import (
    GitStashEntry,
)


STASH_FIELD_SEPARATOR = "\x1f"
STASH_LIST_FORMAT = f"%gd{STASH_FIELD_SEPARATOR}%H{STASH_FIELD_SEPARATOR}%s"

_STASH_INDEX_PATTERN = re.compile(
    r"^stash@\{(\d+)\}$",
)


def parse_git_stash_list_output(
    output: str,
) -> tuple[GitStashEntry, ...]:
    """Parse `git stash list` output produced with `STASH_LIST_FORMAT`."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git stash output must be a string."
        )

    entries: list[GitStashEntry] = []

    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split(
            STASH_FIELD_SEPARATOR,
        )

        if len(
            fields,
        ) != 3:
            raise ValueError(
                f"Invalid Git stash status line: {line!r}"
            )

        selector, commit_oid, message = fields
        selector = selector.strip()
        commit_oid = commit_oid.strip()

        match = _STASH_INDEX_PATTERN.match(
            selector,
        )

        if match is None or not commit_oid:
            raise ValueError(
                f"Invalid Git stash status line: {line!r}"
            )

        entries.append(
            GitStashEntry(
                index=int(
                    match.group(1),
                ),
                commit_oid=commit_oid,
                message=message,
            ),
        )

    return tuple(
        entries,
    )
