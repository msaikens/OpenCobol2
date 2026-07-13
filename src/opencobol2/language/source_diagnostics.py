"""Runs the full lex/parse/semantic pipeline and merges every diagnostic.

A thin orchestration layer over the three independent language-service
stages, for callers (an editor overlay, a problems list) that just want
"every issue found in this source text" without caring which stage found
it -- `LexDiagnostic` and `ParseDiagnostic` already share the same shape
(`severity`/`message`/`position`), so callers can treat the merged tuple
uniformly.
"""

from __future__ import annotations

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.diagnostics import LexDiagnostic, ParseDiagnostic
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.parser import parse_cobol_tokens
from opencobol2.language.semantic import analyze_compilation_unit


def compute_source_diagnostics(
    source_text: str,
    *,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> tuple[LexDiagnostic | ParseDiagnostic, ...]:
    """Lex, parse, and semantically analyze source text, merging diagnostics.

    Never raises: a crash at any stage just truncates the diagnostic list
    there rather than breaking the editor. Parsing only runs if lexing
    didn't raise; semantic analysis only runs if parsing produced a
    compilation unit.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
    except Exception:
        return ()

    diagnostics: list[
        LexDiagnostic | ParseDiagnostic
    ] = list(
        lex_result.diagnostics,
    )

    try:
        parse_result = parse_cobol_tokens(
            lex_result,
        )
    except Exception:
        return tuple(
            diagnostics,
        )

    diagnostics.extend(
        parse_result.diagnostics,
    )

    if parse_result.unit is not None:
        try:
            semantic_result = analyze_compilation_unit(
                parse_result.unit,
            )
        except Exception:
            return tuple(
                diagnostics,
            )

        diagnostics.extend(
            semantic_result.diagnostics,
        )

    return tuple(
        diagnostics,
    )
