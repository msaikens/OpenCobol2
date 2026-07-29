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
from opencobol2.services.compilers import (
    DefaultCompilerProfileNotConfiguredError,
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

        for (
            key,
            value,
        ) in profile.environment_overrides.items():
            if os.name == "nt":
                # Editor §CompilerAbstraction-2: `os.environ` is
                # case-insensitive on Windows, but the plain dict this
                # builds is not -- a plain-dict `.update()` would leave
                # a stale differently-cased entry (e.g. ambient "PATH"
                # plus an override "Path") both present, and which one
                # a spawned child process actually observes would
                # depend on incidental dict ordering rather than the
                # override deterministically winning. Same pattern
                # already established in
                # `services/project.py::_merge_environment`.
                existing_key = _find_case_insensitive_key(
                    environment,
                    key,
                )

                if (
                    existing_key is not None
                    and existing_key != key
                ):
                    del environment[existing_key]

            environment[key] = value

        for (
            configuration_key,
            environment_key,
        ) in _GNUCOBOL_ENVIRONMENT_CONFIGURATION_KEYS.items():
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

            # Editor §CompilerAbstraction-1: a whitespace-padded value
            # (a leading/trailing space from a pasted path, say) must
            # not be passed through unstripped -- `Path(padded)` and a
            # padded environment variable value both silently fail to
            # resolve as if the value were absent, rather than raising
            # a clear "invalid path" error.
            stripped_value = value.strip()

            if not stripped_value:
                continue

            environment[environment_key] = stripped_value

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
        """Return the selected default compiler profile."""
        profile = (
            self.settings_service
            .current
            .compilers
            .default_profile
        )

        if profile is None:
            # Editor §CompilerAbstraction-3: matches the typed error
            # `CompilerProfileService.resolve_default` already raises
            # for the identical condition, rather than a bare
            # `ValueError` a caller following this codebase's own
            # "catch the typed domain error" convention wouldn't catch.
            raise DefaultCompilerProfileNotConfiguredError(
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

        stripped_value = value.strip()

        if not stripped_value:
            return None

        # Editor §CompilerAbstraction-1: a whitespace-padded path (a
        # leading/trailing space from a pasted value) must not be
        # passed through unstripped -- `Path(padded).is_file()` fails
        # to resolve even when the unpadded file genuinely exists,
        # silently treating a configured compiler as absent instead of
        # a clear "invalid path" error.
        return Path(
            stripped_value,
        )


def _find_case_insensitive_key(
    environment: dict[str, str],
    key: str,
) -> str | None:
    """Return an existing key matching `key` case-insensitively, if any.

    Mirrors `services/project.py::_find_case_insensitive_key` exactly;
    duplicated locally rather than imported since the two modules are
    otherwise unrelated and this is a small, self-contained helper.
    """

    folded_key = key.casefold()

    for existing_key in environment:
        if existing_key.casefold() == folded_key:
            return existing_key

    return None