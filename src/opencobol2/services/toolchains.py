"""Application services for configured compiler toolchains."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

from opencobol2.settings import (
    SettingsService,
)
from opencobol2.toolchains import (
    discover_gnucobol,
    GnuCobolToolchain,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GnuCobolToolchainService:
    """Discovers GnuCOBOL using current application settings."""

    settings_service: SettingsService

    def process_environment(
        self,
        base_environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Build the configured environment for external tool processes."""
        environment = dict(
            os.environ
            if base_environment is None
            else base_environment
        )

        environment.update(
            self.settings_service
            .current
            .toolchains
            .environment_overrides
        )

        return environment

    def discover(
        self,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> GnuCobolToolchain | None:
        """Discover GnuCOBOL using the current settings snapshot."""
        toolchain_settings = (
            self.settings_service.current.toolchains
        )

        environment = self.process_environment(
            base_environment,
        )

        return discover_gnucobol(
            explicit_path=(
                toolchain_settings.gnucobol_compiler_path
            ),
            environment=environment,
        )