"""Domain models for custom local compiler integration."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.compiler.diagnostics import (
    CompilerDiagnostic,
)
from opencobol2.compiler.models import (
    CompileResult,
    CompilerExecutionStatus,
)


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CustomLocalCompilation:
    """Structured result from a custom local compiler runtime."""

    process_result: CompileResult
    diagnostics: tuple[CompilerDiagnostic, ...] = ()
    success_return_codes: tuple[int, ...] = (
        0,
    )

    def __post_init__(self) -> None:
        """Normalize and validate custom compiler result state."""

        if not isinstance(
            self.process_result,
            CompileResult,
        ):
            raise TypeError(
                "Process result must be CompileResult."
            )

        diagnostics = tuple(
            self.diagnostics,
        )

        if not all(
            isinstance(
                diagnostic,
                CompilerDiagnostic,
            )
            for diagnostic in diagnostics
        ):
            raise TypeError(
                "Diagnostics must contain "
                "CompilerDiagnostic instances."
            )

        success_return_codes = tuple(
            self.success_return_codes,
        )

        for return_code in success_return_codes:
            if (
                not isinstance(
                    return_code,
                    int,
                )
                or isinstance(
                    return_code,
                    bool,
                )
            ):
                raise TypeError(
                    "Successful return codes must be integers."
                )

        if (
            len(
                set(
                    success_return_codes,
                )
            )
            != len(
                success_return_codes,
            )
        ):
            raise ValueError(
                "Successful return codes must be unique."
            )

        object.__setattr__(
            self,
            "diagnostics",
            diagnostics,
        )
        object.__setattr__(
            self,
            "success_return_codes",
            success_return_codes,
        )

    @property
    def succeeded(
        self,
    ) -> bool:
        """Return whether the configured compiler considered this successful."""

        return (
            self.process_result.status
            is CompilerExecutionStatus.COMPLETED
            and self.process_result.return_code
            in self.success_return_codes
        )