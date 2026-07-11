"""Unit tests for ThemeService active-theme orchestration."""

from __future__ import annotations

import pytest

from opencobol2.services.theming import ThemeService
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    LIGHT_THEME_ID,
    ThemeNotFoundError,
    ThemeRegistry,
)


def _create_service(
    initial_theme_id: str = DARK_THEME_ID,
) -> ThemeService:
    return ThemeService(
        registry=create_builtin_theme_registry(),
        initial_theme_id=initial_theme_id,
    )


def test_service_starts_with_requested_active_theme() -> None:
    service = _create_service(
        initial_theme_id=LIGHT_THEME_ID,
    )

    assert service.active_theme.theme_id == LIGHT_THEME_ID


def test_service_rejects_unknown_initial_theme() -> None:
    with pytest.raises(ThemeNotFoundError):
        _create_service(
            initial_theme_id="unknown",
        )


def test_service_switches_active_theme() -> None:
    service = _create_service()

    theme = service.set_active_theme(
        LIGHT_THEME_ID,
    )

    assert theme.theme_id == LIGHT_THEME_ID
    assert service.active_theme.theme_id == LIGHT_THEME_ID


def test_service_rejects_switching_to_unknown_theme() -> None:
    service = _create_service()

    with pytest.raises(ThemeNotFoundError):
        service.set_active_theme("unknown")

    assert service.active_theme.theme_id == DARK_THEME_ID


def test_service_requires_theme_registry() -> None:
    with pytest.raises(
        TypeError,
        match="Theme service registry must be ThemeRegistry",
    ):
        ThemeService(
            registry=object(),  # type: ignore[arg-type]
            initial_theme_id=DARK_THEME_ID,
        )


def test_service_exposes_registry() -> None:
    registry = create_builtin_theme_registry()
    service = ThemeService(
        registry=registry,
        initial_theme_id=DARK_THEME_ID,
    )

    assert service.registry is registry
    assert isinstance(
        service.registry,
        ThemeRegistry,
    )
