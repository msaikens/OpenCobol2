"""Unit tests for activated GnuCOBOL compiler runtimes."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.compiler import (
    CompileRequest,
    CompilerOutputKind,
    GnuCobolCompiler,
)
from opencobol2.compiler.providers import (
    CompilerExecutionKind,
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)
from opencobol2.compiler.runtimes import (
    GnuCobolRuntime,
    GnuCobolRuntimeFactory,
    GnuCobolRuntimeUnavailableError,
)
from opencobol2.services import (
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
)


def _create_toolchain() -> GnuCobolToolchain:
    """Create a validated test GnuCOBOL toolchain."""
    return GnuCobolToolchain(
        compiler_path=Path(
            "C:/gnucobol/bin/cobc.exe"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2",
        version_text="cobc 3.2",
        info_text="build environment: test",
    )


def _create_profile() -> CompilerProfile:
    """Create a test GnuCOBOL compiler profile."""
    return CompilerProfile(
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="Test GnuCOBOL",
    )


def _create_toolchain_service(
    tmp_path: Path,
) -> GnuCobolToolchainService:
    """Create an isolated configured toolchain service."""
    return GnuCobolToolchainService(
        settings_service=SettingsService(
            SettingsStorage(
                tmp_path / "settings.json",
            )
        )
    )


def test_runtime_exposes_gnucobol_identity() -> None:
    profile_id = uuid4()
    toolchain = _create_toolchain()
    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    runtime = GnuCobolRuntime(
        profile_id=profile_id,
        toolchain=toolchain,
        compiler=compiler,
    )

    assert (
        runtime.provider_id
        == GNUCOBOL_PROVIDER_ID
    )
    assert runtime.profile_id == profile_id
    assert (
        runtime.execution_kind
        is CompilerExecutionKind.LOCAL_PROCESS
    )


def test_runtime_compiler_must_use_runtime_toolchain() -> None:
    runtime_toolchain = _create_toolchain()

    compiler_toolchain = GnuCobolToolchain(
        compiler_path=Path(
            "D:/other/bin/cobc.exe"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2",
        version_text="cobc 3.2",
        info_text="build environment: other",
    )

    compiler = GnuCobolCompiler(
        toolchain=compiler_toolchain,
    )

    with pytest.raises(
        ValueError,
        match="compiler must use the runtime toolchain",
    ):
        GnuCobolRuntime(
            profile_id=uuid4(),
            toolchain=runtime_toolchain,
            compiler=compiler,
        )


def test_runtime_compile_delegates_to_compiler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    toolchain = _create_toolchain()
    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )
    runtime = GnuCobolRuntime(
        profile_id=profile_id,
        toolchain=toolchain,
        compiler=compiler,
    )

    request = CompileRequest(
        source_path=Path(
            "program.cob",
        ),
        output_path=Path(
            "program.exe",
        ),
        output_kind=CompilerOutputKind.EXECUTABLE,
    )

    expected_result = object()
    captured_request: CompileRequest | None = None
    captured_environment = None

    def fake_compile(
        self: GnuCobolCompiler,
        request_value: CompileRequest,
        *,
        base_environment=None,
    ):
        nonlocal captured_request
        nonlocal captured_environment

        captured_request = request_value
        captured_environment = base_environment

        return expected_result

    monkeypatch.setattr(
        GnuCobolCompiler,
        "compile",
        fake_compile,
    )

    base_environment = {
        "PATH": "test-path",
    }

    result = runtime.compile(
        request,
        base_environment=base_environment,
    )

    assert result is expected_result
    assert captured_request is request
    assert captured_environment is base_environment

def test_factory_exposes_gnucobol_provider_id(
    tmp_path: Path,
) -> None:
    factory = GnuCobolRuntimeFactory(
        toolchain_service=_create_toolchain_service(
            tmp_path,
        ),
    )

    assert (
        factory.provider_id
        == GNUCOBOL_PROVIDER_ID
    )


def test_factory_discovers_profile_toolchain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _create_profile()
    toolchain = _create_toolchain()
    service = _create_toolchain_service(
        tmp_path,
    )

    captured_profile: CompilerProfile | None = None

    def fake_discover(
        self: GnuCobolToolchainService,
        profile_value: CompilerProfile | None = None,
        *,
        base_environment=None,
    ) -> GnuCobolToolchain:
        nonlocal captured_profile
        captured_profile = profile_value

        return toolchain

    monkeypatch.setattr(
        GnuCobolToolchainService,
        "discover",
        fake_discover,
    )

    factory = GnuCobolRuntimeFactory(
        toolchain_service=service,
    )

    runtime = factory.create_runtime(
        profile,
    )

    assert captured_profile is profile
    assert isinstance(
        runtime,
        GnuCobolRuntime,
    )
    assert runtime.profile_id == profile.profile_id
    assert runtime.toolchain is toolchain
    assert runtime.compiler.toolchain is toolchain


def test_factory_applies_configured_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _create_profile()
    toolchain = _create_toolchain()

    def fake_discover(
        self: GnuCobolToolchainService,
        profile_value: CompilerProfile | None = None,
        *,
        base_environment=None,
    ) -> GnuCobolToolchain:
        return toolchain

    monkeypatch.setattr(
        GnuCobolToolchainService,
        "discover",
        fake_discover,
    )

    factory = GnuCobolRuntimeFactory(
        toolchain_service=_create_toolchain_service(
            tmp_path,
        ),
        timeout_seconds=45,
    )

    runtime = factory.create_runtime(
        profile,
    )

    assert isinstance(
        runtime,
        GnuCobolRuntime,
    )
    assert runtime.compiler.timeout_seconds == 45


def test_factory_rejects_non_gnucobol_profile(
    tmp_path: Path,
) -> None:
    profile = CompilerProfile(
        provider_id="example.other",
        display_name="Other Compiler",
    )

    factory = GnuCobolRuntimeFactory(
        toolchain_service=_create_toolchain_service(
            tmp_path,
        ),
    )

    with pytest.raises(
        ValueError,
        match="requires provider",
    ):
        factory.create_runtime(
            profile,
        )


def test_factory_rejects_unavailable_toolchain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _create_profile()

    def fake_discover(
        self: GnuCobolToolchainService,
        profile_value: CompilerProfile | None = None,
        *,
        base_environment=None,
    ) -> None:
        return None

    monkeypatch.setattr(
        GnuCobolToolchainService,
        "discover",
        fake_discover,
    )

    factory = GnuCobolRuntimeFactory(
        toolchain_service=_create_toolchain_service(
            tmp_path,
        ),
    )

    with pytest.raises(
        GnuCobolRuntimeUnavailableError,
        match="Unable to discover a usable GnuCOBOL",
    ):
        factory.create_runtime(
            profile,
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
    ],
)
def test_factory_timeout_must_be_positive(
    tmp_path: Path,
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="timeout must be greater than zero",
    ):
        GnuCobolRuntimeFactory(
            toolchain_service=_create_toolchain_service(
                tmp_path,
            ),
            timeout_seconds=timeout_seconds,
        )