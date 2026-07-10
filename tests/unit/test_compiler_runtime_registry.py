"""Unit tests for compiler runtime factory registration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntime,
    CompilerRuntimeFactoryAlreadyRegisteredError,
    CompilerRuntimeFactoryNotFoundError,
    CompilerRuntimeFactoryRegistry,
)


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class FakeCompilerRuntime:
    """Fake compiler runtime for registry tests."""

    provider_id: str
    profile_id: UUID
    execution_kind: CompilerExecutionKind


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class FakeCompilerRuntimeFactory:
    """Fake compiler runtime factory for registry tests."""

    provider_id: str
    execution_kind: CompilerExecutionKind

    def create_runtime(
        self,
        profile: CompilerProfile,
    ) -> CompilerRuntime:
        """Create a fake compiler runtime."""

        return FakeCompilerRuntime(
            provider_id=self.provider_id,
            profile_id=profile.profile_id,
            execution_kind=self.execution_kind,
        )


def test_registry_registers_factory() -> None:
    registry = CompilerRuntimeFactoryRegistry()
    factory = FakeCompilerRuntimeFactory(
        provider_id="example.compiler",
        execution_kind=(
            CompilerExecutionKind.LOCAL_PROCESS
        ),
    )

    registry.register(
        factory,
    )

    assert registry.factories == (
        factory,
    )
    assert (
        registry.get(
            "example.compiler",
        )
        is factory
    )


def test_registry_preserves_registration_order() -> None:
    registry = CompilerRuntimeFactoryRegistry()

    first = FakeCompilerRuntimeFactory(
        provider_id="example.first",
        execution_kind=(
            CompilerExecutionKind.LOCAL_PROCESS
        ),
    )
    second = FakeCompilerRuntimeFactory(
        provider_id="example.second",
        execution_kind=(
            CompilerExecutionKind.REMOTE_JOB
        ),
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.factories == (
        first,
        second,
    )


def test_duplicate_provider_factory_is_rejected() -> None:
    registry = CompilerRuntimeFactoryRegistry()

    registry.register(
        FakeCompilerRuntimeFactory(
            provider_id="example.compiler",
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
        )
    )

    with pytest.raises(
        CompilerRuntimeFactoryAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            FakeCompilerRuntimeFactory(
                provider_id="example.compiler",
                execution_kind=(
                    CompilerExecutionKind.REMOTE_JOB
                ),
            )
        )


def test_unknown_provider_factory_is_rejected() -> None:
    registry = CompilerRuntimeFactoryRegistry()

    with pytest.raises(
        CompilerRuntimeFactoryNotFoundError,
        match="not registered",
    ):
        registry.get(
            "example.unknown",
        )


def test_empty_factory_provider_id_is_rejected() -> None:
    registry = CompilerRuntimeFactoryRegistry()

    with pytest.raises(
        ValueError,
        match="provider ID must not be empty",
    ):
        registry.register(
            FakeCompilerRuntimeFactory(
                provider_id="   ",
                execution_kind=(
                    CompilerExecutionKind.LOCAL_PROCESS
                ),
            )
        )