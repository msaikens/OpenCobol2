"""Parsing of Git commit history."""

from __future__ import annotations

from opencobol2.git.models import (
    GitCommitLogEntry,
)


LOG_FIELD_SEPARATOR = "\x1f"
LOG_RECORD_SEPARATOR = "\x1e"

LOG_FORMAT = (
    "%H"
    f"{LOG_FIELD_SEPARATOR}%P"
    f"{LOG_FIELD_SEPARATOR}%an"
    f"{LOG_FIELD_SEPARATOR}%ae"
    f"{LOG_FIELD_SEPARATOR}%aI"
    f"{LOG_FIELD_SEPARATOR}%cn"
    f"{LOG_FIELD_SEPARATOR}%ce"
    f"{LOG_FIELD_SEPARATOR}%cI"
    f"{LOG_FIELD_SEPARATOR}%s"
    f"{LOG_FIELD_SEPARATOR}%b"
    f"{LOG_RECORD_SEPARATOR}"
)

_EXPECTED_FIELD_COUNT = 10


def parse_git_log_output(
    output: str,
) -> tuple[GitCommitLogEntry, ...]:
    """Parse `git log` output produced with `LOG_FORMAT`."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git log output must be a string."
        )

    if not output:
        return ()

    entries: list[GitCommitLogEntry] = []
    raw_segments = output.split(
        LOG_RECORD_SEPARATOR,
    )

    for index, raw_segment in enumerate(
        raw_segments,
    ):
        segment = (
            raw_segment.removeprefix(
                "\n",
            )
            if index > 0
            else raw_segment
        )

        if not segment:
            continue

        fields = segment.split(
            LOG_FIELD_SEPARATOR,
        )

        if len(
            fields,
        ) != _EXPECTED_FIELD_COUNT:
            raise ValueError(
                f"Invalid Git log record: {raw_segment!r}"
            )

        (
            commit_oid,
            parents_raw,
            author_name,
            author_email,
            authored_at,
            committer_name,
            committer_email,
            committed_at,
            subject,
            body,
        ) = fields

        parent_oids = tuple(
            parent_oid
            for parent_oid in parents_raw.split(
                " ",
            )
            if parent_oid
        )

        entries.append(
            GitCommitLogEntry(
                commit_oid=commit_oid,
                parent_oids=parent_oids,
                author_name=author_name,
                author_email=author_email,
                authored_at=authored_at,
                committer_name=committer_name,
                committer_email=committer_email,
                committed_at=committed_at,
                subject=subject,
                body=body,
            ),
        )

    return tuple(
        entries,
    )
