"""Compiler runtime factory registration and lookup.

Holds the set of known :class:`CompilerRuntimeFactory` implementations,
keyed by the compiler provider identifier each one supports, so a
runtime factory can be looked up for a given provider without the
caller needing to know which factory implementation backs it.
"""

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
    """Registers compiler runtime factories by provider identifier.

    :ivar _factories: Mapping of provider ID to registered
        :class:`CompilerRuntimeFactory`, in registration order.
    """

    __slots__ = (
        "_factories",
    )

    def __init__(
        self,
    ) -> None:
        """Initialize an empty registry with no factories registered.

        :returns: None.
        """
        self._factories: dict[
            str,
            CompilerRuntimeFactory,
        ] = {}

    @property
    def factories(
        self,
    ) -> tuple[CompilerRuntimeFactory, ...]:
        """Return the registered runtime factories.

        :returns: Every registered :class:`CompilerRuntimeFactory`, in
            the order it was registered.
        """

        return tuple(
            self._factories.values(),
        )

    def register(
        self,
        factory: CompilerRuntimeFactory,
    ) -> None:
        """Register one compiler runtime factory.

        :param factory: The runtime factory to register, identified by
            its ``provider_id``.
        :returns: None. The factory is added to the registry.
        :raises ValueError: If ``factory.provider_id`` is empty or
            whitespace-only.
        :raises CompilerRuntimeFactoryAlreadyRegisteredError: If a
            factory for the same provider is already registered.
        """

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
        """Return the runtime factory for a provider.

        :param provider_id: The compiler provider identifier the
            factory was registered under.
        :returns: The matching :class:`CompilerRuntimeFactory`.
        :raises CompilerRuntimeFactoryNotFoundError: If no factory is
            registered for ``provider_id``.
        """

        try:
            return self._factories[
                provider_id
            ]
        except KeyError:
            raise CompilerRuntimeFactoryNotFoundError(
                "Compiler runtime factory is not registered "
                f"for provider: {provider_id}"
            ) from None