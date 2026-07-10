"""Application service for activating configured compiler runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from opencobol2.compiler.runtimes import (
    CompilerRuntime,
    CompilerRuntimeFactoryRegistry,
)
from opencobol2.services.compilers import (
    CompilerProfileResolution,
    CompilerProfileService,
)


class CompilerRuntimeActivationError(RuntimeError):
    """Raised when a runtime factory creates an invalid runtime."""


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CompilerRuntimeActivationService:
    """Activates provider-specific runtimes for compiler profiles."""

    profile_service: CompilerProfileService
    runtime_factory_registry: CompilerRuntimeFactoryRegistry

    def activate_default(
        self,
    ) -> CompilerRuntime:
        """Activate the selected default compiler runtime."""

        resolution = (
            self.profile_service.resolve_default()
        )

        return self.activate_resolution(
            resolution,
        )

    def activate(
        self,
        profile_id: UUID,
    ) -> CompilerRuntime:
        """Activate the runtime for one configured profile."""

        resolution = self.profile_service.resolve(
            profile_id,
        )

        return self.activate_resolution(
            resolution,
        )

    def activate_resolution(
        self,
        resolution: CompilerProfileResolution,
    ) -> CompilerRuntime:
        """Activate a runtime from a resolved compiler profile."""

        if not isinstance(
            resolution,
            CompilerProfileResolution,
        ):
            raise TypeError(
                "Resolution must be CompilerProfileResolution."
            )

        factory = self.runtime_factory_registry.get(
            resolution.profile.provider_id,
        )

        runtime = factory.create_runtime(
            resolution.profile,
        )

        self._validate_runtime(
            runtime,
            resolution,
        )

        return runtime

    @staticmethod
    def _validate_runtime(
        runtime: CompilerRuntime,
        resolution: CompilerProfileResolution,
    ) -> None:
        """Validate activated runtime identity and execution metadata."""

        if (
            runtime.provider_id
            != resolution.profile.provider_id
        ):
            raise CompilerRuntimeActivationError(
                "Activated compiler runtime provider ID "
                "does not match the compiler profile."
            )

        if (
            runtime.profile_id
            != resolution.profile.profile_id
        ):
            raise CompilerRuntimeActivationError(
                "Activated compiler runtime profile ID "
                "does not match the compiler profile."
            )

        if (
            runtime.execution_kind
            is not resolution.execution_kind
        ):
            raise CompilerRuntimeActivationError(
                "Activated compiler runtime execution kind "
                "does not match the compiler provider."
            )