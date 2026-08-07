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
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

from opencobol2.compiler import EXECUTABLE_SUFFIX
from opencobol2.compiler.providers import (
    CompilerProfile,
    CompilerProviderRegistry,
    CustomLocalCompilerProvider,
    CUSTOM_COMPILER_PROVIDER_ID,
    GNUCOBOL_PROVIDER_ID,
    GnuCobolCompilerProvider,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryRegistry,
    CustomLocalCompilerRuntimeFactory,
    GnuCobolRuntimeFactory,
)
from opencobol2.documents import DocumentService
from opencobol2.gui.build_commands import (
    create_build_project_handler,
    create_rebuild_project_handler,
    create_view_listing_handler,
    discover_cobol_source_files,
)
from opencobol2.gui.editor import EditorTabsWidget
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
from opencobol2.theming import DARK_THEME_ID, create_builtin_theme_registry


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
    assert "Build complete: 2 file(s) compiled, 0 up to date." in output_text

    assert problems_widget.rowCount() == 2
    severities = {
        problems_widget.item(row, 0).text()
        for row in range(problems_widget.rowCount())
    }
    assert severities == {"WARNING", "ERROR"}

    output_directory = tmp_path / project.properties.output_directory
    assert (output_directory / f"main{EXECUTABLE_SUFFIX}").is_file()
    assert (output_directory / f"sub{EXECUTABLE_SUFFIX}").is_file()


def test_build_handler_keeps_same_named_sources_in_different_directories_separate(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §CompilerProcess-1: output paths used to be derived from
    # the source filename alone, discarding its directory -- two
    # source files with the same base name in different folders (a
    # realistic copybook/utility-naming pattern) silently clobbered
    # each other's compiled binary.
    module_a = tmp_path / "moduleA"
    module_b = tmp_path / "moduleB"
    module_a.mkdir()
    module_b.mkdir()
    (module_a / "UTILS.cbl").write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    (module_b / "UTILS.cbl").write_text(
        "IDENTIFICATION DIVISION.\n",
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
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)

    output_directory = tmp_path / project.properties.output_directory

    assert (output_directory / "moduleA" / f"UTILS{EXECUTABLE_SUFFIX}").is_file()
    assert (output_directory / "moduleB" / f"UTILS{EXECUTABLE_SUFFIX}").is_file()
    assert "Build complete: 2 file(s) compiled, 0 up to date." in (
        output_widget.toPlainText()
    )


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
    assert (output_directory / f"main{EXECUTABLE_SUFFIX}").is_file()


def test_build_handler_prefers_project_compiler_profile_over_global_default(
    qapp,
    tmp_path: Path,
) -> None:
    (tmp_path / "main.cbl").write_text(
        "IDENTIFICATION DIVISION.\n",
    )

    global_script = tmp_path / "global_stub.py"
    global_script.write_text(
        _STUB_COMPILER_SCRIPT.replace(
            "unused data item",
            "compiled by the global profile",
        )
    )
    project_script = tmp_path / "project_stub.py"
    project_script.write_text(
        _STUB_COMPILER_SCRIPT.replace(
            "unused data item",
            "compiled by the project profile",
        )
    )

    global_profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Global Compiler",
        configuration={
            "executable_path": sys.executable,
            "compile_arguments": (
                str(global_script),
                "{source}",
                "-o",
                "{output}",
            ),
        },
    )
    project_profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Project Compiler",
        configuration={
            "executable_path": sys.executable,
            "compile_arguments": (
                str(project_script),
                "{source}",
                "-o",
                "{output}",
            ),
        },
    )

    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=global_profile.profile_id,
            profiles=(
                global_profile,
                project_profile,
            ),
        )
    )

    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        properties=replace(
            project.properties,
            default_compiler_profile_id=(
                project_profile.profile_id
            ),
        ),
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

    output_text = output_widget.toPlainText()
    assert "compiled by the project profile" in output_text
    assert "compiled by the global profile" not in output_text


def test_build_project_skips_a_file_whose_output_is_newer_than_its_source(
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

    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    _configure_stub_profile(
        settings_service,
        _write_stub_compiler(tmp_path),
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
    output_directory = tmp_path / project.properties.output_directory
    output_path = output_directory / f"main{EXECUTABLE_SUFFIX}"
    first_build_mtime = output_path.stat().st_mtime

    output_widget.clear()
    handler(None)

    output_text = output_widget.toPlainText()
    assert "main.cbl: up to date, skipping" in output_text
    assert "Build complete: 0 file(s) compiled, 1 up to date." in output_text
    # The stub compiler rewrites its output file on every real
    # invocation -- an unchanged mtime proves it was never re-run, not
    # just that the log line said so.
    assert output_path.stat().st_mtime == first_build_mtime


def test_build_project_recompiles_a_file_whose_source_changed_after_its_last_output(
    qapp,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "main.cbl"
    source_path.write_text(
        "IDENTIFICATION DIVISION.\n",
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
    handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=(
            _build_runtime_activation_service(settings_service)
        ),
    )

    handler(None)
    output_directory = tmp_path / project.properties.output_directory
    output_path = output_directory / f"main{EXECUTABLE_SUFFIX}"
    first_build_mtime = output_path.stat().st_mtime

    # Force the source's mtime meaningfully ahead of the first build's
    # output, rather than relying on real wall-clock elapsing between
    # the two `handler(None)` calls -- some filesystems' mtime
    # resolution is coarse enough to make that flaky.
    newer_time = first_build_mtime + 5
    os.utime(source_path, (newer_time, newer_time))

    output_widget.clear()
    handler(None)

    output_text = output_widget.toPlainText()
    assert "main.cbl: succeeded" in output_text
    assert "Build complete: 1 file(s) compiled, 0 up to date." in output_text
    assert output_path.stat().st_mtime > first_build_mtime


def test_rebuild_project_always_recompiles_even_when_up_to_date(
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

    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    _configure_stub_profile(
        settings_service,
        _write_stub_compiler(tmp_path),
    )

    output_widget = OutputWidget()
    runtime_activation_service = _build_runtime_activation_service(
        settings_service,
    )
    build_handler = create_build_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=runtime_activation_service,
    )
    rebuild_handler = create_rebuild_project_handler(
        project_explorer=ProjectExplorerWidget(project),
        output_widget=output_widget,
        problems_widget=ProblemsWidget(),
        runtime_activation_service=runtime_activation_service,
    )

    build_handler(None)
    output_widget.clear()
    rebuild_handler(None)

    output_text = output_widget.toPlainText()
    assert "main.cbl: succeeded" in output_text
    assert "Build complete: 1 file(s) compiled, 0 up to date." in output_text


def _build_editor_tabs() -> EditorTabsWidget:
    theme = create_builtin_theme_registry().get(DARK_THEME_ID)
    return EditorTabsWidget(
        document_service=DocumentService(),
        theme=theme,
    )


def test_view_listing_shows_message_when_no_editor_tab_open(
    qapp,
    tmp_path: Path,
) -> None:
    editor_tabs = _build_editor_tabs()
    handler = create_view_listing_handler(
        editor_tabs_widget=editor_tabs,
        project_explorer=ProjectExplorerWidget(None),
        compiler_profile_service=MagicMock(),
        toolchain_service=MagicMock(),
        output_widget=OutputWidget(),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()


def test_view_listing_shows_message_for_non_cobol_file(
    qapp,
    tmp_path: Path,
) -> None:
    editor_tabs = _build_editor_tabs()
    text_path = tmp_path / "notes.txt"
    text_path.write_text("just notes")
    editor_tabs.open_path(text_path)

    handler = create_view_listing_handler(
        editor_tabs_widget=editor_tabs,
        project_explorer=ProjectExplorerWidget(None),
        compiler_profile_service=MagicMock(),
        toolchain_service=MagicMock(),
        output_widget=OutputWidget(),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.information",
    ) as mock_information:
        handler(None)

    mock_information.assert_called_once()
    assert "not a saved" in mock_information.call_args.args[2]


def test_view_listing_shows_message_when_no_default_profile_configured(
    qapp,
    tmp_path: Path,
) -> None:
    editor_tabs = _build_editor_tabs()
    source_path = tmp_path / "main.cbl"
    source_path.write_text("IDENTIFICATION DIVISION.\n")
    editor_tabs.open_path(source_path)

    compiler_profile_service = MagicMock()
    compiler_profile_service.resolve_default.side_effect = LookupError(
        "no default compiler profile configured",
    )
    handler = create_view_listing_handler(
        editor_tabs_widget=editor_tabs,
        project_explorer=ProjectExplorerWidget(None),
        compiler_profile_service=compiler_profile_service,
        toolchain_service=MagicMock(),
        output_widget=OutputWidget(),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()


def test_view_listing_requires_a_gnucobol_profile(
    qapp,
    tmp_path: Path,
) -> None:
    editor_tabs = _build_editor_tabs()
    source_path = tmp_path / "main.cbl"
    source_path.write_text("IDENTIFICATION DIVISION.\n")
    editor_tabs.open_path(source_path)

    resolution = MagicMock()
    resolution.profile.provider_id = CUSTOM_COMPILER_PROVIDER_ID
    compiler_profile_service = MagicMock()
    compiler_profile_service.resolve_default.return_value = resolution

    handler = create_view_listing_handler(
        editor_tabs_widget=editor_tabs,
        project_explorer=ProjectExplorerWidget(None),
        compiler_profile_service=compiler_profile_service,
        toolchain_service=MagicMock(),
        output_widget=OutputWidget(),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "requires a GnuCOBOL compiler profile" in (
        mock_warning.call_args.args[2]
    )


def test_view_listing_shows_message_when_toolchain_undiscoverable(
    qapp,
    tmp_path: Path,
) -> None:
    editor_tabs = _build_editor_tabs()
    source_path = tmp_path / "main.cbl"
    source_path.write_text("IDENTIFICATION DIVISION.\n")
    editor_tabs.open_path(source_path)

    resolution = MagicMock()
    resolution.profile.provider_id = GNUCOBOL_PROVIDER_ID
    compiler_profile_service = MagicMock()
    compiler_profile_service.resolve_default.return_value = resolution

    toolchain_service = MagicMock()
    toolchain_service.discover.return_value = None

    handler = create_view_listing_handler(
        editor_tabs_widget=editor_tabs,
        project_explorer=ProjectExplorerWidget(None),
        compiler_profile_service=compiler_profile_service,
        toolchain_service=toolchain_service,
        output_widget=OutputWidget(),
    )

    with patch(
        "opencobol2.gui.build_commands.QMessageBox.warning",
    ) as mock_warning:
        handler(None)

    mock_warning.assert_called_once()
    assert "Unable to discover a usable GnuCOBOL toolchain" in (
        mock_warning.call_args.args[2]
    )
