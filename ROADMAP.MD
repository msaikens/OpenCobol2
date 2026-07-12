# OpenCobol2 Roadmap

This is the phase-by-phase build roadmap for OpenCobol2. It is reconciled against the actual source tree (not just self-reported progress) as of 2026-07-11. See [README.MD](README.MD) for a narrative description of what each implemented subsystem actually does.

Status legend: ✅ done · 🔶 partially done · ⬜ not started · 🚫 intentionally out of scope

## Phase 1 — Foundation (core application complete; Git foundation complete except deliberately deferred items)

Everything in "Core application" below started as a Qt-independent registry/model, fully unit tested on its own. Most of it is now also rendered by the Phase 7 shell (see below); each bullet notes whether that rendering exists yet.

**Core application**

* ✅ Service registry
* ✅ Dependency injection
* ✅ Command framework
* ✅ Menu contribution framework (including submenus and dynamic menus)
* ✅ Toolbar contribution framework
* ✅ Status bar (`StatusBarItemDefinition`/`StatusBarItemRegistry`/`StatusBarService` mirror the menu/toolbar contribution pattern; the Phase 7 shell renders one label per registered item — left-aligned via `QStatusBar.addWidget`, right-aligned via `addPermanentWidget` — and refreshes them from live application state; no click-to-execute-a-command support yet, items are read-only)
* ✅ Tool-window/docking registry (id, title, default dock area, default visibility; now actually rendered as real `QDockWidget` panels by the Phase 7 shell, see below)
* ✅ Theme system (`Theme`/`ThemeColors`/`ThemeKind` models, a `ThemeRegistry`, a built-in catalog of four themes — Light, Dark, High Contrast Light, High Contrast Dark — a `ThemeService` for active-theme selection, and a persisted `ThemeSettings` section; the Phase 7 shell now applies the active theme's palette to real widgets)
* ✅ Accent color normalization (per-tool-window accent override, scoped to the accessibility profile below)
* ✅ Accessibility preference profiles (color-vision assistance strategies, tool-window accent overrides)
* ✅ Settings framework
* ✅ Configuration persistence (schema-versioned, atomic same-directory JSON writes)
* ✅ Qt-independent document/workspace model (open/save/dirty tracking, encoding + BOM + line-ending handling)
* ✅ Project model

**Git foundation**

Done:

* ✅ Process runner
* ✅ Porcelain-v2 status parser
* ✅ Repository discovery and status
* ✅ Stage / unstage / stage all / unstage all
* ✅ Commit staged changes
* ✅ Create repository / clone repository
* ✅ Remote management (list, add, remove, rename)
* ✅ Fetch, pull, push (merge-conflict-aware)
* ✅ Branch management (list, create, delete, switch)
* ✅ Tag management (list, create — lightweight and annotated, delete)
* ✅ Stash (list, push, apply/pop, drop)
* ✅ Commit history / log
* ✅ Reset (soft/mixed/hard), revert, cherry-pick
* ✅ Diff engine (worktree, staged/index, and per-commit unified diffs)

Still remaining:

* ⬜ Blame
* ⬜ Merge
* ⬜ Rebase
* ⬜ Worktrees
* ⬜ Submodules

We are not implementing every Git feature immediately. The IDE only needs enough Git to compete with VS Code — blame/merge/rebase/worktrees/submodules are deferred until a concrete need shows up.

## Phase 2 — Project System

Most of the non-GUI foundation is done; what remains is almost entirely GUI (Phase 7).

* ✅ Virtual (logical) folders
* ✅ Linked files
* ✅ Excluded file patterns
* ✅ Project properties (output directory, default compiler profile reference, default launch configuration)
* ✅ Project-level environment variable overrides
* ✅ Tasks (user-defined, directly executable)
* ✅ Launch configurations (directly executable, layered environment resolution)
* 🔶 Compiler profiles / runtime profiles — the compiler-provider and runtime abstraction exists (Phase 5) and a project can reference a profile by ID, but there is no project-level UI/CRUD for authoring profiles yet
* ✅ Project Explorer (`ProjectExplorerWidget`, Phase 7: a real tree showing the project's physical files honoring `excluded_patterns`, virtual folders with nested members, and linked files not already organized into a virtual folder; all four File > Project commands — New, Open, Save As, Close — are wired to real handlers)

## Phase 3 — Editor

This is still the largest remaining subsystem. The Qt-independent document core (Phase 1) already covers three of these at the model level; everything else needs an actual editor widget, which does not exist yet.

* ✅ Encoding detection (document-core level)
* ✅ BOM support (document-core level)
* ✅ CRLF/LF conversion (document-core level)
* ⬜ Split editors
* ⬜ Tabs
* ⬜ Dirty tracking UI (state exists in the document core; no visible indicator yet)
* ⬜ Autosave
* ⬜ Undo/redo manager
* ⬜ Code folding
* ⬜ Bookmarks
* ⬜ Breakpoints
* ⬜ Minimap
* ⬜ Line numbers
* ⬜ Search/replace
* ⬜ Multiple cursors
* ⬜ Column selection
* ⬜ Printing

## Phase 4 — COBOL Language Services

The analysis pipeline (lexer through cross-references) is done and verified against real legacy `.cbl` files. Everything editor-facing built on top of it still needs to be built.

* ✅ Lexer (fixed and free format)
* ✅ Parser
* ✅ AST
* ✅ Semantic analysis (data-item symbol table, procedure symbol table, duplicate-name detection)
* ✅ Symbol tables
* ✅ Cross references (data-name and procedure-name reference index — the foundation for go-to-definition/find-references/rename)
* 🔶 Diagnostics (lex/parse/semantic diagnostic data models exist and are populated; not yet surfaced in an IDE problems panel)
* ⬜ Outline
* ⬜ Hover
* ⬜ Go to definition (data foundation exists; navigation feature itself is not built)
* ⬜ Find references (same — data foundation exists, feature is not built)
* ⬜ Rename
* ⬜ Quick fixes
* ⬜ Syntax coloring
* ⬜ Formatting
* ⬜ Code completion
* ⬜ Snippets
* ⬜ Signature help
* ⬜ Documentation lookup

## Phase 5 — Compiler Integration

Scope decision: OpenCobol2 supports GnuCOBOL and custom local compiler profiles only. Micro Focus, IBM Enterprise COBOL, ACUCOBOL, and Visual COBOL providers are intentionally not planned.

* ✅ Compiler abstraction (provider registry + configuration)
* ✅ GnuCOBOL provider
* ✅ Custom local compiler provider
* 🚫 Micro Focus provider (out of scope)
* 🚫 IBM Enterprise COBOL provider (out of scope)
* 🚫 ACUCOBOL provider (out of scope)
* 🚫 Visual COBOL provider (out of scope)
* ✅ Compile commands (structured compile requests, real `cobc`/custom-toolchain process invocation)
* 🔶 Link commands (GnuCOBOL's single-invocation `cobc` model handles compile+link together; a distinct link step isn't needed for the currently supported providers)
* ⬜ Build pipelines (multi-file/whole-project builds)
* ⬜ Incremental build
* ✅ Error parser
* ✅ Warning parser
* ⬜ Listing parser

## Phase 6 — Debugger

Still untouched.

* ⬜ Debugger abstraction
* ⬜ GDB adapter
* ⬜ Breakpoints
* ⬜ Watch window
* ⬜ Locals
* ⬜ Call stack
* ⬜ Memory
* ⬜ Registers
* ⬜ Threads
* ⬜ Expression evaluation

## Phase 7 — UI

The application shell now renders for real (`src/opencobol2/gui/`): a `MainWindow` builds a live menu bar and toolbars from command contributions (rebuilt from live command/dynamic-menu state every time a menu opens), docks every registered tool window (with a pluggable per-tool-window content factory), renders a real content-driven status bar, and applies the active theme's palette. It launches via `python -m opencobol2.gui.application` or the `opencobol2` console script (`create_main_window()` wires the real built-in command/tool-window/theme/status-bar registries together, plus an optional `Project` to seed the Project Explorer). File > New/Open/Save As/Close Project are all real, working commands, the status bar reflects the open project and active theme live, View > Command Palette (Ctrl+Shift+P) opens a real searchable command list, and Tools > Settings opens a real Preferences dialog that applies changes to the running window immediately. Project Explorer and Git Changes are the first tool windows with real content; Output, Problems, Git Repository, and the rest are still placeholders.

* ✅ Application shell (`MainWindow`: live menu bar + toolbars rendered from command contributions, a real content-driven status bar, theme palette application, a real runnable bootstrap)
* ✅ Status bar (see Phase 1 above for the domain model; the shell's built-in items show the open project's name — reacting live to `ProjectExplorerWidget.project_changed` — and the active theme, reacting when `apply_active_theme()` runs)
* ✅ Command Palette (`CommandPaletteDialog`, `opencobol2.gui.command_palette`: lists every registered command with its category, filters live by typed text against title and category, arrow-key navigable, executes on Enter/double-click; disabled commands show but don't execute, hidden commands are omitted; wired to View > Command Palette / Ctrl+Shift+P)
* ✅ Tool windows (rendering the Phase 1 registry: one `QDockWidget` per registered definition, initial dock area + visibility applied, visibility synced bidirectionally with `ToolWindowService`, pluggable real content per tool window; pinning/auto-hide and floating-geometry restoration are not implemented yet — plain QDockWidget floating/closable behavior is used as-is)
* ⬜ Welcome page
* ⬜ Recent projects
* ✅ Preferences dialog (`SettingsDialog`, `opencobol2.gui.settings_dialog`: Editor/COBOL/Theme tabs backed by the real `SettingsService`; wired to Tools > Settings; applying immediately updates the running window's palette and status bar via an `on_applied` callback, not just the persisted file. No compiler-profile or external-tool-path editing yet — those stay on `Tools > Compiler Profiles`, still unconfigured)
* ✅ Project explorer (`ProjectExplorerWidget`: real physical-file tree honoring `excluded_patterns`, virtual folders, and linked files — see Phase 2; all four project file commands — New, Open, Save As, Close (`opencobol2.gui.project_commands`) — are wired to real handlers using stock `QFileDialog`/`QInputDialog` prompts, no custom dialog widgets built yet)
* ⬜ Output window (dock panel renders; real content not built)
* ⬜ Problems window (dock panel renders; real content not built)
* ⬜ Terminal
* 🔶 Git window (`GitChangesWidget`, `opencobol2.gui.git_changes`: real working-tree status against `GitService`, honoring a repository auto-discovered from the open project's root; branch name, staged/unstaged file lists, stage/unstage via double-click or Stage All/Unstage All, and commit with a message box — all verified against a real `git` repository, which caught and fixed a real bug in `GitService.unstage_all()` — `git rm --recursive` isn't a valid long option, only `-r` is. Git Repository dock panel — branches/tags/remotes/history browsing — still renders as a placeholder)
* ⬜ Search window (Find Results dock panel renders; real content not built)
* ⬜ Outline
* ⬜ Bookmarks
* ⬜ Task list
* ⬜ Extensions UI

## Phase 8 — Extension SDK

Still untouched. One of the biggest goals of the modernization branch.

* ⬜ Plugin loader
* ⬜ Manifest schema
* ⬜ Extension lifecycle
* ⬜ Dependency resolution
* ⬜ Version compatibility
* ⬜ Commands
* ⬜ Menus
* ⬜ Toolbars
* ⬜ Language extensions
* ⬜ Compiler extensions
* ⬜ Debugger extensions
* ⬜ Theme extensions

## Phase 9 — Testing

Coverage for the foundation built so far is strong.

* ✅ Unit tests (800+, covering every implemented subsystem)
* ✅ Real-executable smoke tests (real `git.exe`, real GnuCOBOL `cobc`, real `.cbl` files under `legacy/opencobolide/tests/testfiles/`)
* 🔶 Integration tests (`tests/integration/` covers real GnuCOBOL toolchain discovery and diagnostics; broader cross-subsystem integration coverage is still thin)
* 🔶 GUI tests (the Phase 7 shell — menus, toolbars, dock widgets, theming, bootstrap — is unit tested against a real offscreen `QApplication`; no interaction-simulation/visual-regression tooling yet)
* ⬜ End-to-end tests
* ⬜ Performance tests
* ⬜ Startup tests
* ⬜ Memory leak testing
* ⬜ Plugin compatibility tests
* ⬜ Windows installer tests

## Phase 10 — Distribution

Still to build.

* ⬜ Windows installer
* ⬜ Portable ZIP
* ⬜ Embedded GnuCOBOL
* ⬜ Automatic updates
* ⬜ Crash reporting
* ⬜ Telemetry (optional)
* ⬜ Code signing
* ⬜ MSIX packaging
