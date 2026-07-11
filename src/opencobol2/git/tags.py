"""Parsing of Git tag references."""

from __future__ import annotations

from opencobol2.git.models import (
    GitTag,
)


TAG_FOR_EACH_REF_FORMAT = (
    "%(objecttype)\t%(refname:short)\t%(objectname)"
)


def parse_git_tag_for_each_ref_output(
    output: str,
) -> tuple[GitTag, ...]:
    """Parse `git for-each-ref` tag listing output."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git tag output must be a string."
        )

    tags: list[GitTag] = []

    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split(
            "\t",
        )

        if len(
            fields,
        ) != 3:
            raise ValueError(
                f"Invalid Git tag status line: {line!r}"
            )

        object_type, name, target_oid = fields

        object_type = object_type.strip()
        name = name.strip()
        target_oid = target_oid.strip()

        if not name or not target_oid:
            raise ValueError(
                f"Invalid Git tag status line: {line!r}"
            )

        tags.append(
            GitTag(
                name=name,
                target_oid=target_oid,
                annotated=(
                    object_type == "tag"
                ),
            ),
        )

    return tuple(
        tags,
    )
