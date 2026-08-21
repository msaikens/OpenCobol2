"""Cross-platform GnuCOBOL toolchain discovery.

Locates an installed GnuCOBOL compiler by trying, in order, an explicit
user-configured path, the executable available on ``PATH``, paths
derived from known environment variables (MSYS2/MinGW prefixes and
GnuCOBOL-specific variables), and conventional per-platform
installation directories. A candidate location is only accepted as a
real toolchain once it has actually been probed by invoking it and
parsing its version and ``--info`` output.
"""

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
    r"^\s*(?P<key>[^:]+?)\s*:\s*(?P<value>.*?)\s*$"
)


@dataclass(frozen=True, slots=True)
class _ToolchainCandidate:
    """One not-yet-probed candidate compiler location.

    :ivar path: The filesystem path to a candidate ``cobc`` executable.
    :ivar source: Which discovery mechanism produced this candidate.
    """

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

    :param explicit_path: An optional user-configured compiler path or
        directory, tried before any other discovery mechanism.
    :param environment: The process environment to search and probe
        candidates with. Defaults to the real ``os.environ`` when
        omitted.
    :returns: The first successfully probed :class:`GnuCobolToolchain`,
        or None if no candidate could be found and validated.
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
    """Yield unique GnuCOBOL compiler candidates in priority order.

    :param explicit_path: An optional user-configured compiler path or
        directory, yielded first when present.
    :param environment: The process environment to derive
        environment-variable and PATH candidates from.
    :returns: Every distinct candidate location, in discovery-priority
        order, deduplicated by normalized absolute path.
    """
    seen: set[str] = set()

    def candidate(
        path: str | os.PathLike[str] | None,
        source: ToolchainSource,
    ) -> _ToolchainCandidate | None:
        """Build a deduplicated candidate for one path, if not already seen.

        :param path: The raw candidate path, or None/empty when absent.
        :param source: Which discovery mechanism this candidate comes from.
        :returns: A new :class:`_ToolchainCandidate`, or None if `path`
            is empty or its normalized absolute form was already
            returned by an earlier call.
        """
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
    """Yield compiler candidates derived from process environment values.

    :param environment: The process environment to inspect for a
        direct ``COBC`` override and MSYS2/MinGW/GnuCOBOL prefix
        variables.
    :returns: Candidate ``cobc`` paths inferred from environment
        variables, in priority order.
    """
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
    """Yield conventional platform-specific compiler locations.

    :param environment: The process environment used to resolve
        platform-specific installation roots (e.g. ``ProgramFiles``,
        ``SystemDrive`` on Windows).
    :returns: Candidate ``cobc`` paths at well-known installation
        directories for the current platform.
    """
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
    """Normalize a configured compiler path.

    :param path: A user-configured path, which may point directly at
        the compiler executable or at its containing directory.
    :returns: `path`, expanded, with the platform compiler executable
        name appended when `path` refers to a directory.
    """
    expanded_path = path.expanduser()

    if expanded_path.is_dir():
        return expanded_path / _compiler_executable_name()

    return expanded_path


def _compiler_executable_name() -> str:
    """Return the platform-specific GnuCOBOL compiler executable name.

    :returns: ``"cobc.exe"`` on Windows, otherwise ``"cobc"``.
    """
    return "cobc.exe" if sys.platform == "win32" else "cobc"


def _probe_candidate(
    candidate: _ToolchainCandidate,
    base_environment: Mapping[str, str],
) -> GnuCobolToolchain | None:
    """Probe a compiler candidate and return its toolchain description.

    :param candidate: The candidate compiler location to probe.
    :param base_environment: The environment to layer probe-specific
        overrides on top of before invoking the compiler.
    :returns: A fully populated :class:`GnuCobolToolchain` if the
        candidate exists and both the ``--version`` and ``--info``
        probes succeed, otherwise None.
    """
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
    """Result of a compiler metadata probe.

    :ivar returncode: The probe subprocess's exit code.
    :ivar output: The probe subprocess's combined stdout/stderr output.
    """

    returncode: int
    output: str


def _run_probe(
    compiler_path: Path,
    argument: str,
    environment: Mapping[str, str],
) -> _ProbeResult | None:
    """Run one compiler metadata probe.

    :param compiler_path: The compiler executable to invoke.
    :param argument: The single command-line argument to pass (e.g.
        ``"--version"`` or ``"--info"``).
    :param environment: The environment to run the subprocess with.
    :returns: The probe's result, or None if the subprocess could not
        be started, timed out, or otherwise failed at the OS level.
    """
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
    """Build an isolated environment for probing a compiler candidate.

    :param compiler_path: The candidate compiler executable whose
        directory is prepended to ``PATH``.
    :param base_environment: The environment to copy and layer
        candidate-specific overrides on top of.
    :returns: A new environment mapping with the compiler's directory
        prepended to ``PATH`` and any inferred layout variables applied.
    """
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

    :param compiler_path: The candidate compiler executable whose
        parent installation prefix is used to derive layout paths.
    :param environment: The environment mapping to mutate in place.
        Existing ``COB_CONFIG_DIR``/``COB_COPY_DIR``/``COB_LIBRARY_PATH``
        entries are left untouched.
    :returns: None. `environment` is updated in place.
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
    """Extract the numeric GnuCOBOL version from compiler output.

    :param output: The raw ``cobc --version`` output to search.
    :returns: The matched version string (e.g. ``"3.2.0"``), or None if
        no version-shaped substring was found.
    """
    match = _VERSION_PATTERN.search(output)

    if match is None:
        return None

    return match.group("version")


def _parse_info(output: str) -> dict[str, str]:
    """Parse ``cobc --info`` output into key/value pairs.

    :param output: The raw ``cobc --info`` output to parse.
    :returns: A mapping from each recognized ``key : value`` line's key
        to its value. Lines that don't match the expected format are
        skipped.
    """
    information: dict[str, str] = {}

    for line in output.splitlines():
        match = _INFO_PATTERN.match(line)

        if match is None:
            continue

        information[match.group("key")] = match.group("value")

    return information


def _parse_64_bit_mode(value: str | None) -> bool | None:
    """Parse the GnuCOBOL 64-bit mode information value.

    :param value: The raw ``64bit-mode`` value from ``cobc --info``
        output, or None if that key was absent.
    :returns: True for ``"yes"``, False for ``"no"``, or None if
        `value` is None or doesn't match either expected string
        (case-insensitively).
    """
    if value is None:
        return None

    normalized_value = value.strip().lower()

    if normalized_value == "yes":
        return True

    if normalized_value == "no":
        return False

    return None


def _path_or_none(value: str | None) -> Path | None:
    """Convert a non-empty path string to a Path.

    :param value: A path string, or None/empty when absent.
    :returns: A :class:`~pathlib.Path` wrapping `value`, or None if
        `value` is None or empty.
    """
    if not value:
        return None

    return Path(value)


def _environment_overrides(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Return only GnuCOBOL-specific environment overrides.

    :param environment: The environment to filter.
    :returns: A new mapping containing only the ``COB_CONFIG_DIR``,
        ``COB_COPY_DIR``, and ``COB_LIBRARY_PATH`` entries present in
        `environment`.
    """
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