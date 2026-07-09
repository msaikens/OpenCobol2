"""GnuCOBOL-specific compiler domain models."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.diagnostics import CompilerDiagnostic
from opencobol2.compiler.models import CompileResult


@dataclass(frozen=True, slots=True, kw_only=True)
class GnuCobolCompilation:
    """Describes the complete outcome of one GnuCOBOL compilation."""

    process_result: CompileResult
    diagnostics: tuple[CompilerDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        """Normalize compilation values into stable domain types."""
        object.__setattr__(
            self,
            "diagnostics",
            tuple(self.diagnostics),
        )

    @property
    def succeeded(self) -> bool:
        """Return whether the compiler process completed successfully."""
        return self.process_result.succeeded