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
    """A one-line signature hint for the FUNCTION call the cursor is inside.

    :ivar name: The intrinsic function's name, exactly as written at the
        call site (original casing preserved).
    :ivar signature: The formatted signature string to display, e.g.
        ``"FUNCTION TRIM(argument [, LEADING | TRAILING])"``.
    """

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

    Per Editor §Editor-Facing-3, tokens are scanned in source order but
    the search deliberately does not return on the first match: scanning
    in source order and stopping at the first match would always pick
    the outermost FUNCTION call, since an outer call's parentheses fully
    enclose any nested call's. Instead, every candidate whose range
    contains the cursor is considered, and the last match wins --
    necessarily the most deeply nested one, since a later match can only
    exist if it lies inside an earlier, containing match. Because of the
    Editor §Editor-Facing-6 handling described below, a signature-bearing
    candidate can still turn out to have no known signature; that case
    uses `continue` rather than returning `None` outright, so a more
    specific known inner call can still be found even when an outer or
    unrecognized wrapper isn't.

    Per Editor §Editor-Facing-6, an unclosed call -- the user is still
    typing its argument list, which is exactly when signature help is
    most useful -- must not be treated as no match at all. When no
    matching close paren is found, only the lower bound (the position
    just after the open paren) is checked against the cursor, since
    there's no upper bound to test against.

    :param source_text: The complete COBOL source text to analyze.
    :param line: The 1-based line of the cursor position to describe.
    :param column: The 1-based column of the cursor position to
        describe.
    :param source_format: Whether `source_text` is fixed-format or
        free-format COBOL. Defaults to :attr:`CobolSourceFormat.FIXED`.
    :returns: The signature help for the innermost enclosing intrinsic
        FUNCTION call, or `None` if the cursor isn't inside a recognized
        call, or if lexing raised.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
    except Exception:
        return None

    tokens = lex_result.tokens
    best: SignatureHelp | None = None

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
            if not _position_at_or_after(
                open_paren.span.end,
                line,
                column,
            ):
                continue
        elif not _position_between(
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
            continue

        best = SignatureHelp(
            name=name_token.text,
            signature=signature,
        )

    return best


def _find_matching_close_paren(
    tokens,
    start_index: int,
):
    """Find the close parenthesis that matches an already-opened one.

    :param tokens: The full token sequence to scan.
    :param start_index: The index to begin scanning from, i.e. the
        index just after the open parenthesis whose match is sought.
    :returns: The matching :class:`~opencobol2.language.tokens.Token`
        for the right parenthesis, accounting for nested parentheses
        in between, or `None` if the tokens run out before the
        nesting depth returns to zero.
    """

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
    """Check whether a line/column position lies within a span, inclusive.

    :param start: The span's start position, exposing `line` and
        `column` attributes.
    :param end: The span's end position, exposing `line` and `column`
        attributes.
    :param line: The 1-based line of the position to test.
    :param column: The 1-based column of the position to test.
    :returns: `True` if `(line, column)` is between `start` and `end`,
        inclusive of both endpoints; `False` otherwise.
    """

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


def _position_at_or_after(
    start,
    line: int,
    column: int,
) -> bool:
    """Check whether a line/column position is at or after a given position.

    :param start: The reference position, exposing `line` and `column`
        attributes.
    :param line: The 1-based line of the position to test.
    :param column: The 1-based column of the position to test.
    :returns: `True` if `(line, column)` is equal to or after `start`;
        `False` otherwise.
    """

    return (
        line,
        column,
    ) >= (
        start.line,
        start.column,
    )
