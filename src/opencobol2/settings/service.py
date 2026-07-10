"""Application service for persisted OpenCobol2 settings."""

from __future__ import annotations

from dataclasses import replace

from opencobol2.settings.models import (
    ApplicationSettings,
    CobolSettings,
    EditorSettings,
    ToolchainSettings,
)
from opencobol2.settings.storage import (
    SettingsStorage,
)


class SettingsService:
    """Owns the current persisted application settings snapshot."""

    __slots__ = (
        "_storage",
        "_current",
    )

    def __init__(
        self,
        storage: SettingsStorage | None = None,
    ) -> None:
        self._storage = (
            storage
            if storage is not None
            else SettingsStorage()
        )

        self._current = self._storage.load()

    @property
    def storage(
        self,
    ) -> SettingsStorage:
        """Return the settings persistence service."""
        return self._storage

    @property
    def current(
        self,
    ) -> ApplicationSettings:
        """Return the current application settings snapshot."""
        return self._current

    def reload(
        self,
    ) -> ApplicationSettings:
        """Reload persisted settings and replace the current snapshot."""
        settings = self._storage.load()

        self._current = settings

        return settings

    def apply(
        self,
        settings: ApplicationSettings,
    ) -> ApplicationSettings:
        """Persist and apply a complete settings snapshot."""
        if not isinstance(
            settings,
            ApplicationSettings,
        ):
            raise TypeError(
                "Settings must be ApplicationSettings."
            )

        self._storage.save(
            settings,
        )

        self._current = settings

        return settings

    def update_toolchains(
        self,
        toolchains: ToolchainSettings,
    ) -> ApplicationSettings:
        """Persist replacement toolchain settings."""
        settings = replace(
            self._current,
            toolchains=toolchains,
        )

        return self.apply(
            settings,
        )

    def update_editor(
        self,
        editor: EditorSettings,
    ) -> ApplicationSettings:
        """Persist replacement editor settings."""
        settings = replace(
            self._current,
            editor=editor,
        )

        return self.apply(
            settings,
        )

    def update_cobol(
        self,
        cobol: CobolSettings,
    ) -> ApplicationSettings:
        """Persist replacement COBOL settings."""
        settings = replace(
            self._current,
            cobol=cobol,
        )

        return self.apply(
            settings,
        )