"""Application services for configured compiler toolchains."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from opencobol2.compiler.providers import (
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.settings import (
    SettingsService,
)
from opencobol2.toolchains import (
    discover_gnucobol,
    GnuCobolToolchain,
)


_GNUCOBOL_ENVIRONMENT_CONFIGURATION_KEYS = {
    "config_directory": "COB_CONFIG_DIR",
    "copy_directory": "COB_COPY_DIR",
    "library_path": "COB_LIBRARY_PATH",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class GnuCobolToolchainService:
    """Discovers GnuCOBOL from configured compiler profiles."""

    settings_service: SettingsService

    def process_environment(
        self,
        profile: CompilerProfile,
        base_environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Build the GnuCOBOL process environment for a profile."""
        self._validate_profile(
            profile,
        )

        environment = dict(
            os.environ
            if base_environment is None
            else base_environment
        )

        environment.update(
            profile.environment_overrides,
        )

        for (
            configuration_key,
            environment_key,
        ) in (
            _GNUCOBOL_ENVIRONMENT_CONFIGURATION_KEYS.items()
        ):
            value = profile.configuration.get(
                configuration_key,
            )

            if value is None:
                continue

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    "GnuCOBOL profile configuration "
                    f"{configuration_key!r} must be a string."
                )

            if not value.strip():
                continue

            environment[environment_key] = value

        return environment

    def discover(
        self,
        profile: CompilerProfile | None = None,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> GnuCobolToolchain | None:
        """Discover GnuCOBOL using a selected compiler profile."""
        selected_profile = (
            self._default_profile()
            if profile is None
            else profile
        )

        self._validate_profile(
            selected_profile,
        )

        explicit_path = self._compiler_path(
            selected_profile,
        )
        environment = self.process_environment(
            selected_profile,
            base_environment,
        )

        return discover_gnucobol(
            explicit_path=explicit_path,
            environment=environment,
        )

    def _default_profile(
        self,
    ) -> CompilerProfile:
        """Return the currently selected default compiler profile."""
        profile = (
            self.settings_service
            .current
            .compilers
            .default_profile
        )

        if profile is None:
            raise ValueError(
                "No default compiler profile is configured."
            )

        return profile

    @staticmethod
    def _validate_profile(
        profile: CompilerProfile,
    ) -> None:
        """Require a GnuCOBOL compiler profile."""
        if not isinstance(
            profile,
            CompilerProfile,
        ):
            raise TypeError(
                "Profile must be CompilerProfile."
            )

        if profile.provider_id != GNUCOBOL_PROVIDER_ID:
            raise ValueError(
                "GnuCOBOL toolchain discovery requires "
                f"provider {GNUCOBOL_PROVIDER_ID!r}; "
                f"received {profile.provider_id!r}."
            )

    @staticmethod
    def _compiler_path(
        profile: CompilerProfile,
    ) -> Path | None:
        """Return the configured explicit GnuCOBOL compiler path."""
        value = profile.configuration.get(
            "compiler_path",
        )

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "GnuCOBOL profile configuration "
                "'compiler_path' must be a string."
            )

        if not value.strip():
            return None

        return Path(
            value,
        )