"""Compiler provider configuration resolution."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from opencobol2.compiler.providers.models import (
    CompilerProfile,
    CompilerProvider,
    JsonValue,
)


def resolve_compiler_profile_configuration(
    provider: CompilerProvider,
    profile: CompilerProfile,
) -> Mapping[str, JsonValue]:
    """Resolve explicit profile values over provider field defaults."""

    provider.validate_profile(
        profile,
    )

    configuration: dict[str, JsonValue] = {}

    for field in provider.configuration_fields:
        if field.key in profile.configuration:
            configuration[field.key] = (
                profile.configuration[field.key]
            )
        elif field.default is not None:
            configuration[field.key] = field.default

    return MappingProxyType(
        configuration,
    )