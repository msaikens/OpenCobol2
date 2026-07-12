"""Application service for persisted OpenCobol2 settings."""

from __future__ import annotations

from dataclasses import replace

from opencobol2.settings.models import (
    ApplicationSettings,
    CobolSettings,
    CompilerSettings,
    EditorSettings,
    ExternalToolSettings,
    RecentProjectsSettings,
    ThemeSettings,
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

    def update_compilers(
        self,
        compilers: CompilerSettings,
    ) -> ApplicationSettings:
        """Persist replacement compiler profile settings."""
        if not isinstance(
            compilers,
            CompilerSettings,
        ):
            raise TypeError(
                "Compiler settings must be CompilerSettings."
            )

        settings = replace(
            self._current,
            compilers=compilers,
        )

        return self.apply(
            settings,
        )

    def update_external_tools(
        self,
        external_tools: ExternalToolSettings,
    ) -> ApplicationSettings:
        """Persist replacement external tool settings."""
        if not isinstance(
            external_tools,
            ExternalToolSettings,
        ):
            raise TypeError(
                "External tool settings must be "
                "ExternalToolSettings."
            )

        settings = replace(
            self._current,
            external_tools=external_tools,
        )

        return self.apply(
            settings,
        )

    def update_editor(
        self,
        editor: EditorSettings,
    ) -> ApplicationSettings:
        """Persist replacement editor settings."""
        if not isinstance(
            editor,
            EditorSettings,
        ):
            raise TypeError(
                "Editor settings must be EditorSettings."
            )

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
        if not isinstance(
            cobol,
            CobolSettings,
        ):
            raise TypeError(
                "COBOL settings must be CobolSettings."
            )

        settings = replace(
            self._current,
            cobol=cobol,
        )

        return self.apply(
            settings,
        )

    def update_theme(
        self,
        theme: ThemeSettings,
    ) -> ApplicationSettings:
        """Persist replacement theme settings."""
        if not isinstance(
            theme,
            ThemeSettings,
        ):
            raise TypeError(
                "Theme settings must be ThemeSettings."
            )

        settings = replace(
            self._current,
            theme=theme,
        )

        return self.apply(
            settings,
        )

    def update_recent_projects(
        self,
        recent_projects: RecentProjectsSettings,
    ) -> ApplicationSettings:
        """Persist replacement recent-projects settings."""
        if not isinstance(
            recent_projects,
            RecentProjectsSettings,
        ):
            raise TypeError(
                "Recent projects settings must be "
                "RecentProjectsSettings."
            )

        settings = replace(
            self._current,
            recent_projects=recent_projects,
        )

        return self.apply(
            settings,
        )