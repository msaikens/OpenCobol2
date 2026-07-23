"""Signature hints for GnuCOBOL intrinsic FUNCTION calls.

Scoped to intrinsic functions only. COBOL's CALL statement doesn't carry
a statically known signature from the calling side -- that would need
linkage-section analysis of the callee, which isn't modeled -- so
subprogram calls are deliberately out of scope here, the same boundary
the deeper per-verb grammar work draws elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.tokens import TokenKind


_INTRINSIC_FUNCTION_SIGNATURES: dict[str, str] = {
    "UPPER-CASE": "FUNCTION UPPER-CASE(argument)",
    "LOWER-CASE": "FUNCTION LOWER-CASE(argument)",
    "NUMVAL": "FUNCTION NUMVAL(argument)",
    "NUMVAL-C": "FUNCTION NUMVAL-C(argument [, currency-string])",
    "LENGTH": "FUNCTION LENGTH(argument)",
    "TRIM": "FUNCTION TRIM(argument [, LEADING | TRAILING])",
    "MOD": "FUNCTION MOD(argument-1, argument-2)",
    "MAX": "FUNCTION MAX(argument-1 [, argument-2] ...)",
    "MIN": "FUNCTION MIN(argument-1 [, argument-2] ...)",
    "SUM": "FUNCTION SUM(argument-1 [, argument-2] ...)",
    "CURRENT-DATE": "FUNCTION CURRENT-DATE()",
    "DATE-OF-INTEGER": "FUNCTION DATE-OF-INTEGER(argument)",
    "INTEGER-OF-DATE": "FUNCTION INTEGER-OF-DATE(argument)",
    "REVERSE": "FUNCTION REVERSE(argument)",
    "CONCATENATE": "FUNCTION CONCATENATE(argument-1, argument-2 ...)",
    "RANDOM": "FUNCTION RANDOM([argument])",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class SignatureHelp:
    """A one-line signature hint for the FUNCTION call the cursor is inside."""

    name: str
    signature: str


def compute_signature_help(
    source_text: str,
    *,
    line: int,
    column: int,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> SignatureHelp | None:
    """Describe the intrinsic FUNCTION call whose parentheses the cursor is inside.

    Never raises: any failure just returns `None` rather than breaking
    the editor. Only recognizes documented intrinsic functions -- an
    undocumented one yields no signature help, same policy as
    Documentation lookup.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
    except Exception:
        return None

    tokens = lex_result.tokens

    for index, token in enumerate(tokens):
        if (
            token.kind is not TokenKind.RESERVED_WORD
            or token.text.upper() != "FUNCTION"
        ):
            continue

        if index + 2 >= len(tokens):
            continue

        name_token = tokens[index + 1]
        open_paren = tokens[index + 2]

        if (
            open_paren.kind
            is not TokenKind.LEFT_PARENTHESIS
        ):
            continue

        close_paren = _find_matching_close_paren(
            tokens,
            index + 3,
        )

        if close_paren is None:
            continue

        if not _position_between(
            open_paren.span.end,
            close_paren.span.start,
            line,
            column,
        ):
            continue

        signature = _INTRINSIC_FUNCTION_SIGNATURES.get(
            name_token.text.upper(),
        )

        if signature is None:
            return None

        return SignatureHelp(
            name=name_token.text,
            signature=signature,
        )

    return None


def _find_matching_close_paren(
    tokens,
    start_index: int,
):
    depth = 1

    for index in range(
        start_index,
        len(tokens),
    ):
        if (
            tokens[index].kind
            is TokenKind.LEFT_PARENTHESIS
        ):
            depth += 1
        elif (
            tokens[index].kind
            is TokenKind.RIGHT_PARENTHESIS
        ):
            depth -= 1

            if depth == 0:
                return tokens[index]

    return None


def _position_between(
    start,
    end,
    line: int,
    column: int,
) -> bool:
    position = (
        line,
        column,
    )

    return (
        position
        >= (
            start.line,
            start.column,
        )
        and position
        <= (
            end.line,
            end.column,
        )
    )
