"""Shared pytest configuration for OpenCobol2.

GUI-specific fixtures must import Qt and application modules lazily so that
non-GUI tests can be collected and executed without initializing the desktop
application stack.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def application():
    """Create the legacy application only for tests that explicitly request it."""
    from open_cobol_ide.app import Application

    app = Application()
    yield app

    quit_method = getattr(app, "quit", None)
    if callable(quit_method):
        quit_method()