"""Compiler runtime capability contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from opencobol2.compiler.diagnostics import (
    CompilerDiagnostic,
)
from opencobol2.compiler.models import (
    CompileRequest,
    CompileResult,
)
from opencobol2.compiler.runtimes.models import (
    CompilerRuntime,
)


@runtime_checkable
class LocalCompilationResult(Protocol):
    """Result contract shared by local compiler runtimes."""

    @property
    def process_result(
        self,
    ) -> CompileResult:
        """Return the underlying local process result."""

        ...

    @property
    def diagnostics(
        self,
    ) -> tuple[CompilerDiagnostic, ...]:
        """Return parsed compiler diagnostics."""

        ...

    @property
    def succeeded(
        self,
    ) -> bool:
        """Return whether compilation succeeded."""

        ...


@runtime_checkable
class LocalCompilerRuntime(
    CompilerRuntime,
    Protocol,
):
    """Capability contract for local request-based compilation."""

    def compile(
        self,
        request: CompileRequest,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> LocalCompilationResult:
        """Compile one local COBOL request."""

        ...