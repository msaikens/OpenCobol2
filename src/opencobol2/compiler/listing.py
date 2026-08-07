"""Parsing for GnuCOBOL `-t` program listing files.

Scoped narrowly to the per-line source echo every `-t` listing contains
(a six-digit line number followed by the original source line) --
verified against real `cobc -t` output rather than assumed from
documentation. Deliberately does not parse the cross-reference/
data-item-usage tables some listings also carry further down the file;
that's materially more parsing surface than this scope covers. Errors
and warnings GnuCOBOL interleaves directly into the source-echo section
(and the page-break/summary text between pages) simply don't match the
source-line pattern below and are skipped -- diagnostics already have
their own dedicated parser, `gnucobol_diagnostics.parse_gnucobol_diagnostics`,
driven from stdout/stderr rather than the listing file.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_SOURCE_LINE_PATTERN = re.compile(r"^(\d{6})  (.*)$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ListingSourceLine:
    """One source line as GnuCOBOL echoed it into a `-t` listing."""

    line_number: int
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedListing:
    """The source lines recovered from one GnuCOBOL `-t` listing file."""

    source_lines: tuple[ListingSourceLine, ...] = ()


def parse_gnucobol_listing(text: str) -> ParsedListing:
    """Extract the source-echo lines from a GnuCOBOL `-t` listing.

    Never raises: unparseable or unexpected input (a truncated file, a
    listing from an unrelated tool) just yields fewer -- or zero --
    source lines rather than an exception, the same contract every
    other diagnostics/language parser in this codebase already follows.
    """

    source_lines: list[ListingSourceLine] = []

    for raw_line in text.splitlines():
        match = _SOURCE_LINE_PATTERN.match(raw_line)

        if match is None:
            continue

        source_lines.append(
            ListingSourceLine(
                line_number=int(match.group(1)),
                text=match.group(2),
            )
        )

    return ParsedListing(source_lines=tuple(source_lines))
