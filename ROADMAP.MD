# OpenCobol2 Roadmap

This is the phase-by-phase build roadmap for OpenCobol2. It is reconciled against the actual source tree (not just self-reported progress) as of 2026-07-12. See [README.MD](README.MD) for a narrative description of what each implemented subsystem actually does.

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
* ✅ Theme system (`Theme`/`ThemeColors`/`ThemeKind` models, a `ThemeRegistry`, a built-in catalog of four themes — Light, Dark, High Contrast Light, High Contrast Dark — a `ThemeService` for active-theme selection, and a persisted `ThemeSettings` section; the Phase 7 shell now applies the active theme's palette to real widgets; `ThemeColors` also carries four syntax-token color fields — `syntax_keyword`/`syntax_string`/`syntax_number`/`syntax_comment` — consumed by the Phase 3/7 syntax highlighter)
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

Complete. The last remaining gap (a project-level UI for selecting a default compiler profile) closed with `ProjectPropertiesDialog`.

* ✅ Virtual (logical) folders
* ✅ Linked files
* ✅ Excluded file patterns
* ✅ Project properties (output directory, default compiler profile reference, default launch configuration)
* ✅ Project-level environment variable overrides
* ✅ Tasks (user-defined, directly executable)
* ✅ Launch configurations (directly executable, layered environment resolution)
* ✅ Compiler profiles / runtime profiles — the compiler-provider and runtime abstraction exists (Phase 5), `CompilerProfilesDialog` (Tools > Compiler Profiles, Phase 7) authors the global `CompilerSettings.profiles` list, and `ProjectPropertiesDialog` (`opencobol2.gui.project_properties_dialog`, Phase 7 — right-click the project's root item in Project Explorer > Properties...) now lets one specific project select which of those profiles its `properties.default_compiler_profile_id` should reference (or fall back to the global default). Build Project (Phase 5/7) prefers a project's own profile over the global default when one is set.
* ✅ Project Explorer (`ProjectExplorerWidget`, Phase 7: a real tree showing the project's physical files honoring `excluded_patterns`, virtual folders with nested members, and linked files not already organized into a virtual folder; all four File > Project commands — New, Open, Save As, Close — are wired to real handlers)

## Phase 3 — Editor

A first-cut editor widget now exists (`EditorTabsWidget`/`SourceEditorWidget`, `opencobol2.gui.editor`), built on the Qt-independent document core (Phase 1) below. It now has real COBOL syntax highlighting, code folding, and a minimap (see below) — split editors and multiple cursors are still ahead.

* ✅ Encoding detection (document-core level)
* ✅ BOM support (document-core level)
* ✅ CRLF/LF conversion (document-core level)
* ⬜ Split editors
* ✅ Tabs (`EditorTabsWidget`: one tab per open document, docked as the shell's central widget; double-clicking a physical file in Project Explorer opens it, reusing an already-open tab for the same path)
* ✅ Dirty tracking UI (tab title grows a trailing `*` while the document's `is_modified`, reflecting the document-core state live as the user types)
* ✅ Autosave (`EditorSettings.autosave_enabled`/`autosave_interval_seconds`, editable in the Settings dialog's Editor tab; a `QTimer` on `EditorTabsWidget`, started/stopped/re-interval'd every time `apply_editor_settings()` runs — bootstrap, live Settings-dialog apply, or otherwise — sweeps every open tab on each timeout and silently saves any document that's both modified and already has a path, skipping untitled documents and swallowing `OSError` rather than surfacing a blocking dialog from a background timer. Building this caught and fixed a real persistence bug: `SettingsStorage` serialized/deserialized `EditorSettings` through a hand-written field list rather than the dataclass itself, so the two new fields silently never round-tripped to disk — the existing exhaustive round-trip test didn't catch it because it happened to leave both fields at their defaults, so the same wrong default came back on reload and the equality check passed anyway. Fixed the storage code and strengthened that test to use non-default values for every field, present and future)
* ✅ Undo/redo manager (Qt's built-in `QPlainTextEdit` undo stack — Ctrl+Z/Ctrl+Y — no custom implementation needed)
* ✅ Code folding (fold ranges from a new Qt-independent language service, `opencobol2.language.compute_fold_ranges` — walks the real parser's AST for divisions/sections/paragraphs/IF/PERFORM/EVALUATE bodies rather than guessing from indentation; the editor gutter gets a clickable `+`/`-` marker per foldable line, collapsing hides the range via `QTextBlock.setVisible` and paints a `⋯` badge on the fold's start line; nested collapsed folds survive their parent being expanded; gated by `EditorSettings.code_folding`, a real persisted setting with no consumer until now. Not yet built: folding individual group data items by level-number nesting — `DataSectionNode` holds a flat item list, not a level-number tree)
* ✅ Bookmarks (`SourceEditorWidget.toggle_bookmark_at_cursor`/`bookmarked_lines`, stored as live `QTextBlock` handles so a bookmark keeps tracking its physical line of text across edits elsewhere — see Phase 7 below for the real `BookmarksWidget` panel built on top. Session-only, no persistence)
* ✅ Breakpoints, editor-side UI only (`SourceEditorWidget.toggle_breakpoint_at_cursor`/`breakpoint_lines`, and a new `BreakpointsWidget` panel — both a straight mirror of Bookmarks: live `QTextBlock` handles so a breakpoint keeps tracking its physical line of text across edits elsewhere, session-only, no persistence. Painted as a small filled circle in a new dedicated gutter region to the left of the bookmark strip, rather than sharing that same 4px column, since a line can carry both a bookmark and a breakpoint at once. Edit > Toggle Breakpoint (F9). Purely visual/state — there is no debugger backend to actually break execution at one of these yet; see Phase 6, still untouched)
* ✅ Minimap (`_MinimapArea`/`SourceEditorWidget`, `opencobol2.gui.editor` — a fixed-width strip docked to the viewport's right edge, the same sibling-widget-plus-viewport-margin pattern the line-number gutter already used, just mirrored to the other side. Rather than rendering the real text at an unreadably tiny font size, each non-blank line is painted as a density tick whose width is proportional to that line's character count (capped at 80 characters), colored from `editor_foreground`; a translucent `current_line_highlight`-colored band shows which lines the real viewport currently covers. Clicking or dragging within it moves the cursor to the corresponding line via the existing `go_to_line()`, the same "click a location, jump the editor there" pattern already used by Outline/Bookmarks/Find Results. Gated by a new `EditorSettings.show_minimap` toggle (default on, editable in the Settings dialog's Editor tab) — disabling it hides the strip and gives its width back to the text area)
* ✅ Line numbers (`SourceEditorWidget`'s gutter, the standard `QPlainTextEdit` line-number-area pattern — width scales with digit count, repainted on scroll/edit, colored from `Theme.colors.line_number_foreground`; also renders current-line highlighting via `setExtraSelections`, colored from `current_line_highlight` — both fields existed in the theme model since Phase 1 with no consumer until now, and both recolor live via `EditorTabsWidget.apply_theme()` on a theme switch)
* ✅ Search/replace (`SourceEditorWidget`'s in-editor find bar: forward/backward find with wraparound, an optional match-case toggle, Replace, and Replace All, all driven by Qt's own `QPlainTextEdit.find()` rather than hand-rolled search logic; wired to Edit > Find / Replace, Ctrl+F / Ctrl+H, which were registered commands with menu contributions but no handler until now)
* ✅ Syntax highlighting (`CobolSyntaxHighlighter`, `opencobol2.gui.syntax_highlighter`: a `QSyntaxHighlighter` driven by the real `tokenize_cobol_source` lexer — Phase 4 — coloring reserved words, string/alphanumeric literals, numeric literals, and comments from four new `Theme.colors` fields, `syntax_keyword`/`syntax_string`/`syntax_number`/`syntax_comment`, added to all four built-in themes; attached only to recognized COBOL files — `.cbl`/`.cob`, and untitled/new documents — not to any other file opened in the editor; re-lexes the whole document per edit rather than incrementally, an honest scaling limitation for very large files)
* ✅ Font/tab-width settings (`EditorSettings.font_family`/`font_size`/`tab_width` — real, persisted, editable in the Settings dialog's Editor tab since before Phase 7, but with no consumer anywhere until now; applied to every `SourceEditorWidget` as a real `QFont` and tab stop distance, falling back to the system fixed-pitch font when no family is configured, live-updated through the same Settings-dialog callback as the theme)
* ✅ Fixed-format coding-area guides (`CodingAreaGuides`, `opencobol2.gui.coding_area_guides` — see Phase 4 for the full description)
* ⬜ Multiple cursors
* ⬜ Column selection
* ✅ Printing (File > Print (Ctrl+P), a new `BuiltInCommandIds.FILE_PRINT` command — opens a real, native `QPrintDialog` over a `QPrinter`, and on acceptance prints the active tab through `EditorTabsWidget.print_active_tab()`, which just delegates to `QPlainTextEdit`'s own built-in `print_()` rather than any hand-rolled pagination/rendering, the same "no custom implementation needed" precedent as undo/redo. A rejected dialog prints nothing)

## Phase 4 — COBOL Language Services

The analysis pipeline (lexer through cross-references) is done and verified against real legacy `.cbl` files. Everything editor-facing built on top of it still needs to be built.

* ✅ Lexer (fixed and free format)
* ✅ Parser
* ✅ AST
* ✅ Semantic analysis (data-item symbol table, procedure symbol table, duplicate-name detection)
* ✅ Symbol tables
* ✅ Cross references (data-name and procedure-name reference index — the foundation for go-to-definition/find-references/rename)
* ✅ Diagnostics (`compute_source_diagnostics`, `opencobol2.language.source_diagnostics` — runs lex, then parse if lexing didn't raise, then semantic analysis if a compilation unit resulted, merging every stage's diagnostics; `LexDiagnostic`/`ParseDiagnostic` already share the same `severity`/`message`/`position` shape, so callers treat them uniformly. Surfaced two ways in Phase 7's editor: `CobolSyntaxHighlighter` underlines each diagnostic's position in a severity-colored squiggle — since a diagnostic carries only a point, not a span, the underline covers the run of non-whitespace characters starting there, an approximation of "the token that's wrong"; and `ProblemsWidget` gained a second, independent diagnostics bucket (`set_live_diagnostics`, scoped to the active editor tab, refreshed on the same `EditorTabsWidget.active_document_changed` signal Outline uses) so live editor diagnostics and the last build's diagnostics coexist without either wiping out the other. A real AST precision limit surfaced while testing this: `MoveStatement.target_names` is a flat tuple of strings with no per-name span, so an "undefined data name" diagnostic points at the MOVE statement's own start rather than at the specific missing name — not a bug in this work, but a real limitation of today's AST worth fixing later if go-to-definition-quality precision is ever needed here)
* ✅ Outline (`compute_outline`, `opencobol2.language.outline` — see Phase 7 below for the real `OutlineWidget` built on top of it)
* ✅ Hover (`compute_hover`, `opencobol2.language.hover` — mirrors `find_definition`'s pipeline (lex → parse → identify the token under the cursor via the same shared `identifier_at` helper → semantic analysis), then describes what the symbol table found: a paragraph or section by kind and name, or a data item rendered as its level number, name, and every clause (`PIC`, `VALUE`, etc.) reconstructed from the clause's own tokens using their real spans to reproduce exact source spacing — e.g. `9(5)V99` stays adjacent, not `9(5) V99`. When the cursor is on a reserved word instead of an identifier, falls back to Documentation lookup below rather than returning nothing. Wired into `SourceEditorWidget` by overriding `event()` to intercept Qt's own `QEvent.Type.ToolTip` event (fired automatically after the mouse rests over the widget) and showing `QToolTip` text at the pointer; gated to COBOL-recognized files, same as syntax highlighting and diagnostics. No command/menu entry — hover is mouse-driven, not keyboard-triggered)
* ✅ Go to definition (`find_definition`, `opencobol2.language.navigation` — resolves the `IDENTIFIER` token under the cursor against the real symbol table (`SymbolTable.find_procedure_symbol`/`find_data_symbols`), single-compilation-unit-scoped since the parser and semantic analyzer never see more than one file at a time and the project model has no cross-file "calls" concept to walk even if they did. Edit > Go to Definition (F12) moves the active tab's cursor to the result. A data-item definition points at the item's own start — its level number — rather than at the name itself, since `DataItemNode.span` covers the whole entry; a real, documented precision limit, not a bug)
* ✅ Find references (`find_references`, same module — every `DataNameReference`/`ProcedureNameReference` matching the identifier under the cursor, plus its own definition, deduplicated and sorted. Edit > Find All References (Shift+F12) reuses the existing Find Results panel rather than a new widget, converting each location into a `FindResult` for the current file; only works for a document that's already been saved, since a `FindResult` needs a real path)
* ✅ Rename (`SourceEditorWidget.rename_symbol_at_cursor`, `opencobol2.gui.editor` — reuses `references_at_cursor()` entirely rather than adding a new language service. Deliberately does NOT trust `SourceLocation.column` as the exact start of the name text: the two documented AST precision limits above (a data item definition pointing at its level number, a MOVE target reference pointing at the MOVE statement's own start) made an initial column-and-length-based replacement implementation silently corrupt source text — caught by testing against real multi-reference source before it shipped. Fixed by rewriting one whole LINE per affected line instead, using a case-insensitive regex matching the old name as a complete COBOL word (bounded by anything other than a letter, digit, or hyphen, since hyphens are legal name characters) so a same-prefixed-but-longer identifier like `WS-COUNT-TOTAL` is never partially matched when renaming `WS-COUNT`. All replacements happen inside one `beginEditBlock()`/`endEditBlock()` pair, so the whole rename undoes in a single Ctrl+Z. Edit > Rename Symbol (F2) prompts for a new name via `QInputDialog`, prefilled with the current name)
* ⬜ Quick fixes
* ✅ Syntax coloring (`CobolSyntaxHighlighter`, `opencobol2.gui.syntax_highlighter` — Phase 3/7: a `QSyntaxHighlighter` driven by the real lexer, coloring reserved words, string/numeric literals, and comments from theme-configurable colors)
* ✅ Fixed-format coding-area guides (`CodingAreaGuides`, `opencobol2.gui.coding_area_guides` — Phase 3/7: column rulers/shading for the sequence area, indicator column, Area A, the Area A/B boundary, and the reference area, independently toggleable via the six `CobolGuideSettings` fields that existed since before Phase 7 with no consumer until now)
* ✅ Code folding (`compute_fold_ranges`, `opencobol2.language.folding` — Qt-independent, walks the real parser's AST for division/section/paragraph/IF/PERFORM/EVALUATE spans; the Phase 3/7 editor gutter renders and toggles it, see Phase 3)
* ✅ Formatting (`SourceEditorWidget.format_document()`, `opencobol2.gui.editor` — Edit > Format Document (Shift+Alt+F). Deliberately conservative: fixed-format COBOL source is column-sensitive, so this never attempts COBOL-aware re-indentation. Trims trailing whitespace from every line unconditionally; separately, converts literal tab characters to spaces via `EditorSettings.insert_spaces`/`tab_width` — but only in that direction, since converting existing spaces back to tabs would be a lossy, ambiguous guess about which runs of spaces "should" become one. This finally gives `insert_spaces` a real consumer; it had been a persisted, Settings-dialog-editable field with none since before Phase 7. All changes apply inside one undo step)
* ⬜ Code completion
* ⬜ Snippets
* ⬜ Signature help
* ✅ Documentation lookup (a second lookup inside `compute_hover` itself, `opencobol2.language.hover` — when the cursor is on a reserved word rather than an identifier, matches it against `_RESERVED_WORD_DOCS`, a hand-picked table of ~50 of the most common division/section keywords and statement verbs, each with a short, generic, factual one-line description. Deliberately not exhaustive — COBOL's real reserved-word table has hundreds of entries, and a vague or wrong description would be worse than no hover at all, so an undocumented reserved word just yields no hover rather than a guess. Reuses the exact same `QToolTip` wiring as symbol hover; no separate command or panel)

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
* 🔶 Build pipelines (`opencobol2.gui.build_commands`, wired to Build > Build Project: finds every `.cbl`/`.cob` file under the project root and compiles each independently through `CompilerRuntimeActivationService`, logging to the Output/Problems panels — see Phase 7. No multi-file program linking yet; the project model has no "main program"/entry-point concept to link around.)
* ⬜ Incremental build (every Build Project run recompiles every source file)
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

The application shell now renders for real (`src/opencobol2/gui/`): a `MainWindow` builds a live menu bar and toolbars from command contributions (rebuilt from live command/dynamic-menu state every time a menu opens), docks every registered tool window (with a pluggable per-tool-window content factory), has a real central document-editing widget, renders a real content-driven status bar, and applies the active theme's palette. It launches via `python -m opencobol2.gui.application` or the `opencobol2` console script (`create_main_window()` wires the real built-in command/tool-window/theme/status-bar/compiler registries together, plus an optional `Project` to seed the Project Explorer). File > New/Open/Save/Save As/Save All/Close/Close All (document-level) and File > New/Open/Save As/Close Project are all real, working commands (and File > Open Recent Project actually lists real, still-existing project files — File > Open Recent File does not yet), double-clicking a physical file in Project Explorer opens it in an editor tab, the status bar reflects the open project and active theme live, View > Command Palette (Ctrl+Shift+P) opens a real searchable command list, Tools > Settings opens a real Preferences dialog (now including an External Tools tab for the Git executable path) that applies changes to the running window immediately, Tools > Compiler Profiles opens a real dialog for managing compiler profiles, and Build > Build Project compiles the open project's COBOL sources through the real compiler integration layer. When no editor tabs are open, a real Welcome page (New/Open Project, recent projects) shows in the central editor area instead of a blank widget. Edit > Find in Files (Ctrl+Shift+F) searches every source file under the project root and lists matches in the Find Results panel; double-clicking one jumps straight to it in the editor. A first-cut Terminal panel runs one shell command at a time (not a full interactive PTY) rooted at the open project's directory. An Outline panel shows the active editor tab's division/section/paragraph structure and jumps to any entry on double-click. A Task List panel scans project comments for TODO/FIXME/HACK/XXX markers and refreshes automatically when the open project changes. Edit > Toggle Bookmark (Ctrl+F2) marks the cursor's line, painted as a colored strip in the gutter, and a Bookmarks panel lists every bookmark across every open tab. Project Explorer, Git Changes, Git Repository, Output, Problems, Find Results, Terminal, Outline, Task List, and Bookmarks are the tool windows with real content; Extensions is the only placeholder left.

* ✅ Application shell (`MainWindow`: live menu bar + toolbars rendered from command contributions, a real content-driven status bar, theme palette application, a real runnable bootstrap)
* ✅ Status bar (see Phase 1 above for the domain model; the shell's built-in items show the open project's name — reacting live to `ProjectExplorerWidget.project_changed` — and the active theme, reacting when `apply_active_theme()` runs)
* ✅ Command Palette (`CommandPaletteDialog`, `opencobol2.gui.command_palette`: lists every registered command with its category, filters live by typed text against title and category, arrow-key navigable, executes on Enter/double-click; disabled commands show but don't execute, hidden commands are omitted; wired to View > Command Palette / Ctrl+Shift+P)
* ✅ Tool windows (rendering the Phase 1 registry: one `QDockWidget` per registered definition, initial dock area + visibility applied, visibility synced bidirectionally with `ToolWindowService`, pluggable real content per tool window; pinning/auto-hide and floating-geometry restoration are not implemented yet — plain QDockWidget floating/closable behavior is used as-is)
* ✅ Welcome page (`WelcomePageWidget`, `opencobol2.gui.welcome_page`: an overlay child of `EditorTabsWidget`, shown when the tab count is zero and hidden otherwise, rather than replacing `MainWindow`'s central widget. New Project / Open Project buttons and a recent-projects list, all decoupled from application services via plain signals — `new_project_requested`/`open_project_requested`/`open_recent_project_requested` — wired in `application.py` to the same command handlers as the File menu's Project commands. Building this exposed and fixed a real ordering bug: the New/Open/Open-Recent Project handlers recorded recent-project state *after* `ProjectExplorerWidget.set_project()` had already fired `project_changed`, so anything refreshing itself from that signal read stale recent-project data)
* ✅ Recent projects (`RecentProjectsSettings` persists up to 10 project file paths, newest first, deduplicated on reopen; File > Open Recent Project lists them live via a `DynamicMenuContribution`, skipping any that no longer exist on disk; New/Open/Save-As all record the project file automatically)
* ✅ Preferences dialog (`SettingsDialog`, `opencobol2.gui.settings_dialog`: Editor/COBOL/Theme/External Tools tabs backed by the real `SettingsService`; wired to Tools > Settings; applying immediately updates the running window's palette, status bar, and `GitService` executable path via an `on_applied` callback, not just the persisted file)
* ✅ Compiler Profiles dialog (`CompilerProfilesDialog`, `opencobol2.gui.compiler_profiles_dialog`: list/add/remove/rename configured `CompilerProfile`s, pick a registered provider when adding, select the default, and edit each profile's configuration through a form generated from that provider's `CompilerConfigurationField` schema — every field kind: string, path (with a browse button), boolean, string list, string map, integer list, choice; validates every profile against its provider before saving; wired to Tools > Compiler Profiles. No `on_applied` callback needed — Build Project resolves the default profile from `SettingsService.current` fresh on every build)
* ✅ Project explorer (`ProjectExplorerWidget`: real physical-file tree honoring `excluded_patterns`, virtual folders, and linked files — see Phase 2; all four project file commands — New, Open, Save As, Close (`opencobol2.gui.project_commands`) — are wired to real handlers using stock `QFileDialog`/`QInputDialog` prompts, no custom dialog widgets built yet; double-clicking a physical file item emits `file_double_clicked`, wired to the editor below; right-clicking the project's root item offers Properties..., opening `ProjectPropertiesDialog` — see Phase 2)
* ✅ Editor, first cut (`EditorTabsWidget`/`SourceEditorWidget`, `opencobol2.gui.editor`: docked as `MainWindow`'s central widget via a new `central_widget` constructor parameter; one `QPlainTextEdit`-based tab per open document, backed by the Phase 1/3 `DocumentService`; dirty tracking shown as a trailing `*` in the tab title; File > New/Open/Save/Save As/Save All/Close/Close All all wired to real handlers, including unsaved-changes Save/Discard/Cancel prompts on close; a real line-number gutter and current-line highlight, both colored from the active theme and recolored live via `apply_theme()` on a theme switch; Edit > Find/Replace (Ctrl+F/Ctrl+H) open a real in-editor find bar; real COBOL syntax highlighting, fixed-format coding-area guides, and code folding for recognized files; a real configured font and tab width, and a minimap — see Phase 3. No split editors or multiple cursors yet)
* ✅ Output window (`OutputWidget`, `opencobol2.gui.output_panel`: a read-only, append-only log; Build > Build Project streams compiler process stdout/stderr and per-file status lines into it)
* ✅ Problems window (`ProblemsWidget`, `opencobol2.gui.problems_panel`: a read-only table of severity/file/line/column/message, replaced with each build's parsed `CompilerDiagnostic`s)
* ✅ Terminal, first cut (`TerminalWidget`, `opencobol2.gui.terminal_panel`: a command-input box over a read-only output log. Not a real interactive PTY-based terminal — no ConPTY/pty, no persistent shell session, no live-streaming output, no interactive prompts — each typed command runs to completion through a real, synchronous `subprocess.run(shell=True, capture_output=True)` call (mirroring the same blocking-subprocess pattern the compiler integration layer already uses) before its stdout/stderr/exit code append to the log. `shell=True` is intentional, not a command-injection concern: the only input source is the user directly typing into their own IDE's terminal. A new `BuiltInToolWindowIds.TERMINAL`/`VIEW_TERMINAL` pair was registered from scratch, unlike the other Phase 7 panels which already had placeholder registrations. The working directory tracks the open project's root automatically, falling back to the process's own current directory with no project open)
* ✅ Git window — both dock panels now have real content, sharing one repository auto-discovered from the open project's root:
  * `GitChangesWidget` (`opencobol2.gui.git_changes`): working-tree status, branch name, staged/unstaged file lists, stage/unstage via double-click or Stage All/Unstage All, and commit with a message box — verified against a real `git` repository, which caught and fixed a real bug in `GitService.unstage_all()` (`git rm --recursive` isn't a valid long option, only `-r` is).
  * `GitRepositoryWidget` (`opencobol2.gui.git_repository`): four tabs — Branches (current branch marked, double-click to switch, New Branch button, right-click Delete), Tags (New Tag button prompting for an optional annotation message, right-click Delete), Remotes (Add Remote button, right-click Rename/Remove), and History (last 100 commits, read-only) — all wired to real `GitService` calls. Destructive actions (delete/remove) require a confirmation prompt. No editing of remote URLs after creation, no branch/tag rename.
* ✅ Search window (`FindResultsWidget`, `opencobol2.gui.find_results_panel`: a File/Line/Column/Text results table backed by `opencobol2.gui.search_commands.search_project_for_text`, a case-insensitive substring search over every `.cbl`/`.cob` file under the project root — same file discovery as Build Project. Edit > Find in Files (Ctrl+Shift+F) prompts for a query, populates the table, and force-shows the Find Results dock widget directly rather than through `ToolWindowService.activate()`, since the dock manager only syncs dock-widget-visibility *into* the service, not back out — a pre-existing one-way-sync gap this surfaced. Double-clicking a result opens the file (`EditorTabsWidget.open_path_at_line`, backed by a new `SourceEditorWidget.go_to_line`) and places the cursor at the match)
* ✅ Outline (`OutlineWidget`, `opencobol2.gui.outline_panel`, backed by a new Qt-independent language service `opencobol2.language.compute_outline` that walks the real parser's AST the same way `compute_fold_ranges` does — division → section → paragraph, program name shown on the IDENTIFICATION DIVISION entry, unnamed leading paragraphs excluded, data-item-level nesting deliberately out of scope for the same reason folding excludes it. Reflects whichever editor tab is active, refreshing on tab switch and on every edit of the active tab via a new `EditorTabsWidget.active_document_changed` signal — a same-tab-only edit guard keeps a background tab's programmatic text change from spuriously refreshing it. Double-clicking any entry moves the active tab's cursor there via the same `SourceEditorWidget.go_to_line` used by Find Results. A new `BuiltInToolWindowIds.OUTLINE`/`VIEW_OUTLINE` pair was registered from scratch, same as Terminal)
* ✅ Bookmarks (`BookmarksWidget`, `opencobol2.gui.bookmarks_panel`, and new bookmark state on `SourceEditorWidget`: Edit > Toggle Bookmark (Ctrl+F2) toggles a bookmark on the cursor's line, painted as a thin colored strip in the line-number gutter. Bookmarks are stored as live `QTextBlock` handles rather than plain line numbers, so a bookmark keeps tracking the same physical line of text — not whatever line now has the same number — when an edit elsewhere shifts line numbers around it; this is the same class of staleness bug `_expand_all_folds()` had to be fixed for earlier in Phase 3. `EditorTabsWidget.all_bookmarks()` aggregates bookmarks across every open tab (keyed by `document_id`, not path, so untitled documents can be bookmarked too) and forwards a `bookmarks_changed` signal from whichever tab changed. No persistence across sessions — bookmarks live only as long as their tab stays open. A new `BuiltInToolWindowIds.BOOKMARKS`/`VIEW_BOOKMARKS` pair was registered from scratch, same as Terminal/Outline/Task List)
* ✅ Task list (`TaskListWidget`, `opencobol2.gui.task_list_panel`, backed by a new Qt-independent language service `opencobol2.language.compute_task_list_entries` that scans real lexer `COMMENT` tokens — not a blind substring search — for `TODO`/`FIXME`/`HACK`/`XXX` tags, so a tag inside a string literal or identifier is correctly ignored. `opencobol2.gui.task_list_commands.scan_project_for_tasks` walks every project file the same way `search_project_for_text` does. Scanning is on demand (a Refresh button) rather than filesystem-watched, plus an automatic rescan whenever the open project changes — including once at bootstrap for a project passed in upfront, mirroring the same "explicit initial call, not just a signal" pattern the Welcome page and Terminal working directory already use. Double-clicking an entry opens its file at the match. A new `BuiltInToolWindowIds.TASK_LIST`/`VIEW_TASK_LIST` pair was registered from scratch, same as Terminal and Outline)
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

* ✅ Unit tests (1000+, covering every implemented subsystem)
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
