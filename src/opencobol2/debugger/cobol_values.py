"""Decoding raw GnuCOBOL-compiled memory bytes into COBOL variable values.

GnuCOBOL stores every data item as a plain byte buffer with no
runtime type information a debugger can introspect on its own -- the
byte *layout* is entirely determined by the item's PICTURE clause and
USAGE, which this codebase already parses from source (see
`opencobol2.language`). This module decodes raw bytes read from a live
debug session back into a human-readable value, given that PICTURE/
USAGE information.

Every encoding rule below was verified against real bytes read from a
real `cobc`-compiled, `gdb`-inspected program -- not assumed from
documentation:

* DISPLAY (the default, no USAGE clause): plain ASCII digit
  characters, one byte per digit, with the decimal point purely
  implied by the PICTURE's `V` position (never stored). A signed
  field's *last* character may be an "overpunch": lowercase `p`-`y`
  in place of digits `0`-`9` marks the value negative (`004r` decodes
  as `-42`); an ordinary digit there means positive. GnuCOBOL was not
  observed emitting a distinct positive-overpunch character, so a
  positive sign never changes the character.
* COMP-3 / PACKED-DECIMAL: standard packed BCD -- two decimal digits
  per byte, with the final nibble a sign flag (`0xC`/`0xF` positive,
  `0xD`/`0xB` negative) rather than a digit.
* BINARY (plain, no COMP-5): a big-endian two's-complement integer.
* COMP-5: a *native* binary integer -- little-endian on the x86_64
  hosts this codebase targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DataUsage(StrEnum):
    """How a COBOL data item's bytes are laid out in memory."""

    DISPLAY = "display"
    COMP_3 = "comp-3"
    COMP_5 = "comp-5"
    BINARY = "binary"
    UNSUPPORTED = "unsupported"


_USAGE_CLAUSE_KEYWORDS = {
    "DISPLAY": DataUsage.DISPLAY,
    "COMP-3": DataUsage.COMP_3,
    "COMPUTATIONAL-3": DataUsage.COMP_3,
    "PACKED-DECIMAL": DataUsage.COMP_3,
    "COMP-5": DataUsage.COMP_5,
    "COMPUTATIONAL-5": DataUsage.COMP_5,
    "COMP": DataUsage.BINARY,
    "COMPUTATIONAL": DataUsage.BINARY,
    "COMP-4": DataUsage.BINARY,
    "COMPUTATIONAL-4": DataUsage.BINARY,
    "BINARY": DataUsage.BINARY,
    # Floating point -- not modeled (would need IEEE-754 decoding this
    # codebase hasn't verified against real GnuCOBOL output). Mapped
    # explicitly to UNSUPPORTED rather than left to fall through to the
    # DISPLAY default, since silently decoding float bytes as ASCII
    # digits would produce plausible-looking garbage instead of an
    # honest "can't decode this" result.
    "COMP-1": DataUsage.UNSUPPORTED,
    "COMPUTATIONAL-1": DataUsage.UNSUPPORTED,
    "COMP-2": DataUsage.UNSUPPORTED,
    "COMPUTATIONAL-2": DataUsage.UNSUPPORTED,
}


def usage_from_clause_keyword(
    keyword: str | None,
) -> DataUsage:
    """Map a data description clause keyword (e.g. `"COMP-3"`) to a `DataUsage`.

    Defaults to `DISPLAY`, COBOL's own implicit default when no USAGE
    clause is present.
    """

    if keyword is None:
        return DataUsage.DISPLAY

    return _USAGE_CLAUSE_KEYWORDS.get(
        keyword.upper(),
        DataUsage.DISPLAY,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class PictureSpec:
    """The shape of a PICTURE clause needed to decode its raw bytes.

    `is_numeric` is `False` for alphanumeric (`X`/`A`) pictures, in
    which case the other fields are meaningless and the raw bytes
    decode as plain text instead.
    """

    is_numeric: bool
    total_digits: int = 0
    scale: int = 0
    is_signed: bool = False


_ALPHANUMERIC_SYMBOLS = frozenset(
    "XA",
)
_DIGIT_SYMBOLS = frozenset(
    "9Z",
)
_REPEATABLE_SYMBOLS = (
    _ALPHANUMERIC_SYMBOLS
    | _DIGIT_SYMBOLS
    | frozenset(
        "*+-.",
    )
)


def parse_picture_spec(
    pic_text: str,
) -> PictureSpec:
    """Parse a rendered PIC clause (e.g. `"PIC 9(5)V99"`) into a `PictureSpec`.

    Deliberately narrow: only tracks what's needed to decode a raw
    byte buffer back into a value (digit counts, decimal scale, sign)
    -- not full picture-editing symbols like `Z`/`*`/`+` suppression,
    which only matter for *display formatting*, not value decoding.
    """

    text = pic_text.strip().upper()

    for prefix in (
        "PICTURE",
        "PIC",
    ):
        if text.startswith(
            prefix,
        ):
            text = text[
                len(
                    prefix,
                ) :
            ].strip()
            break

    is_signed = False
    integer_digits = 0
    fractional_digits = 0
    in_fraction = False
    is_alphanumeric = False
    saw_a_digit_symbol = False

    index = 0

    while index < len(
        text,
    ):
        char = text[index]

        if char in " ,":
            index += 1
            continue

        if char == "S":
            is_signed = True
            index += 1
            continue

        if char == "V":
            in_fraction = True
            index += 1
            continue

        if char in _REPEATABLE_SYMBOLS:
            index += 1
            count = 1

            if (
                index < len(text)
                and text[index] == "("
            ):
                close_index = text.find(
                    ")",
                    index,
                )

                if close_index == -1:
                    break

                count = int(
                    text[
                        index
                        + 1 : close_index
                    ],
                )
                index = close_index + 1

            if char in _ALPHANUMERIC_SYMBOLS:
                is_alphanumeric = True
            elif char in _DIGIT_SYMBOLS:
                saw_a_digit_symbol = True

                if in_fraction:
                    fractional_digits += (
                        count
                    )
                else:
                    integer_digits += count

            continue

        index += 1

    if (
        is_alphanumeric
        or not saw_a_digit_symbol
    ):
        return PictureSpec(
            is_numeric=False,
        )

    return PictureSpec(
        is_numeric=True,
        total_digits=(
            integer_digits
            + fractional_digits
        ),
        scale=fractional_digits,
        is_signed=is_signed,
    )


_NEGATIVE_OVERPUNCH_DIGITS = {
    chr(
        ord(
            "p",
        )
        + digit,
    ): digit
    for digit in range(
        10,
    )
}


def decode_field_value(
    raw_bytes: bytes,
    *,
    picture: PictureSpec,
    usage: DataUsage,
) -> str:
    """Decode a raw byte buffer into a human-readable value.

    Returns alphanumeric fields as plain trimmed text. Numeric fields
    are decoded per `usage`; `DataUsage.UNSUPPORTED` (floating point)
    falls back to a hex dump rather than guessing.
    """

    if not picture.is_numeric:
        return raw_bytes.decode(
            "ascii",
            errors="replace",
        ).rstrip()

    if usage is DataUsage.DISPLAY:
        return _decode_display_numeric(
            raw_bytes,
            picture,
        )

    if usage is DataUsage.COMP_3:
        return _decode_packed_decimal(
            raw_bytes,
            picture,
        )

    if usage in (
        DataUsage.BINARY,
        DataUsage.COMP_5,
    ):
        return _decode_binary(
            raw_bytes,
            picture,
            usage=usage,
        )

    return raw_bytes.hex()


def _apply_scale(
    digit_text: str,
    *,
    scale: int,
    is_negative: bool,
) -> str:
    if scale > 0:
        integer_part = (
            digit_text[:-scale] or "0"
        )
        fractional_part = digit_text[
            -scale:
        ]
        value_text = (
            f"{integer_part}."
            f"{fractional_part}"
        )
    else:
        value_text = digit_text

    return (
        f"-{value_text}"
        if is_negative
        else value_text
    )


def _decode_display_numeric(
    raw_bytes: bytes,
    picture: PictureSpec,
) -> str:
    text = raw_bytes.decode(
        "ascii",
        errors="replace",
    )
    is_negative = False

    if text:
        last_character = text[-1]
        overpunch_digit = (
            _NEGATIVE_OVERPUNCH_DIGITS.get(
                last_character,
            )
        )

        if overpunch_digit is not None:
            is_negative = True
            text = (
                text[:-1]
                + str(
                    overpunch_digit,
                )
            )

    return _apply_scale(
        text,
        scale=picture.scale,
        is_negative=is_negative,
    )


def _decode_packed_decimal(
    raw_bytes: bytes,
    picture: PictureSpec,
) -> str:
    nibbles: list[int] = []

    for byte in raw_bytes:
        nibbles.append(
            (byte >> 4) & 0xF,
        )
        nibbles.append(
            byte & 0xF,
        )

    sign_nibble = nibbles[-1]
    digit_nibbles = nibbles[:-1]

    if picture.total_digits > 0:
        digit_nibbles = digit_nibbles[
            -picture.total_digits :
        ]

    digit_text = "".join(
        str(nibble)
        for nibble in digit_nibbles
    )
    is_negative = sign_nibble in (
        0xD,
        0xB,
    )

    return _apply_scale(
        digit_text,
        scale=picture.scale,
        is_negative=is_negative,
    )


def _decode_binary(
    raw_bytes: bytes,
    picture: PictureSpec,
    *,
    usage: DataUsage,
) -> str:
    byte_order = (
        "little"
        if usage is DataUsage.COMP_5
        else "big"
    )
    value = int.from_bytes(
        raw_bytes,
        byte_order,
        signed=picture.is_signed,
    )
    is_negative = value < 0
    digit_text = str(
        abs(
            value,
        ),
    ).rjust(
        picture.total_digits,
        "0",
    )

    return _apply_scale(
        digit_text,
        scale=picture.scale,
        is_negative=is_negative,
    )
