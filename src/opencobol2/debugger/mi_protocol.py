"""A parser for GDB/MI (Machine Interface) output records.

Grounded in real output captured from a live GDB 14.2 (MinGW-W64)
session started with `--interpreter=mi2` against a debug-symbol-enabled
binary, not assumed formats -- GDB's MI grammar has known real-world
inconsistencies across versions and commands (some list values are
lists of bare tuples, `[{name="a"}, ...]`; others are lists of named
results, `[bkpt={...}, ...]`), and this parser handles both.

GDB's own grammar (https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI-Output-Syntax.html):

    output ::= ( out-of-band-record )* [ result-record ] "(gdb)" nl
    result-record ::= [ token ] "^" result-class ( "," result )* nl
    out-of-band-record ::= async-record | stream-record
    async-record ::= exec-async-output | status-async-output | notify-async-output
    exec-async-output ::= [ token ] "*" async-output
    status-async-output ::= [ token ] "+" async-output
    notify-async-output ::= [ token ] "=" async-output
    async-output ::= async-class ( "," result )* nl
    result ::= variable "=" value
    value ::= const | tuple | list
    tuple ::= "{}" | "{" result ( "," result )* "}"
    list ::= "[]" | "[" value ( "," value )* "]" | "[" result ( "," result )* "]"
    stream-record ::= console-stream-output | target-stream-output | log-stream-output
    console-stream-output ::= "~" c-string nl
    target-stream-output ::= "@" c-string nl
    log-stream-output ::= "&" c-string nl

Only one full `output` line is parsed at a time -- `parse_mi_line` is
meant to be called once per line as an adapter reads GDB's stdout
incrementally, since async records (like a breakpoint being hit) can
arrive at any time relative to a command's own result record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


MIValue = str | tuple["MIValue", ...] | dict[str, "MIValue"]


class MIRecordKind(StrEnum):
    """Which of GDB/MI's record kinds one parsed line represents."""

    RESULT = "result"
    EXEC_ASYNC = "exec-async"
    STATUS_ASYNC = "status-async"
    NOTIFY_ASYNC = "notify-async"
    CONSOLE_STREAM = "console-stream"
    TARGET_STREAM = "target-stream"
    LOG_STREAM = "log-stream"
    PROMPT = "prompt"


class MIParseError(ValueError):
    """Raised when a recognized GDB/MI record's body is malformed."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MIRecord:
    """One parsed line of GDB/MI output.

    `token` is the optional numeric request ID GDB echoes back on
    result and async records when the adapter sends one with a command
    (`5-break-insert ...` -> `5^done,...`) -- the mechanism that lets a
    command's response be matched up even when unrelated async records
    (like a breakpoint hit) interleave with it. `klass` is the
    result-class (`"done"`, `"running"`, `"error"`, ...) or async-class
    (`"stopped"`, `"thread-created"`, ...); `None` for stream records
    and the prompt. `results` holds every `variable=value` pair for
    result/async records. `text` holds the decoded C-string for stream
    records.
    """

    kind: MIRecordKind
    token: int | None = None
    klass: str | None = None
    results: dict[str, MIValue] = field(
        default_factory=dict,
    )
    text: str | None = None

    def get(
        self,
        name: str,
        default: MIValue | None = None,
    ) -> MIValue | None:
        """Return one named result, or a default if it's absent."""

        return self.results.get(
            name,
            default,
        )


_STREAM_PREFIX_KINDS = {
    "~": MIRecordKind.CONSOLE_STREAM,
    "@": MIRecordKind.TARGET_STREAM,
    "&": MIRecordKind.LOG_STREAM,
}

_RECORD_PREFIX_KINDS = {
    "^": MIRecordKind.RESULT,
    "*": MIRecordKind.EXEC_ASYNC,
    "+": MIRecordKind.STATUS_ASYNC,
    "=": MIRecordKind.NOTIFY_ASYNC,
}

_C_STRING_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "\\": "\\",
}

_OCTAL_DIGITS = frozenset(
    "01234567",
)

# Editor §DebuggerCore-2: bounds `_MIValueParser`'s recursion so a
# pathologically deep MI value (whether from real GDB output or a
# malformed line) raises a clean `MIParseError` instead of an uncaught
# `RecursionError` -- the latter isn't a `MIParseError`, so it would
# escape `_read_loop`'s exception guard entirely and kill the
# background reader thread. Comfortably below Python's default
# recursion limit (~3 stack frames are spent per MI nesting level) and
# far beyond any realistic COBOL data hierarchy's nesting depth.
_MAX_MI_VALUE_DEPTH = 200


def parse_mi_line(
    line: str,
) -> MIRecord | None:
    """Parse one line of raw GDB/MI output into a record.

    Returns `None` for a blank line or one that doesn't start with a
    recognized MI record marker (GDB occasionally emits plain text that
    isn't part of the MI protocol proper). Raises `MIParseError` if a
    recognized record's body is malformed -- that indicates either a
    real GDB protocol change or a bug in this parser, either of which
    is worth surfacing rather than silently corrupting adapter state.
    """

    if not line:
        return None

    if line in (
        "(gdb)",
        "(gdb) ",
    ):
        return MIRecord(
            kind=MIRecordKind.PROMPT,
        )

    index = 0

    while (
        index < len(line)
        and line[index].isdigit()
    ):
        index += 1

    token = (
        int(
            line[:index],
        )
        if index > 0
        else None
    )

    if index >= len(line):
        return None

    marker = line[index]

    if marker in _STREAM_PREFIX_KINDS:
        parser = _MIValueParser(
            line[index + 1 :],
        )
        text = parser.parse_c_string()
        return MIRecord(
            kind=_STREAM_PREFIX_KINDS[
                marker
            ],
            text=text,
        )

    if marker not in _RECORD_PREFIX_KINDS:
        return None

    parser = _MIValueParser(
        line[index + 1 :],
    )
    klass = parser.parse_identifier()
    results: dict[str, MIValue] = {}

    while parser.consume_char_if(
        ",",
    ):
        name, value = parser.parse_result()
        results[name] = value

    parser.expect_end()

    return MIRecord(
        kind=_RECORD_PREFIX_KINDS[marker],
        token=token,
        klass=klass,
        results=results,
    )


class _MIValueParser:
    """A small recursive-descent parser for one MI record's value grammar."""

    def __init__(
        self,
        text: str,
    ) -> None:
        self._text = text
        self._pos = 0
        self._depth = 0

    def _peek(
        self,
    ) -> str:
        return (
            self._text[self._pos]
            if self._pos < len(self._text)
            else ""
        )

    def consume_char_if(
        self,
        char: str,
    ) -> bool:
        if self._peek() == char:
            self._pos += 1
            return True

        return False

    def expect_end(
        self,
    ) -> None:
        if self._pos != len(self._text):
            raise MIParseError(
                "Unexpected trailing MI "
                f"text: {self._text[self._pos:]!r}"
            )

    def parse_identifier(
        self,
    ) -> str:
        start = self._pos

        while self._pos < len(
            self._text,
        ) and (
            self._text[
                self._pos
            ].isalnum()
            or self._text[self._pos]
            in "-_"
        ):
            self._pos += 1

        if self._pos == start:
            raise MIParseError(
                "Expected an identifier at "
                f"position {start} in {self._text!r}"
            )

        return self._text[start : self._pos]

    def parse_result(
        self,
    ) -> tuple[str, MIValue]:
        name = self.parse_identifier()

        if not self.consume_char_if(
            "=",
        ):
            raise MIParseError(
                f"Expected '=' after {name!r} "
                f"in {self._text!r}"
            )

        return name, self.parse_value()

    def parse_value(
        self,
    ) -> MIValue:
        self._depth += 1

        try:
            if self._depth > _MAX_MI_VALUE_DEPTH:
                raise MIParseError(
                    "MI value nesting exceeds the maximum "
                    f"supported depth ({_MAX_MI_VALUE_DEPTH}) "
                    f"in {self._text!r}"
                )

            char = self._peek()

            if char == '"':
                return self.parse_c_string()

            if char == "{":
                return self.parse_tuple()

            if char == "[":
                return self.parse_list()

            raise MIParseError(
                f"Unexpected character {char!r} "
                f"at position {self._pos} in {self._text!r}"
            )
        finally:
            self._depth -= 1

    def parse_tuple(
        self,
    ) -> dict[str, MIValue]:
        if not self.consume_char_if(
            "{",
        ):
            raise MIParseError(
                f"Expected '{{' in {self._text!r}",
            )

        result: dict[str, MIValue] = {}

        if self.consume_char_if(
            "}",
        ):
            return result

        while True:
            name, value = self.parse_result()
            result[name] = value

            if self.consume_char_if(
                ",",
            ):
                continue

            break

        if not self.consume_char_if(
            "}",
        ):
            raise MIParseError(
                f"Expected '}}' in {self._text!r}",
            )

        return result

    def parse_list(
        self,
    ) -> tuple[MIValue, ...]:
        if not self.consume_char_if(
            "[",
        ):
            raise MIParseError(
                f"Expected '[' in {self._text!r}",
            )

        items: list[MIValue] = []

        if self.consume_char_if(
            "]",
        ):
            return tuple(
                items,
            )

        while True:
            items.append(
                self._parse_list_element(),
            )

            if self.consume_char_if(
                ",",
            ):
                continue

            break

        if not self.consume_char_if(
            "]",
        ):
            raise MIParseError(
                f"Expected ']' in {self._text!r}",
            )

        return tuple(
            items,
        )

    def _parse_list_element(
        self,
    ) -> MIValue:
        """Parse one list element: a bare value, or a `name=value` result.

        GDB's grammar allows both forms inside one list (`[value, ...]`
        or `[name=value, ...]`) -- and per that grammar, a bare value
        never starts with an identifier character, so peeking for one
        unambiguously tells the two apart.
        """

        if self._peek().isalpha():
            name, value = self.parse_result()
            return {
                name: value,
            }

        return self.parse_value()

    def parse_c_string(
        self,
    ) -> str:
        if not self.consume_char_if(
            '"',
        ):
            raise MIParseError(
                "Expected a quoted string at "
                f"position {self._pos} in {self._text!r}"
            )

        characters: list[str] = []

        while True:
            if self._pos >= len(
                self._text,
            ):
                raise MIParseError(
                    f"Unterminated string in {self._text!r}",
                )

            char = self._text[self._pos]

            if char == '"':
                self._pos += 1
                break

            if char == "\\":
                self._pos += 1

                if self._pos >= len(
                    self._text,
                ):
                    raise MIParseError(
                        "Unterminated escape in "
                        f"{self._text!r}"
                    )

                escaped = self._text[self._pos]

                # Editor §DebuggerCore-9: GDB emits a real octal escape
                # (1-3 octal digits) for any non-printable byte inside
                # an evaluated string/array value -- e.g. a COBOL field
                # containing control characters. The previous
                # single-character fallback kept each digit literally
                # (`\001` -> `"001"`, 3 characters) instead of decoding
                # the full sequence into the one control byte it
                # actually represents (`\x01`, 1 character).
                if escaped in _OCTAL_DIGITS:
                    octal_start = self._pos
                    octal_end = min(
                        octal_start + 3,
                        len(self._text),
                    )

                    while (
                        self._pos < octal_end
                        and self._text[self._pos]
                        in _OCTAL_DIGITS
                    ):
                        self._pos += 1

                    octal_digits = self._text[
                        octal_start : self._pos
                    ]
                    characters.append(
                        chr(
                            int(
                                octal_digits,
                                8,
                            ),
                        ),
                    )
                    continue

                characters.append(
                    _C_STRING_ESCAPES.get(
                        escaped,
                        escaped,
                    )
                )
                self._pos += 1
                continue

            characters.append(
                char,
            )
            self._pos += 1

        return "".join(
            characters,
        )
