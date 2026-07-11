"""Active color-theme selection and orchestration."""

from __future__ import annotations

from opencobol2.theming import (
    Theme,
    ThemeRegistry,
)


class ThemeService:
    """Manages the active IDE color theme."""

    def __init__(
        self,
        *,
        registry: ThemeRegistry,
        initial_theme_id: str,
    ) -> None:
        """Initialize theme selection against a registry."""

        if not isinstance(
            registry,
            ThemeRegistry,
        ):
            raise TypeError(
                "Theme service registry must be ThemeRegistry."
            )

        self._registry = registry
        self._active_theme_id = registry.get(
            initial_theme_id,
        ).theme_id

    @property
    def registry(
        self,
    ) -> ThemeRegistry:
        """Return the underlying theme registry."""

        return self._registry

    @property
    def active_theme(
        self,
    ) -> Theme:
        """Return the currently active theme."""

        return self._registry.get(
            self._active_theme_id,
        )

    def set_active_theme(
        self,
        theme_id: str,
    ) -> Theme:
        """Select a registered theme as the active theme."""

        theme = self._registry.get(
            theme_id,
        )

        self._active_theme_id = theme.theme_id

        return theme
