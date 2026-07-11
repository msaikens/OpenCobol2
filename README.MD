# OpenCobol2

A modern, cross-platform COBOL integrated development environment built on the foundations of OpenCobolIDE.

> **Project status: Pre-alpha**
>
> OpenCobol2 is under active foundation development. It is not yet ready to replace an existing production IDE or serve as a daily-use COBOL development environment. Stable installers and a complete application shell are not available yet.

## About OpenCobol2

OpenCobol2 is a public successor project to the archived OpenCobolIDE project originally created by Colin Duquesnoy.

The repository preserves the inherited Git history and GPL licensing of OpenCobolIDE, but OpenCobol2 is not an in-place port of the archived application.

The project uses a successor architecture:

```text
src/opencobol2/
    Current OpenCobol2 product code

legacy/opencobolide/
    Archived OpenCobolIDE reference implementation
```

The legacy application is retained to preserve project history and to provide reference material for COBOL-specific behavior, workflows, and feature requirements.

New OpenCobol2 product code belongs under `src/opencobol2`.

## Project goals

OpenCobol2 is intended to become a modern COBOL development environment with:

* Cross-platform desktop support.
* First-class GnuCOBOL integration.
* Compiler discovery without machine-specific installation assumptions.
* Configurable compiler and toolchain paths.
* COBOL-aware diagnostics and navigation.
* Customizable syntax highlighting.
* Fixed-format COBOL reference guides and coding-area visualization.
* Configurable automatic indentation.
* Code folding and collapsing.
* Project, build, test, and debug workflows.
* First-class Git and GitHub integration.
* A public plugin API for community extensions.
* Remote server and mainframe resource editing.
* Command search and a modern IDE command system.
* A testable core architecture independent of the desktop widget layer.

OpenCobol2 is intended to support both modern COBOL development and environments where COBOL still interacts with long-lived enterprise and mainframe systems.

## Current foundation

The current OpenCobol2 foundation includes the following implemented subsystems.

### GnuCOBOL toolchain discovery

OpenCobol2 can discover and validate GnuCOBOL compiler installations from:

1. An explicit compiler path.
2. `PATH`.
3. Environment-derived installation prefixes.
4. Known platform installation locations.

Compiler candidates are probed with real GnuCOBOL metadata commands before being accepted.

The toolchain model records compiler metadata and constructs an isolated process environment for compiler execution.

OpenCobol2 does not assume a specific MSYS2, MinGW, Linux, macOS, or user-local installation path.

### Compiler integration

The compiler subsystem currently provides:

* Structured compile request models.
* Structured process result models.
* Executable and module output modes.
* Fixed- and free-format source selection.
* COBOL dialect selection.
* Copybook search paths.
* Library search paths.
* Linked libraries.
* Additional compiler arguments and build inputs.
* Deterministic GnuCOBOL command construction.
* Real `cobc` process invocation.
* Timeout and process-start failure handling.
* Parsed GnuCOBOL diagnostics.
* GnuCOBOL-specific compilation outcomes.

The actual COBOL compiler remains GnuCOBOL. OpenCobol2 provides the IDE integration layer around `cobc`.

### Compiler diagnostics

OpenCobol2 can parse structured diagnostics from GnuCOBOL textual output.

The diagnostic model supports:

* Errors.
* Warnings.
* Notes.
* Source paths.
* Line and column locations.
* Warning or diagnostic codes.
* Original raw compiler text.

The parser currently understands GCC-style and MSC-style GnuCOBOL diagnostic locations and is tested against a real failing GnuCOBOL compilation.

### Document model and storage

The document subsystem currently provides:

* Qt-independent text document models.
* Internal LF newline normalization.
* LF, CRLF, and CR on-disk line-ending preservation.
* Encoding validation.
* UTF-8, UTF-16, and UTF-32 byte-order mark handling.
* Explicit UTF-16 and UTF-32 byte-order preservation.
* Modified-state tracking.
* Atomic-style same-directory replacement saves.
* Preservation of existing file mode bits when replacing files.
* Multiple open-document workspace state.
* Stable document identity for untitled files.
* Duplicate local-path protection.
* Active-document tracking.
* New, open, save, Save As, and close workflows.
* Unsaved-change protection.

The document core does not depend on Qt widgets.

### Settings framework

OpenCobol2 has a typed, schema-versioned application settings model with JSON persistence:

* Configured compiler profiles, including a default profile selection.
* External tool paths (for example, an explicit Git executable path).
* Editor font, spacing, and indentation preferences.
* COBOL fixed-format guide visibility preferences.
* Atomic, same-directory replacement saves.

A settings service exposes the current settings snapshot and supports reload and partial updates.

### Command, menu, and tool window framework

OpenCobol2 has a Qt-independent command and contribution framework:

* A command registry with declarative command definitions, an extensible built-in command catalog, and placeholder commands reserved for future GUI wiring.
* Menu, toolbar, and status bar contribution registries, including submenu and dynamic menu support.
* A tool window registry describing docked panels (id, title, default dock area, default visibility, accessibility description) ahead of any concrete widget implementation.
* Accessibility preference profiles.

These registries are fully unit tested independently of Qt. No menu bar, toolbar, or docked panel is rendered yet; that depends on the future GUI shell.

### Git integration

OpenCobol2 wraps the local `git` executable directly (no third-party Git library) behind a Qt-independent service layer:

* Repository discovery, `status --porcelain=v2` parsing, staging, unstaging, and commits.
* Repository creation and cloning.
* Remote management: list, add, remove, rename.
* Fetch, pull, and push, with merge-conflict-aware error reporting.
* Local branch management: list, create, delete, switch.
* Local tag management: list, create (lightweight and annotated), delete.
* Stash management: list, push, apply/pop, drop.
* Commit history retrieval.
* Reset (soft/mixed/hard), revert, and cherry-pick.
* Raw unified diff retrieval for the worktree, the index, and individual commits.

Every operation is unit tested against a mocked process layer and additionally verified against a real `git` executable in an isolated throwaway repository. Blame, merge, rebase, worktrees, and submodules are intentionally not yet implemented — GitHub-specific workflows (authentication, pull requests, issues) are a separate, not-yet-started integration.

### Project system

OpenCobol2 has a persisted project model that stays independent of any specific compiler dialect beyond the compiler profile it references:

* Project identity, root path, and build/launch default properties.
* Virtual (logical) folders, independent of physical directory layout.
* Linked files sourced from outside the project root.
* Excluded file patterns and project-level environment variable overrides.
* User-defined tasks and launch configurations, directly executable as local processes with layered environment resolution (ambient OS environment, then project overrides, then task/launch overrides).

Project persistence uses the same schema-versioned, atomic-replacement JSON storage pattern as application settings. The Project Explorer tree widget itself is not built yet; it depends on the future GUI shell.

### COBOL language services (lexer, parser, semantic analysis)

OpenCobol2 has begun in-house COBOL language services, independent of the GnuCOBOL compiler process:

* A COBOL lexer supporting both fixed and free source format, with fixed-format sequence area/indicator column/Area A/B handling, continuation of alphanumeric literals across source lines, whole-line and inline (`*>`) comments, a curated reserved-word table, and diagnostics for unterminated literals, malformed continuations, and unrecognized characters.
* A recursive-descent parser building a real AST for program identity, data description entries (including FILE SECTION `FD`/`SD` entries), and procedure division structure (paragraphs, sections). It gives full structure to IF/ELSE/END-IF, PERFORM (out-of-line, inline, `VARYING`/`UNTIL`/`TIMES`), and EVALUATE/WHEN, including COBOL's implicit period-based scope termination (a lone `.` can close every enclosing IF/PERFORM/EVALUATE at once). Every other statement verb (ADD, CALL, STRING, and so on) is captured as a generic statement (verb plus raw tokens) rather than being deeply modeled yet; a verb's nested-statement clauses (`ON SIZE ERROR`, `AT END`, `ON OVERFLOW`) are a known, documented gap. The environment division is recognized but parsed opaquely.
* A first semantic analysis pass: a symbol table for data items (respecting level-number nesting, including 66 RENAMES, 77 standalone items, and 88 condition names) and for procedure division paragraphs/sections (flagging duplicate names), plus reference resolution for MOVE targets and PERFORM targets (undefined-name and ambiguous-name diagnostics). Broader reference resolution (MOVE source expressions, IF/EVALUATE conditions, unmodeled-verb operands) awaits deeper per-verb grammar.

All three are tested against synthetic COBOL source and against the real `.cbl` files preserved under `legacy/opencobolide/tests/testfiles/`. Higher-level language services (outline, hover, go-to-definition, completion) are not yet implemented.

## Planned architecture milestones

Before committing the application structure to a GUI, OpenCobol2 is establishing contracts for the following systems. Settings, the command/menu/tool-window registries, Git, the project model, and a COBOL lexer/parser are already implemented (see "Current foundation" above); this section covers what still sits ahead of them.

### GUI shell

No Qt/PySide6 widget code exists yet anywhere in the codebase — every subsystem above is deliberately Qt-independent so far. The GUI shell still needs to be built, including:

* An actual menu bar and toolbar rendering the existing command/menu contribution registries.
* A command search interface over registered commands.
* The planned primary menu surface:

```text
File
Edit
Git
Project
Build
Debug
Test
Tools
Plugins
Window
Help
```

* Docked tool window widgets (Project Explorer, Git, Output, Problems, Terminal, Search, Outline, Bookmarks, Task List, Extensions) backed by the existing tool window registry.
* A text editor widget (tabs, split editors, dirty tracking, undo/redo, folding, minimap, multiple cursors, and the rest of the editor feature set).

### Deeper COBOL language services

With a lexer, parser, and first semantic pass in place, the next COBOL language milestones are:

* Deeper per-verb statement grammar (ADD/SUBTRACT/MULTIPLY/DIVIDE/COMPUTE operand structure, STRING/UNSTRING, nested `ON SIZE ERROR`/`AT END`/`ON OVERFLOW` clauses) and structural parsing of the environment division (SELECT/ASSIGN, SOURCE-COMPUTER, and so on).
* Broader reference resolution (MOVE source expressions, IF/EVALUATE conditions) once that deeper grammar exists.
* Cross references, outline, hover, go-to-definition, find references, rename.
* Configurable syntax highlighting driven by the token stream.
* Fixed-format column and coding-area guides (sequence area, indicator column, Area A/B, reference margin visualization) in the editor.
* Automatic indentation and division/section/paragraph/data-group/structured-statement folding.
* Code completion, snippets, signature help, documentation lookup.

These language services will be testable independently from the Qt editor widget, following the same pattern as the lexer, parser, and semantic analysis.

### GitHub integration

GitHub integration is a separate, not-yet-started layer on top of the existing Git service: authenticated GitHub account and repository workflows, with pull request and issue integration planned as the project develops.

### Compiler integration (remaining)

The compiler subsystem already supports GnuCOBOL and a generic custom local compiler profile. Not yet built: build pipelines, incremental build, and dedicated warning/listing parsers beyond the existing diagnostic parsing. Additional vendor providers (Micro Focus, IBM Enterprise COBOL, ACUCOBOL, Visual COBOL) are explicitly out of scope for now — the project is intentionally scoped to GnuCOBOL and custom compiler profiles.

### Debugger

Not yet started: a debugger abstraction, a GDB adapter, breakpoints, watch window, locals, call stack, memory, registers, threads, and expression evaluation.

### Plugins

OpenCobol2 is intended to expose a versioned community plugin API.

Planned extension points include:

* Commands.
* Menu contributions.
* Settings schemas.
* Syntax themes.
* Language services.
* Toolchain providers.
* Build providers.
* Test providers.
* Remote resource providers.
* Project types.
* Application panels and views.

Plugins should use defined registries and APIs instead of directly monkey-patching the application window.

### Remote and mainframe development

OpenCobol2 is intended to support resources that are not represented by a local `Path`.

Planned remote resource providers include:

* Local files.
* SSH-accessible files.
* z/OSMF resources.
* Mainframe data sets and members.

The remote-resource architecture will account for host encoding, resource identity, and record-oriented mainframe resources rather than treating every remote source as a UTF-8 POSIX file.

## Repository layout

The repository is organized around a hard boundary between current and archived code.

```text
OpenCobol2/
├── docs/
├── legacy/
│   └── opencobolide/
├── resources/
├── src/
│   └── opencobol2/
├── tests/
│   ├── integration/
│   └── unit/
├── tools/
├── AUTHORS.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── README.md
└── setup.py
```

## Development requirements

OpenCobol2 currently targets:

* Python 3.14 or newer.
* PySide6 6.10 or newer.
* pytest 9 or newer for testing.
* pytest-cov 7 or newer for coverage tooling.
* Modern PEP 517 packaging through `pyproject.toml`.

A GnuCOBOL installation is required to run real compiler integration tests and will ultimately be required for GnuCOBOL compilation features.

GnuCOBOL is not bundled into the OpenCobol2 source tree.

## Development setup

Clone the repository and create a virtual environment.

```powershell
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install OpenCobol2 in editable development mode:

```powershell
python -m pip install -e ".[dev]"
```

Run the complete test suite:

```powershell
python -m pytest -v
```

Integration tests that require a real GnuCOBOL installation skip cleanly when no valid compiler is discovered.

## Development status

OpenCobol2 is currently focused on architecture and foundation work.

Compiler, document, settings, command/menu/tool-window, source-control (Git), project-model, and COBOL language-service (lexer, parser, first semantic pass) boundaries are now implemented and extensively unit tested, Qt-independent from the start. The GUI shell that will actually render all of this — menu bar, toolbar, editor widget, docked panels — has not been built yet, nor has deeper COBOL semantic analysis, the plugin system, debugger, or remote/mainframe resource layer.

This build-the-core-first order is intended to prevent the successor application from becoming a thin modern shell around decade-old implementation patterns.

## Contributing

Contributions are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before starting significant work and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

The archived implementation under `legacy/opencobolide` should be treated as reference material unless a change specifically concerns archival preservation.

## Authors and project history

OpenCobol2 preserves the history of OpenCobolIDE and recognizes the original project's authors and contributors.

See [AUTHORS.md](AUTHORS.md) for project attribution.

The complete Git history remains the authoritative record of individual code contributions.

## License

OpenCobol2 is distributed under the GNU General Public License version 3 or later.

See [LICENSE](LICENSE) for the complete license text.

OpenCobol2 preserves the GPL licensing and inherited history of OpenCobolIDE.
