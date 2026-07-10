"""Application services for resolving configured compiler profiles."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
    CompilerProvider,
    CompilerProviderRegistry,
)
from opencobol2.settings import (
    SettingsService,
)


class CompilerProfileNotFoundError(LookupError):
    """Raised when a configured compiler profile cannot be found."""


class DefaultCompilerProfileNotConfiguredError(LookupError):
    """Raised when no default compiler profile is configured."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerProfileResolution:
    """Pairs a configured profile with its validated provider."""

    profile: CompilerProfile
    provider: CompilerProvider

    def __post_init__(self) -> None:
        """Validate the resolved profile and provider pairing."""
        if not isinstance(
            self.profile,
            CompilerProfile,
        ):
            raise TypeError(
                "Profile must be CompilerProfile."
            )

        if self.provider.provider_id != self.profile.provider_id:
            raise ValueError(
                "Compiler profile provider ID does not match "
                "the resolved provider."
            )

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return how the resolved provider performs compilation."""
        return self.provider.execution_kind


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerProfileService:
    """Resolves configured compiler profiles against active providers."""

    settings_service: SettingsService
    provider_registry: CompilerProviderRegistry

    def resolve_default(
        self,
    ) -> CompilerProfileResolution:
        """Resolve the currently selected default compiler profile."""
        profile_id = (
            self.settings_service
            .current
            .compilers
            .default_profile_id
        )

        if profile_id is None:
            raise DefaultCompilerProfileNotConfiguredError(
                "No default compiler profile is configured."
            )

        return self.resolve(
            profile_id,
        )

    def resolve(
        self,
        profile_id: UUID,
    ) -> CompilerProfileResolution:
        """Resolve one configured profile against its provider."""
        if not isinstance(
            profile_id,
            UUID,
        ):
            raise TypeError(
                "Compiler profile ID must be a UUID."
            )

        profile = (
            self.settings_service
            .current
            .compilers
            .get_profile(
                profile_id,
            )
        )

        if profile is None:
            raise CompilerProfileNotFoundError(
                "Compiler profile is not configured: "
                f"{profile_id}"
            )

        provider = self.provider_registry.get(
            profile.provider_id,
        )

        provider.validate_profile(
            profile,
        )

        return CompilerProfileResolution(
            profile=profile,
            provider=provider,
        )