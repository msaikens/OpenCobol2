"""Compiler runtime factory registration and lookup."""

from __future__ import annotations

from opencobol2.compiler.runtimes.models import (
    CompilerRuntimeFactory,
)


class CompilerRuntimeFactoryAlreadyRegisteredError(
    ValueError,
):
    """Raised when a runtime factory is already registered."""


class CompilerRuntimeFactoryNotFoundError(
    LookupError,
):
    """Raised when no runtime factory supports a provider."""


class CompilerRuntimeFactoryRegistry:
    """Registers compiler runtime factories by provider identifier."""

    __slots__ = (
        "_factories",
    )

    def __init__(
        self,
    ) -> None:
        self._factories: dict[
            str,
            CompilerRuntimeFactory,
        ] = {}

    @property
    def factories(
        self,
    ) -> tuple[CompilerRuntimeFactory, ...]:
        """Return runtime factories in registration order."""

        return tuple(
            self._factories.values(),
        )

    def register(
        self,
        factory: CompilerRuntimeFactory,
    ) -> None:
        """Register one compiler runtime factory."""

        provider_id = factory.provider_id.strip()

        if not provider_id:
            raise ValueError(
                "Compiler runtime factory provider ID "
                "must not be empty."
            )

        if provider_id in self._factories:
            raise (
                CompilerRuntimeFactoryAlreadyRegisteredError(
                    "Compiler runtime factory is already "
                    f"registered for provider: {provider_id}"
                )
            )

        self._factories[
            provider_id
        ] = factory

    def get(
        self,
        provider_id: str,
    ) -> CompilerRuntimeFactory:
        """Return the runtime factory for a provider."""

        try:
            return self._factories[
                provider_id
            ]
        except KeyError:
            raise CompilerRuntimeFactoryNotFoundError(
                "Compiler runtime factory is not registered "
                f"for provider: {provider_id}"
            ) from None