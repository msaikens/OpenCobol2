"""Unit tests for decoding raw GnuCOBOL memory bytes into COBOL values.

Every byte fixture below was read directly from a real `cobc`-compiled,
real-`gdb`-inspected program (via `-data-read-memory-bytes`), not
hand-guessed -- see the encoding rules documented in
`opencobol2.debugger.cobol_values` for how each was independently
verified (packed-decimal sign nibbles, sign-overpunch characters,
COMP-5 vs. BINARY byte order).
"""

from __future__ import annotations

from opencobol2.debugger.cobol_values import (
    DataUsage,
    decode_field_value,
    parse_picture_spec,
    usage_from_clause_keyword,
)


def test_parse_picture_spec_unsigned_integer() -> None:
    spec = parse_picture_spec(
        "PIC 9(4)",
    )

    assert spec.is_numeric is True
    assert spec.total_digits == 4
    assert spec.scale == 0
    assert spec.is_signed is False


def test_parse_picture_spec_signed_integer() -> None:
    spec = parse_picture_spec(
        "PIC S9(4)",
    )

    assert spec.is_signed is True
    assert spec.total_digits == 4


def test_parse_picture_spec_with_decimal_scale() -> None:
    spec = parse_picture_spec(
        "PIC 9(5)V99",
    )

    assert spec.total_digits == 7
    assert spec.scale == 2
    assert spec.is_signed is False


def test_parse_picture_spec_signed_with_scale() -> None:
    spec = parse_picture_spec(
        "PIC S9(5)V99",
    )

    assert spec.total_digits == 7
    assert spec.scale == 2
    assert spec.is_signed is True


def test_parse_picture_spec_alphanumeric_is_not_numeric() -> None:
    spec = parse_picture_spec(
        "PIC X(10)",
    )

    assert spec.is_numeric is False


def test_parse_picture_spec_accepts_picture_keyword_spelled_out() -> None:
    spec = parse_picture_spec(
        "PICTURE 9(3)",
    )

    assert spec.is_numeric is True
    assert spec.total_digits == 3


def test_usage_from_clause_keyword_defaults_to_display() -> None:
    assert (
        usage_from_clause_keyword(
            None,
        )
        is DataUsage.DISPLAY
    )
    assert (
        usage_from_clause_keyword(
            "DISPLAY",
        )
        is DataUsage.DISPLAY
    )


def test_usage_from_clause_keyword_recognizes_comp3_variants() -> None:
    assert (
        usage_from_clause_keyword(
            "COMP-3",
        )
        is DataUsage.COMP_3
    )
    assert (
        usage_from_clause_keyword(
            "PACKED-DECIMAL",
        )
        is DataUsage.COMP_3
    )


def test_usage_from_clause_keyword_recognizes_comp5() -> None:
    assert (
        usage_from_clause_keyword(
            "COMP-5",
        )
        is DataUsage.COMP_5
    )


def test_usage_from_clause_keyword_recognizes_binary_variants() -> None:
    assert (
        usage_from_clause_keyword(
            "BINARY",
        )
        is DataUsage.BINARY
    )
    assert (
        usage_from_clause_keyword(
            "COMP",
        )
        is DataUsage.BINARY
    )


def test_decode_display_unsigned_positive() -> None:
    # Real bytes for PIC S9(4) VALUE 42 -> "0042".
    value = decode_field_value(
        b"0042",
        picture=parse_picture_spec(
            "PIC S9(4)",
        ),
        usage=DataUsage.DISPLAY,
    )

    assert value == "0042"


def test_decode_display_signed_negative_overpunch() -> None:
    # Real bytes for PIC S9(4) VALUE -42 -> "004r" (sign-overpunch).
    value = decode_field_value(
        b"004r",
        picture=parse_picture_spec(
            "PIC S9(4)",
        ),
        usage=DataUsage.DISPLAY,
    )

    assert value == "-0042"


def test_decode_display_negative_overpunch_digit_nine() -> None:
    # Real bytes for PIC S9(4) VALUE -9 -> "000y".
    value = decode_field_value(
        b"000y",
        picture=parse_picture_spec(
            "PIC S9(4)",
        ),
        usage=DataUsage.DISPLAY,
    )

    assert value == "-0009"


def test_decode_display_with_scale() -> None:
    # Real bytes for PIC 9(5)V99 VALUE 123.45 -> "0012345".
    value = decode_field_value(
        b"0012345",
        picture=parse_picture_spec(
            "PIC 9(5)V99",
        ),
        usage=DataUsage.DISPLAY,
    )

    assert value == "00123.45"


def test_decode_alphanumeric_trims_trailing_padding() -> None:
    value = decode_field_value(
        b"HELLO     ",
        picture=parse_picture_spec(
            "PIC X(10)",
        ),
        usage=DataUsage.DISPLAY,
    )

    assert value == "HELLO"


def test_decode_packed_decimal_positive() -> None:
    # Real bytes for PIC S9(5)V99 COMP-3 VALUE 123.45 -> 0x0012345c.
    value = decode_field_value(
        bytes.fromhex(
            "0012345c",
        ),
        picture=parse_picture_spec(
            "PIC S9(5)V99",
        ),
        usage=DataUsage.COMP_3,
    )

    assert value == "00123.45"


def test_decode_packed_decimal_negative() -> None:
    # Real bytes for PIC S9(5)V99 COMP-3 VALUE -123.45 -> 0x0012345d.
    value = decode_field_value(
        bytes.fromhex(
            "0012345d",
        ),
        picture=parse_picture_spec(
            "PIC S9(5)V99",
        ),
        usage=DataUsage.COMP_3,
    )

    assert value == "-00123.45"


def test_decode_comp5_little_endian() -> None:
    # Real bytes for PIC 9(4) COMP-5 VALUE 4660 -> 0x3412 (little-endian).
    value = decode_field_value(
        bytes.fromhex(
            "3412",
        ),
        picture=parse_picture_spec(
            "PIC 9(4)",
        ),
        usage=DataUsage.COMP_5,
    )

    assert value == "4660"


def test_decode_binary_big_endian() -> None:
    # BINARY (plain, non-COMP-5) is big-endian: verified via the
    # modular-truncation cobc applies to an out-of-range literal --
    # 305419896 (0x12345678) into PIC 9(8) truncated to 8 digits
    # (mod 10**8 = 5419896), and 5419896.to_bytes(4, "big") is exactly
    # the real bytes cobc/gdb produced (0x0052b378).
    value = decode_field_value(
        bytes.fromhex(
            "0052b378",
        ),
        picture=parse_picture_spec(
            "PIC 9(8)",
        ),
        usage=DataUsage.BINARY,
    )

    assert value == "05419896"


def test_usage_from_clause_keyword_maps_floating_point_to_unsupported() -> (
    None
):
    assert (
        usage_from_clause_keyword(
            "COMP-1",
        )
        is DataUsage.UNSUPPORTED
    )
    assert (
        usage_from_clause_keyword(
            "COMP-2",
        )
        is DataUsage.UNSUPPORTED
    )


def test_decode_field_value_unsupported_usage_falls_back_to_hex() -> None:
    value = decode_field_value(
        b"\x01\x02",
        picture=parse_picture_spec(
            "PIC 9(4)",
        ),
        usage=DataUsage.UNSUPPORTED,
    )

    assert value == "0102"
