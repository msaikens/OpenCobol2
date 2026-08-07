"""Unit tests for GnuCOBOL `-t` listing parsing.

The sample text below is captured verbatim from a real `cobc -t` run
(GnuCOBOL 3.2.0) against a small fixture, including a real interleaved
error line and a real page-break/summary footer, rather than a guessed
format.
"""

from __future__ import annotations

from opencobol2.compiler.listing import (
    ListingSourceLine,
    parse_gnucobol_listing,
)


_CLEAN_LISTING = (
    "GnuCOBOL 3.2.0          hello.cbl            Fri Aug 07 2026 00:03:17  Page 0001\n"
    "\n"
    "LINE    PG/LN  A...B............................................................\n"
    "\n"
    "000001         IDENTIFICATION DIVISION.\n"
    "000002         PROGRAM-ID. HELLO.\n"
    "000003         DATA DIVISION.\n"
    "000004         WORKING-STORAGE SECTION.\n"
    '000005         01  WS-MESSAGE PIC X(20) VALUE "HELLO WORLD".\n'
    "000006         PROCEDURE DIVISION.\n"
    "000007             DISPLAY WS-MESSAGE.\n"
    "000008             STOP RUN.\n"
    "\n"
    "\n"
    "0 warnings in compilation group\n"
    "0 errors in compilation group\n"
)

_LISTING_WITH_INTERLEAVED_ERROR_AND_PAGE_BREAK = (
    "GnuCOBOL 3.2.0          err.cbl              Fri Aug 07 2026 00:05:00  Page 0001\n"
    "\n"
    "LINE    PG/LN  A...B............................................................\n"
    "\n"
    "000001         IDENTIFICATION DIVISION.\n"
    "000002         PROGRAM-ID. ERRTEST.\n"
    "000003         DATA DIVISION.\n"
    "000004         WORKING-STORAGE SECTION.\n"
    "000005         01  WS-KNOWN PIC X(20).\n"
    "000006         PROCEDURE DIVISION.\n"
    "000007             MOVE WS-UNKNOWN-NAME TO WS-KNOWN.\n"
    "error: 'WS-UNKNOWN-NAME' is not defined\n"
    "000008             STOP RUN.\n"
    "\n"
    "\n"
    "\x0cGnuCOBOL 3.2.0          err.cbl              Fri Aug 07 2026 00:05:00  Page 0002\n"
    "\n"
    "Error/Warning summary:\n"
    "\n"
    "err.cbl:7: error: 'WS-UNKNOWN-NAME' is not defined\n"
    "\n"
    "0 warnings in compilation group\n"
    "1 error in compilation group\n"
)


def test_parses_every_source_line_from_a_clean_listing() -> None:
    parsed = parse_gnucobol_listing(_CLEAN_LISTING)

    assert parsed.source_lines == (
        ListingSourceLine(line_number=1, text="       IDENTIFICATION DIVISION."),
        ListingSourceLine(line_number=2, text="       PROGRAM-ID. HELLO."),
        ListingSourceLine(line_number=3, text="       DATA DIVISION."),
        ListingSourceLine(line_number=4, text="       WORKING-STORAGE SECTION."),
        ListingSourceLine(
            line_number=5,
            text='       01  WS-MESSAGE PIC X(20) VALUE "HELLO WORLD".',
        ),
        ListingSourceLine(line_number=6, text="       PROCEDURE DIVISION."),
        ListingSourceLine(line_number=7, text="           DISPLAY WS-MESSAGE."),
        ListingSourceLine(line_number=8, text="           STOP RUN."),
    )


def test_skips_interleaved_error_lines_and_page_breaks() -> None:
    parsed = parse_gnucobol_listing(
        _LISTING_WITH_INTERLEAVED_ERROR_AND_PAGE_BREAK,
    )

    # Exactly the 8 real source lines -- not the interleaved "error:"
    # line, not either page's header, not the "Error/Warning summary:"
    # footer or its repeated diagnostic text.
    assert [line.line_number for line in parsed.source_lines] == list(
        range(1, 9),
    )
    assert parsed.source_lines[6].text == (
        "           MOVE WS-UNKNOWN-NAME TO WS-KNOWN."
    )
    assert not any(
        "error" in line.text.lower() for line in parsed.source_lines
    )


def test_empty_text_yields_no_source_lines() -> None:
    parsed = parse_gnucobol_listing("")

    assert parsed.source_lines == ()


def test_unrelated_text_yields_no_source_lines() -> None:
    parsed = parse_gnucobol_listing(
        "this is not a GnuCOBOL listing at all\njust some prose\n",
    )

    assert parsed.source_lines == ()


def test_handles_crlf_line_endings() -> None:
    crlf_listing = _CLEAN_LISTING.replace("\n", "\r\n")

    parsed = parse_gnucobol_listing(crlf_listing)

    assert len(parsed.source_lines) == 8
    assert parsed.source_lines[0].text == "       IDENTIFICATION DIVISION."
