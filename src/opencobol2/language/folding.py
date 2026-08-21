"""Derives code-folding ranges from the real COBOL parser's AST.

Folds at the division/section/paragraph level and around IF/PERFORM/
EVALUATE statement bodies. Deliberately out of scope for now: folding
individual group data items by level-number nesting -- `DataSectionNode`
holds a flat `items` tuple rather than a level-number tree, so inferring
group boundaries would need extra logic not yet justified by demand.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.ast_nodes import (
    CompilationUnitNode,
    DataDivisionNode,
    EvaluateStatement,
    IfStatement,
    ParagraphNode,
    PerformStatement,
    ProcedureDivisionNode,
)
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.parser import parse_cobol_tokens


@dataclass(frozen=True, slots=True, kw_only=True)
class FoldRange:
    """One foldable, 1-based, inclusive line range.

    :ivar start_line: The first line of the foldable range, 1-based
        and inclusive.
    :ivar end_line: The last line of the foldable range, 1-based and
        inclusive.
    """

    start_line: int
    end_line: int


def compute_fold_ranges(
    source_text: str,
    *,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> tuple[FoldRange, ...]:
    """Compute foldable ranges for a COBOL source document.

    Never raises: parsing errors or genuinely invalid mid-edit source just
    yield no fold ranges for this pass, rather than breaking the editor.

    :param source_text: The complete COBOL source text to analyze.
    :param source_format: Whether `source_text` is fixed-format or
        free-format COBOL. Defaults to :attr:`CobolSourceFormat.FIXED`.
    :returns: Every foldable range found, deduplicated and sorted by
        start line. Empty if lexing or parsing raised, or if parsing
        produced no compilation unit.
    """

    try:
        lex_result = tokenize_cobol_source(
            source_text,
            source_format=source_format,
        )
        parse_result = parse_cobol_tokens(
            lex_result,
        )
    except Exception:
        return ()

    if parse_result.unit is None:
        return ()

    collected: list[FoldRange] = []
    _collect_from_unit(
        parse_result.unit,
        collected,
    )

    seen_ranges: set[
        tuple[
            int,
            int,
        ]
    ] = set()
    unique_ranges: list[FoldRange] = []

    for fold_range in collected:
        if fold_range.end_line <= fold_range.start_line:
            continue

        key = (
            fold_range.start_line,
            fold_range.end_line,
        )

        if key in seen_ranges:
            continue

        seen_ranges.add(
            key,
        )
        unique_ranges.append(
            fold_range,
        )

    return tuple(
        sorted(
            unique_ranges,
            key=lambda fold_range: fold_range.start_line,
        )
    )


def _collect_from_unit(
    unit: CompilationUnitNode,
    collected: list[FoldRange],
) -> None:
    """Collect fold ranges for every division of a compilation unit.

    :param unit: The parsed compilation unit to walk.
    :param collected: The accumulator that every discovered
        :class:`FoldRange` is appended to.
    :returns: None. Ranges are appended to `collected` in place.
    """

    _add(
        unit.identification,
        collected,
    )

    if unit.environment is not None:
        _add(
            unit.environment,
            collected,
        )

    if unit.data is not None:
        _add(
            unit.data,
            collected,
        )
        _collect_from_data_division(
            unit.data,
            collected,
        )

    if unit.procedure is not None:
        _add(
            unit.procedure,
            collected,
        )
        _collect_from_procedure_division(
            unit.procedure,
            collected,
        )


def _collect_from_data_division(
    data_division: DataDivisionNode,
    collected: list[FoldRange],
) -> None:
    """Collect one fold range per data division section.

    :param data_division: The parsed data division to walk.
    :param collected: The accumulator that every discovered
        :class:`FoldRange` is appended to.
    :returns: None. Ranges are appended to `collected` in place.
    """

    for section in data_division.sections:
        _add(
            section,
            collected,
        )


def _collect_from_procedure_division(
    procedure_division: ProcedureDivisionNode,
    collected: list[FoldRange],
) -> None:
    """Collect fold ranges for every section and paragraph in a
    procedure division, including paragraphs nested inside a section.

    :param procedure_division: The parsed procedure division to walk.
    :param collected: The accumulator that every discovered
        :class:`FoldRange` is appended to.
    :returns: None. Ranges are appended to `collected` in place.
    """

    for paragraph in procedure_division.paragraphs:
        _collect_from_paragraph(
            paragraph,
            collected,
        )

    for section in procedure_division.sections:
        _add(
            section,
            collected,
        )

        for paragraph in section.paragraphs:
            _collect_from_paragraph(
                paragraph,
                collected,
            )


def _collect_from_paragraph(
    paragraph: ParagraphNode,
    collected: list[FoldRange],
) -> None:
    """Collect a fold range for one paragraph and for any foldable
    statement inside its body.

    :param paragraph: The parsed paragraph to walk.
    :param collected: The accumulator that every discovered
        :class:`FoldRange` is appended to.
    :returns: None. Ranges are appended to `collected` in place.
    """

    _add(
        paragraph,
        collected,
    )
    _collect_from_statements(
        paragraph.statements,
        collected,
    )


def _collect_from_statements(
    statements: tuple[
        object,
        ...,
    ],
    collected: list[FoldRange],
) -> None:
    """Collect fold ranges for IF/PERFORM/EVALUATE statement bodies,
    recursing into nested bodies so every foldable construct is found
    regardless of nesting depth.

    An IF branch, out-of-line PERFORM, or EVALUATE (or one of its WHEN
    branches) with an empty body is deliberately skipped: a fold range
    that would hide zero lines of content collapses nothing, so no
    :class:`FoldRange` is produced for it. This keeps an IF with two
    empty branches consistent with an equally-empty PERFORM, which
    already received no fold range under the same reasoning.

    :param statements: The statement list to scan, typically a
        paragraph's or branch's body.
    :param collected: The accumulator that every discovered
        :class:`FoldRange` is appended to.
    :returns: None. Ranges are appended to `collected` in place.
    """

    for statement in statements:
        if isinstance(
            statement,
            IfStatement,
        ):
            if (
                statement.then_statements
                or statement.else_statements
            ):
                _add(
                    statement,
                    collected,
                )

            _collect_from_statements(
                statement.then_statements,
                collected,
            )
            _collect_from_statements(
                statement.else_statements,
                collected,
            )
        elif isinstance(
            statement,
            PerformStatement,
        ):
            if statement.body:
                _add(
                    statement,
                    collected,
                )
                _collect_from_statements(
                    statement.body,
                    collected,
                )
        elif isinstance(
            statement,
            EvaluateStatement,
        ):
            if any(
                branch.statements
                for branch in statement.branches
            ):
                _add(
                    statement,
                    collected,
                )

            for branch in statement.branches:
                if branch.statements:
                    _add(
                        branch,
                        collected,
                    )

                _collect_from_statements(
                    branch.statements,
                    collected,
                )


def _add(
    node,
    collected: list[FoldRange],
) -> None:
    """Append one AST node's source span as a :class:`FoldRange`.

    :param node: Any parsed AST node exposing a `span` attribute with
        `start.line`/`end.line` source positions.
    :param collected: The accumulator to append the new
        :class:`FoldRange` to.
    :returns: None. The range is appended to `collected` in place.
    """

    collected.append(
        FoldRange(
            start_line=node.span.start.line,
            end_line=node.span.end.line,
        )
    )
