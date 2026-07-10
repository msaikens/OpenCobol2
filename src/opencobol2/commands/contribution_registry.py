"""Registration of command surface contributions."""

from __future__ import annotations

from opencobol2.commands.contributions import (
    CommandSurfaceContribution,
    CommandSurfaceKind,
    DynamicMenuContribution,
    SubmenuContribution,
    CommandContribution,
)


class CommandContributionAlreadyRegisteredError(
    ValueError,
):
    """Raised when a contribution ID is already registered."""


class CommandContributionNotFoundError(
    LookupError,
):
    """Raised when a contribution ID is not registered."""


class CommandContributionRegistry:
    """Ordered registry of command surface contributions."""

    def __init__(
        self,
    ) -> None:
        """Initialize an empty contribution registry."""

        self._contributions: dict[
            str,
            CommandSurfaceContribution,
        ] = {}

    @property
    def contributions(
        self,
    ) -> tuple[CommandSurfaceContribution, ...]:
        """Return contributions in registration order."""

        return tuple(
            self._contributions.values(),
        )

    def register(
        self,
        contribution: CommandSurfaceContribution,
    ) -> None:
        """Register one command surface contribution."""

        if not isinstance(
            contribution,
            (
                CommandContribution,
                SubmenuContribution,
                DynamicMenuContribution,
            ),
        ):
            raise TypeError(
                "Command contribution registry entries must be "
                "command surface contribution instances."
            )

        if (
            contribution.contribution_id
            in self._contributions
        ):
            raise CommandContributionAlreadyRegisteredError(
                "Command contribution is already registered: "
                f"{contribution.contribution_id!r}."
            )

        self._contributions[
            contribution.contribution_id
        ] = contribution

    def unregister(
        self,
        contribution_id: str,
    ) -> CommandSurfaceContribution:
        """Remove and return a registered contribution."""

        normalized_contribution_id = (
            _normalize_contribution_id(
                contribution_id,
            )
        )

        try:
            return self._contributions.pop(
                normalized_contribution_id,
            )
        except KeyError as error:
            raise CommandContributionNotFoundError(
                "Command contribution is not registered: "
                f"{normalized_contribution_id!r}."
            ) from error

    def get(
        self,
        contribution_id: str,
    ) -> CommandSurfaceContribution:
        """Return a registered contribution."""

        normalized_contribution_id = (
            _normalize_contribution_id(
                contribution_id,
            )
        )

        try:
            return self._contributions[
                normalized_contribution_id
            ]
        except KeyError as error:
            raise CommandContributionNotFoundError(
                "Command contribution is not registered: "
                f"{normalized_contribution_id!r}."
            ) from error

    def for_surface(
        self,
        surface_kind: CommandSurfaceKind,
        surface_id: str,
    ) -> tuple[CommandSurfaceContribution, ...]:
        """Return ordered contributions for one application surface."""

        if not isinstance(
            surface_kind,
            CommandSurfaceKind,
        ):
            raise TypeError(
                "Command surface kind must be CommandSurfaceKind."
            )

        normalized_surface_id = _normalize_surface_id(
            surface_id,
        )

        matching_contributions = tuple(
            contribution
            for contribution in self._contributions.values()
            if (
                contribution.surface_kind
                is surface_kind
                and contribution.surface_id
                == normalized_surface_id
            )
        )

        return tuple(
            sorted(
                matching_contributions,
                key=lambda contribution: (
                    contribution.group_order,
                    contribution.order,
                ),
            )
        )


def _normalize_contribution_id(
    contribution_id: str,
) -> str:
    """Normalize and validate a contribution identifier."""

    if not isinstance(
        contribution_id,
        str,
    ):
        raise TypeError(
            "Command contribution ID must be a string."
        )

    normalized_contribution_id = (
        contribution_id.strip()
    )

    if not normalized_contribution_id:
        raise ValueError(
            "Command contribution ID must not be empty."
        )

    return normalized_contribution_id


def _normalize_surface_id(
    surface_id: str,
) -> str:
    """Normalize and validate a command surface identifier."""

    if not isinstance(
        surface_id,
        str,
    ):
        raise TypeError(
            "Command surface ID must be a string."
        )

    normalized_surface_id = surface_id.strip()

    if not normalized_surface_id:
        raise ValueError(
            "Command surface ID must not be empty."
        )

    return normalized_surface_id