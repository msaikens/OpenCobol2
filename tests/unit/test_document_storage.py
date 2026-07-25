"""Unit tests for text document filesystem storage."""

from __future__ import annotations

from pathlib import Path
import stat

import pytest

import opencobol2.documents.storage as document_storage
from opencobol2.documents import (
    ByteOrderMark,
    DocumentDecodeError,
    DocumentStorage,
    LineEnding,
    TextDocument,
)


def test_loads_utf8_document_and_detects_crlf(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_bytes(
        b"FIRST\r\nSECOND\r\n"
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
    )

    assert document.path == source_path
    assert document.text == "FIRST\nSECOND\n"
    assert document.encoding == "utf-8"
    assert document.line_ending is LineEnding.CRLF
    assert document.byte_order_mark is None
    assert document.is_modified is False


@pytest.mark.parametrize(
    (
        "byte_order_mark",
        "encoding",
    ),
    [
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
        (
            ByteOrderMark.UTF32_LE,
            "utf-32-le",
        ),
        (
            ByteOrderMark.UTF32_BE,
            "utf-32-be",
        ),
    ],
)
def test_loads_supported_unicode_bom(
    tmp_path: Path,
    byte_order_mark: ByteOrderMark,
    encoding: str,
) -> None:
    source_path = tmp_path / "unicode.cob"

    source_path.write_bytes(
        byte_order_mark.bytes
        + "FIRST\r\nSECOND\r\n".encode(
            encoding,
        )
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
    )

    assert document.text == "FIRST\nSECOND\n"
    assert document.encoding == encoding
    assert document.line_ending is LineEnding.CRLF
    assert (
        document.byte_order_mark
        is byte_order_mark
    )
    assert document.is_modified is False


def test_load_uses_explicit_fallback_encoding(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.cob"

    source_path.write_bytes(
        "café\r\n".encode(
            "cp1252",
        )
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
        fallback_encoding="cp1252",
    )

    assert document.text == "café\n"
    assert document.encoding == "cp1252"
    assert document.line_ending is LineEnding.CRLF
    assert document.byte_order_mark is None


def test_load_raises_document_decode_error_on_bad_encoding(
    tmp_path: Path,
) -> None:
    """A file that isn't valid UTF-8 (the default assumed encoding, with
    no BOM to override it) must fail with a clear domain error instead
    of a raw UnicodeDecodeError escaping the storage layer."""

    source_path = tmp_path / "legacy.cob"
    source_path.write_bytes(
        "café\r\n".encode(
            "cp1252",
        )
    )

    storage = DocumentStorage()

    with pytest.raises(
        DocumentDecodeError,
        match="could not be decoded",
    ):
        storage.load(
            source_path,
        )


def test_load_detects_dominant_line_ending(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "mixed.cob"

    source_path.write_bytes(
        b"FIRST\nSECOND\r\nTHIRD\r\nFOURTH\r\n"
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
    )

    assert document.text == (
        "FIRST\nSECOND\nTHIRD\nFOURTH\n"
    )
    assert document.line_ending is LineEnding.CRLF


def test_save_preserves_encoding_bom_and_line_ending(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_bytes(
        ByteOrderMark.UTF16_BE.bytes
        + "FIRST\r\nSECOND\r\n".encode(
            "utf-16-be",
        )
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
    )

    document.replace_text(
        "CHANGED\nSECOND\n"
    )

    assert document.is_modified is True

    saved_path = storage.save(
        document,
    )

    assert saved_path == source_path
    assert source_path.read_bytes() == (
        ByteOrderMark.UTF16_BE.bytes
        + "CHANGED\r\nSECOND\r\n".encode(
            "utf-16-be",
        )
    )
    assert document.is_modified is False


def test_save_overwrites_read_only_file(
    tmp_path: Path,
) -> None:
    """os.replace() refuses to overwrite a read-only destination on
    Windows regardless of the replacement file's own mode -- Save must
    still succeed when the user explicitly asked to save."""

    source_path = tmp_path / "program.cob"
    source_path.write_bytes(
        b"FIRST\r\n"
    )
    source_path.chmod(
        stat.S_IREAD,
    )

    storage = DocumentStorage()

    try:
        document = storage.load(
            source_path,
        )
        document.replace_text(
            "CHANGED\n"
        )

        saved_path = storage.save(
            document,
        )

        assert saved_path == source_path
        assert source_path.read_bytes() == b"CHANGED\r\n"
    finally:
        source_path.chmod(
            stat.S_IWRITE | stat.S_IREAD,
        )


def test_save_as_assigns_path_to_untitled_document(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "new-program.cob"

    document = TextDocument(
        text="FIRST\nSECOND\n",
        line_ending=LineEnding.CR,
    )

    storage = DocumentStorage()

    saved_path = storage.save(
        document,
        path=destination,
    )

    assert saved_path == destination
    assert destination.read_bytes() == (
        b"FIRST\rSECOND\r"
    )
    assert document.path == destination
    assert document.is_untitled is False
    assert document.is_modified is False


def test_save_untitled_document_requires_path() -> None:
    document = TextDocument(
        text="PROGRAM",
    )

    storage = DocumentStorage()

    with pytest.raises(
        ValueError,
        match="requires a save path",
    ):
        storage.save(
            document,
        )


def test_failed_replace_leaves_document_modified_and_cleans_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "program.cob"

    source_path.write_bytes(
        b"ORIGINAL"
    )

    storage = DocumentStorage()

    document = storage.load(
        source_path,
    )

    document.replace_text(
        "CHANGED",
    )

    def fail_replace(
        source: Path,
        destination: Path,
    ) -> None:
        raise PermissionError(
            "replacement denied",
        )

    monkeypatch.setattr(
        document_storage.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        PermissionError,
        match="replacement denied",
    ):
        storage.save(
            document,
        )

    assert source_path.read_bytes() == b"ORIGINAL"
    assert document.is_modified is True
    assert tuple(
        tmp_path.glob(
            f".{source_path.name}.*.tmp"
        )
    ) == ()


def test_byte_order_mark_participates_in_modified_state() -> None:
    document = TextDocument(
        text="PROGRAM",
        path="program.cob",
        encoding="utf-8",
    )

    document.set_byte_order_mark(
        ByteOrderMark.UTF8,
    )

    assert document.is_modified is True

    document.mark_saved()

    assert document.is_modified is False

    document.set_encoding(
        "latin-1",
    )

    assert document.encoding == "iso8859-1"
    assert document.byte_order_mark is None
    assert document.is_modified is True


def test_incompatible_byte_order_mark_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="encoding and byte-order mark are incompatible",
    ):
        TextDocument(
            text="PROGRAM",
            encoding="utf-8",
            byte_order_mark=ByteOrderMark.UTF16_BE,
        )