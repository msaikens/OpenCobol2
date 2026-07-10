"""Compiler provider contracts, registries, and built-in providers."""

from opencobol2.compiler.providers.builtins import (
    CUSTOM_COMPILER_PROVIDER_ID,
    GNUCOBOL_PROVIDER_ID,
    CustomLocalCompilerProvider,
    GnuCobolCompilerProvider,
    create_builtin_compiler_provider_registry,
)
from opencobol2.compiler.providers.configuration import (
    resolve_compiler_profile_configuration,
)
from opencobol2.compiler.providers.models import (
    CompilerConfigurationField,
    CompilerConfigurationFieldKind,
    CompilerExecutionKind,
    CompilerProfile,
    CompilerProvider,
    JsonValue,
)
from opencobol2.compiler.providers.registry import (
    CompilerProviderAlreadyRegisteredError,
    CompilerProviderNotFoundError,
    CompilerProviderRegistry,
)


__all__ = [
    "CompilerConfigurationField",
    "CompilerConfigurationFieldKind",
    "CompilerExecutionKind",
    "CompilerProfile",
    "CompilerProvider",
    "CompilerProviderAlreadyRegisteredError",
    "CompilerProviderNotFoundError",
    "CompilerProviderRegistry",
    "CUSTOM_COMPILER_PROVIDER_ID",
    "CustomLocalCompilerProvider",
    "GNUCOBOL_PROVIDER_ID",
    "GnuCobolCompilerProvider",
    "JsonValue",
    "create_builtin_compiler_provider_registry",
    "resolve_compiler_profile_configuration",
]