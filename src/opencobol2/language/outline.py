"""Derives a navigable outline tree from the real COBOL parser's AST.

Mirrors `opencobol2.language.folding`'s walk of the same AST shape, but
produces a display tree (division -> section -> paragraph) rather than
foldable line ranges. Deliberately out of scope for now, same as folding:
individual data items within a data section, since `DataSectionNode` holds
a flat `items` tuple rather than a level-number tree.
"""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language.ast_nodes import CompilationUnitNode
from opencobol2.language.lexer import tokenize_cobol_source
from opencobol2.language.parser import parse_cobol_tokens


@dataclass(frozen=True, slots=True, kw_only=True)
class OutlineNode:
    """One entry in a COBOL source outline tree.

    :ivar name: The display label for the entry, e.g. a division
        name, a ``"<name> SECTION"`` label, or a paragraph name.
    :ivar kind: One of ``"division"``, ``"section"``, or
        ``"paragraph"``.
    :ivar line: The 1-based source line where the entry starts.
    :ivar children: The nested outline entries, e.g. sections and
        paragraphs under a division. Empty for leaf entries such as
        paragraphs.
    """

    name: str
    kind: str
    line: int
    children: tuple[
        "OutlineNode",
        ...,
    ] = ()


def compute_outline(
    source_text: str,
    *,
    source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    ),
) -> tuple[OutlineNode, ...]:
    """Compute the top-level outline entries for a COBOL source document.

    Never raises: parsing errors or genuinely invalid mid-edit source just
    yield an empty outline for this pass, rather than breaking the editor.

    :param source_text: The complete COBOL source text to analyze.
    :param source_format: Whether `source_text` is fixed-format or
        free-format COBOL. Defaults to :attr:`CobolSourceFormat.FIXED`.
    :returns: The top-level outline entries (one per division present),
        each nesting its sections and paragraphs. Empty if lexing or
        parsing raised, or if parsing produced no compilation unit.
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

    return _build_from_unit(
        parse_result.unit,
    )


def _build_from_unit(
    unit: CompilationUnitNode,
) -> tuple[OutlineNode, ...]:
    nodes: list[OutlineNode] = [
        OutlineNode(
            name=(
                "IDENTIFICATION DIVISION ("
                f"{unit.identification.program_name})"
            ),
            kind="division",
            line=unit.identification.span.start.line,
        )
    ]

    if unit.environment is not None:
        nodes.append(
            OutlineNode(
                name="ENVIRONMENT DIVISION",
                kind="division",
                line=unit.environment.span.start.line,
            )
        )

    if unit.data is not None:
        nodes.append(
            OutlineNode(
                name="DATA DIVISION",
                kind="division",
                line=unit.data.span.start.line,
                children=tuple(
                    OutlineNode(
                        name=f"{section.name} SECTION",
                        kind="section",
                        line=section.span.start.line,
                    )
                    for section in unit.data.sections
                ),
            )
        )

    if unit.procedure is not None:
        nodes.append(
            OutlineNode(
                name="PROCEDURE DIVISION",
                kind="division",
                line=unit.procedure.span.start.line,
                children=(
                    _named_paragraph_nodes(
                        unit.procedure.paragraphs,
                    )
                    + tuple(
                        OutlineNode(
                            name=f"{section.name} SECTION",
                            kind="section",
                            line=section.span.start.line,
                            children=_named_paragraph_nodes(
                                section.paragraphs,
                            ),
                        )
                        for section in unit.procedure.sections
                    )
                ),
            )
        )

    return tuple(
        nodes,
    )


def _named_paragraph_nodes(
    paragraphs,
) -> tuple[OutlineNode, ...]:
    return tuple(
        OutlineNode(
            name=paragraph.name,
            kind="paragraph",
            line=paragraph.span.start.line,
        )
        for paragraph in paragraphs
        if paragraph.name is not None
    )
