"""Diagnostic parsing for custom local COBOL compilers."""

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

_GCC_UNLOCATED_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>fatal error|error|warning|note)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_MSVC_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r"\("
    r"(?P<line>[1-9]\d*)"
    r"(?:,(?P<column>[1-9]\d*))?"
    r"\)"
    r"\s*:\s*"
    r"(?P<severity>fatal error|error|warning|note)"
    r"(?:\s+(?P<code>[^:\s]+))?"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_MSVC_UNLOCATED_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>fatal error|error|warning|note)"
    r"(?:\s+(?P<code>[^:\s]+))?"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_GCC_TRAILING_CODE_PATTERN = re.compile(
    r"\s+"
    r"\[(?P<code>[^\]]+)\]"
    r"\s*$",
)

# Editor §CompilerProcess-7: mirrors the identical generic fallback
# patterns in `gnucobol_diagnostics.py` -- every pattern above requires
# the severity token to be literally one of
# `fatal error|error|warning|note`, so a line using any other category
# word produced zero diagnostics. These are only tried after the
# format-specific closed-word-list patterns have already failed, so
# every existing recognized-severity line still resolves exactly as
# before.
_GENERIC_GCC_DIAGNOSTIC_PATTERN = re.compile(
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

_GENERIC_GCC_UNLOCATED_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>[A-Za-z]+)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_GENERIC_MSVC_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?P<source_path>.+)"
    r"\("
    r"(?P<line>[1-9]\d*)"
    r"(?:,(?P<column>[1-9]\d*))?"
    r"\)"
    r"\s*:\s*"
    r"(?P<severity>[A-Za-z]+)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)

_GENERIC_MSVC_UNLOCATED_DIAGNOSTIC_PATTERN = re.compile(
    r"^"
    r"(?:[^:]+:\s*)?"
    r"(?P<severity>[A-Za-z]+)"
    r":\s*"
    r"(?P<message>.+?)"
    r"\s*$",
    re.IGNORECASE,
)


def parse_custom_local_diagnostics(
    output: str,
    diagnostic_format: str,
) -> tuple[CompilerDiagnostic, ...]:
    """Parse compiler output using a configured diagnostic format."""

    if not isinstance(
        output,
        str,
    ):
        raise TypeError(
            "Compiler diagnostic output must be a string."
        )

    if not isinstance(
        diagnostic_format,
        str,
    ):
        raise TypeError(
            "Diagnostic format must be a string."
        )

    normalized_format = (
        diagnostic_format.strip().casefold()
    )

    if normalized_format == "none":
        return ()

    if normalized_format not in {
        "gcc",
        "msvc",
    }:
        raise ValueError(
            "Unsupported custom compiler diagnostic format: "
            f"{diagnostic_format!r}."
        )

    diagnostics: list[CompilerDiagnostic] = []

    for raw_text in output.splitlines():
        if not raw_text:
            continue

        if raw_text[0].isspace():
            continue

        if normalized_format == "gcc":
            match = (
                _GCC_COLUMN_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GCC_LINE_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GCC_UNLOCATED_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GENERIC_GCC_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GENERIC_GCC_UNLOCATED_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
            )
        else:
            match = (
                _MSVC_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _MSVC_UNLOCATED_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GENERIC_MSVC_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
                or _GENERIC_MSVC_UNLOCATED_DIAGNOSTIC_PATTERN.match(
                    raw_text,
                )
            )

        if match is None:
            continue

        severity = _parse_severity(
            match.group(
                "severity",
            )
        )

        message = match.group(
            "message",
        )
        code = match.groupdict().get(
            "code",
        )

        if normalized_format == "gcc":
            message, gcc_code = _extract_gcc_code(
                message,
            )

            if gcc_code is not None:
                code = gcc_code

        # Editor §CompilerProcess-2: mirrors the identical guard in
        # `gnucobol_diagnostics.py` -- a diagnostic-shaped line
        # truncated right after its severity prefix can match via
        # lazy-quantifier backtracking with a message that strips down
        # to empty, which would otherwise crash `CompilerDiagnostic`'s
        # own non-empty-message invariant instead of being skipped.
        if not message.strip():
            continue

        source_path_text = match.groupdict().get(
            "source_path",
        )
        line_text = match.groupdict().get(
            "line",
        )
        column_text = match.groupdict().get(
            "column",
        )

        diagnostics.append(
            CompilerDiagnostic(
                severity=severity,
                message=message,
                source_path=(
                    Path(
                        source_path_text,
                    )
                    if source_path_text is not None
                    else None
                ),
                line=(
                    int(
                        line_text,
                    )
                    if line_text is not None
                    else None
                ),
                column=(
                    int(
                        column_text,
                    )
                    if column_text is not None
                    else None
                ),
                code=code,
                raw_text=raw_text,
            )
        )

    return tuple(
        diagnostics,
    )


def _parse_severity(
    value: str,
) -> DiagnosticSeverity:
    """Translate compiler severity text to the domain model."""

    normalized_value = value.casefold()

    if normalized_value in {
        "error",
        "fatal error",
    }:
        return DiagnosticSeverity.ERROR

    if normalized_value == "warning":
        return DiagnosticSeverity.WARNING

    return DiagnosticSeverity.NOTE


def _extract_gcc_code(
    message: str,
) -> tuple[str, str | None]:
    """Separate a trailing GCC-style diagnostic code."""

    match = _GCC_TRAILING_CODE_PATTERN.search(
        message,
    )

    if match is None:
        return (
            message,
            None,
        )

    message_without_code = message[
        :match.start()
    ].rstrip()

    if not message_without_code:
        return (
            message,
            None,
        )

    return (
        message_without_code,
        match.group(
            "code",
        ),
    )