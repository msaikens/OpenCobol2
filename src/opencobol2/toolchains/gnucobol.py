"""Cross-platform GnuCOBOL toolchain discovery."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterable, Mapping

from opencobol2.toolchains.models import (
    GnuCobolToolchain,
    ToolchainSource,
)


_VERSION_PATTERN = re.compile(
    r"(?P<version>\d+\.\d+(?:\.\d+)?)"
)

_INFO_PATTERN = re.compile(
    r"^\s*(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*?)\s*$"
)


@dataclass(frozen=True, slots=True)
class _ToolchainCandidate:
    """Internal compiler discovery candidate."""

    path: Path
    source: ToolchainSource


def discover_gnucobol(
    explicit_path: str | os.PathLike[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> GnuCobolToolchain | None:
    """Discover and validate an installed GnuCOBOL toolchain.

    Discovery order:

    1. Explicit user-configured compiler path.
    2. Compiler available through PATH.
    3. Compiler roots exposed through environment variables.
    4. Common platform installation locations.

    A candidate is returned only when the compiler can be successfully
    probed for version and compiler information.
    """
    process_environment = dict(
        os.environ if environment is None else environment
    )

    for candidate in _iter_candidates(
        explicit_path=explicit_path,
        environment=process_environment,
    ):
        toolchain = _probe_candidate(
            candidate,
            process_environment,
        )

        if toolchain is not None:
            return toolchain

    return None


def _iter_candidates(
    *,
    explicit_path: str | os.PathLike[str] | None,
    environment: Mapping[str, str],
) -> Iterable[_ToolchainCandidate]:
    """Yield unique GnuCOBOL compiler candidates in priority order."""
    seen: set[str] = set()

    def candidate(
        path: str | os.PathLike[str] | None,
        source: ToolchainSource,
    ) -> _ToolchainCandidate | None:
        if not path:
            return None

        resolved_path = _normalize_compiler_path(Path(path))

        key = os.path.normcase(
            os.path.abspath(resolved_path)
        )

        if key in seen:
            return None

        seen.add(key)

        return _ToolchainCandidate(
            path=resolved_path,
            source=source,
        )

    explicit_candidate = candidate(
        explicit_path,
        ToolchainSource.EXPLICIT,
    )

    if explicit_candidate is not None:
        yield explicit_candidate

    path_match = shutil.which(
        _compiler_executable_name(),
        path=environment.get("PATH"),
    )

    path_candidate = candidate(
        path_match,
        ToolchainSource.PATH,
    )

    if path_candidate is not None:
        yield path_candidate

    for path in _environment_candidates(environment):
        environment_candidate = candidate(
            path,
            ToolchainSource.ENVIRONMENT,
        )

        if environment_candidate is not None:
            yield environment_candidate

    for path in _well_known_candidates(environment):
        well_known_candidate = candidate(
            path,
            ToolchainSource.WELL_KNOWN,
        )

        if well_known_candidate is not None:
            yield well_known_candidate


def _environment_candidates(
    environment: Mapping[str, str],
) -> Iterable[Path]:
    """Yield compiler candidates derived from process environment values."""
    compiler_override = environment.get("COBC")

    if compiler_override:
        yield Path(compiler_override)

    for variable in (
        "MINGW_PREFIX",
        "MSYSTEM_PREFIX",
        "GNUCOBOL_HOME",
    ):
        prefix = environment.get(variable)

        if prefix:
            yield Path(prefix) / "bin" / _compiler_executable_name()


def _well_known_candidates(
    environment: Mapping[str, str],
) -> Iterable[Path]:
    """Yield conventional platform-specific compiler locations."""
    executable = _compiler_executable_name()

    if sys.platform == "win32":
        system_drive = environment.get("SystemDrive", "C:")
        program_files = environment.get("ProgramFiles")
        program_files_x86 = environment.get("ProgramFiles(x86)")

        if program_files:
            yield (
                Path(program_files)
                / "GnuCOBOL"
                / "bin"
                / executable
            )

        if program_files_x86:
            yield (
                Path(program_files_x86)
                / "GnuCOBOL"
                / "bin"
                / executable
            )

        msys_root = Path(f"{system_drive}\\msys64")

        for prefix_name in (
            "ucrt64",
            "mingw64",
            "clang64",
        ):
            yield (
                msys_root
                / prefix_name
                / "bin"
                / executable
            )

    elif sys.platform == "darwin":
        yield Path("/opt/homebrew/bin") / executable
        yield Path("/usr/local/bin") / executable

    else:
        yield Path("/usr/bin") / executable
        yield Path("/usr/local/bin") / executable


def _normalize_compiler_path(path: Path) -> Path:
    """Normalize a configured compiler path."""
    expanded_path = path.expanduser()

    if expanded_path.is_dir():
        return expanded_path / _compiler_executable_name()

    return expanded_path


def _compiler_executable_name() -> str:
    """Return the platform-specific GnuCOBOL compiler executable name."""
    return "cobc.exe" if sys.platform == "win32" else "cobc"


def _probe_candidate(
    candidate: _ToolchainCandidate,
    base_environment: Mapping[str, str],
) -> GnuCobolToolchain | None:
    """Probe a compiler candidate and return its toolchain description."""
    compiler_path = candidate.path

    if not compiler_path.is_file():
        return None

    environment = _build_candidate_environment(
        compiler_path,
        base_environment,
    )

    version_result = _run_probe(
        compiler_path,
        "--version",
        environment,
    )

    if (
        version_result is None
        or version_result.returncode != 0
        or not version_result.output.strip()
    ):
        return None

    version = _parse_version(version_result.output)

    if version is None:
        return None

    info_result = _run_probe(
        compiler_path,
        "--info",
        environment,
    )

    if info_result is None or info_result.returncode != 0:
        return None

    info = _parse_info(info_result.output)

    return GnuCobolToolchain(
        compiler_path=compiler_path.resolve(),
        source=candidate.source,
        version=version,
        version_text=version_result.output.strip(),
        info_text=info_result.output.strip(),
        target=info.get("build environment"),
        config_directory=_path_or_none(
            environment.get("COB_CONFIG_DIR")
            or info.get("COB_CONFIG_DIR")
        ),
        copy_directory=_path_or_none(
            environment.get("COB_COPY_DIR")
            or info.get("COB_COPY_DIR")
        ),
        library_path=_path_or_none(
            environment.get("COB_LIBRARY_PATH")
        ),
        is_64_bit=_parse_64_bit_mode(
            info.get("64bit-mode")
        ),
        environment=_environment_overrides(environment),
    )


@dataclass(frozen=True, slots=True)
class _ProbeResult:
    """Result of a compiler metadata probe."""

    returncode: int
    output: str


def _run_probe(
    compiler_path: Path,
    argument: str,
    environment: Mapping[str, str],
) -> _ProbeResult | None:
    """Run one compiler metadata probe."""
    try:
        completed_process = subprocess.run(
            [
                str(compiler_path),
                argument,
            ],
            env=dict(environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=10,
            check=False,
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return None

    return _ProbeResult(
        returncode=completed_process.returncode,
        output=completed_process.stdout,
    )


def _build_candidate_environment(
    compiler_path: Path,
    base_environment: Mapping[str, str],
) -> dict[str, str]:
    """Build an isolated environment for probing a compiler candidate."""
    environment = dict(base_environment)

    compiler_directory = compiler_path.parent

    environment["PATH"] = os.pathsep.join(
        entry
        for entry in (
            str(compiler_directory),
            environment.get("PATH", ""),
        )
        if entry
    )

    _apply_layout_environment(
        compiler_path,
        environment,
    )

    return environment


def _apply_layout_environment(
    compiler_path: Path,
    environment: dict[str, str],
) -> None:
    """Apply environment values inferred from a verified installation layout.

    Layout inference is capability-based. Paths are only exported when the
    corresponding directory or configuration file actually exists.
    """
    prefix = compiler_path.parent.parent

    config_directory = (
        prefix
        / "share"
        / "gnucobol"
        / "config"
    )

    copy_directory = (
        prefix
        / "share"
        / "gnucobol"
        / "copy"
    )

    library_candidates = (
        prefix / "lib" / "gnucobol",
        prefix / "lib" / "gnu-cobol",
    )

    default_config = config_directory / "default.conf"

    if (
        "COB_CONFIG_DIR" not in environment
        and default_config.is_file()
    ):
        environment["COB_CONFIG_DIR"] = str(
            config_directory.resolve()
        )

    if (
        "COB_COPY_DIR" not in environment
        and copy_directory.is_dir()
    ):
        environment["COB_COPY_DIR"] = str(
            copy_directory.resolve()
        )

    if "COB_LIBRARY_PATH" not in environment:
        for library_path in library_candidates:
            if library_path.is_dir():
                environment["COB_LIBRARY_PATH"] = str(
                    library_path.resolve()
                )
                break


def _parse_version(output: str) -> str | None:
    """Extract the numeric GnuCOBOL version from compiler output."""
    match = _VERSION_PATTERN.search(output)

    if match is None:
        return None

    return match.group("version")


def _parse_info(output: str) -> dict[str, str]:
    """Parse ``cobc --info`` output into key/value pairs."""
    information: dict[str, str] = {}

    for line in output.splitlines():
        match = _INFO_PATTERN.match(line)

        if match is None:
            continue

        information[match.group("key")] = match.group("value")

    return information


def _parse_64_bit_mode(value: str | None) -> bool | None:
    """Parse the GnuCOBOL 64-bit mode information value."""
    if value is None:
        return None

    normalized_value = value.strip().lower()

    if normalized_value == "yes":
        return True

    if normalized_value == "no":
        return False

    return None


def _path_or_none(value: str | None) -> Path | None:
    """Convert a non-empty path string to a Path."""
    if not value:
        return None

    return Path(value)


def _environment_overrides(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Return only GnuCOBOL-specific environment overrides."""
    variable_names = (
        "COB_CONFIG_DIR",
        "COB_COPY_DIR",
        "COB_LIBRARY_PATH",
    )

    return {
        variable_name: environment[variable_name]
        for variable_name in variable_names
        if variable_name in environment
    }