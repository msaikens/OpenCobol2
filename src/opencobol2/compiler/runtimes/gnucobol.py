"""Activated GnuCOBOL compiler runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from opencobol2.compiler.gnucobol import (
    GnuCobolCompiler,
)
from opencobol2.compiler.gnucobol_models import (
    GnuCobolCompilation,
)
from opencobol2.compiler.models import (
    CompileRequest,
)
from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.compiler.runtimes.models import (
    CompilerRuntime,
)
from opencobol2.services.toolchains import (
    GnuCobolToolchainService,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
)


class GnuCobolRuntimeUnavailableError(RuntimeError):
    """Raised when a GnuCOBOL runtime cannot discover its compiler."""


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GnuCobolRuntime:
    """Activated local-process runtime for one GnuCOBOL profile."""

    profile_id: UUID
    toolchain: GnuCobolToolchain
    compiler: GnuCobolCompiler

    def __post_init__(self) -> None:
        """Validate activated GnuCOBOL runtime state."""
        if not isinstance(
            self.profile_id,
            UUID,
        ):
            raise TypeError(
                "GnuCOBOL runtime profile ID must be a UUID."
            )

        if not isinstance(
            self.toolchain,
            GnuCobolToolchain,
        ):
            raise TypeError(
                "GnuCOBOL runtime toolchain must be "
                "GnuCobolToolchain."
            )

        if not isinstance(
            self.compiler,
            GnuCobolCompiler,
        ):
            raise TypeError(
                "GnuCOBOL runtime compiler must be "
                "GnuCobolCompiler."
            )

        if self.compiler.toolchain is not self.toolchain:
            raise ValueError(
                "GnuCOBOL runtime compiler must use "
                "the runtime toolchain."
            )

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the GnuCOBOL provider identifier."""
        return GNUCOBOL_PROVIDER_ID

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return the GnuCOBOL execution model."""
        return CompilerExecutionKind.LOCAL_PROCESS

    def compile(
        self,
        request: CompileRequest,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> GnuCobolCompilation:
        """Compile a local COBOL request with GnuCOBOL."""
        return self.compiler.compile(
            request,
            base_environment=base_environment,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class GnuCobolRuntimeFactory:
    """Activates GnuCOBOL runtimes from configured profiles."""

    toolchain_service: GnuCobolToolchainService
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Validate GnuCOBOL runtime factory configuration."""
        if self.timeout_seconds <= 0:
            raise ValueError(
                "GnuCOBOL runtime compiler timeout must be "
                "greater than zero."
            )

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the supported compiler provider identifier."""
        return GNUCOBOL_PROVIDER_ID

    def create_runtime(
        self,
        profile: CompilerProfile,
    ) -> CompilerRuntime:
        """Create an activated runtime for one GnuCOBOL profile."""
        if not isinstance(
            profile,
            CompilerProfile,
        ):
            raise TypeError(
                "Profile must be CompilerProfile."
            )

        if profile.provider_id != self.provider_id:
            raise ValueError(
                "GnuCOBOL runtime factory requires provider "
                f"{self.provider_id!r}; "
                f"received {profile.provider_id!r}."
            )

        toolchain = self.toolchain_service.discover(
            profile,
        )

        if toolchain is None:
            raise GnuCobolRuntimeUnavailableError(
                "Unable to discover a usable GnuCOBOL "
                f"toolchain for compiler profile "
                f"{profile.profile_id}."
            )

        compiler = GnuCobolCompiler(
            toolchain=toolchain,
            timeout_seconds=self.timeout_seconds,
        )

        return GnuCobolRuntime(
            profile_id=profile.profile_id,
            toolchain=toolchain,
            compiler=compiler,
        )