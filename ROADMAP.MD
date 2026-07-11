# OpenCobol2 Roadmap

This is the phase-by-phase build roadmap for OpenCobol2. It is reconciled against the actual source tree (not just self-reported progress) as of 2026-07-11. See [README.MD](README.MD) for a narrative description of what each implemented subsystem actually does.

Status legend: ✅ done · 🔶 partially done · ⬜ not started · 🚫 intentionally out of scope

## Phase 1 — Foundation (~90–95% complete)

Everything in "Core application" below is a Qt-independent registry/model. It is fully unit tested, but nothing is rendered by a GUI yet — that is Phase 7.

**Core application**

* ✅ Service registry
* ✅ Dependency injection
* ✅ Command framework
* ✅ Menu contribution framework (including submenus and dynamic menus)
* ✅ Toolbar contribution framework
* ✅ Status bar contributions
* ✅ Tool-window/docking registry (id, title, default dock area, default visibility — metadata only, no rendered docking widget yet)
* ⬜ Theme system (no light/dark palette or stylesheet engine exists yet)
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
* ⬜ Project Explorer (the actual tree widget — blocked on Phase 7's GUI shell)

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

Still untouched — the GUI shell itself. Every registry built in Phase 1 (commands, menus, toolbars, tool windows) and the Project Explorer (Phase 2) are waiting on this phase.

* ⬜ Welcome page
* ⬜ Recent projects
* ⬜ Preferences dialogs
* ⬜ Tool windows (rendering the Phase 1 registry)
* ⬜ Project explorer
* ⬜ Output window
* ⬜ Problems window
* ⬜ Terminal
* ⬜ Git window
* ⬜ Search window
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
* ⬜ GUI tests
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
