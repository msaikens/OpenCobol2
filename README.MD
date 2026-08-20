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
* Up to 10 recently opened project file paths, newest first, deduplicated whenever one is reopened (see "Application shell" below).
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

* `Theme`, `ThemeColors`, and `ThemeKind` models describing a named palette (background, foreground, accent, selection, editor, line-number, current-line, diagnostic-severity, and syntax-token colors) validated as `#RRGGBB` hex values.
* A `ThemeRegistry` for registering and resolving themes by ID, plus a built-in catalog of four themes: Light, Dark, High Contrast Light, and High Contrast Dark.
* A `ThemeService` that tracks the active theme against a registry and validates theme switches.
* The active theme selection is persisted as part of application settings.

The Phase 7 application shell (below) now applies the active theme's palette to real widgets.

The command, menu, tool-window, status-bar, and theme registries above are fully unit tested independently of Qt, in addition to their Phase 7 rendering.

### Application shell

OpenCobol2 has a real, launchable Qt application shell (`src/opencobol2/gui/`), independent from — and built entirely on top of — the Qt-independent registries above:

* `MainWindow` builds a live menu bar and toolbars from command surface contributions. Menus rebuild themselves from current command/dynamic-menu state every time they open, so enabled/checked state and dynamic entries (like the recent-projects list below) are never stale.
* Every registered tool window is rendered as a real `QDockWidget`: initial dock area and visibility come from `ToolWindowService`, and visibility changes made through the real widget (closing a panel, for example) are synced back into that service. Pinning/auto-hide and floating-geometry restoration are not implemented yet; panels use plain `QDockWidget` floating/closable behavior as-is. Each tool window can be given real content through a pluggable per-tool-window content factory; panels without one fall back to a placeholder. Project Explorer, Git Changes, Git Repository, Output, Problems, Find Results, Terminal, Outline, Task List, Bookmarks, Breakpoints, Call Stack, Locals, Watch, Threads, Registers, and Memory now have real content (see "Project system", "Git integration", "Build integration", "Document editing", and "Debugger" below) — Extensions is the only one still falling back to the placeholder.
* The status bar renders one real label per registered status bar item — left-aligned items via `QStatusBar.addWidget`, right-aligned items via `addPermanentWidget` — and `MainWindow.refresh_status_bar()` re-resolves every item's provider on demand. The built-in items show the currently open project's name (updating live off `ProjectExplorerWidget.project_changed`) and the active theme's name (updating whenever `apply_active_theme()` runs).
* The active color theme is applied to the shell as a real `QPalette`.
* A `CommandPaletteDialog` (View > Command Palette, Ctrl+Shift+P) lists every registered command with its category, filters live as the user types (matching against both title and category), supports arrow-key navigation, and executes the selected command on Enter or double-click. Commands the current `CommandState` reports as disabled are shown but not executable; hidden commands are omitted entirely.
* A `SettingsDialog` (Tools > Settings) edits Editor, COBOL, Theme, and External Tools settings against the real `SettingsService` across four tabs, preloaded from and persisted back to the same settings file every other subsystem reads. Applying changes doesn't just write to disk — an `on_applied` callback immediately switches the running window's active theme and refreshes the palette and status bar, and updates the running `GitService`'s configured Git executable (`ExternalToolSettings.git_executable_path`, blank meaning "resolve `git` from `PATH`"), so both are visible the moment you click OK.
* A `CompilerProfilesDialog` (Tools > Compiler Profiles) manages `CompilerSettings.profiles` against the real `SettingsService`: add a profile (choosing a registered provider — GnuCOBOL or a custom local compiler), remove one (with confirmation), rename it, select the default, and edit its configuration through a form generated from that provider's `CompilerConfigurationField` schema (every field kind: string, path with a file-picker browse button, boolean, string list, string map, integer list, and choice). Saving validates every profile against its provider first and refuses to close on a validation error (a missing required field, for example). No `on_applied` callback is needed here — Build Project always resolves the default profile from `SettingsService.current` at build time, so a newly added or edited profile takes effect on the very next build.
* File > New/Open/Save As Project all record the project file into `RecentProjectsSettings`, and File > Open Recent Project lists them as real, individually clickable menu entries (`opencobol2.gui.project_commands`) — entries pointing at a file that no longer exists are quietly skipped rather than shown as a broken link.
* The shell's central widget is a real `EditorTabsWidget` (see "Document editing" below), and `create_main_window()` wires it in via `MainWindow`'s new `central_widget` parameter.
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

A real `GitChangesWidget` (`opencobol2.gui.git_changes`) now renders inside the application shell's Git Changes dock panel: the current branch name, staged and unstaged file lists (with a status letter — `M`/`A`/`D`/`R`/`?` and so on), stage/unstage via double-click or "Stage All"/"Unstage All" buttons, and commit with a typed message. Building this against a *real* repository (not a mock) caught and fixed a genuine bug: `GitService.unstage_all()` invoked `git rm --cached --recursive`, but `git rm` only accepts the short `-r` flag — every prior test for that path was mocked and asserted the broken command was constructed "correctly."

A real `GitRepositoryWidget` (`opencobol2.gui.git_repository`) renders inside the Git Repository dock panel: four tabs — Branches (current branch marked with `* `, double-click to switch, a "New Branch..." button, right-click to delete), Tags ("New Tag..." prompts for a name and an optional annotation message, right-click to delete), Remotes ("Add Remote..." prompts for a name and URL, right-click to rename or remove), and History (last 100 commits, read-only) — all populated from and wired to real `GitService` calls. Every destructive action (delete a branch or tag, remove a remote) asks for confirmation first. `GitService` errors — an in-progress merge, uncommitted changes blocking a branch switch, a duplicate name — surface through a message box rather than failing silently.

Both panels track whatever Git repository `GitService.discover_repository()` finds at the currently open project's root, falling back to an empty state if there is none or if `git` itself is unavailable, and both refresh automatically whenever the open project changes.

### Project system

OpenCobol2 has a persisted project model that stays independent of any specific compiler dialect beyond the compiler profile it references:

* Project identity, root path, and build/launch default properties.
* Virtual (logical) folders, independent of physical directory layout.
* Linked files sourced from outside the project root.
* Excluded file patterns and project-level environment variable overrides.
* User-defined tasks and launch configurations, directly executable as local processes with layered environment resolution (ambient OS environment, then project overrides, then task/launch overrides).

Project persistence uses the same schema-versioned, atomic-replacement JSON storage pattern as application settings.

A real Project Explorer (`ProjectExplorerWidget`) now renders inside the application shell's dock panel (see "Application shell" above): a physical file/directory tree of the project root honoring `excluded_patterns`, a "Virtual Folders" branch showing the logical folder tree (including nested folders, member file paths, and referenced linked files), and a "Linked Files" branch for any linked file not already organized into a virtual folder. Double-clicking a physical file item emits `file_double_clicked` with its path, which the shell wires to the editor (see "Document editing" below) — double-clicking a directory, virtual-folder member, or linked file does nothing yet.

All four project file commands (`opencobol2.gui.project_commands`) are wired to real handlers: New Project prompts for a name, a root directory, and a save location, then creates and persists a project; Open Project prompts for a project file and loads it through `ProjectStorage`; Save Project As persists the currently open project to a new location; Close Project clears the panel back to its empty state. `create_main_window(project=...)` can also seed a project directly.

Right-clicking the project's root item in Project Explorer offers Properties..., opening a real `ProjectPropertiesDialog` (`opencobol2.gui.project_properties_dialog`): a combo box lets you pick which of the globally configured compiler profiles (see "Compiler Profiles dialog" above) this specific project should default to, or fall back to the global default. Accepting updates the in-memory project immediately (persist it via File > Save Project As, same as any other project change) — this was the last remaining Phase 2 gap: a project could always *reference* a compiler profile by ID at the model level, but nothing in the GUI could set that reference until now.

### Build integration

Build > Build Project (`opencobol2.gui.build_commands`) wires the application shell to the real compiler integration layer: it recursively finds every `.cbl`/`.cob` file under the open project's root (honoring `excluded_patterns`), activates a compiler profile through `CompilerRuntimeActivationService` — the project's own `properties.default_compiler_profile_id` if Project Properties has set one, otherwise the globally configured default (GnuCOBOL auto-discovery or a custom local compiler) — and compiles each file independently as its own executable — the project model has no "main program"/entry-point concept yet, so there is no multi-file program linking. A per-file `_is_up_to_date()` mtime check skips recompiling any source file whose output is already newer than it, logging `"<file>: up to date, skipping"` rather than re-invoking the compiler; Build > Rebuild Project clears the output directory first, which always makes every file "not up to date" again. On Windows, output paths always carry the real `.exe` suffix `cobc -x` forces onto them (`EXECUTABLE_SUFFIX`, `opencobol2.compiler.models`). Process output streams to the real `OutputWidget` dock panel and parsed diagnostics populate the real `ProblemsWidget` table (severity, file, line, column, message). Build > View Listing File (`create_view_listing_handler`) compiles the active editor tab's source with GnuCOBOL's `-t` listing option and opens the resulting `.lst` file as a real editor tab, parsed line-by-line by `opencobol2.compiler.listing.parse_gnucobol_listing`; it requires the active tab's source to already be saved and the resolved default compiler profile to be GnuCOBOL specifically, since the `-t` flag is GnuCOBOL-only. Verified end to end against both a real GnuCOBOL installation and a stub custom-local compiler: no project open, no source files found, and no compiler profile configured all report a clear message instead of failing silently.

### Document editing

The application shell's central widget is a real `EditorTabsWidget` (`opencobol2.gui.editor`), backed by the already-existing Qt-independent document model (`opencobol2.documents`: `TextDocument` for open/save/dirty/encoding/BOM/line-ending state, `DocumentWorkspace` for open-document tracking, `DocumentService` coordinating both against real filesystem storage). Each open document gets its own tab wrapping a `SourceEditorWidget` (a `QPlainTextEdit`); editing syncs the text back into the document model live, and the tab title grows a trailing `*` while the document `is_modified`. File > New/Open/Save/Save As/Save All/Close/Close All are all wired to real handlers: Save on an untitled document redirects to Save As; closing (or Close All) a modified document prompts Save/Discard/Cancel, and choosing Save then cancelling its own Save As dialog correctly aborts the close rather than losing the tab. Double-clicking a physical file in Project Explorer opens it in a tab, reusing an already-open tab for the same path rather than duplicating it.

Each editor also renders a real line-number gutter and highlights the current line — both colored from the active `Theme`'s `line_number_foreground` and `current_line_highlight` fields, which existed in the color model since Phase 1 but had no consumer until now. `EditorTabsWidget.apply_theme()` recolors every open tab immediately when the theme changes (wired into the same Settings-dialog `on_applied` callback that already updates the window palette and `GitService`), and any tab opened afterward picks up the new colors automatically.

Edit > Find (Ctrl+F) and Edit > Replace (Ctrl+H) open a real in-editor find bar as a floating overlay on the active tab — both were already registered commands with menu contributions but no handler, so triggering them previously would have raised `BuiltInCommandHandlerNotConfiguredError`. The bar supports forward/backward find with wraparound, an optional "Match case" toggle, Replace, and Replace All, all built on Qt's own `QPlainTextEdit.find()` rather than hand-rolled search logic.

Files recognized as COBOL (`.cbl`/`.cob`, and untitled/new documents — this IDE has no other file type to open or create yet) get real syntax highlighting: `CobolSyntaxHighlighter` (`opencobol2.gui.syntax_highlighter`) tokenizes the whole document with the real COBOL lexer (`opencobol2.language.tokenize_cobol_source`) and colors reserved words, string/alphanumeric literals, numeric literals, and comments from four new `Theme.colors` fields (`syntax_keyword`, `syntax_string`, `syntax_number`, `syntax_comment`, added to all four built-in themes). It re-lexes the whole buffer on the first `highlightBlock()` call after the text changes rather than incrementally per line — an honest first-cut trade-off, fine for typical COBOL source files but not built to scale to very large ones. `apply_theme()` recolors and rehighlights live, same as the line-number gutter above. Non-recognized files (anything else opened in the editor) get no highlighting at all.

Tools > Settings' COBOL tab has a Source Format choice (Fixed/Free) that persisted correctly but had no effect on anything until now: highlighting, live diagnostics, folding, completion, hover, signature help, go to definition, find references, and quick fixes all silently assumed Fixed regardless of it. Fixed format's sequence-area (columns 1-6) and indicator-column (7) stripping only makes sense for source that starts its actual code at column 8 — applied to source that doesn't (nothing stops it in an editor with no punch cards to line up against), it silently swallows the first several characters of every line as if they weren't there, which is exactly why `IDENTIFICATION DIVISION.` starting at column 1 got misread as `ICATION DIVISION.`: `IDENTIFICATION`'s own first six characters were mistaken for the sequence area, leaving `DIVISION` highlighted normally while `IDENTIFICATION` wasn't, and raising a spurious "Expected IDENTIFICATION DIVISION" diagnostic despite the line being correct COBOL. `SourceEditorWidget`/`EditorTabsWidget` now carry a real `source_format` (`opencobol2.compiler.CobolSourceFormat`), threaded into every one of those language-service calls and the highlighter itself, defaulting to Fixed but changeable at any time via `apply_source_format()` — wired to the Settings dialog the same way theme/font/guides already are, so picking Free there actually takes effect immediately on every open tab (including both views of a split).

Every editor now uses a real, configured font: `EditorSettings.font_family`/`font_size` (long-persisted, editable in the Settings dialog's Editor tab, but previously never applied anywhere) set the editor's `QFont`, falling back to the system's fixed-pitch font when no family is configured; `EditorSettings.tab_width` sets the real tab stop distance. A monospace font is also a real prerequisite for the column-accurate coding-area guides below. Not wired yet: `insert_spaces`, `automatic_indentation`, and `indentation_width` — those govern key-handling behavior (what happens on Tab/Enter), a separate, still-unbuilt feature.

Files recognized as COBOL also render real fixed-format coding-area guides — `CodingAreaGuides` (`opencobol2.gui.coding_area_guides`) draws column rulers/shading for the sequence area (columns 1-6), indicator column (7), Area A (8-11), the Area A/B boundary (column 12), and the reference area (columns 73-80), using column constants now exposed from the lexer (`opencobol2.language.FIXED_FORMAT_*`). Each is independently toggleable via `CobolGuideSettings` (`show_sequence_area`, `show_indicator_column`, `show_area_a`, `show_area_b_boundary`, `show_reference_area`, `shade_areas`) — six real, persisted settings (editable in the Settings dialog's COBOL tab) that existed with zero visual consumer until now. Both the editor font/tab settings and the coding-area guides recolor and re-apply live through the same Settings-dialog `on_applied` callback as the theme and Git executable path.

Files recognized as COBOL also get real code folding, gated by `EditorSettings.code_folding` (a long-persisted, editable-in-Settings-dialog toggle with no consumer until now). Fold ranges come from a new Qt-independent language service, `opencobol2.language.compute_fold_ranges`, which walks the real parser's AST (divisions, sections, paragraphs, and IF/PERFORM/EVALUATE statement bodies) rather than guessing from indentation — deliberately out of scope for now: folding individual group data items by level-number nesting, since `DataSectionNode` holds a flat item list rather than a level-number tree. The editor's gutter grows a clickable `+`/`-` marker next to any foldable line; collapsing hides the range's lines (via `QTextBlock.setVisible`) and paints a small `⋯` badge on the fold's start line. Folding a range that contains an already-collapsed nested range preserves the nested collapse when the outer range is later expanded. If an edit shifts line numbers out from under a collapsed fold (recomputed on every `blockCountChanged`, not per keystroke, since fold ranges only change when lines are added or removed), everything expands automatically rather than risking the wrong lines staying hidden.

Autosave is real: `EditorSettings.autosave_enabled`/`autosave_interval_seconds` (editable in the Settings dialog's Editor tab, disabled by default) drive a `QTimer` on `EditorTabsWidget` that, on every timeout, silently saves any open document that's both modified and already has a path — untitled documents are left alone rather than prompted for Save As, and a save failure is swallowed rather than shown in an interrupting dialog, since this runs on a background timer. The timer restarts with the current interval every time settings are (re)applied, including at bootstrap. Verifying this against real persistence caught a genuine bug: `SettingsStorage` serialized/deserialized `EditorSettings` field-by-field via a hand-written list rather than the dataclass itself, so the two new fields silently failed to round-trip to disk — masked in the existing exhaustive round-trip test because it happened to leave both at their defaults, so the same (wrong) default came back on reload and the equality check passed regardless. Fixed the storage code and strengthened that test to use non-default values for every field.

Files recognized as COBOL (and every other open file) now show a minimap: a fixed-width strip docked to the right edge of the viewport, positioned the same way the line-number gutter is positioned on the left (a sibling `QWidget` plus a matching `setViewportMargins()` reservation). Rather than rendering the real text at an illegibly tiny font, each non-blank line is painted as a density tick whose width is proportional to that line's length (capped at 80 characters); a translucent band shows which lines the real viewport currently covers. Clicking or dragging inside it jumps the cursor to that line via the same `go_to_line()` every other navigable panel already uses. `EditorSettings.show_minimap` (default on, editable in the Settings dialog's Editor tab) turns it off entirely, giving its width back to the text area.

File > Print (Ctrl+P) opens a real, native `QPrintDialog` over a `QPrinter`; accepting it prints the active tab via a new `EditorTabsWidget.print_active_tab()`, which is a thin delegation to `QPlainTextEdit`'s own built-in `print_()` rather than any hand-rolled pagination or rendering — no custom implementation needed, same as the undo/redo stack. Rejecting the dialog prints nothing.

View > Toggle Split Editor (Ctrl+\) splits the active tab into two `SourceEditorWidget` views sharing one Qt `QTextDocument` (`SourceEditorWidget.become_split_view_of`) side by side in a `QSplitter` — typing in either shows up in both immediately, since Qt keeps every view attached to a document in sync automatically, with no manual text-copying between them needed. The second view never gets its own syntax highlighter (that would double-highlight the shared document against two independent `CobolSyntaxHighlighter`s); it relies entirely on the first view's. Fold ranges, bookmarks, and breakpoints stay each view's own state, though, and can diverge between the two as you work in each independently — the same trade-off most editors make for split views of one file. Triggering the command again closes the split. Only one tab's page widget is ever wrapped this way (`_SplitEditorPane`, `opencobol2.gui.editor`); every other tab's page widget is its `SourceEditorWidget` directly, unchanged from before this feature existed.

Edit > Add Cursor Above/Below (Ctrl+Alt+Up/Down) — and Ctrl+Alt+Click anywhere in the buffer — add a secondary cursor at the same column on an adjacent line (or wherever clicked); typing, Backspace, Delete, Enter, and Tab (when `insert_spaces` is on) replicate across every cursor as one undo step, and arrow-key navigation moves them all together, keeping their relative positions aligned. This relies on Qt automatically keeping every `QTextCursor` attached to a document correctly positioned as edits happen anywhere else in it, the same "live cursor" behavior bookmarks already use to track their line across edits elsewhere. Secondary cursors render as thin caret lines painted directly in `paintEvent` (an `ExtraSelection` can't represent a zero-width caret — it paints nothing without an actual character to highlight). A plain click or Escape collapses back to a single cursor.

Alt+Shift+Up/Down/Left/Right extends a rectangular column (box) selection — the same keybinding Visual Studio and Notepad++ both already use for it — and Alt+drag does the same with the mouse. Typing inserts the same character at that column on every selected line; Backspace/Delete edit within the column range the same way. A line shorter than the selection's columns is skipped entirely rather than padded with "virtual space," and editing is carefully confined to each line's own text — Backspace at column 0 or Delete at a line's last column deliberately does nothing rather than deleting into the newline and silently merging two lines together, a real bug caught while building this. A plain arrow key (without Alt+Shift) exits column-selection mode and moves the cursor normally.

File > Open Recent File is not yet built (unlike Open Recent Project, there is no persisted recent-files list wired up yet — the menu currently lists nothing).

When no documents are open, the editor area shows a real Welcome page (`WelcomePageWidget`, `opencobol2.gui.welcome_page`) instead of a blank tab widget: a New Project / Open Project button pair and a recent-projects list, both wired to the same handlers as the File menu's Project commands (opening a project records it to the persisted recent-projects list and reopening one moves it back to the front, same as the existing Open Recent Project menu). It's built as an overlay child of `EditorTabsWidget` — shown when the tab count is zero, hidden the moment a document opens, and reappearing once the last tab closes — rather than replacing `MainWindow`'s central widget, since existing code and tests assume `centralWidget()` is always the `EditorTabsWidget` itself. The widget itself is decoupled from application services: it only emits signals (`new_project_requested`, `open_project_requested`, `open_recent_project_requested`), which `application.py` connects to the real command service. Fixing this wiring surfaced a real ordering bug in the existing New/Open/Open-Recent Project handlers: recent-project state was being recorded *after* `ProjectExplorerWidget.set_project()` already fired its `project_changed` signal, so anything refreshing itself from that signal (the Welcome page's list included) would read stale recent-project data. All three handlers now record first, then update the explorer.

Edit > Find in Files (Ctrl+Shift+F) searches every `.cbl`/`.cob` file under the open project's root — the same file discovery Build Project uses — for a case-insensitive substring match, and lists every matching line's file/line/column/text in a real Find Results panel (`FindResultsWidget`, `opencobol2.gui.find_results_panel`). Double-clicking a result opens that file (reusing an already-open tab if there is one) and moves the cursor straight to the match, via a new `SourceEditorWidget.go_to_line()`/`EditorTabsWidget.open_path_at_line()` pair. Since the Find Results dock panel starts hidden and nothing currently syncs `ToolWindowService` state changes back to the real `QDockWidget` (the dock manager only listens the other way, dock → service — a pre-existing gap), running a search shows and raises that dock widget directly rather than going through the service.

A first-cut Terminal panel (`TerminalWidget`, `opencobol2.gui.terminal_panel`, wired to a new View > Terminal command) is a command-input box over a read-only output log — not a real interactive PTY-based terminal. There's no persistent shell session, no live-streaming output, and no interactive input (a command that prompts for input just hangs until a 60-second timeout); each typed command runs to completion via a real, synchronous `subprocess.run(shell=True, capture_output=True)` call before its stdout, stderr, and exit code append to the log, mirroring the same blocking-subprocess pattern the compiler integration layer already uses for Build Project. `shell=True` is deliberate rather than a command-injection concern, since a terminal's only input source is the user typing directly into their own IDE. The working directory tracks whatever project is currently open, falling back to the process's own current directory otherwise.

An Outline panel (`OutlineWidget`, `opencobol2.gui.outline_panel`, wired to a new View > Outline command) shows the active editor tab's COBOL structure as a tree — divisions, data sections, and procedure sections/paragraphs — backed by a new Qt-independent language service, `opencobol2.language.compute_outline`, that walks the real parser's AST the same way `compute_fold_ranges` already does (and shares its documented scope limit: no data-item-level nesting, since `DataSectionNode` holds a flat item list). The tree follows whichever tab is active and refreshes on every edit to it, via a new `EditorTabsWidget.active_document_changed` signal that fires on tab switches and on the active tab's own `textChanged` — a same-tab guard keeps a background tab's programmatic text change from spuriously refreshing an unrelated outline. Double-clicking any entry jumps the active tab's cursor there, reusing the same `SourceEditorWidget.go_to_line()` Find Results already uses.

A Task List panel (`TaskListWidget`, `opencobol2.gui.task_list_panel`, wired to a new View > Task List command) lists every `TODO`/`FIXME`/`HACK`/`XXX` comment across the open project, backed by a new Qt-independent language service, `opencobol2.language.compute_task_list_entries`, that scans real lexer `COMMENT` tokens rather than doing a blind substring search — a tag sitting inside a string literal or identifier is correctly not matched. `opencobol2.gui.task_list_commands.scan_project_for_tasks` walks every project source file the same way `search_project_for_text` already does for Find in Files. There's no filesystem watcher, so the list only updates on a manual Refresh click or whenever the open project changes (including once at bootstrap for a project passed in upfront). Double-clicking an entry opens its file at the match.

Edit > Toggle Bookmark (Ctrl+F2) toggles a bookmark on the cursor's current line, painted as a thin colored strip in the line-number gutter (`SourceEditorWidget.toggle_bookmark_at_cursor()`/`bookmarked_lines`). Bookmarks are stored as live `QTextBlock` handles rather than plain line numbers, so a bookmark keeps following the same physical line of text when an edit elsewhere shifts line numbers around it — the same class of bug `_expand_all_folds()` had to be fixed for earlier. A Bookmarks panel (`BookmarksWidget`, `opencobol2.gui.bookmarks_panel`, wired to a new View > Bookmarks command) aggregates bookmarks across every open tab, keyed by document ID rather than file path so untitled documents can be bookmarked too; double-clicking an entry switches to that tab and jumps the cursor there. There's no persistence — bookmarks disappear once their tab closes.

Edit > Toggle Breakpoint (F9) works the same way, painted as a small filled circle in its own dedicated gutter region rather than sharing the bookmark strip's 4px column, since one line can carry both at once. A Breakpoints panel (`BreakpointsWidget`, `opencobol2.gui.breakpoints_panel`, wired to a new View > Breakpoints command) mirrors the Bookmarks panel exactly. This is now synced to a real GDB breakpoint whenever a debug session is active against the same source file — see "Debugger" below.

Edit > Format Document (Shift+Alt+F) trims trailing whitespace from every line, and separately expands literal tab characters to spaces if `EditorSettings.insert_spaces` is enabled — never the other direction, since collapsing existing spaces back into tabs would be a lossy guess about which runs "should" become one. It's deliberately conservative: fixed-format COBOL is column-sensitive, so there's no attempt at COBOL-aware re-indentation here. This is also the first real consumer `insert_spaces`/`tab_width` have had; both were persisted, Settings-dialog-editable fields before this with nothing reading them.

Files recognized as COBOL now get live diagnostics as you type, not just syntax coloring: `CobolSyntaxHighlighter` also runs `opencobol2.language.compute_source_diagnostics` (lex, then parse, then semantic analysis, merging every stage's diagnostics) and underlines each one in a severity-colored squiggle — red for errors, amber for warnings. A diagnostic only carries a point position, not a span, so the underline covers the run of non-whitespace characters starting there rather than an exact token range. The same diagnostics also populate the Problems panel through a second, independent bucket (`ProblemsWidget.set_live_diagnostics()`, refreshed on tab switch/edit via the same `active_document_changed` signal Outline uses) that coexists with the last build's diagnostics rather than replacing them — running a build doesn't erase what the active editor is flagging, and switching tabs doesn't erase the last build's results. Live diagnostics are scoped to the active tab only, same as Outline. Testing this against a real "undefined data name" case surfaced an honest AST limitation: `MoveStatement.target_names` is a flat tuple of strings with no per-name position, so that diagnostic points at the MOVE statement's own start rather than at the specific missing name.

Edit > Go to Definition (F12) and Edit > Find All References (Shift+F12) resolve the identifier under the cursor against the real symbol table (`opencobol2.language.navigation`), single-file-scoped since the parser only ever sees one compilation unit at a time. Go to Definition moves the active tab's cursor straight to the result. Find All References reuses the existing Find Results panel rather than a new widget — every reference (plus the definition itself) becomes a result the same way a Find in Files match would, so double-clicking one navigates the same way; it only works for a document that's already been saved, since a Find Result needs a real file path. Testing go-to-definition against a real data item turned up the same kind of AST precision limit as the diagnostics work above: a data item's definition location points at its level number, since `DataItemNode.span` covers the whole entry, not at the name itself.

Hovering the mouse over an identifier shows a tooltip describing it (`compute_hover`, `opencobol2.language.hover`), reusing the same lex/parse/identify/analyze pipeline as go-to-definition: a paragraph or section shows its kind and name; a data item shows its level number, name, and every clause (`PIC`, `VALUE`, and so on) reconstructed from the clause's own tokens using their real source spans, so spacing like `9(5)V99` comes back exactly as written rather than guessed from punctuation. `SourceEditorWidget` picks this up by overriding `event()` to intercept Qt's own `QEvent.Type.ToolTip` event (fired automatically once the mouse rests over the widget) and calling `QToolTip.showText()`/`hideText()` — no new command or menu entry, since hover is mouse-driven rather than keyboard-triggered.

Hovering a reserved word instead of an identifier (Documentation lookup) falls back to a second lookup inside `compute_hover` itself against `_RESERVED_WORD_DOCS`, a hand-picked table of roughly 50 of the most common division/section keywords and statement verbs (`MOVE`, `PERFORM`, `IF`, and so on), each with a short, generic, factual one-line description. Deliberately not exhaustive — real COBOL has hundreds of reserved words, and a vague or wrong description would be worse than no hover at all, so a reserved word missing from the table just yields no hover rather than a guess. Reuses the exact same `QToolTip` wiring as symbol hover.

Signature help (`compute_signature_help`, `opencobol2.language.signature_help`) is scoped to GnuCOBOL intrinsic `FUNCTION` calls only — a `CALL` statement has no statically known signature from the calling side without linkage-section analysis of the callee, which isn't modeled, so subprogram calls are out of scope. It walks the token stream for a `FUNCTION name(` sequence, tracks parenthesis depth to find the matching close paren (so a nested call like `FUNCTION MOD((WS-A), WS-B)` still resolves correctly), and checks whether the hovered position falls between them, against a hand-picked table of about 15 common intrinsics. `SourceEditorWidget.hover_info_at()` tries this before ordinary hover — being inside a function call's argument list is a narrower condition than "hovering over some token," so it takes priority when both could apply — reusing the exact same `QToolTip` mechanism rather than a separate popup.

Right-clicking a line with a diagnostic can show a Quick Fix in the standard context menu (`compute_quick_fix`, `opencobol2.language.quick_fixes`). Deliberately narrow: exactly one fix exists, inserting the missing closing quote for an unterminated alphanumeric literal — inventing a fix for a diagnostic without an unambiguous, mechanically correct repair (like "Undefined data name," where there's no way to know what the user meant) would risk silently applying the wrong edit, worse than offering none. The diagnostic already carries the position of the literal's opening quote character, so the fix re-reads that one character from the source and reinserts it at the end of the line — this assumes the common same-line-forgot-a-quote mistake rather than a genuine multi-line continuation, since that's all the diagnostic's own position can safely support, but it's a suggestion the user explicitly applies and can undo in one step either way. `SourceEditorWidget.build_context_menu()` builds the menu (standard actions plus the fix, if one applies) as its own method, separate from the `contextMenuEvent()` override that shows it — specifically so it stays testable without ever calling `QMenu.exec()`, which opens a real, blocking native popup loop that (unlike overriding a Qt virtual method by subclassing) can't be intercepted by monkeypatching at the class level.

Edit > Rename Symbol (F2) prompts for a new name (pre-filled with the current one) and renames every reference to whatever's under the cursor, reusing `references_at_cursor()` entirely rather than adding a new language service. This one caught a real bug before it shipped: an initial implementation trusted `SourceLocation.column` as the exact start of the name text and blindly overwrote `len(name)` characters from there — which silently corrupted the source, because both documented AST precision limits above (a data item definition pointing at its level number, not its name; a MOVE target reference pointing at the MOVE statement's own start) mean that position often is *not* where the name starts. Fixed by rewriting one whole line per affected line instead, matching the old name as a complete COBOL word via a case-insensitive regex bounded by anything other than a letter, digit, or hyphen (hyphens are legal COBOL name characters), so renaming `WS-COUNT` never touches a longer identifier like `WS-COUNT-TOTAL`. Every replacement happens inside one `beginEditBlock()`/`endEditBlock()` pair, so the whole rename undoes in a single Ctrl+Z.

Code completion (`compute_completions`, `opencobol2.language.completion`) triggers automatically while typing an identifier-like prefix, or explicitly via Edit > Trigger Suggest (Ctrl+Space), and lists candidates from four sources: reserved words, the same hand-picked intrinsic-`FUNCTION` table signature help uses, this file's own data-item/paragraph/section symbols from a real lex→parse→`analyze_compilation_unit` pass (swallowed silently on failure — an expected transient state while mid-edit), and the built-in snippets described next. The file's own symbols rank first, snippets second, keywords and intrinsics last. `SourceEditorWidget` renders a real popup (`_CompletionPopup`) positioned under the cursor, navigable with the arrow keys and accepted with Tab or Enter; Escape dismisses it.

Snippets (`opencobol2.language.snippets`) are six hand-picked COBOL skeletons — program, IF/END-IF, PERFORM UNTIL, EVALUATE, paragraph, and DISPLAY — offered through the same completion popup and inserted as a real multi-stop tab session: accepting one inserts its literal text, and each `${n:default text}`/`${n}` placeholder becomes a selected span that Tab advances through in order, same as a conventional snippet editor. Deliberately minimal syntax, no nested placeholders or repeated stop references, matching this codebase's existing "hand-picked, not exhaustive" policy for reserved-word documentation and intrinsic signatures.

### COBOL language services (lexer, parser, semantic analysis)

OpenCobol2 has begun in-house COBOL language services, independent of the GnuCOBOL compiler process:

* A COBOL lexer supporting both fixed and free source format, with fixed-format sequence area/indicator column/Area A/B handling, continuation of alphanumeric literals across source lines, whole-line and inline (`*>`) comments, and diagnostics for unterminated literals, malformed continuations, and unrecognized characters. The reserved-word table is sourced from a full COBOL reserved-word reference (the standard Reserved / Standard-only / Potential-reserved-word split), keeping only words reserved under GnuCOBOL's default dialect, plus two documented GnuCOBOL-specific exceptions (`END-ACCEPT`, `END-DISPLAY`) that the reference marks as merely potential but GnuCOBOL genuinely supports as scope terminators.
* A recursive-descent parser building a real AST for program identity, data description entries (including FILE SECTION `FD`/`SD` entries), and procedure division structure (paragraphs, sections). It gives full structure to IF/ELSE/END-IF, PERFORM (out-of-line, inline, `VARYING`/`UNTIL`/`TIMES`), and EVALUATE/WHEN, including COBOL's implicit period-based scope termination (a lone `.` can close every enclosing IF/PERFORM/EVALUATE at once). Every other statement verb (ADD, CALL, STRING, and so on) is captured as a generic statement (verb plus raw tokens) rather than being deeply modeled yet; a verb's nested-statement clauses (`ON SIZE ERROR`, `AT END`, `ON OVERFLOW`) are a known, documented gap. The environment division is recognized but parsed opaquely.
* Semantic analysis: a symbol table for data items (respecting level-number nesting, including 66 RENAMES, 77 standalone items, and 88 condition names) and for procedure division paragraphs/sections (flagging duplicate names), plus a cross-reference index recording every successfully resolved name usage (the foundation for future go-to-definition, find-references, and rename). MOVE targets and PERFORM targets are structurally guaranteed name positions, so an unresolved one is an ERROR; every other token list a statement carries (MOVE sources, IF/EVALUATE conditions, PERFORM modifiers, DISPLAY operands, and unmodeled-verb operands) is scanned best-effort at WARNING level, since those lists mix data names with syntax not deeply modeled yet (intrinsic functions, index-names). Verifying this coverage against real legacy source also caught and fixed three real parser gaps: `PERFORM data-name TIMES` misparsed as an out-of-line target, the `END PROGRAM name.` marker not being recognized, and missing `INPUT`/`OUTPUT`/`I-O`/`EXTEND`/`FUNCTION` reserved words. A real performance bug was also caught and fixed here: `SymbolTable.find_data_symbols`/`find_procedure_symbols` did a linear scan over every symbol on every call, and reference resolution calls one of them once per name reference in the source — O(references × symbols), which measured around 800ms of analysis alone on a synthetic ~9,600-line file with 4,800 data items and 4,800 references, re-run on every keystroke since live diagnostics analyze on every edit (this is what surfaced as an editor that appeared to hang while backspacing in a large file). `SymbolTable` now builds a name → symbols index once, lazily, on first lookup, dropping that to O(references + symbols) — about 15ms on the same file. The syntax highlighter and code folding also each independently re-lexed/re-parsed the same text on every keystroke; the highlighter now hands its already-computed lex result to `compute_source_diagnostics` instead of letting it re-lex from scratch, and fold-range recomputation is now debounced the same way completion already was, so a burst of edits (in particular Backspace's own key-repeat) settles into one recompute rather than one per keystroke.

All three are tested against synthetic COBOL source and against the real `.cbl` files preserved under `legacy/opencobolide/tests/testfiles/`. Higher-level language services built on top of them — outline, diagnostics, go-to-definition, find-references, hover (including reserved-word documentation lookup and intrinsic-function signature help), rename, formatting, quick fixes, code completion, and snippets — are all done (see "Document editing" above).

## Planned architecture milestones

OpenCobol2 has established contracts for most core systems, and a first real GUI shell now sits on top of them. Settings, the command/menu/tool-window registries, Git, the project model, a COBOL lexer/parser, and the application shell described below are already implemented (see "Current foundation" above); this section covers what still sits ahead of them.

For a detailed, phase-by-phase status of every planned subsystem (including what's fully done, partially done, or intentionally out of scope), see [ROADMAP.MD](ROADMAP.MD).

### GUI shell

The application shell exists and runs (see "Application shell" under "Current foundation" above: a live menu bar and toolbars rendered from the command/menu contribution registries, and docked tool-window panels backed by the tool window registry). What's still ahead:

* Real content for the Extensions panel — the only docked tool window still rendering as a placeholder (Project Explorer, Git Changes, Git Repository, Output, Problems, Find Results, Terminal, Outline, Task List, and Bookmarks now have real content).
* A dedicated New Project dialog widget — today it's a sequence of stock `QInputDialog`/`QFileDialog` prompts rather than a single purpose-built form.
* The text editor widget has a first cut (tabbed `QPlainTextEdit`s, dirty tracking, undo/redo via Qt's built-in stack, syntax highlighting, coding-area guides, code folding, a minimap, split editors, multiple cursors, and column selection — see "Document editing" above); still missing: a persisted recent-files list.
* Tool-window pinning/auto-hide and floating-geometry persistence, which the current dock manager doesn't implement yet.

A Welcome page, shown when no editor tabs are open (New/Open Project, recent projects), is now built too — see "Document editing" above.

### Deeper COBOL language services

With a lexer, parser, and first semantic pass in place, the next COBOL language milestones are:

* Deeper per-verb statement grammar (ADD/SUBTRACT/MULTIPLY/DIVIDE/COMPUTE operand structure, STRING/UNSTRING, nested `ON SIZE ERROR`/`AT END`/`ON OVERFLOW` clauses) and structural parsing of the environment division (SELECT/ASSIGN, SOURCE-COMPUTER, and so on).
* Broader reference resolution (MOVE source expressions, IF/EVALUATE conditions) once that deeper grammar exists.
* Cross references, outline, hover, go-to-definition, find references, and rename are all done — see "Document editing" above and `opencobol2.language.outline`/`navigation`/`hover`.
* Automatic indentation. Division/section/paragraph/structured-statement folding is done (see "Document editing" above); data-group folding by level-number nesting is not — `DataSectionNode` holds a flat item list rather than a level-number tree. Format Document is done, but deliberately conservative (trailing-whitespace trim and tab-to-space expansion only, no COBOL-column-aware re-indentation) — see "Document editing" above.
* Code completion and snippets are done — see "Document editing" above and `opencobol2.language.completion`/`snippets`.
* Documentation lookup for reserved words, signature help for intrinsic FUNCTION calls, and quick fixes are all done — see "Document editing" above and `opencobol2.language.hover`/`signature_help`/`quick_fixes`.

These language services will be testable independently from the Qt editor widget, following the same pattern as the lexer, parser, and semantic analysis.

### GitHub integration

GitHub integration is a separate, not-yet-started layer on top of the existing Git service: authenticated GitHub account and repository workflows, with pull request and issue integration planned as the project develops.

### Compiler integration (remaining)

The compiler subsystem already supports GnuCOBOL and a generic custom local compiler profile, and Build > Build Project (see "Build integration" above) now compiles every source file in a project as an independent, unlinked build, skipping files that are already up to date. A GnuCOBOL-specific listing parser (`opencobol2.compiler.listing`) and Build > View Listing File are also done — see "Build integration" above. Not yet built: multi-file program linking — the project model has no "main program"/entry-point concept yet, so there's nothing to link against. Additional vendor providers (Micro Focus, IBM Enterprise COBOL, ACUCOBOL, Visual COBOL) are explicitly out of scope for now — the project is intentionally scoped to GnuCOBOL and custom compiler profiles.

### Debugger

The debugger is complete, end to end: a real GDB session, real dock-widget panels, and a real Debug menu, all empirically verified against a real `cobc`-compiled COBOL program rather than mocked. `opencobol2.debugger` provides Qt-independent domain models (`DebuggerState`, `StopReason`, `Breakpoint`, `StackFrame`, `Variable`, `ThreadInfo`, `RegisterValue`, `MemoryBytes`, `WatchExpression`, `StoppedEvent`) and two collaborating services: `GdbAdapter` spawns a real `gdb --interpreter=mi2` subprocess and speaks its MI protocol over a token-correlated async command/response loop (so unrelated events — a breakpoint hit, a new thread — never get mistaken for a command's own result), and `DebuggerService` drives it — breakpoints by COBOL source file:line (GDB genuinely honors the `#line` directives a `cobc -g -debug` build emits), run/continue/step, call stack, threads, registers, raw memory reads, arbitrary GDB expression evaluation, and the star feature: reading a live COBOL variable's *decoded* value. GnuCOBOL doesn't expose COBOL data names as GDB-lookupable symbols — each item compiles to an anonymous raw byte buffer, with its COBOL name surviving only as a comment in the compiler's generated `<name>.c.l.h`/`.c.h` header files. `opencobol2.debugger.gnucobol_symbols` parses those comments to recover the mapping, and `opencobol2.debugger.cobol_values` decodes the live bytes per the item's real PICTURE/USAGE clauses — DISPLAY (including sign-overpunch negatives), COMP-3/PACKED-DECIMAL, COMP-5, and BINARY are all decoded correctly, with every byte-encoding rule independently verified against real compiled/inspected values rather than assumed from documentation; COMP-1/COMP-2 floating point is explicitly reported as unsupported rather than silently decoded wrong. `DebuggerService.step_over_cobol_line()`/`step_into_cobol_line()` implement "smart stepping": a single raw step command can land inside GnuCOBOL's own runtime frame-management code rather than the next COBOL source line (verified empirically), so these repeat the step internally until execution reaches a `.cbl`/`.cob` frame, firing exactly one stop event for the result rather than one per internal step. The compiler-integration layer has a first-class way to request the debug build these features depend on: `CompileRequest.debug_symbols` (GnuCOBOL-specific — the custom local compiler provider is template-driven with no equivalent) inserts `-g -debug` into the real `cobc` invocation.

On the GUI side, a new Debug menu — Start Debugging (F5), Stop Debugging, Continue, Step Over (F10), Step Into (F11), Step Out (Shift+F11) — drives a `DebugSessionController` (`opencobol2.gui.debug_session`), a thin thread-safe Qt bridge around one `DebuggerService` session (its `stopped` signal relies on Qt's own auto-queued cross-thread connection handling, since a GDB stop can arrive from either the adapter's background reader thread or synchronously from a smart step's replayed callback). Start Debugging (`opencobol2.gui.debug_commands`) compiles the *active editor tab's* source with debug symbols — mirroring Build Project's existing single-file scope — and requires a GnuCOBOL compiler profile specifically, since the whole variable-decoding pipeline depends on it. Six new dock-widget panels show the live session: Call Stack (double-click a frame to jump to it), Locals (every top-level data item the debugger can decode, refreshed on every stop), Watch (user-added expressions — a COBOL name read via `read_variable`, falling back to a raw GDB expression), Threads (read-only for now), Registers, and Memory (address/length-driven hex dump). Phase 3's editor breakpoint toggle is now synced live to a real GDB breakpoint whenever a debug session is active against the same source file. Building this surfaced a genuinely non-obvious `cobc` behavior on Windows: it always forces its output filename to end in `.exe`, *replacing* any other extension the requested name already has rather than appending to it (`demo.debug` compiles to `demo.exe`, not `demo.debug.exe`) — worth knowing before assuming a compiled output's path.

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

Compiler, document, settings, command/menu/tool-window, source-control (Git), project-model, and COBOL language-service (lexer, parser, first semantic pass) boundaries are now implemented and extensively unit tested, Qt-independent from the start. A first real GUI shell now renders a live menu bar, toolbars, a status bar, and docked tool-window panels on top of that foundation, plus a Command Palette and a Settings dialog. The text editor has tabs, dirty tracking, undo/redo, autosave, line numbers, find/replace, syntax highlighting, live lex/parse/semantic diagnostics (underlined in the editor and listed in Problems), go to definition, find all references, hover tooltips, rename, code completion, snippets, format document, fixed-format coding-area guides, code folding, a minimap, split editors, multiple cursors, column selection, and printing, backed by a real `DocumentService`, with a Welcome page shown when no documents are open. Edit > Find in Files searches project source files and lists matches in a Find Results panel, a first-cut Terminal panel runs one shell command at a time, an Outline panel shows the active file's division/section/paragraph structure, a Task List panel scans project comments for TODO/FIXME/HACK/XXX markers, and Edit > Toggle Bookmark/Toggle Breakpoint plus Bookmarks and Breakpoints panels mark and list lines across open tabs (a breakpoint syncs to a real GDB breakpoint whenever a debug session is active against the same file). Project Explorer, Git Changes, Git Repository, Output, Problems, Find Results, Terminal, Outline, Task List, Bookmarks, Breakpoints, Call Stack, Locals, Watch, Threads, Registers, and Memory are the tool-window panels with real content; Extensions is the only placeholder left. A GDB-backed debugger now runs real COBOL debug sessions end-to-end (breakpoints by source line, stepping, call stack, threads, registers, memory, and decoded variable values) with a full Debug menu and six dock-widget panels wired into the running application — see "Debugger" below. Deeper COBOL semantic analysis, the plugin system, and remote/mainframe resource layer remain ahead.

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
