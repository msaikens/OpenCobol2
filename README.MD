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
* A selected color theme (see "Color theme system" below).
* Atomic, same-directory replacement saves.

A settings service exposes the current settings snapshot and supports reload and partial updates.

### Command, menu, and tool window framework

OpenCobol2 has a Qt-independent command and contribution framework:

* A command registry with declarative command definitions, an extensible built-in command catalog, and placeholder commands reserved for future GUI wiring.
* Menu and toolbar contribution registries, including submenu and dynamic menu support.
* A tool window registry describing docked panels (id, title, default dock area, default visibility, accessibility description). The Phase 7 shell now renders these as real docked panels.
* Accessibility preference profiles.

### Status bar item contribution model

OpenCobol2 has a Qt-independent status bar item model, mirroring the menu/toolbar contribution pattern above:

* `StatusBarItemDefinition` describes one item: an ID, a left/right `StatusBarItemAlignment`, a display order, and a zero-argument provider callable that returns its current `StatusBarItemContent` (text, optional tooltip, visibility).
* A `StatusBarItemRegistry` for registering items and listing them per alignment, ordered for display.
* A `StatusBarService` that resolves items (individually or by alignment) by calling their providers for current content.

Items are read-only — there is no click-to-execute-a-command support yet. The Phase 7 application shell (below) renders these as real labels and keeps them refreshed from live application state.

### Color theme system

OpenCobol2 has a Qt-independent color theme model, independent of any rendered stylesheet:

* `Theme`, `ThemeColors`, and `ThemeKind` models describing a named palette (background, foreground, accent, selection, editor, line-number, current-line, and diagnostic-severity colors) validated as `#RRGGBB` hex values.
* A `ThemeRegistry` for registering and resolving themes by ID, plus a built-in catalog of four themes: Light, Dark, High Contrast Light, and High Contrast Dark.
* A `ThemeService` that tracks the active theme against a registry and validates theme switches.
* The active theme selection is persisted as part of application settings.

The Phase 7 application shell (below) now applies the active theme's palette to real widgets.

The command, menu, tool-window, status-bar, and theme registries above are fully unit tested independently of Qt, in addition to their Phase 7 rendering.

### Application shell

OpenCobol2 has a real, launchable Qt application shell (`src/opencobol2/gui/`), independent from — and built entirely on top of — the Qt-independent registries above:

* `MainWindow` builds a live menu bar and toolbars from command surface contributions. Menus rebuild themselves from current command/dynamic-menu state every time they open, so enabled/checked state and dynamic entries (like a future recent-files list) are never stale.
* Every registered tool window is rendered as a real `QDockWidget`: initial dock area and visibility come from `ToolWindowService`, and visibility changes made through the real widget (closing a panel, for example) are synced back into that service. Pinning/auto-hide and floating-geometry restoration are not implemented yet; panels use plain `QDockWidget` floating/closable behavior as-is. Each tool window can be given real content through a pluggable per-tool-window content factory; panels without one fall back to a placeholder. Project Explorer and Git Changes are the first two panels with real content (see "Project system" and "Git integration" below) — Output, Problems, Git Repository, and the rest still fall back to the placeholder.
* The status bar renders one real label per registered status bar item — left-aligned items via `QStatusBar.addWidget`, right-aligned items via `addPermanentWidget` — and `MainWindow.refresh_status_bar()` re-resolves every item's provider on demand. The built-in items show the currently open project's name (updating live off `ProjectExplorerWidget.project_changed`) and the active theme's name (updating whenever `apply_active_theme()` runs).
* The active color theme is applied to the shell as a real `QPalette`.
* A `CommandPaletteDialog` (View > Command Palette, Ctrl+Shift+P) lists every registered command with its category, filters live as the user types (matching against both title and category), supports arrow-key navigation, and executes the selected command on Enter or double-click. Commands the current `CommandState` reports as disabled are shown but not executable; hidden commands are omitted entirely.
* A `SettingsDialog` (Tools > Settings) edits Editor, COBOL, and Theme settings against the real `SettingsService` across three tabs, preloaded from and persisted back to the same settings file every other subsystem reads. Applying changes doesn't just write to disk — an `on_applied` callback immediately switches the running window's active theme and refreshes the palette and status bar, so a theme change is visible the moment you click OK.
* `create_main_window()` (`opencobol2.gui.application`) wires the real built-in command, tool-window, theme, and status-bar registries together into a working window, optionally seeded with a `Project` to show in the Project Explorer. The application launches via `python -m opencobol2.gui.application` or the `opencobol2` console script (`[project.gui-scripts]`).

The shell is unit tested against a real, offscreen (`QT_QPA_PLATFORM=offscreen`) `QApplication` — no display server is required to run these tests.

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

A real `GitChangesWidget` (`opencobol2.gui.git_changes`) now renders inside the application shell's Git Changes dock panel: the current branch name, staged and unstaged file lists (with a status letter — `M`/`A`/`D`/`R`/`?` and so on), stage/unstage via double-click or "Stage All"/"Unstage All" buttons, and commit with a typed message. The panel tracks whatever Git repository `GitService.discover_repository()` finds at the currently open project's root, falling back to an empty state if there is none or if `git` itself is unavailable. Building this against a *real* repository (not a mock) caught and fixed a genuine bug: `GitService.unstage_all()` invoked `git rm --cached --recursive`, but `git rm` only accepts the short `-r` flag — every prior test for that path was mocked and asserted the broken command was constructed "correctly."

### Project system

OpenCobol2 has a persisted project model that stays independent of any specific compiler dialect beyond the compiler profile it references:

* Project identity, root path, and build/launch default properties.
* Virtual (logical) folders, independent of physical directory layout.
* Linked files sourced from outside the project root.
* Excluded file patterns and project-level environment variable overrides.
* User-defined tasks and launch configurations, directly executable as local processes with layered environment resolution (ambient OS environment, then project overrides, then task/launch overrides).

Project persistence uses the same schema-versioned, atomic-replacement JSON storage pattern as application settings.

A real Project Explorer (`ProjectExplorerWidget`) now renders inside the application shell's dock panel (see "Application shell" above): a physical file/directory tree of the project root honoring `excluded_patterns`, a "Virtual Folders" branch showing the logical folder tree (including nested folders, member file paths, and referenced linked files), and a "Linked Files" branch for any linked file not already organized into a virtual folder.

All four project file commands (`opencobol2.gui.project_commands`) are wired to real handlers: New Project prompts for a name, a root directory, and a save location, then creates and persists a project; Open Project prompts for a project file and loads it through `ProjectStorage`; Save Project As persists the currently open project to a new location; Close Project clears the panel back to its empty state. `create_main_window(project=...)` can also seed a project directly.

### COBOL language services (lexer, parser, semantic analysis)

OpenCobol2 has begun in-house COBOL language services, independent of the GnuCOBOL compiler process:

* A COBOL lexer supporting both fixed and free source format, with fixed-format sequence area/indicator column/Area A/B handling, continuation of alphanumeric literals across source lines, whole-line and inline (`*>`) comments, and diagnostics for unterminated literals, malformed continuations, and unrecognized characters. The reserved-word table is sourced from a full COBOL reserved-word reference (the standard Reserved / Standard-only / Potential-reserved-word split), keeping only words reserved under GnuCOBOL's default dialect, plus two documented GnuCOBOL-specific exceptions (`END-ACCEPT`, `END-DISPLAY`) that the reference marks as merely potential but GnuCOBOL genuinely supports as scope terminators.
* A recursive-descent parser building a real AST for program identity, data description entries (including FILE SECTION `FD`/`SD` entries), and procedure division structure (paragraphs, sections). It gives full structure to IF/ELSE/END-IF, PERFORM (out-of-line, inline, `VARYING`/`UNTIL`/`TIMES`), and EVALUATE/WHEN, including COBOL's implicit period-based scope termination (a lone `.` can close every enclosing IF/PERFORM/EVALUATE at once). Every other statement verb (ADD, CALL, STRING, and so on) is captured as a generic statement (verb plus raw tokens) rather than being deeply modeled yet; a verb's nested-statement clauses (`ON SIZE ERROR`, `AT END`, `ON OVERFLOW`) are a known, documented gap. The environment division is recognized but parsed opaquely.
* Semantic analysis: a symbol table for data items (respecting level-number nesting, including 66 RENAMES, 77 standalone items, and 88 condition names) and for procedure division paragraphs/sections (flagging duplicate names), plus a cross-reference index recording every successfully resolved name usage (the foundation for future go-to-definition, find-references, and rename). MOVE targets and PERFORM targets are structurally guaranteed name positions, so an unresolved one is an ERROR; every other token list a statement carries (MOVE sources, IF/EVALUATE conditions, PERFORM modifiers, DISPLAY operands, and unmodeled-verb operands) is scanned best-effort at WARNING level, since those lists mix data names with syntax not deeply modeled yet (intrinsic functions, index-names). Verifying this coverage against real legacy source also caught and fixed three real parser gaps: `PERFORM data-name TIMES` misparsed as an out-of-line target, the `END PROGRAM name.` marker not being recognized, and missing `INPUT`/`OUTPUT`/`I-O`/`EXTEND`/`FUNCTION` reserved words.

All three are tested against synthetic COBOL source and against the real `.cbl` files preserved under `legacy/opencobolide/tests/testfiles/`. Higher-level language services (outline, hover, go-to-definition, completion) are not yet implemented.

## Planned architecture milestones

OpenCobol2 has established contracts for most core systems, and a first real GUI shell now sits on top of them. Settings, the command/menu/tool-window registries, Git, the project model, a COBOL lexer/parser, and the application shell described below are already implemented (see "Current foundation" above); this section covers what still sits ahead of them.

For a detailed, phase-by-phase status of every planned subsystem (including what's fully done, partially done, or intentionally out of scope), see [ROADMAP.MD](ROADMAP.MD).

### GUI shell

The application shell exists and runs (see "Application shell" under "Current foundation" above: a live menu bar and toolbars rendered from the command/menu contribution registries, and docked tool-window panels backed by the tool window registry). What's still ahead:

* Real content for each remaining docked tool-window panel — Git Repository, Output, Problems, Terminal, Search, Outline, Bookmarks, Task List, and Extensions panels currently render as placeholders (Project Explorer and Git Changes now have real content).
* A dedicated New Project dialog widget — today it's a sequence of stock `QInputDialog`/`QFileDialog` prompts rather than a single purpose-built form.
* A Welcome page and a recent-projects list. Preferences now exist (Tools > Settings) but only cover editor/COBOL/theme settings — compiler-profile and external-tool-path editing are still ahead.
* A text editor widget (tabs, split editors, dirty tracking, undo/redo, folding, minimap, multiple cursors, and the rest of the editor feature set) — the biggest remaining piece, and a prerequisite for docking anything into the shell's document area.
* Tool-window pinning/auto-hide and floating-geometry persistence, which the current dock manager doesn't implement yet.

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

Compiler, document, settings, command/menu/tool-window, source-control (Git), project-model, and COBOL language-service (lexer, parser, first semantic pass) boundaries are now implemented and extensively unit tested, Qt-independent from the start. A first real GUI shell now renders a live menu bar, toolbars, a status bar, and docked tool-window panels on top of that foundation, plus a Command Palette and a Settings dialog. Project Explorer and Git Changes are the first panels with real content; Output, Git Repository, and the rest are still placeholders, and the text editor widget has not been built yet. Deeper COBOL semantic analysis, the plugin system, debugger, and remote/mainframe resource layer also remain ahead.

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
