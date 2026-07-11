"""Parsing of Git remote configuration."""

from __future__ import annotations

from opencobol2.git.models import (
    GitRemote,
)


def parse_git_remote_v_output(
    output: str,
) -> tuple[GitRemote, ...]:
    """Parse `git remote -v` output into ordered remote configurations."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Git remote output must be a string."
        )

    order: list[str] = []
    fetch_urls: dict[str, str] = {}
    push_urls: dict[str, str] = {}

    for line in output.splitlines():
        if not line.strip():
            continue

        name, _, remainder = line.partition(
            "\t",
        )
        name = name.strip()
        remainder = remainder.strip()

        if not name or not remainder:
            raise ValueError(
                f"Invalid Git remote status line: {line!r}"
            )

        url, _, kind = remainder.rpartition(
            " ",
        )
        url = url.strip()
        kind = kind.strip(
            "()",
        )

        if (
            not url
            or kind not in (
                "fetch",
                "push",
            )
        ):
            raise ValueError(
                f"Invalid Git remote status line: {line!r}"
            )

        if name not in order:
            order.append(
                name,
            )

        if kind == "fetch":
            fetch_urls[name] = url
        else:
            push_urls[name] = url

    remotes: list[GitRemote] = []

    for name in order:
        fetch_url = (
            fetch_urls.get(name)
            or push_urls.get(name)
        )
        push_url = (
            push_urls.get(name)
            or fetch_urls.get(name)
        )

        remotes.append(
            GitRemote(
                name=name,
                fetch_url=fetch_url,
                push_url=push_url,
            ),
        )

    return tuple(
        remotes,
    )
