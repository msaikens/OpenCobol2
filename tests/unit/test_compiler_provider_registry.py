"""Unit tests for compiler provider registration."""

from __future__ import annotations

import pytest

from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
    CompilerProviderAlreadyRegisteredError,
    CompilerProviderNotFoundError,
    CompilerProviderRegistry,
    create_builtin_compiler_provider_registry,
    CUSTOM_COMPILER_PROVIDER_ID,
    GNUCOBOL_PROVIDER_ID,
)


class _StubCompilerProvider:
    """Test compiler provider."""

    provider_id = "example.stub"
    display_name = "Stub Compiler"
    execution_kind = CompilerExecutionKind.LOCAL_PROCESS
    configuration_fields = ()

    def __init__(
        self,
    ) -> None:
        self.validated_profile: CompilerProfile | None = None

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        self.validated_profile = profile


def test_register_and_get_provider() -> None:
    registry = CompilerProviderRegistry()

    provider = _StubCompilerProvider()

    registry.register(
        provider,
    )

    assert registry.providers == (
        provider,
    )

    assert (
        registry.get(
            provider.provider_id,
        )
        is provider
    )


def test_duplicate_provider_id_is_rejected() -> None:
    registry = CompilerProviderRegistry()

    registry.register(
        _StubCompilerProvider(),
    )

    with pytest.raises(
        CompilerProviderAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            _StubCompilerProvider(),
        )


def test_unknown_provider_is_rejected() -> None:
    registry = CompilerProviderRegistry()

    with pytest.raises(
        CompilerProviderNotFoundError,
        match="not registered",
    ):
        registry.get(
            "missing",
        )


def test_profile_validation_routes_to_provider() -> None:
    registry = CompilerProviderRegistry()

    provider = _StubCompilerProvider()

    registry.register(
        provider,
    )

    profile = CompilerProfile(
        provider_id=provider.provider_id,
        display_name="Configured Stub",
    )

    registry.validate_profile(
        profile,
    )

    assert provider.validated_profile is profile


def test_builtin_registry_contains_the_two_builtin_providers() -> None:
    registry = create_builtin_compiler_provider_registry()

    provider_ids = {
        provider.provider_id
        for provider in registry.providers
    }

    assert provider_ids == {
        GNUCOBOL_PROVIDER_ID,
        CUSTOM_COMPILER_PROVIDER_ID,
    }


def test_declarative_provider_normalizes_a_padded_provider_id() -> None:
    # Editor §CompilerAbstraction-4: the registry strips `provider_id`
    # for its own dict key, but a declarative provider used to keep
    # whatever `provider_id` string it was constructed with verbatim --
    # a padded `provider_id` resolved fine via the registry, but then
    # failed the provider's own identity check in `validate_profile`,
    # rejecting a profile the registry had just correctly resolved.
    from opencobol2.compiler.providers.builtins import (
        _DeclarativeCompilerProvider,
    )

    provider = _DeclarativeCompilerProvider(
        provider_id="  plugin.example  ",
        display_name="  Plugin Example  ",
        execution_kind=CompilerExecutionKind.LOCAL_PROCESS,
        configuration_fields=(),
    )

    assert provider.provider_id == "plugin.example"
    assert provider.display_name == "Plugin Example"

    registry = CompilerProviderRegistry()
    registry.register(
        provider,
    )

    profile = CompilerProfile(
        provider_id="plugin.example",
        display_name="Configured Plugin",
    )

    registry.validate_profile(
        profile,
    )