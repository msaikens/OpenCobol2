"""Compiler provider registration and routing."""

from __future__ import annotations

from opencobol2.compiler.providers.models import (
    CompilerProfile,
    CompilerProvider,
)


class CompilerProviderAlreadyRegisteredError(ValueError):
    """Raised when a provider ID is already registered."""


class CompilerProviderNotFoundError(LookupError):
    """Raised when a requested compiler provider is unknown."""


class CompilerProviderRegistry:
    """Registers compiler providers and routes profiles to them."""

    __slots__ = (
        "_providers",
    )

    def __init__(self) -> None:
        self._providers: dict[
            str,
            CompilerProvider,
        ] = {}

    @property
    def providers(
        self,
    ) -> tuple[CompilerProvider, ...]:
        """Return providers in registration order."""
        return tuple(
            self._providers.values()
        )

    def register(
        self,
        provider: CompilerProvider,
    ) -> None:
        """Register one compiler provider."""
        provider_id = provider.provider_id.strip()

        if not provider_id:
            raise ValueError(
                "Compiler provider ID must not be empty."
            )

        if provider_id in self._providers:
            raise CompilerProviderAlreadyRegisteredError(
                "Compiler provider is already registered: "
                f"{provider_id}"
            )

        self._providers[
            provider_id
        ] = provider

    def get(
        self,
        provider_id: str,
    ) -> CompilerProvider:
        """Return a registered provider by ID."""
        try:
            return self._providers[
                provider_id
            ]
        except KeyError:
            raise CompilerProviderNotFoundError(
                "Compiler provider is not registered: "
                f"{provider_id}"
            ) from None

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        """Validate a profile using its registered provider."""
        provider = self.get(
            profile.provider_id,
        )

        provider.validate_profile(
            profile,
        )