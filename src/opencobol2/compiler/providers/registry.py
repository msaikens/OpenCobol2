"""Compiler provider registration and routing.

Holds the set of known :class:`CompilerProvider` implementations, keyed
by their provider ID, and dispatches profile validation to whichever
provider a given :class:`CompilerProfile` names.
"""

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
    """Registers compiler providers and routes profiles to them.

    :ivar _providers: Mapping of provider ID to registered
        :class:`CompilerProvider`, in registration order.
    """

    __slots__ = (
        "_providers",
    )

    def __init__(self) -> None:
        """Initialize an empty registry with no providers registered.

        :returns: None.
        """
        self._providers: dict[
            str,
            CompilerProvider,
        ] = {}

    @property
    def providers(
        self,
    ) -> tuple[CompilerProvider, ...]:
        """Return the registered providers.

        :returns: Every registered :class:`CompilerProvider`, in the
            order it was registered.
        """
        return tuple(
            self._providers.values()
        )

    def register(
        self,
        provider: CompilerProvider,
    ) -> None:
        """Register one compiler provider.

        :param provider: The provider to register, identified by its
            ``provider_id``.
        :returns: None. The provider is added to the registry.
        :raises ValueError: If ``provider.provider_id`` is empty or
            whitespace-only.
        :raises CompilerProviderAlreadyRegisteredError: If a provider
            with the same ID is already registered.
        """
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
        """Return a registered provider by ID.

        :param provider_id: The ID the provider was registered under.
        :returns: The matching :class:`CompilerProvider`.
        :raises CompilerProviderNotFoundError: If no provider with
            ``provider_id`` is registered.
        """
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
        """Validate a profile using its registered provider.

        :param profile: The compiler profile to validate. Its
            ``provider_id`` selects which registered provider performs
            the validation.
        :returns: None. Raises if the provider deems the profile
            invalid.
        :raises CompilerProviderNotFoundError: If ``profile``'s
            provider ID is not registered.
        """
        provider = self.get(
            profile.provider_id,
        )

        provider.validate_profile(
            profile,
        )