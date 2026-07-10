"""Registration of named accessibility profiles."""

from __future__ import annotations

from uuid import UUID

from opencobol2.accessibility.models import (
    AccessibilityProfile,
)


class AccessibilityProfileAlreadyRegisteredError(
    ValueError,
):
    """Raised when an accessibility profile ID is already registered."""


class AccessibilityProfileNotFoundError(
    LookupError,
):
    """Raised when an accessibility profile is not registered."""


class AccessibilityProfileRegistry:
    """Ordered registry of named accessibility profiles."""

    def __init__(
        self,
    ) -> None:
        """Initialize an empty accessibility profile registry."""

        self._profiles: dict[
            UUID,
            AccessibilityProfile,
        ] = {}

    @property
    def profiles(
        self,
    ) -> tuple[AccessibilityProfile, ...]:
        """Return profiles in registration order."""

        return tuple(
            self._profiles.values(),
        )

    def register(
        self,
        profile: AccessibilityProfile,
    ) -> None:
        """Register one accessibility profile."""

        if not isinstance(
            profile,
            AccessibilityProfile,
        ):
            raise TypeError(
                "Accessibility profile registry entries must be "
                "AccessibilityProfile instances."
            )

        if profile.profile_id in self._profiles:
            raise AccessibilityProfileAlreadyRegisteredError(
                "Accessibility profile is already registered: "
                f"{profile.profile_id}."
            )

        self._profiles[
            profile.profile_id
        ] = profile

    def unregister(
        self,
        profile_id: UUID,
    ) -> AccessibilityProfile:
        """Remove and return one accessibility profile."""

        normalized_profile_id = _require_profile_id(
            profile_id,
        )

        try:
            return self._profiles.pop(
                normalized_profile_id,
            )
        except KeyError as error:
            raise AccessibilityProfileNotFoundError(
                "Accessibility profile is not registered: "
                f"{normalized_profile_id}."
            ) from error

    def get(
        self,
        profile_id: UUID,
    ) -> AccessibilityProfile:
        """Return one registered accessibility profile."""

        normalized_profile_id = _require_profile_id(
            profile_id,
        )

        try:
            return self._profiles[
                normalized_profile_id
            ]
        except KeyError as error:
            raise AccessibilityProfileNotFoundError(
                "Accessibility profile is not registered: "
                f"{normalized_profile_id}."
            ) from error

    def contains(
        self,
        profile_id: UUID,
    ) -> bool:
        """Return whether an accessibility profile is registered."""

        normalized_profile_id = _require_profile_id(
            profile_id,
        )

        return (
            normalized_profile_id
            in self._profiles
        )


def _require_profile_id(
    profile_id: UUID,
) -> UUID:
    """Require an accessibility profile UUID."""

    if not isinstance(
        profile_id,
        UUID,
    ):
        raise TypeError(
            "Accessibility profile ID must be a UUID."
        )

    return profile_id