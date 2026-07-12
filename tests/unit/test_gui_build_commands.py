"""Unit tests for the Build Project command, against a real subprocess compiler.

GnuCOBOL is not guaranteed to be installed wherever these tests run, so a
`CustomLocalCompilerProvider` profile pointed at a real stub Python "compiler"
script stands in for it. The stub is a genuine subprocess invocation (not a
mock of the compiler layer), so these tests still exercise the real
`CompilerRuntimeActivationService` -> `CustomLocalCompilerRuntime` ->
`subprocess.run` path end to end.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

from opencobol2.compiler.providers import (
    CompilerProfile,
    CompilerProviderRegistry,
    CustomLocalCompilerProvider,
    CUSTOM_COMPILER_PROVIDER_ID,
    GnuCobolCompilerProvider,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryRegistry,
    CustomLocalCompilerRuntimeFactory,
    GnuCobolRuntimeFactory,
)
from opencobol2.gui.build_commands import (
    create_build_project_handler,
    discover_cobol_source_files,
)
from opencobol2.gui.output_panel import OutputWidget
from opencobol2.gui.problems_panel import ProblemsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import create_project
from opencobol2.services import (
    CompilerProfileService,
    CompilerRuntimeActivationService,
    GnuCobolToolchainService,
)
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


_STUB_COMPILER_SCRIPT = '''
import sys

args = sys.argv[1:]
source = args[0]
output = args[args.index("-o") + 1]

with open(output, "w") as handle:
    handle.write("fake binary")

with open(source) as handle:
    content = handle.read()

if "FAIL" in content:
    print(f"{source}:5:1: error: intentional failure", file=sys.stderr)
    sys.exit(1)

print(f"{source}:2:3: warning: unused data item", file=sys.stderr)
sys.exit(0)
'''


def _write_stub_compiler(
    tmp_path: Path,
) -> Path:
    script = tmp_path / "stub_compiler.py"
    script.write_text(_STUB_COMPILER_SCRIPT)
    return script


def _build_runtime_activation_service(
    settings_service: SettingsService,
) -> CompilerRuntimeActivationService:
    provider_registry = CompilerProviderRegistry()
    provider_registry.register(GnuCobolCompilerProvider())
    provider_registry.register(CustomLocalCompilerProvider())

    runtime_registry = CompilerRuntimeFactoryRegistry()
    runtime_registry.register(
        GnuCobolRuntimeFactory(
            toolchain_service=GnuCobolToolchainService(
                settings_service=settings_service,
            ),
        ),
    )
    runtime_registry.register(CustomLocalCompilerRuntimeFactory())

    return CompilerRuntimeActivationService(
        profile_service=CompilerProfileService(
            settings_service=settings_service,
            provider_registry=provider_registry,
        ),
        runtime_factory_registry=runtime_registry,
    )


def _configure_stub_profile(
    settings_service: SettingsService,
    stub_script: Path,
) -> None:
    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Stub Compiler",
        configuration={
            "executable_path": sys.executable,
            "compile_arguments": (
                str(stub_script),
                "{source}",
                "-o",
                "{output}",
            ),
        },
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(profile,),
        )
    )


def test_discover_cobol_source_files_finds_cbl_and_cob_recursively(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text("x")
    (tmp_path / "sub.cob").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inner.cbl").write_text("x")

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    files = discover_cobol_source_files(project)

    assert files == (
        tmp_path / "main.cbl",
        nested / "inner.cbl",
        tmp_path / "sub.cob",
    )


def test_discover_cobol_source_files_honors_excluded_patterns(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text("x")
    excluded = tmp_path / "excluded_dir"
    excluded.mkdir()
    (excluded / "ignored.cbl").write_text("x")

    project = replace(
        create_project(
            name="Demo",
            root_path=tmp_path,
        ),
        excluded_patterns=("excluded_dir",),
    )

    files = discover_cobol_source_files(project)

    assert files == (tmp_path / "main.cbl",)


def test_build_handler_shows_message_when_no_project_open(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    output_widget = OutputWidget()
    problems_widget = ProblemsWidget()
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(None),
        output_widget=output_widget,
        problems_widget=problems_widget,
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.information",
    ) as mock_info:
        handler(None)

    mock_info.assert_called_once()
    assert output_widget.toPlainText() == ""
    assert problems_widget.rowCount() == 0


def test_build_handler_reports_when_no_source_files_found(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    output_widget = OutputWidget()
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)

    assert "No COBOL source files" in output_widget.toPlainText()


def test_build_handler_reports_runtime_activation_failure(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text("x")
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    # No default profile configured at all -- the most basic "compiler
    # isn't set up yet" case, independent of whether GnuCOBOL happens to be
    # installed on this machine.
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=None,
            profiles=(),
        )
    )
    output_widget = OutputWidget()
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)

    assert "Build failed:" in output_widget.toPlainText()


def test_build_handler_compiles_successful_and_failing_sources(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    (tmp_path / "sub.cob").write_text(
        "IDENTIFICATION DIVISION.\nFAIL\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    _configure_stub_profile(
        settings_service,
        _write_stub_compiler(tmp_path),
    )

    output_widget = OutputWidget()
    problems_widget = ProblemsWidget()
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=problems_widget,
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)

    output_text = output_widget.toPlainText()
    assert "main.cbl: succeeded" in output_text
    assert "sub.cob: FAILED" in output_text
    assert "Build complete: 2 file(s) compiled." in output_text

    assert problems_widget.rowCount() == 2
    severities = {
        problems_widget.item(row, 0).text()
        for row in range(problems_widget.rowCount())
    }
    assert severities == {"WARNING", "ERROR"}

    output_directory = tmp_path / project.properties.output_directory
    assert (output_directory / "main").is_file()
    assert (output_directory / "sub").is_file()


def test_build_handler_creates_missing_output_directory(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    output_directory = tmp_path / project.properties.output_directory
    assert not output_directory.exists()

    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    _configure_stub_profile(
        settings_service,
        _write_stub_compiler(tmp_path),
    )

    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=OutputWidget(),
        problems_widget=ProblemsWidget(),
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)

    assert output_directory.is_dir()
    assert (output_directory / "main").is_file()
