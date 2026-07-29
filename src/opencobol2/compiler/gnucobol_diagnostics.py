"""Parsing for textual GnuCOBOL compiler diagnostics."""

from __future__ import annotations

from pathlib import Path
import re

from opencobol2.compiler.diagnostics import (
    CompilerDiagnostic,
    DiagnosticSeverity,
)


_GCC_COLUMN_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r":(?P<line>[1-9]\d*)"
    r":(?P<column>[1-9]\d*)"
    r":\s*"
    r"(?P<severity>fatal error|error|warning|note)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_GCC_LINE_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r":(?P<line>[1-9]\d*)"
    r":\s*"
    r"(?P<severity>fatal error|error|warning|note)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_MSC_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r"\("
    r"(?P<line>[1-9]\d*)"
    r"(?:,(?P<column>[1-9]\d*))?"
    r"\)"
    r"\s*:\s*"
    r"(?P<severity>fatal error|error|warning|note)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_UNLOCATED_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>fatal error|error|warning|note)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

# Editor §CompilerProcess-7: every pattern above requires the severity
# token to be literally one of `fatal error|error|warning|note` -- a
# line using any other category word (e.g. a hypothetical `info:`
# line) matched none of them and produced zero diagnostics, not even a
# downgraded/miscategorized one. These two generic patterns are tried
# only after all four closed-word-list patterns above have already
# failed to match, so every existing recognized-severity line still
# resolves exactly as before; only a line with a genuinely novel
# severity word falls through to here, where `_parse_severity` already
# maps anything unrecognized to `DiagnosticSeverity.NOTE`.
_GENERIC_CATEGORY_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r":(?P<line>[1-9]\d*)"
    r"(?::(?P<column>[1-9]\d*))?"
    r":\s*"
    r"(?P<severity>[A-Za-z]+)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_GENERIC_UNLOCATED_CATEGORY_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>[A-Za-z]+)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_WARNING_CODE_PATTERN = re.compile(
    r"\s+"
    r"\[(?P<code>-W[^\]]+)\]"
    r"\s*$",
)


def parse_gnucobol_diagnostics(
    output: str,
) -> tuple[CompilerDiagnostic, ...]:
    """Parse structured diagnostics from textual GnuCOBOL output."""
    diagnostics: list[CompilerDiagnostic] = []

    for raw_text in output.splitlines():
        if not raw_text:
            continue

        if raw_text[0].isspace():
            continue

        match = (
            _GCC_COLUMN_DIAGNOSTIC_PATTERN.match(raw_text)
            or _GCC_LINE_DIAGNOSTIC_PATTERN.match(raw_text)
            or _MSC_DIAGNOSTIC_PATTERN.match(raw_text)
            or _UNLOCATED_DIAGNOSTIC_PATTERN.match(raw_text)
            or _GENERIC_CATEGORY_DIAGNOSTIC_PATTERN.match(raw_text)
            or _GENERIC_UNLOCATED_CATEGORY_DIAGNOSTIC_PATTERN.match(
                raw_text,
            )
        )

        if match is None:
            continue

        severity = _parse_severity(
            match.group("severity"),
        )

        message, code = _extract_warning_code(
            match.group("message"),
            severity,
        )

        # Editor §CompilerProcess-2: a diagnostic-shaped line truncated
        # right after its `: severity:` prefix can still match one of
        # the patterns above via lazy-quantifier backtracking, capturing
        # a single leftover whitespace character as the "message" --
        # which then strips down to empty. Constructing a
        # `CompilerDiagnostic` from that would raise `ValueError` from
        # its own non-empty-message invariant, uncaught, crashing a
        # compile that timed out mid-output instead of returning the
        # `TIMED_OUT` result every other timeout produces. Skip rather
        # than emit a diagnostic that can't be built.
        if not message.strip():
            continue

        source_path_text = match.groupdict().get(
            "source_path"
        )
        line_text = match.groupdict().get("line")
        column_text = match.groupdict().get("column")

        diagnostics.append(
            CompilerDiagnostic(
                severity=severity,
                message=message,
                source_path=(
                    Path(source_path_text)
                    if source_path_text is not None
                    else None
                ),
                line=(
                    int(line_text)
                    if line_text is not None
                    else None
                ),
                column=(
                    int(column_text)
                    if column_text is not None
                    else None
                ),
                code=code,
                raw_text=raw_text,
            )
        )

    return tuple(diagnostics)


def _parse_severity(
    value: str,
) -> DiagnosticSeverity:
    """Translate a compiler severity label into the domain model."""
    normalized_value = value.casefold()

    if normalized_value in {
        "error",
        "fatal error",
    }:
        return DiagnosticSeverity.ERROR

    if normalized_value == "warning":
        return DiagnosticSeverity.WARNING

    return DiagnosticSeverity.NOTE


def _extract_warning_code(
    message: str,
    severity: DiagnosticSeverity,
) -> tuple[str, str | None]:
    """Separate a trailing GnuCOBOL warning option from its message.

    Editor §CompilerProcess-4: this used to only run for
    `WARNING`-severity diagnostics, but real GnuCOBOL 3.2.0 also emits
    the same trailing `[-Wxxx]` marker on the `note:` lines that
    accompany a warning -- verified against a real `cobc -Wall` build.
    `custom_local_diagnostics.py`'s equivalent helper already strips
    this for every severity uniformly; this now matches it rather than
    leaving the bracket glued onto every GnuCOBOL-parsed note's message
    with `code` left as `None`.
    """
    if severity not in (
        DiagnosticSeverity.WARNING,
        DiagnosticSeverity.NOTE,
    ):
        return message, None

    match = _WARNING_CODE_PATTERN.search(message)

    if match is None:
        return message, None

    message_without_code = message[
        :match.start()
    ].rstrip()

    if not message_without_code:
        return message, None

    return (
        message_without_code,
        match.group("code"),
    )