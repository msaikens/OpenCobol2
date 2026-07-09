"""Text document domain models."""

from __future__ import annotations

import codecs
from enum import Enum, StrEnum
from pathlib import Path


class LineEnding(StrEnum):
    """Describes a text document's on-disk line-ending convention."""

    LF = "\n"
    CRLF = "\r\n"
    CR = "\r"


class ByteOrderMark(Enum):
    """Describes an explicit Unicode byte-order mark or signature."""

    UTF8 = codecs.BOM_UTF8
    UTF16_LE = codecs.BOM_UTF16_LE
    UTF16_BE = codecs.BOM_UTF16_BE
    UTF32_LE = codecs.BOM_UTF32_LE
    UTF32_BE = codecs.BOM_UTF32_BE

    @property
    def bytes(self) -> bytes:
        """Return the raw byte sequence for the mark."""
        return self.value


_BOM_ENCODINGS = {
    ByteOrderMark.UTF8: "utf-8",
    ByteOrderMark.UTF16_LE: "utf-16-le",
    ByteOrderMark.UTF16_BE: "utf-16-be",
    ByteOrderMark.UTF32_LE: "utf-32-le",
    ByteOrderMark.UTF32_BE: "utf-32-be",
}


class TextDocument:
    """Represents the editable state of one plain-text document."""

    __slots__ = (
        "_path",
        "_text",
        "_encoding",
        "_line_ending",
        "_byte_order_mark",
        "_saved_state",
    )

    def __init__(
        self,
        *,
        text: str,
        path: Path | str | None = None,
        encoding: str = "utf-8",
        line_ending: LineEnding | str = LineEnding.LF,
        byte_order_mark: ByteOrderMark | bytes | None = None,
    ) -> None:
        normalized_encoding, implied_bom = (
            _normalize_encoding_configuration(
                encoding,
            )
        )

        normalized_bom = _normalize_byte_order_mark(
            byte_order_mark,
        )

        if implied_bom is not None:
            if (
                normalized_bom is not None
                and normalized_bom is not implied_bom
            ):
                raise ValueError(
                    "Document encoding and byte-order mark "
                    "are incompatible."
                )

            normalized_bom = implied_bom

        _validate_bom_encoding(
            normalized_encoding,
            normalized_bom,
        )

        self._path = (
            Path(path)
            if path is not None
            else None
        )
        self._text = _normalize_internal_newlines(text)
        self._encoding = normalized_encoding
        self._line_ending = LineEnding(line_ending)
        self._byte_order_mark = normalized_bom
        self._saved_state = self._current_state()

    @property
    def path(self) -> Path | None:
        """Return the document's filesystem path, when assigned."""
        return self._path

    @property
    def text(self) -> str:
        """Return the document text using internal LF line separators."""
        return self._text

    @property
    def encoding(self) -> str:
        """Return the normalized text encoding name."""
        return self._encoding

    @property
    def line_ending(self) -> LineEnding:
        """Return the document's preferred on-disk line ending."""
        return self._line_ending

    @property
    def byte_order_mark(self) -> ByteOrderMark | None:
        """Return the document's explicit Unicode byte-order mark."""
        return self._byte_order_mark

    @property
    def is_untitled(self) -> bool:
        """Return whether the document has no filesystem path."""
        return self._path is None

    @property
    def is_modified(self) -> bool:
        """Return whether document state differs from its saved state."""
        return self._current_state() != self._saved_state

    def replace_text(
        self,
        text: str,
    ) -> None:
        """Replace the document text."""
        self._text = _normalize_internal_newlines(text)

    def set_encoding(
        self,
        encoding: str,
    ) -> None:
        """Change the encoding used when the document is saved."""
        normalized_encoding, implied_bom = (
            _normalize_encoding_configuration(
                encoding,
            )
        )

        if implied_bom is not None:
            normalized_bom = implied_bom
        elif (
            self._byte_order_mark is not None
            and _is_compatible_bom(
                normalized_encoding,
                self._byte_order_mark,
            )
        ):
            normalized_bom = self._byte_order_mark
        else:
            normalized_bom = None

        self._encoding = normalized_encoding
        self._byte_order_mark = normalized_bom

    def set_line_ending(
        self,
        line_ending: LineEnding | str,
    ) -> None:
        """Change the line-ending convention used when saving."""
        self._line_ending = LineEnding(line_ending)

    def set_byte_order_mark(
        self,
        byte_order_mark: ByteOrderMark | bytes | None,
    ) -> None:
        """Change the Unicode byte-order mark used when saving."""
        normalized_bom = _normalize_byte_order_mark(
            byte_order_mark,
        )

        _validate_bom_encoding(
            self._encoding,
            normalized_bom,
        )

        self._byte_order_mark = normalized_bom

    def mark_saved(
        self,
        *,
        path: Path | str | None = None,
    ) -> None:
        """Record the current document state as successfully saved."""
        if path is not None:
            self._path = Path(path)

        if self._path is None:
            raise ValueError(
                "An untitled document cannot be marked saved "
                "without a path."
            )

        self._saved_state = self._current_state()

    def _current_state(
        self,
    ) -> tuple[
        str,
        str,
        LineEnding,
        ByteOrderMark | None,
    ]:
        """Return the state used for modification tracking."""
        return (
            self._text,
            self._encoding,
            self._line_ending,
            self._byte_order_mark,
        )


def _normalize_internal_newlines(
    text: str,
) -> str:
    """Normalize document text to LF separators for internal use."""
    if not isinstance(text, str):
        raise TypeError(
            "Document text must be a string."
        )

    return text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )


def _normalize_encoding_configuration(
    encoding: str,
) -> tuple[str, ByteOrderMark | None]:
    """Normalize an encoding and expand implicit Unicode BOM codecs."""
    if not isinstance(encoding, str):
        raise TypeError(
            "Document encoding must be a string."
        )

    normalized_value = encoding.strip()

    if not normalized_value:
        raise ValueError(
            "Document encoding must not be empty."
        )

    try:
        codec = codecs.lookup(
            normalized_value,
        )
    except LookupError as error:
        raise ValueError(
            f"Unknown document encoding: {encoding!r}."
        ) from error

    if codec.name == "utf-8-sig":
        return (
            "utf-8",
            ByteOrderMark.UTF8,
        )

    if codec.name == "utf-16":
        if codecs.BOM_UTF16 == codecs.BOM_UTF16_LE:
            return (
                "utf-16-le",
                ByteOrderMark.UTF16_LE,
            )

        return (
            "utf-16-be",
            ByteOrderMark.UTF16_BE,
        )

    if codec.name == "utf-32":
        if codecs.BOM_UTF32 == codecs.BOM_UTF32_LE:
            return (
                "utf-32-le",
                ByteOrderMark.UTF32_LE,
            )

        return (
            "utf-32-be",
            ByteOrderMark.UTF32_BE,
        )

    return (
        codec.name,
        None,
    )


def _normalize_byte_order_mark(
    byte_order_mark: ByteOrderMark | bytes | None,
) -> ByteOrderMark | None:
    """Normalize a byte-order mark value."""
    if byte_order_mark is None:
        return None

    if isinstance(
        byte_order_mark,
        ByteOrderMark,
    ):
        return byte_order_mark

    try:
        return ByteOrderMark(
            byte_order_mark,
        )
    except ValueError as error:
        raise ValueError(
            "Unknown Unicode byte-order mark."
        ) from error


def _is_compatible_bom(
    encoding: str,
    byte_order_mark: ByteOrderMark,
) -> bool:
    """Return whether an encoding and byte-order mark agree."""
    return (
        _BOM_ENCODINGS[byte_order_mark]
        == encoding
    )


def _validate_bom_encoding(
    encoding: str,
    byte_order_mark: ByteOrderMark | None,
) -> None:
    """Validate an encoding and explicit byte-order mark combination."""
    if byte_order_mark is None:
        return

    if not _is_compatible_bom(
        encoding,
        byte_order_mark,
    ):
        raise ValueError(
            "Document encoding and byte-order mark "
            "are incompatible."
        )