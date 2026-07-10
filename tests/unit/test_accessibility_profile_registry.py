"""Unit tests for accessibility profile registration."""

from __future__ import annotations

from uuid import uuid4

import pytest

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilityProfileAlreadyRegisteredError,
    AccessibilityProfileNotFoundError,
    AccessibilityProfileRegistry,
)


def _create_profile(
    name: str,
) -> AccessibilityProfile:
    """Create an accessibility profile."""

    return AccessibilityProfile(
        name=name,
    )


def test_registry_preserves_profile_registration_order() -> None:
    registry = AccessibilityProfileRegistry()

    first = _create_profile(
        "Focus Coding",
    )
    second = _create_profile(
        "Low Light",
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.profiles == (
        first,
        second,
    )


def test_registry_get_returns_profile() -> None:
    registry = AccessibilityProfileRegistry()
    profile = _create_profile(
        "Focus Coding",
    )

    registry.register(
        profile,
    )

    assert registry.get(
        profile.profile_id,
    ) is profile


def test_registry_allows_duplicate_profile_names() -> None:
    registry = AccessibilityProfileRegistry()

    first = _create_profile(
        "Focus Coding",
    )
    second = _create_profile(
        "Focus Coding",
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.profiles == (
        first,
        second,
    )


def test_registry_rejects_duplicate_profile_id() -> None:
    registry = AccessibilityProfileRegistry()
    profile = _create_profile(
        "Focus Coding",
    )

    registry.register(
        profile,
    )

    with pytest.raises(
        AccessibilityProfileAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            profile,
        )


def test_registry_unregister_returns_profile() -> None:
    registry = AccessibilityProfileRegistry()
    profile = _create_profile(
        "Focus Coding",
    )

    registry.register(
        profile,
    )

    removed = registry.unregister(
        profile.profile_id,
    )

    assert removed is profile
    assert registry.contains(
        profile.profile_id,
    ) is False


def test_registry_rejects_unknown_profile() -> None:
    registry = AccessibilityProfileRegistry()

    with pytest.raises(
        AccessibilityProfileNotFoundError,
        match="is not registered",
    ):
        registry.get(
            uuid4(),
        )