"""Theme registration and lookup."""

from __future__ import annotations

from opencobol2.theming.models import Theme


class ThemeAlreadyRegisteredError(ValueError):
    """Raised when a theme ID is already registered."""


class ThemeNotFoundError(LookupError):
    """Raised when a requested theme is unknown."""


class ThemeRegistry:
    """Registers available color themes and resolves them by ID."""

    __slots__ = (
        "_themes",
    )

    def __init__(self) -> None:
        self._themes: dict[
            str,
            Theme,
        ] = {}

    @property
    def themes(
        self,
    ) -> tuple[Theme, ...]:
        """Return registered themes in registration order."""

        return tuple(
            self._themes.values()
        )

    def register(
        self,
        theme: Theme,
    ) -> None:
        """Register one color theme."""

        if not isinstance(
            theme,
            Theme,
        ):
            raise TypeError(
                "Registered theme must be Theme."
            )

        if theme.theme_id in self._themes:
            raise ThemeAlreadyRegisteredError(
                "Theme is already registered: "
                f"{theme.theme_id}"
            )

        self._themes[
            theme.theme_id
        ] = theme

    def get(
        self,
        theme_id: str,
    ) -> Theme:
        """Return a registered theme by ID."""

        try:
            return self._themes[
                theme_id
            ]
        except KeyError:
            raise ThemeNotFoundError(
                f"Theme is not registered: {theme_id}"
            ) from None
