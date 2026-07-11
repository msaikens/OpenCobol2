"""AST node models for parsed COBOL source."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.language.tokens import (
    SourceSpan,
    Token,
)


def _require_span(
    value: SourceSpan,
    name: str,
) -> None:
    """Require a value to be SourceSpan."""

    if not isinstance(
        value,
        SourceSpan,
    ):
        raise TypeError(
            f"{name} must be SourceSpan."
        )


def _require_token_tuple(
    values: tuple[Token, ...],
    name: str,
) -> tuple[Token, ...]:
    """Require a tuple of Token instances."""

    normalized = tuple(
        values,
    )

    if not all(
        isinstance(
            value,
            Token,
        )
        for value in normalized
    ):
        raise TypeError(
            f"{name} must contain Token instances."
        )

    return normalized


def _require_statement_tuple(
    values: tuple[object, ...],
    name: str,
) -> tuple[object, ...]:
    """Require a tuple of statement node instances."""

    normalized = tuple(
        values,
    )

    if not all(
        isinstance(
            value,
            _STATEMENT_TYPES,
        )
        for value in normalized
    ):
        raise TypeError(
            f"{name} must contain statement nodes."
        )

    return normalized


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize one non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value


# --- Data division --------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DataDescriptionClause:
    """One clause (PIC, VALUE, OCCURS, ...) on a data description entry."""

    keyword: str
    tokens: tuple[Token, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate clause state."""

        keyword = _require_non_empty_string(
            self.keyword,
            "Data description clause keyword",
        )
        tokens = _require_token_tuple(
            self.tokens,
            "Data description clause tokens",
        )
        _require_span(
            self.span,
            "Data description clause span",
        )

        object.__setattr__(
            self,
            "keyword",
            keyword,
        )
        object.__setattr__(
            self,
            "tokens",
            tokens,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DataItemNode:
    """One data description entry in the data division."""

    level_number: int
    name: str | None
    clauses: tuple[DataDescriptionClause, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate data item state."""

        if (
            not isinstance(
                self.level_number,
                int,
            )
            or isinstance(
                self.level_number,
                bool,
            )
        ):
            raise TypeError(
                "Data item level number must be an integer."
            )

        if self.level_number < 0:
            raise ValueError(
                "Data item level number must not be negative."
            )

        if self.name is not None:
            name = _require_non_empty_string(
                self.name,
                "Data item name",
            )
            object.__setattr__(
                self,
                "name",
                name,
            )

        clauses = tuple(
            self.clauses,
        )

        if not all(
            isinstance(
                clause,
                DataDescriptionClause,
            )
            for clause in clauses
        ):
            raise TypeError(
                "Data item clauses must contain "
                "DataDescriptionClause instances."
            )

        _require_span(
            self.span,
            "Data item span",
        )

        object.__setattr__(
            self,
            "clauses",
            clauses,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSectionNode:
    """One named section within the data division."""

    name: str
    items: tuple[DataItemNode, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate data section state."""

        name = _require_non_empty_string(
            self.name,
            "Data section name",
        )
        items = tuple(
            self.items,
        )

        if not all(
            isinstance(
                item,
                DataItemNode,
            )
            for item in items
        ):
            raise TypeError(
                "Data section items must contain "
                "DataItemNode instances."
            )

        _require_span(
            self.span,
            "Data section span",
        )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "items",
            items,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DataDivisionNode:
    """The data division of one COBOL compilation unit."""

    sections: tuple[DataSectionNode, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate data division state."""

        sections = tuple(
            self.sections,
        )

        if not all(
            isinstance(
                section,
                DataSectionNode,
            )
            for section in sections
        ):
            raise TypeError(
                "Data division sections must contain "
                "DataSectionNode instances."
            )

        _require_span(
            self.span,
            "Data division span",
        )

        object.__setattr__(
            self,
            "sections",
            sections,
        )


# --- Identification / environment divisions -------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentificationDivisionNode:
    """The identification division of one COBOL compilation unit."""

    program_name: str
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate identification division state."""

        program_name = _require_non_empty_string(
            self.program_name,
            "Program name",
        )
        _require_span(
            self.span,
            "Identification division span",
        )

        object.__setattr__(
            self,
            "program_name",
            program_name,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EnvironmentDivisionNode:
    """The environment division of one COBOL compilation unit.

    Environment division content is not structurally parsed in this
    version; the division is recognized and its span captured, but its
    clauses (SOURCE-COMPUTER, SELECT/ASSIGN, and so on) are opaque.
    """

    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate environment division state."""

        _require_span(
            self.span,
            "Environment division span",
        )


# --- Procedure division statements ----------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveStatement:
    """A MOVE statement."""

    source_tokens: tuple[Token, ...]
    target_names: tuple[str, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate move statement state."""

        source_tokens = _require_token_tuple(
            self.source_tokens,
            "Move statement source tokens",
        )
        target_names = tuple(
            self.target_names,
        )

        if not all(
            isinstance(
                target_name,
                str,
            )
            for target_name in target_names
        ):
            raise TypeError(
                "Move statement target names must be strings."
            )

        _require_span(
            self.span,
            "Move statement span",
        )

        object.__setattr__(
            self,
            "source_tokens",
            source_tokens,
        )
        object.__setattr__(
            self,
            "target_names",
            target_names,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DisplayStatement:
    """A DISPLAY statement."""

    operand_tokens: tuple[Token, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate display statement state."""

        operand_tokens = _require_token_tuple(
            self.operand_tokens,
            "Display statement operand tokens",
        )
        _require_span(
            self.span,
            "Display statement span",
        )

        object.__setattr__(
            self,
            "operand_tokens",
            operand_tokens,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StopRunStatement:
    """A STOP RUN statement."""

    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate stop-run statement state."""

        _require_span(
            self.span,
            "Stop run statement span",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GobackStatement:
    """A GOBACK statement."""

    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate goback statement state."""

        _require_span(
            self.span,
            "Goback statement span",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GenericStatement:
    """A statement whose verb is not given dedicated structure yet."""

    verb: str
    tokens: tuple[Token, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate generic statement state."""

        verb = _require_non_empty_string(
            self.verb,
            "Generic statement verb",
        )
        tokens = _require_token_tuple(
            self.tokens,
            "Generic statement tokens",
        )
        _require_span(
            self.span,
            "Generic statement span",
        )

        object.__setattr__(
            self,
            "verb",
            verb,
        )
        object.__setattr__(
            self,
            "tokens",
            tokens,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class IfStatement:
    """An IF / ELSE / END-IF statement."""

    condition_tokens: tuple[Token, ...]
    then_statements: tuple[object, ...]
    else_statements: tuple[object, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate if-statement state."""

        condition_tokens = _require_token_tuple(
            self.condition_tokens,
            "If statement condition tokens",
        )
        then_statements = _require_statement_tuple(
            self.then_statements,
            "If statement then-branch",
        )
        else_statements = _require_statement_tuple(
            self.else_statements,
            "If statement else-branch",
        )
        _require_span(
            self.span,
            "If statement span",
        )

        object.__setattr__(
            self,
            "condition_tokens",
            condition_tokens,
        )
        object.__setattr__(
            self,
            "then_statements",
            then_statements,
        )
        object.__setattr__(
            self,
            "else_statements",
            else_statements,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformStatement:
    """A PERFORM statement (out-of-line, inline, or both)."""

    target_name: str | None
    through_name: str | None
    modifier_tokens: tuple[Token, ...]
    body: tuple[object, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate perform statement state."""

        if self.target_name is not None:
            object.__setattr__(
                self,
                "target_name",
                _require_non_empty_string(
                    self.target_name,
                    "Perform statement target name",
                ),
            )

        if self.through_name is not None:
            object.__setattr__(
                self,
                "through_name",
                _require_non_empty_string(
                    self.through_name,
                    "Perform statement through name",
                ),
            )

        modifier_tokens = _require_token_tuple(
            self.modifier_tokens,
            "Perform statement modifier tokens",
        )
        body = _require_statement_tuple(
            self.body,
            "Perform statement body",
        )
        _require_span(
            self.span,
            "Perform statement span",
        )

        object.__setattr__(
            self,
            "modifier_tokens",
            modifier_tokens,
        )
        object.__setattr__(
            self,
            "body",
            body,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluateWhenBranch:
    """One WHEN branch of an EVALUATE statement."""

    condition_tokens: tuple[Token, ...]
    statements: tuple[object, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate evaluate-branch state."""

        condition_tokens = _require_token_tuple(
            self.condition_tokens,
            "Evaluate branch condition tokens",
        )
        statements = _require_statement_tuple(
            self.statements,
            "Evaluate branch statements",
        )
        _require_span(
            self.span,
            "Evaluate branch span",
        )

        object.__setattr__(
            self,
            "condition_tokens",
            condition_tokens,
        )
        object.__setattr__(
            self,
            "statements",
            statements,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluateStatement:
    """An EVALUATE / WHEN / END-EVALUATE statement."""

    subject_tokens: tuple[Token, ...]
    branches: tuple[EvaluateWhenBranch, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate evaluate statement state."""

        subject_tokens = _require_token_tuple(
            self.subject_tokens,
            "Evaluate statement subject tokens",
        )
        branches = tuple(
            self.branches,
        )

        if not all(
            isinstance(
                branch,
                EvaluateWhenBranch,
            )
            for branch in branches
        ):
            raise TypeError(
                "Evaluate statement branches must contain "
                "EvaluateWhenBranch instances."
            )

        _require_span(
            self.span,
            "Evaluate statement span",
        )

        object.__setattr__(
            self,
            "subject_tokens",
            subject_tokens,
        )
        object.__setattr__(
            self,
            "branches",
            branches,
        )


_STATEMENT_TYPES = (
    MoveStatement,
    DisplayStatement,
    StopRunStatement,
    GobackStatement,
    IfStatement,
    PerformStatement,
    EvaluateStatement,
    GenericStatement,
)


# --- Procedure division structure -----------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ParagraphNode:
    """One paragraph in the procedure division.

    `name` is `None` for the implicit leading paragraph that holds
    statements appearing directly after a division or section header,
    before any paragraph name.
    """

    name: str | None
    statements: tuple[object, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate paragraph state."""

        if self.name is not None:
            object.__setattr__(
                self,
                "name",
                _require_non_empty_string(
                    self.name,
                    "Paragraph name",
                ),
            )

        statements = _require_statement_tuple(
            self.statements,
            "Paragraph statements",
        )
        _require_span(
            self.span,
            "Paragraph span",
        )

        object.__setattr__(
            self,
            "statements",
            statements,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureSectionNode:
    """One named section in the procedure division."""

    name: str
    paragraphs: tuple[ParagraphNode, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate procedure section state."""

        name = _require_non_empty_string(
            self.name,
            "Procedure section name",
        )
        paragraphs = tuple(
            self.paragraphs,
        )

        if not all(
            isinstance(
                paragraph,
                ParagraphNode,
            )
            for paragraph in paragraphs
        ):
            raise TypeError(
                "Procedure section paragraphs must contain "
                "ParagraphNode instances."
            )

        _require_span(
            self.span,
            "Procedure section span",
        )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "paragraphs",
            paragraphs,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureDivisionNode:
    """The procedure division of one COBOL compilation unit."""

    paragraphs: tuple[ParagraphNode, ...]
    sections: tuple[ProcedureSectionNode, ...]
    span: SourceSpan

    def __post_init__(self) -> None:
        """Normalize and validate procedure division state."""

        paragraphs = tuple(
            self.paragraphs,
        )

        if not all(
            isinstance(
                paragraph,
                ParagraphNode,
            )
            for paragraph in paragraphs
        ):
            raise TypeError(
                "Procedure division paragraphs must contain "
                "ParagraphNode instances."
            )

        sections = tuple(
            self.sections,
        )

        if not all(
            isinstance(
                section,
                ProcedureSectionNode,
            )
            for section in sections
        ):
            raise TypeError(
                "Procedure division sections must contain "
                "ProcedureSectionNode instances."
            )

        _require_span(
            self.span,
            "Procedure division span",
        )

        object.__setattr__(
            self,
            "paragraphs",
            paragraphs,
        )
        object.__setattr__(
            self,
            "sections",
            sections,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilationUnitNode:
    """One complete parsed COBOL compilation unit."""

    identification: IdentificationDivisionNode
    environment: EnvironmentDivisionNode | None
    data: DataDivisionNode | None
    procedure: ProcedureDivisionNode | None
    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate compilation unit state."""

        if not isinstance(
            self.identification,
            IdentificationDivisionNode,
        ):
            raise TypeError(
                "Compilation unit identification division must be "
                "IdentificationDivisionNode."
            )

        if (
            self.environment is not None
            and not isinstance(
                self.environment,
                EnvironmentDivisionNode,
            )
        ):
            raise TypeError(
                "Compilation unit environment division must be "
                "EnvironmentDivisionNode or None."
            )

        if (
            self.data is not None
            and not isinstance(
                self.data,
                DataDivisionNode,
            )
        ):
            raise TypeError(
                "Compilation unit data division must be "
                "DataDivisionNode or None."
            )

        if (
            self.procedure is not None
            and not isinstance(
                self.procedure,
                ProcedureDivisionNode,
            )
        ):
            raise TypeError(
                "Compilation unit procedure division must be "
                "ProcedureDivisionNode or None."
            )

        _require_span(
            self.span,
            "Compilation unit span",
        )
