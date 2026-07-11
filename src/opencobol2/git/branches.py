"""Parsing of Git local branch references."""

from __future__ import annotations

from opencobol2.git.models import (
    GitBranch,
)


BRANCH_FOR_EACH_REF_FORMAT = (
    "%(HEAD)\t%(refname:short)\t%(objectname)\t%(upstream:short)"
)


def parse_git_branch_for_each_ref_output(
    output: str,
) -> tuple[GitBranch, ...]:
    """Parse `git for-each-ref` branch listing output."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git branch output must be a string."
        )

    branches: list[GitBranch] = []

    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split(
            "\t",
        )

        if len(
            fields,
        ) != 4:
            raise ValueError(
                f"Invalid Git branch status line: {line!r}"
            )

        head_marker, name, head_oid, upstream = fields

        name = name.strip()
        head_oid = head_oid.strip()
        upstream = upstream.strip()

        if not name or not head_oid:
            raise ValueError(
                f"Invalid Git branch status line: {line!r}"
            )

        branches.append(
            GitBranch(
                name=name,
                head_oid=head_oid,
                is_current=(
                    head_marker.strip() == "*"
                ),
                upstream=upstream or None,
            ),
        )

    return tuple(
        branches,
    )
