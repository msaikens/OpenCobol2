"""Shared pytest fixtures for OpenCobol2 unit tests."""

from __future__ import annotations

from collections.abc import Iterator
import os


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Provide a single offscreen QApplication for GUI tests."""

    application = (
        QApplication.instance()
        or QApplication([])
    )

    yield application
