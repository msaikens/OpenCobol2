"""Filesystem storage services for text documents."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tempfile

from opencobol2.documents.models import (
    ByteOrderMark,
    LineEnding,
    TextDocument,
)


class DocumentDecodeError(ValueError):
    """Raised when a file's bytes can't be decoded as its detected/assumed encoding."""


_BOM_ENCODINGS = (
    (
        ByteOrderMark.UTF32_LE,
        "utf-32-le",
    ),
    (
        ByteOrderMark.UTF32_BE,
        "utf-32-be",
    ),
    (
        ByteOrderMark.UTF8,
        "utf-8",
    ),
    (
        ByteOrderMark.UTF16_LE,
        "utf-16-le",
    ),
    (
        ByteOrderMark.UTF16_BE,
        "utf-16-be",
    ),
)


@dataclass(frozen=True, slots=True)
class DocumentStorage:
    """Loads and saves plain-text documents."""

    default_encoding: str = "utf-8"

    def __post_init__(self) -> None:
        """Validate and normalize storage configuration."""
        object.__setattr__(
            self,
            "default_encoding",
            _normalize_fallback_encoding(
                self.default_encoding,
            ),
        )

    def load(
        self,
        path: Path | str,
        *,
        fallback_encoding: str | None = None,
    ) -> TextDocument:
        """Load one text document from disk."""
        document_path = Path(path)
        data = document_path.read_bytes()

        (
            byte_order_mark,
            detected_encoding,
            content_bytes,
        ) = _detect_byte_order_mark(
            data,
        )

        if detected_encoding is None:
            encoding = _normalize_fallback_encoding(
                self.default_encoding
                if fallback_encoding is None
                else fallback_encoding
            )
        else:
            encoding = detected_encoding

        try:
            text = content_bytes.decode(
                encoding,
                errors="strict",
            )
        except UnicodeDecodeError as error:
            raise DocumentDecodeError(
                f"{document_path} could not be decoded as "
                f"{encoding!r}"
                + (
                    " (no byte-order mark was present, so this was "
                    "a guess)"
                    if byte_order_mark is None
                    else ""
                )
                + f": {error}"
            ) from error

        line_ending = _detect_line_ending(
            text,
        )

        return TextDocument(
            text=text,
            path=document_path,
            encoding=encoding,
            line_ending=line_ending,
            byte_order_mark=byte_order_mark,
        )

    def save(
        self,
        document: TextDocument,
        *,
        path: Path | str | None = None,
    ) -> Path:
        """Save one document through a same-directory replacement file."""
        destination = (
            Path(path)
            if path is not None
            else document.path
        )

        if destination is None:
            raise ValueError(
                "An untitled document requires a save path."
            )

        payload = _encode_document(
            document,
        )

        _write_replacement_file(
            destination,
            payload,
        )

        document.mark_saved(
            path=destination,
        )

        return destination


def _detect_byte_order_mark(
    data: bytes,
) -> tuple[
    ByteOrderMark | None,
    str | None,
    bytes,
]:
    """Detect and remove a supported Unicode byte-order mark."""
    for byte_order_mark, encoding in _BOM_ENCODINGS:
        signature = byte_order_mark.bytes

        if data.startswith(signature):
            return (
                byte_order_mark,
                encoding,
                data[len(signature):],
            )

    return (
        None,
        None,
        data,
    )


def _detect_line_ending(
    text: str,
) -> LineEnding:
    """Detect the dominant newline convention in decoded text."""
    crlf_count = text.count("\r\n")

    text_without_crlf = text.replace(
        "\r\n",
        "",
    )

    lf_count = text_without_crlf.count("\n")
    cr_count = text_without_crlf.count("\r")

    counts = (
        (
            crlf_count,
            LineEnding.CRLF,
        ),
        (
            lf_count,
            LineEnding.LF,
        ),
        (
            cr_count,
            LineEnding.CR,
        ),
    )

    maximum_count = max(
        count
        for count, _ in counts
    )

    if maximum_count == 0:
        return LineEnding.LF

    for count, line_ending in counts:
        if count == maximum_count:
            return line_ending

    raise AssertionError(
        "Line-ending detection did not produce a result."
    )


def _encode_document(
    document: TextDocument,
) -> bytes:
    """Encode a document for its configured on-disk representation."""
    disk_text = document.text.replace(
        "\n",
        document.line_ending.value,
    )

    content_bytes = disk_text.encode(
        document.encoding,
        errors="strict",
    )

    if document.byte_order_mark is None:
        return content_bytes

    return (
        document.byte_order_mark.bytes
        + content_bytes
    )


def _write_replacement_file(
    destination: Path,
    payload: bytes,
) -> None:
    """Write bytes to a sibling temporary file and replace the destination."""
    existing_mode = (
        stat.S_IMODE(
            destination.stat().st_mode,
        )
        if destination.exists()
        else None
    )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name,
            )

            temporary_file.write(
                payload,
            )
            temporary_file.flush()

            os.fsync(
                temporary_file.fileno(),
            )

        if existing_mode is not None:
            os.chmod(
                temporary_path,
                existing_mode,
            )
            # On Windows, os.replace() (MoveFileExW) refuses to
            # overwrite a destination that has the read-only
            # attribute, regardless of the replacement file's own
            # mode -- there is no such check on POSIX, where this is
            # a no-op. Grant owner-write so the swap can proceed; the
            # temp file's chmod() above already carries the original
            # mode (read-only included) onto the file that lands at
            # `destination`, so the net effect preserves it.
            os.chmod(
                destination,
                existing_mode | stat.S_IWRITE,
            )

        os.replace(
            temporary_path,
            destination,
        )
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _normalize_fallback_encoding(
    encoding: str,
) -> str:
    """Validate an encoding used when no Unicode BOM is present."""
    if not isinstance(encoding, str):
        raise TypeError(
            "Fallback encoding must be a string."
        )

    normalized_value = encoding.strip()

    if not normalized_value:
        raise ValueError(
            "Fallback encoding must not be empty."
        )

    try:
        codec = codecs.lookup(
            normalized_value,
        )
    except LookupError as error:
        raise ValueError(
            f"Unknown fallback encoding: {encoding!r}."
        ) from error

    if codec.name in {
        "utf-8-sig",
        "utf-16",
        "utf-32",
    }:
        raise ValueError(
            "Fallback encoding must not require or imply "
            "a Unicode byte-order mark."
        )

    return codec.name