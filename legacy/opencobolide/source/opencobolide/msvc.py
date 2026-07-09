"""Microsoft Visual C++ environment discovery utilities.

This module initializes process environment values required to invoke
MSVC-based compiler toolchains on Windows.
"""

from __future__ import annotations

from functools import cache
import logging
import os
import subprocess


#: Environment variables collected from the Visual C++ developer environment.
INTERESTING = {"include", "lib", "libpath", "path"}


@cache
def get_vc_vars(vcvarsall: str, arch: str) -> dict[str, str]:
    """Return cached Visual C++ environment variables.

    Args:
        vcvarsall: Path to the ``vcvarsall.bat`` script.
        arch: Target architecture, such as ``x86`` or ``x64``.

    Returns:
        Environment variables required by the selected MSVC toolchain.
    """
    env: dict[str, str] = {}

    try:
        _logger().debug("querying vcvarsall")
        vc_env = query_vcvarsall(vcvarsall, arch)
    except (RuntimeError, PermissionError):
        _logger().exception(
            "failed to initialize VC vars; compilation will likely not work"
        )
    else:
        _logger().debug("vcenv: %r", vc_env)

        for key in INTERESTING:
            destination_key = key.upper() if key == "path" else key

            try:
                env[destination_key] = vc_env[key]
            except KeyError:
                _logger().exception(
                    "failed to read %s from vcvarsall environment",
                    key,
                )

    return env


def query_vcvarsall(path: str, arch: str) -> dict[str, str]:
    """Query a Visual C++ developer environment.

    Launch ``vcvarsall.bat`` for the requested architecture and parse
    selected environment variables from the resulting ``set`` output.

    This function originated from distutils2 and was adapted by the
    OpenCobolIDE project.
    """
    result: dict[str, str] = {}

    _logger().debug('querying vcvarsall: "%s" %s set', path, arch)

    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    command = f'"{path}" {arch} & set'

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startup_info,
        )
    except OSError:
        _logger().exception("exception while querying vcvarsall")
        stdout = b""
        stderr = b""
    else:
        stdout, stderr = process.communicate()

        if process.wait() != 0:
            raise RuntimeError(stderr.decode("mbcs"))

    stdout_text = stdout.decode("mbcs")

    for line in stdout_text.splitlines():
        if "=" not in line:
            continue

        key, value = line.strip().split("=", 1)
        key = key.lower()

        if key not in INTERESTING:
            continue

        if value.endswith(os.pathsep):
            value = value[:-1]

        result[key] = _remove_duplicates(value)

    return result


def _remove_duplicates(variable: str) -> str:
    """Remove duplicate path entries while preserving their original order."""
    values = variable.split(os.pathsep)
    unique_values = list(dict.fromkeys(values))
    return os.pathsep.join(unique_values)


def _logger() -> logging.Logger:
    """Return the module logger."""
    return logging.getLogger(__name__)