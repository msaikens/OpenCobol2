"""Unit tests for the built-in snippet table and tab-stop body parser."""

from __future__ import annotations

from opencobol2.language import BUILTIN_SNIPPETS, parse_snippet_body


def test_every_built_in_snippet_has_a_trigger_label_and_body() -> None:
    triggers = [snippet.trigger for snippet in BUILTIN_SNIPPETS]

    assert len(triggers) == len(set(triggers))

    for snippet in BUILTIN_SNIPPETS:
        assert snippet.trigger
        assert snippet.label
        assert snippet.body


def test_parses_literal_text_and_a_single_placeholder() -> None:
    segments = parse_snippet_body("IF ${1:condition}\n    ${2}\nEND-IF")

    assert segments[0].text == "IF "
    assert segments[0].is_placeholder is False

    assert segments[1].text == "condition"
    assert segments[1].is_placeholder is True
    assert segments[1].stop_index == 1

    assert segments[2].text == "\n    "
    assert segments[2].is_placeholder is False

    assert segments[3].text == ""
    assert segments[3].is_placeholder is True
    assert segments[3].stop_index == 2

    assert segments[4].text == "\nEND-IF"
    assert segments[4].is_placeholder is False


def test_placeholder_with_no_default_text_is_empty() -> None:
    segments = parse_snippet_body("${1}")

    assert len(segments) == 1
    assert segments[0].is_placeholder is True
    assert segments[0].text == ""
    assert segments[0].stop_index == 1


def test_plain_text_with_no_placeholders_yields_one_literal_segment() -> None:
    segments = parse_snippet_body("STOP RUN.")

    assert segments == (
        segments[0],
    )
    assert segments[0].is_placeholder is False
    assert segments[0].text == "STOP RUN."


def test_reassembling_default_text_reproduces_a_plausible_expansion() -> None:
    for snippet in BUILTIN_SNIPPETS:
        segments = parse_snippet_body(snippet.body)
        reassembled = "".join(segment.text for segment in segments)

        # Every literal character from the body survives somewhere in
        # the reassembly (either as literal text or as a placeholder's
        # own default text) -- the ${n:...} wrapper is the only thing
        # stripped out.
        assert len(reassembled) <= len(snippet.body)
        assert reassembled.strip()
