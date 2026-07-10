"""Compiler runtime activation domain models."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
)


class CompilerRuntime(Protocol):
    """Base contract implemented by activated compiler runtimes."""

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the compiler provider identifier."""

        ...

    @property
    def profile_id(
        self,
    ) -> UUID:
        """Return the activated compiler profile identifier."""

        ...

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return how this runtime performs compilation."""

        ...


class CompilerRuntimeFactory(Protocol):
    """Creates provider-specific runtimes from compiler profiles."""

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the provider identifier supported by this factory."""

        ...

    def create_runtime(
        self,
        profile: CompilerProfile,
    ) -> CompilerRuntime:
        """Create an activated runtime for a validated profile."""

        ...