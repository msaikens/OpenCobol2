"""Data models for compiler toolchain discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import os
from pathlib import Path
from typing import Mapping


class ToolchainSource(StrEnum):
    """Describes how a compiler toolchain was discovered."""

    EXPLICIT = "explicit"
    PATH = "path"
    ENVIRONMENT = "environment"
    WELL_KNOWN = "well-known"


@dataclass(frozen=True, slots=True)
class GnuCobolToolchain:
    """A validated GnuCOBOL compiler installation."""

    compiler_path: Path
    source: ToolchainSource
    version: str
    version_text: str
    info_text: str

    target: str | None = None
    config_directory: Path | None = None
    copy_directory: Path | None = None
    library_path: Path | None = None
    is_64_bit: bool | None = None

    environment: Mapping[str, str] = field(default_factory=dict)

    @property
    def bin_directory(self) -> Path:
        """Return the directory containing the GnuCOBOL compiler."""
        return self.compiler_path.parent

    def process_environment(
        self,
        base_environment: Mapping[str, str],
    ) -> dict[str, str]:
        """Create a process environment suitable for this toolchain."""
        environment = dict(base_environment)
        environment.update(self.environment)

        existing_path = environment.get("PATH", "")

        environment["PATH"] = os.pathsep.join(
            entry
            for entry in (
                str(self.bin_directory),
                existing_path,
            )
            if entry
        )

        return environment