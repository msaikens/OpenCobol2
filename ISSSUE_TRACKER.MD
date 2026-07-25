# Phase 1–4 Issue Tracker

Generated from a full read-only review of every subsystem the roadmap lists under **Phase 1 — Foundation**, **Phase 2 — Project System**, **Phase 3 — Editor**, and **Phase 4 — COBOL Language Services**. Phase 1 covers: the command/menu/toolbar contribution framework, status bar, tool-window/docking registry, theme system, accessibility profiles, settings framework + persistence, the Qt-independent document/workspace model, and the Git foundation. Phase 2 covers: the Project domain model (virtual folders, linked files, excluded patterns, project properties, environment overrides), its JSON persistence layer, and the task/launch-configuration execution service. Both of those passes deliberately scope to the Qt-independent domain/service layer and exclude the Phase 7 GUI panels that render these subsystems (Project Explorer, Project Properties dialog, etc.) — those are a separate roadmap phase. Phase 3, by contrast, *is* the Qt editor widget itself (`SourceEditorWidget`/`EditorTabsWidget` and their satellite files), so that review is necessarily real Qt/GUI code, unlike Phases 1–2. Phase 3's own document-core-level items (encoding detection, BOM support, CRLF/LF conversion) were already covered under Phase 1's document/workspace model review and were not re-reviewed here. Phase 4 is the Qt-independent lexer/parser/AST/semantic-analysis pipeline and everything editor-facing built on top of it (hover, navigation, folding, quick fixes, signature help); the GUI wiring that consumes it (rename, quick-fix context menu, syntax highlighter, coding-area guides) was already reviewed under Phase 3 and is not repeated here. Phase 5 onward is otherwise out of scope.

Methodology: every file in scope was read in full against the corresponding tests, cross-referenced against the codebase's own established conventions (frozen/slots/kw_only dataclasses with `__post_init__` validation, atomic-write persistence, real-subprocess Git testing). A sample of the highest-severity findings in every pass was independently re-verified by direct code inspection (and, for Git, direct reasoning about the constructed command arguments) rather than accepted at face value; those are marked **[verified]** below. Everything else reflects the reviewing pass's own confidence level, and is marked **[confirmed]** (the reviewer read the exact trigger conditions in the code) or **[plausible, unconfirmed]** (a real gap in defenses, but no concrete trigger was constructed).

**Phase 1 fix status: complete.** Every Phase 1 finding has been triaged; each is now tagged inline with **FIXED** (code changed + regression test added, full Phase 1 suite re-run green — 1557 unit tests passing after the sweep), **DEFERRED** (a deliberate scope decision, with the reason given at the tag), or **NOT A BUG** (investigated further and found to already work correctly, with the verification described at the tag). Phases 2–4 below are still purely findings; no fixes have been applied there yet.

---

# Phase 1 — Foundation

## Priority items (highest impact across all Phase 1 subsystems)

All seven — **FIXED**, see the corresponding subsection below for each.

1. **App can fail to launch at all from a bad `settings.json`** — Settings §1 below.
2. **A settings file with custom compiler profiles but no explicit default ID fails to load entirely** — Settings §2 below.
3. **`git stash` can report success while silently stashing nothing** — Git §1 below.
4. **Opening a non-UTF-8, no-BOM COBOL source file crashes the app** — Documents §1 below.
5. **Saving a read-only file crashes instead of failing gracefully** — Documents §2 below.
6. **A single broken status-bar or menu-provider contributor can break the whole status bar / whole menu** — Status Bar §1, Commands §1 below.
7. **`git reset`/`log`/`revert`/`cherry-pick` build ref arguments without `--`, unlike every other Git command in the service** — Git §2 below.

---

## Git foundation

Files: `src/opencobol2/git/*.py`, `src/opencobol2/services/git.py`

### 1. `stash_changes` can report success while stashing nothing — HIGH — **[verified]** — **FIXED**

Now captures the stash list's top entry before the push and compares it against the top entry after; raises `GitCommandFailedError` if they're identical (no new stash was actually created), instead of returning the pre-existing entry as if it were new. Regression test: `test_stash_changes_detects_noop_when_only_untracked_changes` in `tests/unit/test_git_stash.py`.

`src/opencobol2/services/git.py:1524-1601`

The only pre-check is `status.clean` (raises `GitNothingToStashError` if the repo has *no* changes at all — confirmed untracked files count as "not clean" via `git/status.py`'s `_parse_untracked_change`). After running `git stash push`, the method assumes success purely because `self._get_stashes(repository_root)` is non-empty, and returns `refreshed_stashes[0]` as "the new entry" — it never compares the stash list/oid before vs. after the push.

**Concrete trigger:** a repo already has one stash entry; the working tree has *only* untracked files; caller invokes `stash_changes(path)` with the default `include_untracked=False`. `status.clean` is `False` (untracked files are changes), so the guard doesn't fire. `git stash push` (no `--include-untracked`) finds nothing stashable, prints "No local changes to save," exits 0. `refreshed_stashes` is non-empty because it still contains the *pre-existing* stash — so the method returns that stale entry as if it were newly created. The untracked files are never actually stashed; the caller is told the operation succeeded. `tests/unit/test_git_stash.py` has no case combining a pre-existing stash with untracked-only changes.

### 2. `reset`/`get_history`/`revert_commit`/`cherry_pick_commit`/`get_commit_diff` build ref arguments with no `--` separator — HIGH (for `reset`) / MEDIUM (others) — **[verified for `reset` and `get_history`]** — **FIXED**

Empirically tested real `git` behavior first, since a naive fix would have broken `reset`: a **leading** `--` before a ref switches `git reset` into path-reset mode and silently no-ops instead of moving the branch pointer (confirmed live: `git reset --hard -- HEAD~1` left history unchanged), whereas a **trailing** `--` after the ref works correctly everywhere tested (`reset`, `log`, `show`, `revert`, `cherry-pick`) and closes off the ref-vs-path ambiguity without changing behavior. Fix has two parts: (1) `_require_ref_name`/`_normalize_optional_ref_name` (the latter via a new `is_free_text` flag, since it's also reused for tag/stash *messages* which legitimately can start with `-`) now reject any ref/branch/tag/commit-ish value starting with `-`, closing the actual argument-injection vector; (2) `reset`, `get_history`, `revert_commit`, `cherry_pick_commit`, and `get_commit_diff` all now append a trailing `--` after the ref as defense-in-depth. Regression tests: `test_reset_rejects_dash_prefixed_target` plus updated exact-command assertions across `tests/unit/test_git_reset_revert_cherrypick.py`, `test_git_history.py`, `test_git_diff.py`.

`src/opencobol2/services/git.py`: `reset` 1729-1736, `get_history` 1482-1495, `revert_commit` 1763-1774, `cherry_pick_commit` 1810-1821, `get_commit_diff` 1897-1903

Every other ref/name-taking command in this file (`stage_paths`, `create_branch`, `delete_branch`, `switch_branch`, `create_tag`, `delete_tag`, `add_remote`/`remove_remote`/`rename_remote`, `fetch`/`pull`/`push`) places the user-supplied value after a literal `"--"` — directly confirmed for `switch_branch` (`("switch", "--", normalized_name)`, `git.py:1264-1280`). `reset` (confirmed: `("reset", f"--{mode}", normalized_target)`, no `--`) and `get_history` (confirmed: `arguments += (normalized_ref,)`, no `--`) do not follow this pattern; nothing in `_require_ref_name`/`_normalize_optional_ref_name` rejects a leading `-`.

**Concrete trigger:** this same service's own `create_branch`/`create_tag` already allow creating a ref literally named e.g. `-force` (git itself permits this when disambiguated with `--`). Calling `reset(path, target="-force", mode="mixed")` builds `git reset --mixed -force` — an ambiguous, unpredictable invocation for a destructive operation. Calling `get_history(path, ref="-force")` builds `git log --format=... -force`, which git rejects as an unrecognized option instead of showing that ref's history.

### 3. `revert_commit`/`cherry_pick_commit` cannot target a merge commit — MEDIUM — **[confirmed]** — **FIXED**

Both now accept an optional `mainline: int | None` parameter that adds `-m <n>` to the git invocation when given. Regression tests: `test_revert_commit_with_mainline_verifies_exact_git_command`, `test_cherry_pick_commit_with_mainline_verifies_exact_git_command`.

`src/opencobol2/services/git.py:1746-1791`, `1793-1838`

Neither exposes git's `-m/--mainline <parent-number>` option, so reverting/cherry-picking an existing merge commit always fails with git's own "commit is a merge but no -m option was given." The history/log parser already handles merge commits (multiple parents) correctly, so this reads as a missed step rather than a deliberate cut — revert/cherry-pick are listed "done" in the roadmap, unlike merge/rebase which are explicitly out of scope.

### 4. `invoke_git_process` decodes subprocess output with no pinned encoding — MEDIUM-HIGH — **[confirmed]** — **FIXED**

`subprocess.run(...)` now passes `encoding="utf-8"` explicitly (kept alongside `errors="replace"` as a fallback for genuinely malformed bytes); the bytes-decode fallback path in `_normalize_process_output` was also pinned to UTF-8.

`src/opencobol2/git/process.py:76-86`

`subprocess.run(..., capture_output=True, text=True, errors="replace", ...)` has no `encoding=` argument, so decoding falls back to `locale.getpreferredencoding()` — commonly a legacy Windows code page, not UTF-8, unless UTF-8 mode is forced. Git's porcelain output (read with `-z`, disabling path quoting) carries raw UTF-8 bytes for non-ASCII names/messages. Every other storage layer in this codebase (`project/storage.py`, `settings/storage.py`, `documents/storage.py`) explicitly pins `encoding="utf-8"`; this is the one outlier. Combined with `errors="replace"` (not `surrogateescape`), a mis-decoded non-ASCII path becomes irreversibly corrupted (`U+FFFD`) and can no longer round-trip back into `stage_paths`/`unstage_paths` — `git add -- <corrupted-path>` then fails with "pathspec did not match any files." No test exercises a non-ASCII path or commit message.

### 5. Single, non-overridable per-instance command timeout applies to network operations too — MEDIUM — **[confirmed]** — **FIXED**

`_invoke` now accepts an optional per-call `timeout_seconds` override (falling back to the service-wide default when omitted), and `clone_repository`/`fetch`/`pull`/`push` all expose it as a keyword parameter. Regression test: `test_fetch_timeout_override_passed_through`.

`src/opencobol2/services/git.py:200-289`, `2068-2091`

`timeout_seconds` (default 30s) is fixed at `GitService` construction and used identically for local `status`/`add` and for `clone`/`fetch`/`pull`/`push`. A legitimately slow clone/fetch over a slow link is killed at 30s and reported as a timeout, with no per-call override available.

### 6. Conflict/clone-failure classification is pure stdout/stderr substring matching — LOW — **[plausible, unconfirmed]** — **DEFERRED**

Left as-is: no concrete real-git message was found that both triggers a false match and is unrelated to the condition being tested for, and a structural rewrite (parsing exit codes / `MERGE_HEAD` presence instead of substrings) is a larger design change than warranted for a design-fragility finding with no live reproduction.

`src/opencobol2/services/git.py:2321-2424`

`_looks_like_clone_source_failure`/`_looks_like_merge_conflict` match marker words (`"conflict"`, `"could not apply"`, `"not found"`, `"unable to access"`) against lower-cased combined output rather than a structural signal (e.g. presence of `MERGE_HEAD`, git's own exit codes). No concrete real-git message was found that both triggers a false match and is unrelated to the condition being tested for, so this is a design fragility rather than a confirmed misclassification today.

### 7. No `GIT_TERMINAL_PROMPT=0` override for network operations — LOW — **[plausible, unconfirmed]** — **FIXED**

`invoke_git_process` now sets `GIT_TERMINAL_PROMPT=0` in the subprocess environment via `setdefault` (so an explicit caller override is still respected), for every invocation. Regression tests: `test_invoke_git_process_disables_terminal_prompt_by_default`, `test_invoke_git_process_respects_explicit_terminal_prompt_override`.

`src/opencobol2/services/git.py:2076-2091`

Nothing disables interactive credential prompting for `fetch`/`pull`/`push`/`clone_repository`. On Windows, Git Credential Manager can pop a native GUI dialog for an authentication-required remote instead of failing fast on stderr; if ignored, the operation is eventually just killed and reported as "timed out" rather than "authentication needed." Not tested against a real authenticated remote.

---

## Command / menu / toolbar contribution framework

Files: `src/opencobol2/commands/*.py`, `src/opencobol2/services/commands.py`, `src/opencobol2/services/command_contributions.py`

### 1. A `DynamicMenuProvider` exception (or a stale command-ID reference) aborts resolution of the *entire* menu surface — HIGH — **[confirmed, with a real production trigger]** — **FIXED**

`resolve_surface` now isolates each contribution's resolution in its own try/except — a raising direct contribution, a raising dynamic-menu provider, or a single bad item within an otherwise-good provider's output is skipped individually rather than aborting the whole surface. Regression tests: `test_service_skips_contribution_for_missing_command`, `test_service_skips_only_broken_contribution_among_others`, `test_dynamic_menu_provider_producing_invalid_items_is_isolated`.

`src/opencobol2/services/command_contributions.py:235-256` (`_resolve_dynamic_menu_contribution`)

`contribution.provider(context)` and the subsequent `self._command_service.get_command(item.command_id)` lookup are not wrapped in exception handling beyond a narrow `tuple(...)` `TypeError` catch. Any other exception propagates out of `resolve_surface()`, discarding every other already-resolved contribution on that surface.

**Concrete trigger:** the real recent-projects provider (`src/opencobol2/gui/project_commands.py:355-381`, `provide_recent_projects`) filters with `path.is_file()` for every path in `recent_projects.paths`, with no try/except. `Path.is_file()` does not catch `ValueError` (e.g. a path string containing an embedded null byte, reachable from a corrupted/hand-edited settings file). That `ValueError` propagates through `resolve_surface(MENU, "file")` and up through `command_menus.py:populate_menu`, which has *already called `menu.clear()`* — so the File menu ends up empty/broken via an unhandled exception surfacing through Qt's `aboutToShow` signal. No test exercises a raising provider.

### 2. No cycle/self-reference guard on submenu contributions, and the real consumer recurses with no visited-set — MEDIUM — **[confirmed mechanism, no live trigger in the current built-in catalog]** — **FIXED**

`connect_menu`/`populate_menu` now thread an `_ancestor_surface_ids` set down the recursion; a submenu whose `submenu_id` is already an ancestor is skipped rather than recursed into, breaking any cycle one level in (so e.g. a direct A→A self-reference still renders the "A" entry once, just with an empty nested submenu, rather than vanishing outright or recursing forever). Regression tests: `test_populate_menu_breaks_self_referencing_submenu_cycle`.

`src/opencobol2/commands/contributions.py:110-193` (`SubmenuContribution.__post_init__`), `src/opencobol2/gui/command_menus.py:103-123`

Nothing checks `submenu_id == surface_id`, and nothing detects a cycle across two submenus (A's `submenu_id` == B's `surface_id` and vice versa). The GUI's `connect_menu` → `populate_menu` → `connect_menu` recursion carries no visited-ID set. Not triggered by the current single-level built-in catalog, but unprotected against a future/plugin-contributed cyclic registration, which would hang/crash on `RecursionError` the moment the menu is shown.

### 3. Dynamic-menu-item `enabled` override is enforced from a stale snapshot, not re-derived at execution time — MEDIUM — **[confirmed]** — **FIXED**

`execute_dynamic_item` now re-derives the command's state fresh and recombines it with the item's own `enabled` override immediately before executing, instead of trusting the `ResolvedDynamicMenuItem` snapshot captured at the last `resolve_surface()` call — this matters because `CommandService.execute()`'s own fresh re-check has no notion of a per-item override at all, so it can't enforce that half by itself.

`src/opencobol2/services/command_contributions.py:189-213`

`execute_dynamic_item` checks `item.state.enabled` from the `ResolvedDynamicMenuItem` captured at the *last* `resolve_surface()` call — never re-evaluated before executing. By contrast, `CommandService.execute()` always calls `command.state(context)` fresh immediately before checking `enabled` (`services/commands.py:76-102`). If an item's per-item `enabled` override depends on live conditions that change between resolution and execution, a caller holding the old resolved object can execute an item that would now resolve as disabled.

### 4. Handler-mapping keys are never cross-validated against the actual built-in command-ID catalog — LOW/MEDIUM — **[confirmed]** — **FIXED (adjacent gap, same root cause)**

Rather than special-casing `BuiltInCommandHandlers`, added `CommandContributionService.validate_contributions()`, which cross-checks every *contribution*'s `command_id` against the live `CommandRegistry` and returns the offending contribution IDs. Wired into `gui/application.py`'s bootstrap right after the contribution service is built, raising a clear `RuntimeError` at startup if any exist — this is more load-bearing now than it would have been standalone, since fix #1 above makes a bad `command_id` reference silently invisible at runtime (isolated and skipped rather than crashing), so a static, fail-fast startup check is what actually catches the typo going forward. Regression tests: `test_validate_contributions_reports_missing_command`, `test_validate_contributions_returns_empty_when_all_resolve`.

`src/opencobol2/commands/builtins.py:222-292`

`BuiltInCommandHandlers` validates its keys are non-empty, pre-stripped strings mapping to callables, but never checks membership against `BuiltInCommandIds`. A typo'd key (e.g. `"file.svae"`) is silently accepted at construction; the real `FILE_SAVE` command keeps its `unconfigured_handler` and only fails at the moment it's actually invoked, with a `BuiltInCommandHandlerNotConfiguredError` message disconnected from the actual typo.

### 5. `separator_before`/`separator_after` live on the same contribution that visibility hides — LOW — **[confirmed interaction, no test coverage]** — **FIXED**

`gui/command_menus.py` and `gui/toolbars.py` now resolve with `include_hidden=True` and gate only the `addAction`/`addMenu` call on `state.visible` — the contribution's own separator flags render regardless, so a hidden item's neighbors keep their intended visual boundary instead of losing it along with the item. Regression test: `test_populate_menu_keeps_separator_around_hidden_contribution`.

`src/opencobol2/services/command_contributions.py` (`resolve_surface` visibility filtering)

If the contribution carrying `separator_before=True` becomes hidden via its own `state_provider`, the visual group boundary disappears along with it. Not necessarily a bug by design, but an untested interaction between two independent features.

### 6. Test filename typo (cosmetic) — **[verified]** — **FIXED**

Renamed via `git mv` to `tests/unit/test_command_contribution_service.py`, preserving history.

`tests/unit/test_commant_contribution_service.py` — "commant" should be "command." Does not affect pytest discovery (still matches `test_*.py`), purely a real typo in the file's actual name.

**Checked and found correct:** duplicate command/contribution IDs are strictly rejected (no silent overwrite); `group_order`/`order` sorting is a stable, validated, non-bool-int sort with deterministic tie-breaking by registration order; every built-in contribution's `command_id` resolves to a real registered command (no dangling references); `CommandService.execute()` cannot be used to bypass a disabled command's state check; ID normalization is whitespace-only and applied identically on read/write (no case-sensitivity inconsistency); `_resolve_external_handler` raises a clear, well-typed error naming the specific unconfigured command.

---

## Settings framework + persistence

Files: `src/opencobol2/settings/*.py`

### 1. No error handling around settings load at application startup — HIGH — **[verified]** — **FIXED**

`SettingsService.__init__` now wraps the initial `self._storage.load()` in try/except; on any exception, it falls back to `ApplicationSettings()` defaults and records the failure on a new `load_error` property (`Exception | None`) so a caller can surface it later (e.g. a startup warning) without the load itself ever blocking launch. Regression tests: `test_service_falls_back_to_defaults_on_corrupt_settings_file`, `test_service_has_no_load_error_on_clean_start`.

`src/opencobol2/settings/service.py:29-38` (`self._current = self._storage.load()`, no try/except) → `src/opencobol2/gui/application.py` (`SettingsService()` constructed unguarded inside `create_main_window`) → `main()` (`application.py:1240-1263`, calls `create_main_window()` with no try/except anywhere in the chain — confirmed by direct inspection).

Every load-time exception this subsystem defines (`SettingsFormatError`, `UnsupportedSettingsVersionError`) propagates uncaught out of `main()`. A single corrupted/incompatible `settings.json` (hand-edited, a future schema bump, or partial corruption from any source) makes the entire application fail to launch with a raw traceback, with no reset-to-defaults recovery path — notably, this exact "degrade gracefully instead of crashing the bootstrap" principle is already applied elsewhere in the same file for Git-repository discovery failures, just not here.

### 2. A settings file with a customized `compilers.profiles` list but no explicit `default_profile_id` fails to load entirely — HIGH — **[reported as directly executed and reproduced by the reviewing agent; not independently re-run by the main session]** — **FIXED**

`_decode_compiler_settings` now only falls back to the bundled `DEFAULT_GNUCOBOL_PROFILE_ID` when `profiles` itself was *also* left unset (i.e. using the fully-default `CompilerSettings()`, where the ID and its matching profile are a pair). When custom profiles are supplied without an explicit `default_profile_id`, the fallback is `None` instead — a value `CompilerSettings` already accepts, and one the toolchain-discovery layer (`services/toolchains.py::_default_profile`) already turns into a clean `ValueError("No default compiler profile is configured.")` at the point of actual use, rather than crashing the whole settings load. Regression test: `test_custom_profiles_without_default_profile_id_loads_with_none`.

`src/opencobol2/settings/storage.py:408-454` (`_decode_compiler_settings`, fallback at 437-444)

When `"default_profile_id"` is omitted from the JSON, the decoder falls back to the built-in `DEFAULT_GNUCOBOL_PROFILE_ID` regardless of whether `"profiles"` was also customized. If a hand-edited or externally-generated settings file supplies custom `profiles` but omits `default_profile_id`, the fallback ID won't be present in the supplied list, `CompilerSettings.__post_init__`'s existing-profile-reference check fails, and the outer exception handling in `_decode_settings` turns this into a `SettingsFormatError` that aborts loading the *entire* settings file — not just the compilers section. Combined with finding #1, this is a full app-launch crash from an otherwise-reasonable hand-authored settings file. Reported as verified by executing a repro JSON directly (`{"schema_version":1,"compilers":{"profiles":[...]}}` with `default_profile_id` omitted); adding an explicit `"default_profile_id": null` to the same file was reported to load successfully, isolating the fallback logic as the cause.

### 3. No locking; concurrent instances can silently clobber each other's saved settings — MEDIUM — **[confirmed by code inspection: no lock/guard exists anywhere in the codebase]** — **DEFERRED**

Not implemented: this is a single-user desktop IDE, not a multi-process daemon, and a real cross-process lock (`QLockFile`/platform-specific file locking) is a meaningfully larger, platform-branching change than the lost-update risk warrants at this stage. The atomic-write mechanism itself (temp file + `os.replace`) already prevents corruption; only a *lost update* between two simultaneously-running instances is at risk, which is a narrow scenario for this application.

`src/opencobol2/settings/storage.py` (whole file), `src/opencobol2/settings/service.py` (`apply`/`update_*`)

No lockfile/single-instance guard exists anywhere (`QLockFile`/`SingleApplication`/`QSharedMemory` all absent from `src/`). `apply()` always writes the complete in-memory snapshot, so two processes (or two `SettingsService` instances) against the same file will have whichever saves last silently discard the other's most recent change — a lost update, not file corruption (the atomic temp-file+`os.replace` write itself is sound).

### 4. "Schema-versioned" persistence has no actual migration path — MEDIUM/LOW (missed step, not a live bug today) — **[confirmed]** — **DEFERRED**

Not implemented: only schema version 1 exists today, so a migration registry has no concrete second version to migrate from/to yet — building one now would be speculative, un-exercisable infrastructure. Flagged here so it's retrofitted at the point a version 2 actually exists, rather than forgotten.

`src/opencobol2/settings/storage.py:332-348`

Both older and newer `schema_version` values are strictly rejected; the only migration-shaped code is a single hardcoded detector for one specific pre-1 legacy layout. There is no per-version decoder/migration registry. Not a live bug while only version 1 exists, but the first legitimate version bump will make every existing user's settings file instantly unloadable (and, per finding #1, fatally so) unless migration code is retrofitted at that time.

### 5. `RecentProjectsSettings` doesn't deduplicate at construction, only via `with_recorded_path` — LOW — **[reported as directly executed]** — **FIXED**

`__post_init__` now deduplicates (keeping first occurrence, preserving order) in addition to truncating to `MAX_RECENT_PROJECTS`, so the class's own "deduplicated, newest first" docstring claim now actually holds regardless of entry point. Regression test: `test_recent_projects_settings_deduplicates_at_construction`.

`src/opencobol2/settings/models.py:318-328` vs. `330-344`

`__post_init__` only truncates to `MAX_RECENT_PROJECTS`; it does not deduplicate. A hand-edited settings file with a duplicate path in `recent_projects.paths` reportedly round-trips with the duplicate intact, contradicting the class's own "deduplicated, newest first" docstring claim. Low severity since the only real production caller (`gui/project_commands.py`) always goes through `with_recorded_path`, which does dedupe.

### 6. No `fsync` of the parent directory after `os.replace` — LOW — **[plausible, unconfirmed — untestable without a real crash/power-loss simulation]** — **DEFERRED**

Not implemented: this is primarily a POSIX/ext4-style crash-consistency concern, and this codebase's primary target/dev platform (Windows/NTFS) doesn't expose an equivalent directory-fsync API or share the same durability gap. Low value relative to the platform-specific complexity of doing it correctly cross-platform.

`src/opencobol2/settings/storage.py:850-885`

The temp file's contents are `fsync`'d before rename, but the directory entry itself is never `fsync`'d afterward, which on some filesystems could theoretically allow a rename to not durably persist across a real crash immediately after `os.replace()` returns. The atomic-replace guarantee itself (no truncated/corrupt file) is not in question — only durability of the *rename* under power loss.

**Checked and found correct:** Windows path case-sensitivity for recent-project dedup (`WindowsPath.__eq__` already normalizes case, confirmed directly); `os.replace` (not `os.rename`) is used, and the temp file is created in the same directory, so the replace can never cross filesystems or hit Windows' overwrite-existing-file limitation; no mutable shared defaults (`[]`/`{}`) found anywhere — every field needing a fresh container correctly uses `field(default_factory=...)`; validation constraints (e.g. `EditorSettings.font_size` positivity, `ThemeSettings.active_theme_id` non-emptiness) are re-enforced at load time via the nested dataclasses' own `__post_init__`, not just at first construction.

---

## Document / workspace model

Files: `src/opencobol2/documents/*.py`

### 1. No real encoding detection beyond BOM-sniffing; a wrong-encoding file crashes instead of degrading — HIGH — **[verified]** — **FIXED**

Added a new `DocumentDecodeError(ValueError)`, raised (wrapping the original `UnicodeDecodeError`) when the strict decode fails, instead of a raw `UnicodeDecodeError` escaping the storage layer. Wired all the way to the GUI: `EditorTabsWidget.open_path` now catches `(OSError, DocumentDecodeError)` and shows `QMessageBox.critical` instead of crashing the double-click/find-result/task-list/call-stack signal handlers that all funnel through it — this also incidentally resolves finding #7 below, since `OSError` (which subsumes `FileNotFoundError`) is now caught at the same call site. Regression tests: `test_load_raises_document_decode_error_on_bad_encoding`, `test_open_path_shows_error_dialog_on_undecodable_file`.

`src/opencobol2/documents/storage.py:60-89` (`DocumentStorage.load`)

When no BOM is present, content is decoded with `content_bytes.decode(encoding, errors="strict")` using `default_encoding`/`fallback_encoding` (default `"utf-8"`) — confirmed no try/except surrounds this call. There is no charset-detection heuristic and no fallback chain.

**Concrete trigger:** a file containing `"café".encode("latin-1")` (no BOM) raises an uncaught `UnicodeDecodeError` on `DocumentStorage().load(path)`, since `0xE9` is not a valid UTF-8 continuation byte. `DocumentService.open_document` does not catch or wrap this either. COBOL source with legacy 8-bit characters (accented text, CP437/CP1252 box-drawing) and no BOM is a realistic scenario for this crash. The mirror problem exists on save: `_encode_document` also uses `errors="strict"`, so content containing characters outside the document's configured encoding raises an uncaught `UnicodeEncodeError` with no domain-specific exception type.

### 2. Saving unconditionally fails when the destination file has the Windows read-only attribute set — HIGH — **[reported as empirically reproduced by the reviewing agent: `os.replace` onto a read-only-attribute destination raised `PermissionError: [WinError 5] Access is denied` in a direct test]** — **FIXED**

`_write_replacement_file` now clears the destination's read-only bit (`os.chmod(destination, existing_mode | stat.S_IWRITE)`) immediately before `os.replace`, since Windows checks the *destination's* attribute regardless of the replacement file's own mode. The temp file already carries the original mode (read-only included) via the existing `os.chmod(temporary_path, existing_mode)` line, so the net effect after the swap correctly preserves the file's read-only status. Regression test: `test_save_overwrites_read_only_file` — verified against a real read-only file on this Windows machine, not just reasoned about.

`src/opencobol2/documents/storage.py:231-282` (`_write_replacement_file`)

The destination's existing file mode is captured and reapplied to the *temporary* file, but the destination's read-only attribute is never cleared before `os.replace(temporary_path, destination)` is used to publish the new content. Any COBOL source checked out read-only (common with some VCS/read-only-media workflows) reportedly cannot be saved through `DocumentService.save_document`/`save_document_as` — the exception propagates uncaught.

### 3. Mixed line-ending files are silently normalized to a single style on every save, rewriting untouched lines — MEDIUM — **[confirmed by reading `_encode_document`/`_detect_line_ending`; concrete repro described but not independently re-run]** — **DEFERRED**

Not changed: correctly preserving per-line endings through the in-memory edit buffer (rather than one dominant style for the whole document) is a real architectural change, not a bug fix — and normalizing to one line ending on save is standard behavior for mainstream editors (e.g. VS Code does the same by default). Reclassifying as an accepted, documented limitation rather than a defect.

`src/opencobol2/documents/storage.py:162-220`

Only one dominant `LineEnding` is tracked per document; save applies `document.text.replace("\n", document.line_ending.value)` to the *entire* file. A file with a 1-LF/3-CRLF mix detects CRLF as dominant; editing only the LF line and saving reportedly rewrites the *other*, untouched LF line to CRLF too — producing an unrelated diff line. No test covers save-time preservation of a mixed-ending file (only detection is tested).

### 4. Brand-new files are saved with restrictive `0600` permissions on POSIX systems — MEDIUM (not applicable on this Windows dev machine; deterministic CPython stdlib behavior) — **[confirmed by code inspection, not independently re-run on POSIX]** — **DEFERRED**

Not fixed in this pass: this development environment is Windows, where the finding doesn't manifest and can't be verified end-to-end. Left for a POSIX-side follow-up rather than changed blind.

`src/opencobol2/documents/storage.py:231-282`

When the destination doesn't yet exist (first save of a new/"Save As" document), the file-mode-reapplication step is skipped, and `tempfile`'s backing file is always created via `os.open(file, flags, 0o600)`. On Linux/macOS, every newly-saved document through this layer ends up owner-only-readable rather than the typical umask-derived `0644`.

### 5. No conflict detection for externally-modified files — LOW/MEDIUM — **[confirmed as an unguarded gap; likely a deliberate Phase 1 scope cut, but undocumented and untested]** — **DEFERRED**

Not implemented: this is feature-sized (mtime/hash tracking plus new "file changed externally — reload or overwrite?" UI), not a bug fix, and is better scoped as its own piece of work.

`src/opencobol2/documents/models.py` (no mtime/hash/generation marker anywhere in `TextDocument`)

Saving blindly overwrites the destination via atomic replace with zero staleness check against changes made to the file externally after it was opened. No test and no documented behavior for this case.

### 6. Saving to a destination that is itself a symlink replaces the symlink with a regular file — LOW — **[plausible, unconfirmed — not creatable in this sandbox without elevated Windows privileges]** — **DEFERRED**

Not fixed: narrow, unconfirmed, and not reproducible in this environment (symlink creation requires elevated privileges on Windows). Lower priority than the confirmed findings that were fixed this pass.

`src/opencobol2/documents/storage.py:273-276`

Standard `os.replace` semantics mean a symlinked destination gets replaced outright rather than the write following the link through to the link's target, which would orphan the original target file. Inferred from documented OS semantics, not executed.

### 7. Opening a nonexistent path raises a raw `FileNotFoundError` instead of a domain-specific exception — LOW — **[confirmed, minor API-consistency gap]** — **RESOLVED (already caught as a side effect of fix #1)**

Not given its own domain exception type: `FileNotFoundError` is already a well-understood, clear stdlib exception (an `OSError` subclass), and `EditorTabsWidget.open_path`'s new `except (OSError, DocumentDecodeError)` (added for fix #1 above) already catches it at the one real GUI entry point, showing the same clear `QMessageBox.critical` dialog rather than crashing. Introducing a parallel domain type wouldn't change behavior at the only call site that matters.

`src/opencobol2/documents/service.py:57-89`, `src/opencobol2/documents/storage.py:67`

Inconsistent with `DocumentSavePathRequiredError`/`DocumentAlreadyOpenError`/`DocumentHasUnsavedChangesError`, all of which are domain-specific; no test exercises this path.

### 8. Duplicate-path detection on a case-insensitive filesystem can miss a collision in a narrow race — LOW — **[plausible, unconfirmed compound race]** — **NOT A BUG (re-verified directly)**

Directly tested on this Windows machine: `Path("FOO.TXT").resolve()` for an *existing* file already returns the canonical on-disk casing (confirmed via `Path.resolve()`'s real filesystem query, not just string manipulation), so `_path_key("Foo.txt") == _path_key("FOO.TXT")` for any file that actually exists at tracking time — which every file the workspace tracks does, since it was just loaded or saved. The `samefile()` fallback provides a second line of defense. The originally-flagged race (external deletion between tracking and the next duplicate check) remains theoretically true but is now confirmed to require that specific narrow window rather than being reachable through ordinary case-difference alone, and this is a single-threaded Qt event loop with no concurrent open operations to race in the first place.

`src/opencobol2/documents/workspace.py:148-165`

`Path.resolve(strict=False)` normalizes differently-cased paths to different strings when the file doesn't exist; the fallback `samefile()` check also fails (raising, caught, returns `False`) in that case. Reported as verified for the "file doesn't exist yet" case specifically, but every path actually tracked in the workspace currently corresponds to a file that was just loaded/saved (so it exists at tracking time, and resolution correctly canonicalizes case on the happy path). The gap only opens if that file is deleted externally between being tracked and the next duplicate check — a narrow, hard-to-trigger race.

**Checked and found correct:** `__init__.py` is a clean re-export with no issues; the dirty-tracking comparison itself (`TextDocument._current_state()`, comparing text/encoding/line-ending/BOM as a tuple) is sound, including the undo-back-to-saved-state case.

---

## Status bar / tool windows / theming / accessibility

Files: `src/opencobol2/status_bar/*.py`, `src/opencobol2/tool_windows/*.py`, `src/opencobol2/theming/*.py`, `src/opencobol2/accessibility/*.py`, and their corresponding `services/*.py` wrappers.

### 1. A single raising status-bar item provider breaks the whole alignment group's refresh — HIGH — **[confirmed by direct repro in the reviewing agent's session: one healthy `LEFT` item plus one raising `LEFT` item, then `resolve_alignment(LEFT)` propagated the exception and lost the healthy item's content too]** — **FIXED**

`resolve_alignment` now resolves each item in its own try/except; a provider that raises (or returns the wrong content type, caught by `ResolvedStatusBarItem`'s own validation) is skipped for that refresh instead of blanking out every other item in the group. Regression test: `test_resolve_alignment_isolates_a_raising_provider`.

`src/opencobol2/services/status_bar.py:73-102` (`resolve_alignment`)

The generator calling `definition.provider()` for every item in an alignment group has no per-item exception handling. One misbehaving contributor (built-in or, eventually, plugin) takes down the *entire* alignment group's refresh, not just its own item. No test in `test_status_bar_service.py` covers a raising provider.

### 2. A tool window can end up simultaneously `floating=True` and `area=DOCUMENT` — MEDIUM/HIGH — **[confirmed by two direct repros: (a) `set_floating` then `move_to_area(DOCUMENT)` directly, and (b) activating an accessibility profile whose override sets `area=DOCUMENT` without specifying `pinned`]** — **FIXED**

`ToolWindowService.set_floating`/`move_to_area` each now reject the combination directly: `set_floating(id, True)` raises `ValueError` if the window's current area is already `DOCUMENT`, and `move_to_area(id, DOCUMENT)` raises `ValueError` if the window is currently floating. Since the accessibility-profile path (repro (b)) routes through these same two methods, it's covered by the same fix — but that path also needed its own change, see finding #3 immediately below. Regression tests: `test_document_area_window_cannot_be_made_floating`, `test_floating_window_cannot_be_moved_to_document_area`.

`src/opencobol2/tool_windows/models.py` (`ToolWindowState.__post_init__`), `src/opencobol2/services/tool_windows.py` (`move_to_area` / `set_floating`), `src/opencobol2/services/accessibility.py:176-238` (`_validate_profile_activation`)

The model enforces "floating ⇒ pinned" and "DOCUMENT area ⇒ pinned," but never "DOCUMENT area ⇒ not floating," and neither service method cross-checks the other axis. More concerning: this is reachable through the *public, validated* accessibility-profile-activation path, not just direct internal misuse — activation's own validation only checks `override.pinned is False` combinations, so an override that leaves `pinned` as `None` sails through even though it silently produces the contradictory `area=document, floating=True, pinned=True` state.

### 3. `AccessibilityService.activate_profile` can leak the wrong exception type for a profile referencing an unregistered tool window — MEDIUM — **[confirmed by direct repro: activating a profile with an override for a nonexistent tool-window ID raised `ToolWindowNotFoundError` (a `LookupError`), not the documented `AccessibilityProfileActivationError` (a `ValueError`)]** — **FIXED (and widened)**

`activate_profile` now wraps its validation-and-apply block in a try/except that catches `AccessibilityProfileActivationError` unchanged (already the right type, raised directly by `_validate_profile_activation`'s own checks) and re-raises anything else from `(ToolWindowNotFoundError, ValueError)` as `AccessibilityProfileActivationError`. Widened beyond the original finding: fixing #2 above added two *new* `ValueError` cases inside `ToolWindowService` (the floating/DOCUMENT-area conflict guards) that `_validate_profile_activation` doesn't pre-check today — without this wrapper, those would have newly leaked out of `activate_profile` as raw `ValueError`s, the exact same class of bug this finding describes, just from a different origin. Regression tests: `test_activate_profile_wraps_stale_tool_window_id`, `test_activate_profile_wraps_floating_document_area_conflict`.

`src/opencobol2/services/accessibility.py:176-238`

`ToolWindowAccessibilityOverride` never checks tool-window existence at construction (correctly — models are registry-agnostic), and the validation step's internal registry lookup isn't wrapped. No corruption occurs (validation runs fully before any mutation), but the escaping exception type breaks the documented contract callers would reasonably rely on. `test_accessibility_service.py` has no test for an override referencing an unregistered ID.

### 4. High Contrast Light theme reuses the plain Light theme's syntax colors almost verbatim, undermining its own purpose — MEDIUM — **[verified]** — **FIXED**

Replaced with a distinct palette, each color individually verified via a WCAG contrast-ratio computation against the theme's `#FFFFFF` background: `syntax_keyword` unchanged (`#0000FF`, 8.59:1 — already AAA-passing), `syntax_string` → `#8B0000` (10.01:1, was `#A31515`/7.85:1), `syntax_number` → `#006400` (7.44:1, was `#098658`/**4.60:1 — previously failed WCAG AAA's 7:1 threshold entirely**, the actual accessibility defect underneath the copy-paste), `syntax_comment` → `#444444` (9.74:1, was `#006400`, freed up by number's move so no two tokens share a color). All four now clear AAA and are pairwise distinct. Regression test: `test_high_contrast_light_syntax_colors_differ_from_light`.

`src/opencobol2/theming/builtins.py`: `_create_light_theme` (`syntax_keyword="#0000FF"`, `syntax_string="#A31515"`, `syntax_number="#098658"`, `syntax_comment="#008000"`) vs. `_create_high_contrast_light_theme` (`syntax_keyword="#0000FF"`, `syntax_string="#A31515"`, `syntax_number="#098658"`, `syntax_comment="#006400"`) — three of four syntax-highlighting colors are byte-for-byte identical between the two themes; only `syntax_comment` was actually darkened. Every other color role in the HC theme (background, foreground, accent, selections, diagnostics, line numbers) was deliberately pushed to a high-contrast value, so this reads as an incomplete copy-paste rather than intentional reuse. The reviewing agent additionally computed contrast ratios and reported `syntax_number` (#098658 on white) at ~4.6:1 — barely clearing WCAG AA (4.5:1) and well short of the ~7–8.6:1 the theme's other fields achieve, meaning number literals are the least legible token color in the theme explicitly built to maximize legibility.

### 5. No direct unit tests for the theme registry/models/builtins — LOW (test-coverage gap, not a behavioral bug) — **[verified via file listing: only `test_theme_service.py` exists]** — **DEFERRED**

Not addressed as a dedicated effort: `test_theming_builtins.py` did gain new coverage as part of fixing #4 above (verifying the high-contrast palette is distinct and internally non-duplicated), but a full `test_theme_registry.py`/`test_theme_models.py` sweep is a coverage-gap task, not a bug fix, and is left for a dedicated pass.


No `test_theme_registry.py`, `test_theme_models.py`, or `test_theme_builtins.py`. Nothing directly tests `ThemeColors`/`Theme` validation edge cases, `ThemeRegistry` duplicate/not-found handling, or the built-in catalog's internal consistency — which is precisely the kind of gap that let finding #4 above go unnoticed.

### 6. Flat, un-prefixed tool-window ID namespace shared between built-in and any future plugin-contributed windows — LOW, not a confirmed bug — **[confirmed as a design characteristic, not a defect: a colliding ID fails closed with `ToolWindowAlreadyRegisteredError` rather than silently overwriting]**
`src/opencobol2/tool_windows/registry.py`

Noted only because it was explicitly asked about; the registry already handles a collision safely.

**Checked and found correct:** status bar item ordering (stable sort by `order` within alignment group, ties preserve registration order) is deterministic and matches its tests; every built-in `ToolWindowDefinition`'s `default_area` is validated to be within its own `allowed_areas` at construction time (so a violating built-in couldn't even be registered); `ThemeColors` validates all 16 declared color fields with no way for an empty/missing value to slip through; `ThemeService`/`ThemeRegistry` fail cleanly (typed `ThemeNotFoundError`, no partial state) on an unknown theme ID; `normalize_tool_window_accent_color` correctly requires `#` + exactly 6 hex digits, case-insensitive in, uppercase out, with 3-digit shorthand deliberately rejected; no mutable shared defaults found anywhere across these four subsystems; `AccessibilityService` validates every override in a profile before applying any of them (no partial application on a later error).

---

## Cross-cutting observations (Phase 1)

- **Error-handling asymmetry across subsystems.** The codebase already has an established, good pattern for "a downstream failure shouldn't crash the whole bootstrap" (Git-repository discovery in `application.py` explicitly catches and degrades). That pattern was not applied consistently to: settings load at startup, dynamic menu provider resolution, or status bar item refresh — all three currently let one failure take down something much larger than the thing that actually failed. **Resolved** — all three now follow the same isolate-and-degrade pattern (Settings §1, Commands §1, Status Bar §1).
- **The `"--"` argument-separator convention in `GitService` is inconsistently applied** — present for every branch/tag/remote/sync command, absent for reset/history/revert/cherry-pick/diff. Worth a single sweep to apply it everywhere ref-like user input reaches a git command line, rather than fixing each call site ad hoc. **Resolved** — Git §2's fix applied the equivalent protection (leading-dash rejection at the shared validator, plus a trailing `--` at each call site) across all five previously-missing commands in one sweep, exactly as suggested here.
- **Encoding is the most under-tested dimension in this phase.** Both the Git process runner and the document storage layer make encoding assumptions with no non-ASCII test coverage anywhere in Phase 1, and both would reportedly fail (crash or corrupt) on legacy 8-bit COBOL source or non-ASCII paths/messages. **Resolved** — Git §4 pinned `encoding="utf-8"` on the process runner, and Documents §1 turned the document-storage decode failure into a caught, user-visible error instead of an uncaught crash; both now have regression tests exercising the previously-uncovered non-ASCII/wrong-encoding path.

---

# Phase 2 — Project System

Scope: `src/opencobol2/project/models.py`, `storage.py`, `service.py`, `process.py`, plus `src/opencobol2/services/project.py` (`ProjectTaskRunnerService` — where the task/launch-config execution logic actually lives; pulled in during review since it's the real implementation of behavior the roadmap attributes to this phase). GUI rendering (`ProjectExplorerWidget`, `ProjectPropertiesDialog`, `project_commands.py`) is Phase 7 and excluded, consistent with the Phase 1 pass above.

## Priority items (highest impact across Phase 2)

1. **Windows drive-relative paths (e.g. `"E:payload/nc.exe"`) bypass the project-confinement validator and can point a task/launch configuration at an arbitrary location outside the project entirely** — §1 below. Found independently by both review passes (once as a validation gap, once as a live exploitation path through the task runner), and independently re-verified directly.
2. **A project file with invalid/truncated UTF-8 crashes with a raw `UnicodeDecodeError` instead of the documented `ProjectFormatError`** — §2 below.
3. **A project can be saved with a `schema_version` its own loader immediately rejects** — §3 below.
4. **Deeply nested virtual folders crash the loader with a bare `RecursionError`** instead of a clean format error — §4 below.

## 1. Windows drive-relative paths escape project confinement — HIGH — **[verified]**

`src/opencobol2/project/models.py:900-929` (`_require_relative_project_path`)

The validator rejects a path only if `Path(value).is_absolute()` or the raw string starts with `"/"`/`"\\"`. A Windows drive-relative string — a drive letter with no root, e.g. `"E:payload/nc.exe"` or `"C:secretdir"` — satisfies neither check: `PureWindowsPath` requires *both* a drive and a root for `is_absolute()` to be `True`, so a drive-only string returns `False`, and it obviously doesn't start with a slash. Directly verified:
```python
>>> Path("E:payload/nc.exe").is_absolute()
False
>>> Path("E:payload/nc.exe").parts
('E:', 'payload', 'nc.exe')          # no ".." present either, so the traversal check also passes
>>> Path("C:/Users/proj/MyCobolApp") / "E:payload/nc.exe"
WindowsPath('E:payload/nc.exe')       # the project root is discarded entirely
```
This affects every field validated by this function: `VirtualFolder.member_paths`, `ProjectTask.working_directory`, `LaunchConfiguration.executable_path`/`working_directory`, and `ProjectProperties.output_directory`. The second review pass traced this all the way through to live exploitation: constructing a `LaunchConfiguration(executable_path="E:payload/nc.exe", working_directory="E:scratch")` on a project rooted at `C:\Users\proj\MyCobolApp` and running it through `ProjectTaskRunnerService.run_launch_configuration` reportedly produces the spawned command `E:payload\nc.exe` with cwd `E:scratch` — nothing of the project root survives the join. A shared or downloaded project file (or one from source control) can silently point a task or launch configuration at an arbitrary location on another drive, defeating the sandboxing the validator's own docstring claims to provide, on this project's primary target platform.

## 2. Invalid/truncated UTF-8 in a project file crashes ungracefully — HIGH — **[verified]**

`src/opencobol2/project/storage.py:73-82` (`ProjectStorage.load`)

```python
try:
    raw_project = json.loads(self._path.read_text(encoding="utf-8"))
except json.JSONDecodeError as error:
    raise ProjectFormatError(...) from error
```
`read_text(encoding="utf-8")` is inside the `try`, but a decode failure raises `UnicodeDecodeError`, which is not a subclass of `json.JSONDecodeError` — confirmed directly by reading the exception hierarchy and the exact except clause. A project file with a single invalid UTF-8 byte (truncated mid multi-byte character, wrong-encoding save from another tool, disk corruption) propagates a raw `UnicodeDecodeError` instead of the documented `ProjectFormatError`, contrary to the "clear error for malformed project files" behavior every other decode error in this same function correctly provides.

## 3. A project can be saved in a schema version its own loader rejects — MEDIUM — **[confirmed]**

`src/opencobol2/project/storage.py:88-126` (`save`), cross-referenced against `Project.__post_init__`

`Project.__post_init__` only requires `schema_version > 0` — any positive integer — not that it equals `CURRENT_PROJECT_SCHEMA_VERSION`. `save()` writes `project.schema_version` verbatim with no normalization. Reported as directly reproduced: constructing a `Project(schema_version=2, ...)` and saving it succeeds silently, but loading it immediately back raises `UnsupportedProjectVersionError`. Nothing in the current call graph constructs a non-default `schema_version` today, so this isn't live yet, but there's no guard preventing a future migration/versioning code path from doing so and producing a file that can never be reopened.

## 4. Deeply nested virtual folders crash the loader with a bare `RecursionError` — MEDIUM/LOW — **[reported as directly reproduced with a ~2000-level-deep nested structure]**

`src/opencobol2/project/storage.py:473-530` (`_decode_virtual_folder`), `src/opencobol2/project/models.py:836-873` (`_collect_virtual_folder_ids`, `_collect_referenced_linked_file_ids`)

`RecursionError` is a `RuntimeError`, not caught by `_decode_project`'s `except (TypeError, ValueError)` clause, so an unusually deep (but not otherwise invalid) nested `virtual_folders` structure crashes with a bare interpreter recursion error rather than a clean `ProjectFormatError`. Requires a pathologically deep tree to trigger in practice.

## 5. Environment-variable override keys are case-sensitive, on a platform where env vars are not — MEDIUM — **[confirmed at the model layer; the merge-layer consequence was empirically tested and found not to break precedence today, but relies on incidental behavior]**

`src/opencobol2/project/models.py:984-1019` (`_require_string_mapping`) validates only type, never case-insensitive key uniqueness — confirmed that `ProjectTask(..., environment_overrides={'PATH': 'a', 'Path': 'b'})` is accepted, both within one override map and across the project/task/launch-config layers. The actual merge (`_merge_environment` in `src/opencobol2/services/project.py:140-156`) starts from `dict(os.environ)` and applies plain `dict.update()` calls per layer — since a plain `dict` is case-sensitive but Windows environment variables are not, a project-level `PATH` and a task-level `Path` become two distinct dict keys handed to `subprocess.run(env=...)` rather than one cleanly overriding the other. The second review pass empirically ran this through a real `subprocess.run`/`CreateProcess` call and found the later-inserted key happened to win — so precedence isn't demonstrably broken today — but the result relies on incidental dict-insertion-order behavior rather than an explicit case-fold merge, and an easy real-world typo (setting `PATH` at one layer, `Path` at another) produces an ambiguous, unvalidated result either way.

## 6. Task/launch-config names are not required to be unique — LOW/MEDIUM — **[confirmed]**

`src/opencobol2/project/models.py:665-726` (`Project.__post_init__`)

Only `task_id`/`launch_configuration_id` (UUIDs) are checked for uniqueness; two `ProjectTask`/`LaunchConfiguration` entries with the identical `name` are accepted into the same project. `get_task`/`get_launch_configuration` only look up by ID today so nothing breaks immediately in the reviewed files, but any future name-based lookup or display (the natural GUI presentation) would be ambiguous with no domain-level guard against it.

## 7. `run_id` is a static identifier, not a per-invocation one — MEDIUM — **[confirmed]**

`src/opencobol2/services/project.py:69-84`, `:108-125`

`run_id` is passed through as the task's/launch-config's own permanent UUID, not a fresh identifier minted per run. `ProjectTaskRunnerService` is a stateless frozen dataclass with no run registry or lock, so nothing distinguishes or prevents two concurrent invocations of the same task — both would report the identical `run_id`, making them indistinguishable to any caller that correlates output or attempts cancellation by that value. No test exercises concurrent invocation.

## 8. Process timeout only kills the direct child, not any grandchildren it spawns — MEDIUM — **[plausible, unconfirmed]**

`src/opencobol2/project/process.py:86-118`

`subprocess.run(..., timeout=timeout_seconds)` relies on CPython's default kill-on-timeout, which terminates only the immediate child process, not any process that child itself spawned (a realistic case for a COBOL toolchain driver invoking a separate linker/backend compiler). No `CREATE_NEW_PROCESS_GROUP`/job-object-based tree-kill is used. Not demonstrated live (would require a real multi-process COBOL build chain to construct), but a well-documented general limitation of this exact subprocess/timeout pattern with no mitigation here.

## 9. Batch-capture execution model has no stdin and cannot stream output, silently misclassifying an interactively-blocked program as a timeout — MEDIUM — **[confirmed by reading the execution model; not run against a real interactive COBOL program]**

`src/opencobol2/project/process.py:87-96`

`capture_output=True` redirects stdout/stderr to pipes with nothing feeding stdin and no incremental output capture. A launch configuration running a program that does `ACCEPT ... FROM CONSOLE` would block indefinitely with no visible output until the fixed service-wide timeout (300s) force-kills it and reports `TIMED_OUT` — indistinguishable from a genuinely slow task. The timeout is also a single non-overridable value for the whole service, not per task/launch config. May be an intentional scope cut if interactive runs are meant to go through the Terminal panel or debugger instead (both out of scope here), but "Launch configurations (directly executable...)" is exactly the roadmap line this file implements, so it's worth flagging explicitly.

## 10. `Project.root_path` is never required to be absolute — LOW — **[confirmed as a validation gap; downstream impact not verified since resolution happens in the out-of-scope-for-this-file service layer]**

`src/opencobol2/project/models.py:557-566`

Nothing in `Project.__post_init__` rejects a relative or drive-less root — and the test suite's own `_project()` test helper already uses a rootless path (`"/source/payroll"`, which is not absolute in `PureWindowsPath` terms) as its "valid" baseline. Relative fields joined against a non-absolute root can resolve against the process's current directory rather than a fixed location.

## 11. No test exercises a real subprocess for task/launch-config execution — LOW — **[confirmed by reading the test files: every test mocks `subprocess.run`/`invoke_task_process`]**

`tests/unit/test_project_process.py`, `tests/unit/test_project_task_runner.py`

Large-output draining without deadlock, a real timeout actually killing a real process, and the `FAILED_TO_START` paths (missing executable, nonexistent working directory) are all untested by the suite itself, though the reviewing pass manually verified the real behavior is currently correct for the missing-executable and bad-cwd cases.

**Checked and found correct:** the atomic-write convention (temp file in the same directory, `flush()` + `fsync()`, then `os.replace()`, `encoding="utf-8"` pinned on both read and write) is correctly followed and matches every other storage layer in this codebase; `default_launch_configuration_id` is correctly cross-validated against the live `launch_configurations` list at every construction, including load time — a project file referencing a deleted launch configuration is correctly rejected rather than silently loading broken; non-string values in `environment_overrides` are correctly rejected everywhere, not silently coerced; no mutable-default-argument bugs found anywhere in the model (all dict fields use `field(default_factory=dict)`, tuple defaults are the immutable `()`); the "layered environment resolution" precedence itself (OS environment < project-level overrides < task/launch-config-level overrides) is implemented correctly — later layers do override earlier ones, aside from the case-sensitivity caveat in finding #5.

## Cross-cutting observations (Phase 2)

- **The same path-confinement validator gap (drive-relative Windows paths) was independently rediscovered by two separate review passes** — once purely by reading the validation logic, once by tracing a live exploitation path through the task runner. That's a strong signal this is a real, structural gap rather than a one-off misreading, and that the fix belongs in the shared validator (`_require_relative_project_path`) rather than at each call site.
- **Error-handling asymmetry echoes the Phase 1 finding**: `ProjectStorage.load()` correctly wraps `json.JSONDecodeError` into a domain-specific exception but misses the (arguably more likely in practice) `UnicodeDecodeError` case — the same "one path handled, a sibling path forgotten" pattern seen in Phase 1's settings/documents loaders.
- **Concurrency and process-tree lifecycle are under-designed for a task runner**: no per-invocation run identity, no protection against double-starting the same task, and no tree-kill on timeout. None of this is exercised by tests, which exclusively mock the subprocess layer.

---

# Phase 3 — Editor

Scope: `src/opencobol2/gui/editor.py` (`SourceEditorWidget`/`EditorTabsWidget` — the single file implementing almost all of Phase 3), plus its satellite files `syntax_highlighter.py`, `coding_area_guides.py`, `bookmarks_panel.py`, and `breakpoints_panel.py`. This phase is genuine Qt/GUI code (unlike Phases 1–2's Qt-independent domain layers), so most findings here are Qt-specific interaction bugs rather than pure logic errors. Split editors, multiple cursors, and column selection are explicitly unimplemented per the roadmap and are not findings. Document-core-level encoding/BOM/CRLF handling was already reviewed under Phase 1.

## Priority items (highest impact across Phase 3)

1. **A bookmark or breakpoint is silently and permanently lost if its line is deleted and the deletion is then undone** — §1 below.
2. **Printing completely ignores code folding — collapsed/hidden content is printed in full anyway, with no visual indication to the user** — §2 below.
3. **A tab character earlier in a line shifts every subsequent syntax-highlight/diagnostic-underline position, coloring the wrong substring** — §4 below.
4. **Editing one line can leave a different, untouched line's syntax highlighting stale** (specifically around continuation string literals) — §5 below.
5. **Fold ranges go stale on any same-line-count edit, so an unrelated fold toggle can hide/reveal the wrong lines** — §3 below.

## 1. Bookmark/breakpoint lost forever if its line is deleted and the delete is undone — HIGH — **[verified]**

`src/opencobol2/gui/editor.py:1251-1305` (`toggle_bookmark_at_cursor`/`_prune_invalid_bookmarks`), `:1307-1363` (the breakpoint mirror)

Bookmarks/breakpoints are tracked via live `QTextBlock` handles specifically so they survive edits *elsewhere* in the document — this is a deliberate, previously-established pattern in this codebase for exactly this staleness problem. But when the underlying block is actually deleted (not just shifted), `block.isValid()` becomes `False` and the entry is pruned. Pressing Undo afterward restores the visible text exactly, but Qt's undo re-inserts new document content rather than reviving the original `QTextBlock` object — so the marker never reappears even though the text is back to identical. Reported as directly reproduced: bookmark line 2 of a 3-line document, delete that entire line, undo — text is restored byte-for-byte but `editor.bookmarked_lines == ()`; identical result for breakpoints. Concrete trigger: bookmark/breakpoint a line, delete the whole line (select + Delete, or Backspace across it), then Ctrl+Z. The marker is gone with no further action and no UI indication it was lost.

## 2. Printing ignores code folding entirely — HIGH — **[reported as empirically verified via real PDF generation: a document with 500 lines folded away printed a PDF byte-for-byte identical in size (467,150 bytes) to the same 500 lines fully visible, versus 3,395 bytes for a genuinely 3-line document]**

`src/opencobol2/gui/editor.py:2606-2623` (`EditorTabsWidget.print_active_tab`, delegating straight to `QPlainTextEdit.print_()`) vs. `:1943-1976` (`_hide_range`/`_show_range`, which hide folded content only via `QTextBlock.setVisible(False)`)

`QPlainTextEdit.print_()` uses the standard document print/layout path, which doesn't consult per-block visibility — that flag only affects the editing widget's own on-screen viewport layout, not printing. Concrete trigger: collapse a large section to keep the visible file short on screen, then File > Print — the printed output silently includes every folded-away line, potentially producing far more pages than what's visible on screen suggests, with nothing telling the user this happened.

## 3. Fold ranges go stale on any edit that doesn't change the line count — MEDIUM — **[reported as directly reproduced]**

`src/opencobol2/gui/editor.py:504-506` (fold-range recompute wired only to `blockCountChanged`), `:2011-2035` (`_update_fold_ranges`), consumed by `toggle_fold` (`:1876-1898`)

Fold ranges only recompute when the document's block (line) count changes. An in-place edit that keeps the same number of lines — e.g. overwriting `IF 1 > 0` with `DISPLAY 1` on the same physical line — leaves the old fold range untouched. Reported as directly reproduced: replacing an `IF` line's text in-place with a `DISPLAY` statement (same line count) leaves the stale `(5, 7)` fold range intact; calling `toggle_fold(5)` afterward still collapses the lines that used to be that `IF`'s body, even though line 5 is no longer an `IF` at all. Concrete trigger: with folding enabled, edit the text of a fold-start or fold-body line without adding/removing a newline, then click the now-stale gutter fold marker.

## 4. Tab characters corrupt syntax-highlight and diagnostic-underline positions — HIGH — **[verified]**

`src/opencobol2/gui/syntax_highlighter.py:141-173` (`highlightBlock`), root cause traced to `src/opencobol2/language/lexer.py:315` (`raw_line.expandtabs(...)`)

The lexer computes every token's/diagnostic's `column` against a tab-*expanded* copy of each line, but the highlighter feeds `self.document().toPlainText()` — the raw, un-expanded Qt document text — into the lexer, then applies the resulting (tab-expanded) column offsets directly against that same raw text via `setFormat(token.span.start.column - 1, len(token.text), format_)`. Confirmed by reading both sides of this mismatch directly: whenever a line contains a tab character before a token, every subsequent token's highlight lands shifted from where the real text actually is. The reviewing pass additionally confirmed this concretely: for source `"\tMOVE A TO B."`, the lexer reports `MOVE` at column 9 (post-tab-expansion), but rendered through the real highlighter this colors the substrings `"TO"` and `" B"` in keyword-blue while `MOVE` itself gets no highlight at all. `SourceEditorWidget` doesn't override tab handling, so pressing Tab inserts a literal `\t` — trivially reachable by any user who indents with Tab rather than spaces.

## 5. An edit on one line can leave a different, untouched line's highlighting stale — HIGH — **[reported as directly reproduced via a scripted repro comparing the highlighter's own retokenized ground truth against its actually-rendered formatting]**

`src/opencobol2/gui/syntax_highlighter.py:141-173` (`highlightBlock`/`_retokenize`)

The highlighter never uses Qt's `setCurrentBlockState`/`previousBlockState` cascade and never calls `self.rehighlight()` after re-tokenizing, relying entirely on Qt's own per-block dirty tracking — which only re-invokes `highlightBlock` for the block whose own text actually changed. For genuinely cross-line constructs (a COBOL continuation string literal spanning two lines), editing line *N* can change what tokens line *N+1* should have — but if line *N+1*'s own text wasn't touched, Qt never calls `highlightBlock` for it, so it keeps its old (now-wrong) formatting. Reported as directly reproduced: a continuation literal spanning lines 0–1 (both correctly left uncolored per the documented cross-line skip), then appending a single `'` to line 0 only. The highlighter's own retokenized ground truth now shows line 1 has become a complete, single-line string literal that should be colored — but the actually-rendered format on that block remains empty, because Qt never re-invoked `highlightBlock` for it. The string literal stays invisible until the user separately edits that exact line.

## 6. Minimap's "visible viewport" indicator is badly wrong once folds hide content spanning the on-screen view — MEDIUM — **[reported as directly reproduced: correct indicator height should be ~398px (nearly the full minimap), computed value was ~21px — roughly 20x too small]**

`src/opencobol2/gui/editor.py:1734-1815` (`paint_minimap`), `:1858-1874` (`_visible_line_count`)

The viewport indicator's height is computed as `_visible_line_count() * line_height`, where `_visible_line_count()` counts on-screen *rendered rows* but `line_height` means "minimap pixels per document *block index*." When folding hides a large span, many rendered rows correspond to widely separated block indices, so these two notions of "line" diverge sharply — a viewport that's actually showing content from block 0 through block 500 (because folding lets the first and last visible chunks appear together on one screen) gets represented as a tiny sliver near the top of the minimap instead of the nearly-full-height band it should be.

## 7. `is_cobol_source`/highlighter/folding are frozen at tab-creation time and never re-evaluated after Save As changes the file extension — MEDIUM — **[reported as directly reproduced]**

`src/opencobol2/gui/editor.py:465-476` (`SourceEditorWidget.__init__`, sets `is_cobol_source`/`_highlighter` once from the initial path) vs. `:2929-2978` (`EditorTabsWidget._save_tab_as`, changes the on-disk path via `save_document_as` without touching either)

Reported as directly reproduced: opening a `.txt` file (COBOL support off) and then Save-As-ing it to `main.cbl` leaves `is_cobol_source` still `False` and `_highlighter` still `None` — no syntax highlighting, hover, diagnostics, quick fixes, or folding ever activate for that tab, even though freshly opening `main.cbl` directly would enable all of them. The reviewing pass also noted the logical reverse (`.cbl` renamed to `.txt` via Save As) would by the same code path incorrectly *keep* COBOL-specific behavior active on a file the app would otherwise treat as plain text. Concrete trigger: File > Open a non-COBOL file, edit it, then File > Save As choosing a `.cbl`/`.cob` name — the tab never gains COBOL support until closed and reopened.

## 8. Coding-area column guides desync once a line word-wraps — MEDIUM/HIGH — **[reported as directly reproduced via a rendering script: a single logical line spanning 4 visual rows in a narrow viewport had its column-73 guide line correctly aligned only for the first visual row]**

`src/opencobol2/gui/coding_area_guides.py:89-150` (`paint`), `:207-242` (`_draw_boundary_line_at`/`_x_for_column`)

Guides are painted as static vertical lines spanning the full viewport height, computed purely from `margin + (column-1)*char_width` — implicitly assuming every visual row begins at logical column 1 of its own line. `SourceEditorWidget` never sets `setLineWrapMode(NoWrap)`, so it keeps Qt's default word-wrap behavior; any fixed-format line wider than the current viewport width wraps into multiple visual rows, and the guide lines (correctly placed for the row starting at column 1) become meaningless for the wrapped continuation rows. Reachable any time the editor pane is narrower than an 80-column line — a resized window or an open side panel, not a contrived scenario. (Column-boundary math itself was checked against the lexer's own `FIXED_FORMAT_*` constants and is exactly correct — this is purely a wrap-interaction bug, not an off-by-one.)

## 9. Bookmarks/Breakpoints panels keep stale rows after their tab closes, and double-clicking one silently does nothing — MEDIUM — **[confirmed by reading the missing signal wiring]**

`src/opencobol2/gui/editor.py:2980-3030` (`_close_tab`, never emits `bookmarks_changed`/`breakpoints_changed`) and `application.py:1070-1092` (panels only refresh on those two signals, which fire on toggle, not on tab close); `_reveal_document_location` (`editor.py:2838-2859`) silently returns when the target tab can no longer be found.

Concrete trigger: bookmark or breakpoint a line, close that tab with no unsaved changes — the row keeps showing in the panel with the old file name until an unrelated bookmark/breakpoint toggle anywhere happens to trigger a refresh. Double-clicking the stale row calls through to `_reveal_document_location`, which finds no matching tab and quietly does nothing — no crash, but no feedback either.

## 10. Continuation (multi-line) string literals are entirely uncolored, and untested — LOW — **[confirmed as a documented, deliberate choice, not a coloring-corruption bug — flagged for the coverage gap, not the behavior itself]**

`src/opencobol2/gui/syntax_highlighter.py:248-263`

Correctly documented as "skip rather than highlight incorrectly" for a literal spanning two physical lines — but the practical result is such a literal is invisible to the string-color theme on both of its lines, which a user could easily mistake for broken highlighting. `tests/unit/test_gui_syntax_highlighter.py` has no test exercising a continuation literal at all.

## 11. No dedicated unit test file for `BreakpointsWidget` — LOW — **[verified: `test_gui_bookmarks_panel.py` exists, `test_gui_breakpoints_panel.py` does not]**

`BreakpointsWidget` is exercised only indirectly at the integration level via `tests/unit/test_gui_application.py`; there's no isolated widget-level test mirroring `test_gui_bookmarks_panel.py`'s direct coverage of e.g. `clear_breakpoints()` or the out-of-range double-click guard, specifically for the breakpoints panel.

**Checked and found correct:** the current-line highlight is the only consumer of `setExtraSelections`, so it never conflicts with find/replace match highlighting (a separate render path); nested collapsed-fold state correctly survives its parent being expanded, traced through 2- and 3-level nesting (the roadmap's claim here holds up against the actual implementation, not just the comment describing it); gutter width genuinely resizes the widget geometry as digit count grows (9→10, 99→100 lines), not just an internal computed value; `replace_all` correctly handles overlapping-pattern searches (e.g. `"aa"` in `"aaaa"`) and empty-replacement deletions with no infinite loop or double-counting; find wraparound is correctly bounded when the search term is absent; `CobolSyntaxHighlighter.apply_theme()` correctly forces a full re-highlight on a theme switch (independent of, and not affected by, finding #5); `bookmarks_panel.py` and `breakpoints_panel.py` are byte-for-byte structurally identical apart from expected renames — no accidental divergence between the two; the `FIXED_FORMAT_*` column constants used by the coding-area guides exactly match the lexer's own constants.

## Cross-cutting observations (Phase 3)

- **The "track state via a live `QTextBlock` handle instead of a plain line number" pattern — this codebase's own established fix for a prior staleness bug — has a real gap of its own**: it survives a block being *shifted*, but not a block being *deleted-then-undone*, since Qt's undo re-inserts new blocks rather than reviving the old object reference. Worth revisiting as a shared concern, since bookmarks and breakpoints both inherit it identically, and any future Phase 3 feature built on the same pattern would too.
- **Two independent, unrelated features (printing, coding-area guides) both silently assume "one visual row == one logical line starting at column 1,"** and both break for the same underlying reason: this editor doesn't force `NoWrap`, and folding/printing/guide-painting code was written as if wrapping and folding-driven visibility never interact with layout. A single design decision (either force `NoWrap`, or make all of these features properly folding/wrap-aware) would resolve several independent findings at once.
- **The syntax highlighter's fundamental structural gap — no cross-block state cascade (`setCurrentBlockState`/`previousBlockState`) and no `rehighlight()` after re-tokenizing** — is the root cause of both the tab-corruption finding and the stale-cross-line-highlighting finding. These read as two symptoms of one missing piece of Qt `QSyntaxHighlighter` plumbing, not two unrelated bugs.

---

# Phase 4 — COBOL Language Services

Scope: the Qt-independent analysis pipeline — `src/opencobol2/language/lexer.py`, `tokens.py`, `parser.py`, `ast_nodes.py`, `semantic.py`, `keywords.py` — and everything editor-facing built on top of it: `navigation.py`, `hover.py`, `outline.py`, `folding.py`, `rendering.py`, `diagnostics.py`, `source_diagnostics.py`, `quick_fixes.py`, `signature_help.py`, `task_list.py`. The GUI wiring that consumes these services (rename, the quick-fix context menu, `CobolSyntaxHighlighter`, coding-area guides) was already reviewed under Phase 3. Two AST precision limits are already known and deliberately accepted in this codebase — a data-item "go to definition" lands on its level number rather than its name, and a MOVE-target diagnostic can only point at the statement's start, not a specific target name — neither is repeated below.

## Priority items (highest impact across Phase 4)

1. **`MOVE ... TO field OF group` (qualified data names) produces a false `Undefined data name: OF` ERROR on entirely valid COBOL** — found independently by two separate review passes (once from the parser side, once from the semantic-analysis side) and directly reproduced. §Parser-3 / §Semantic-2 below.
2. **`PERFORM name THRU` with a missing or malformed through-target crashes the parser with an uncaught `ValueError`** — and because `compute_source_diagnostics` (the actual live-editor entry point) has a deliberate blanket `except Exception` at every pipeline stage specifically so a crash "doesn't break the editor," this doesn't surface as a visible error at all: it **silently truncates every diagnostic for the rest of the file** with zero indication anything went wrong. Directly reproduced both ways. §Parser-4 below.
3. **Legitimate paragraph-name reuse across different sections (a common, legal COBOL pattern) produces a false hard "duplicate procedure division name" ERROR** — directly reproduced. §Semantic-1 below.
4. **`EXIT PERFORM` is silently destroyed**: split into a `GenericStatement` for the bare word `EXIT` plus a phantom, empty `PerformStatement` corresponding to no real PERFORM in the source, with zero diagnostics. Directly reproduced. §Parser-1 below.
5. **A free-format line beginning with `*` is unconditionally treated as a full-line comment**, silently swallowing a COBOL statement's continuation onto its own line (e.g. a multiplication split across lines) with zero diagnostics. Directly reproduced. §Lexer-1 below.
6. **Purely-numeric paragraph/section names (`0100.`, `0200.` — a real, historically common mainframe COBOL style) aren't recognized as headers at all**, silently collapsing the entire procedure division into one anonymous paragraph. Reported as directly reproduced. §Parser-2 below.

## Lexer (`lexer.py`, `tokens.py`)

### Lexer-1. Free-format leading-`*` swallows a valid statement continuation as a full-line comment — HIGH — **[verified]**

`src/opencobol2/language/lexer.py:346-350` (free-format branch of `_prepare_lines`): `is_comment = expanded_line.lstrip().startswith("*")` fires for any line whose first non-blank character is `*`, not just the `*>` inline-comment marker free format actually uses. Free-format COBOL lets one statement flow across physical lines with no continuation marker, so a multiplication expression continued onto its own line is misread as a comment.

Directly reproduced:
```cobol
COMPUTE TOTAL = QUANTITY
    * PRICE.
```
tokenizes to `COMPUTE`, `TOTAL`, `=`, `QUANTITY`, then a single `COMMENT` token for `'    * PRICE.'` — the multiply operator, `PRICE`, and the terminating period vanish entirely, with zero diagnostics raised.

### Lexer-2. Tab expansion used for column math doesn't match the raw character offsets several consumers assume — HIGH — **[verified the lexer/highlighter half directly under Phase 3; the quick-fix half is independently reconfirmed below under Editor-Facing-2]**

`lexer.py:315` tab-expands each line (`expandtabs(8)`) before computing any token/diagnostic column, but multiple downstream consumers (the syntax highlighter, Quick Fix position math, `go_to_line`) treat that column as a literal character-offset move into the real, un-expanded Qt document text. Any line with a real tab before a token is off by the tab's expansion width. See the Phase 3 tracker section for the syntax-highlighter half of this (already recorded there as a Phase 3 finding); see Editor-Facing-2 below for the Quick Fix half, newly found in this pass.

### Lexer-3. A comment line interrupting a continued string literal is treated as fatal termination rather than transparently skipped — MEDIUM — **[confirmed by reading the exact branch condition; COBOL-standard conformance of the trigger itself is unconfirmed]**

`lexer.py:173-196`: whenever a literal is still pending and the current line is classified as a comment, the lexer unconditionally emits an "not terminated" ERROR and abandons the literal, even when the very next physical line is a valid `-` continuation of it.

```cobol
       01  X VALUE 'THIS IS A VERY LONG MESS
      * a note
      -    'AGE THAT CONTINUES'.
```
produces an ERROR, an unrelated WARNING ("Continuation line found without a literal to continue"), and a spurious extra literal token parsed as fresh code on the continuation line — none of which reflects the source's evident intent.

### Lexer-4. Unterminated/comment-interrupted literal tokens always get a zero-length span regardless of their actual text length — MEDIUM — **[confirmed]**

`lexer.py:409-429` (`_finalize_pending_literal`): `span=SourceSpan(start=pending_literal.start_position, end=pending_literal.start_position)` — start and end are identical no matter how long the literal's text is. Any consumer that highlights or selects by span (the diagnostic underline, a hypothetical better Quick Fix) gets a range covering nothing rather than the literal's actual extent.

### Lexer-5. `D`/`d`-indicator (WITH DEBUGGING MODE) lines are unconditionally lexed as live code, and the indicator is discarded before reaching any `Token` — MEDIUM — **[confirmed]**

`lexer.py:34-42`: a `D` in the indicator column is treated exactly like a blank indicator, and `_PreparedLine.indicator` never survives into a `Token`. Per the COBOL standard, a D-line only compiles when `WITH DEBUGGING MODE` is declared; otherwise a real compiler excludes it like a comment. Since no later stage can recover the indicator, a debug-only line referencing a variable that doesn't otherwise exist produces a false "undefined identifier" diagnostic on source a real compiler would never even see.

### Lexer-6. Decimal numeric-literal values are parsed with `float()`, losing precision for realistic COBOL fixed-point magnitudes — MEDIUM — **[verified]**

`lexer.py:876-880`: `value=float(full_text)`. Confirmed: `float("123456789012345678.99")` loses both the fractional part and low-order integer digits (`Decimal(f) == 123456789012345680`) — the token's parsed `.value` diverges from what's actually written for any currency/fixed-point literal at realistic COBOL magnitudes (e.g. `PIC 9(15)V99`). `decimal.Decimal` would avoid this; nothing currently appears to consume `token.value` for this purpose, but it's a latent trap for any future feature that does (e.g. a hover showing a literal's parsed value).

### Lexer-7. `END_OF_FILE` token position can precede real tokens on the same line when the source has no trailing newline — LOW/MEDIUM — **[verified]**

`lexer.py:256-261` computes the EOF line via `self._source.count("\n") + 1`, while every real token's line comes from `str.splitlines()` — these disagree whenever the source has no trailing newline (or uses a line separator `splitlines()` recognizes but bare `\n`-counting doesn't). Confirmed: for `"...DISPLAY 'HI'.\n       STOP RUN."` (no final newline), real tokens on the last line sit at columns 8/13/16, but `END_OF_FILE` is placed at column 1 — before them, breaking the general expectation that EOF is the stream's last/highest position.

### Lexer-8. Signed numeric literals (`+123`, `-45.6`) are never merged into one token, and the behavior is completely untested — LOW

`_ONE_CHARACTER_OPERATORS` always splits a leading `+`/`-` into its own token before digits are scanned. Plausibly intentional (sign vs. subtraction is genuinely context-dependent and reasonably left to the parser), but zero test coverage exists either way, so it's unverified as "intended" vs. "missed."

## Parser / AST (`parser.py`, `ast_nodes.py`)

### Parser-1. `EXIT PERFORM` is silently destroyed into an orphaned `GenericStatement` plus a phantom, empty `PerformStatement` — HIGH — **[verified]**

`_parse_generic_statement`'s operand loop stops the instant it sees any token that's a member of `STATEMENT_VERBS` — but `PERFORM` is itself in that set, so `EXIT`'s own required keyword operand is mistaken for the start of a brand-new statement.

Directly reproduced:
```cobol
           PERFORM UNTIL WS-DONE
               IF WS-FLAG = 1
                   EXIT PERFORM
               END-IF
               DISPLAY WS-FLAG
           END-PERFORM
```
`then_statements` becomes `(GenericStatement(verb='EXIT', tokens=('EXIT',)), PerformStatement(target_name=None, through_name=None, modifier_tokens=(), body=()))`, with zero diagnostics. The word "PERFORM" is preserved nowhere, and a fictitious empty-loop node appears in the tree at that source position — any hover/semantic/folding feature keyed off it would describe a loop that doesn't exist. Zero test coverage for `EXIT` at all.

### Parser-2. Purely-numeric paragraph/section names aren't recognized as headers, collapsing the whole procedure division into one anonymous paragraph — HIGH — **[reported as directly reproduced]**

`_word()` returns `""` for a `NUMERIC_LITERAL` token, and header detection depends on `_word()` being truthy — so a bare-numeric paragraph label (`0100.`, a real, historically common IBM-mainframe COBOL numbering convention) is invisible to it.

```cobol
       0100.
           PERFORM 0200
           STOP RUN.
       0200.
           DISPLAY 'IN 0200'.
```
reportedly produces two misleading "Expected a statement, found '0100'"/"'0200'" diagnostics and silently merges both paragraphs into a single anonymous leading paragraph — the paragraph names are lost entirely, and `PERFORM 0200` then also fails semantic resolution since no paragraph named "0200" exists in the collapsed tree. Any file using this real, legal numbering style loses its entire procedure-division structure at once.

### Parser-3. Qualified MOVE targets (`MOVE x TO field OF group`) inject the qualifier keyword itself as a bogus target name — HIGH — **[verified — found independently by both the parser review and the semantic-analysis review; see Semantic-2 for the semantic-analysis-side confirmation of the same root cause]**

`_parse_move`'s target-collection loop appends every token whose kind is `IDENTIFIER` or `RESERVED_WORD` into `target_names`, with no exclusion for the `OF`/`IN` qualifier keyword — so `MOVE 'X' TO CUSTOMER-NAME OF CUSTOMER-REC.` produces `target_names == ('CUSTOMER-NAME', 'OF', 'CUSTOMER-REC')`. Directly reproduced end-to-end through `analyze_compilation_unit`: this yields a false `Undefined data name: OF` ERROR on completely valid, qualified COBOL — exactly the construct qualification exists to support. The analogous `PERFORM target OF/IN section` case leaks the qualifier into `modifier_tokens` too, producing a lower-severity but still-spurious WARNING instead of an ERROR (see Semantic-6).

### Parser-4. `PERFORM ... THRU` with a missing/malformed through-target crashes the parser, and — via `compute_source_diagnostics`'s deliberate crash-swallowing — silently truncates all diagnostics for the rest of the file — HIGH — **[verified, both the crash and its downstream silent-swallowing interaction]**

`parser.py` (the THRU/THROUGH branch of `_parse_perform`) unconditionally consumes whatever token follows `THRU` with no guard, unlike the equivalent, correctly-guarded handling elsewhere in the file (e.g. PROGRAM-ID). Directly reproduced two ways:
- Source ending right after `PERFORM PARA-A THRU` (nothing before EOF): `through_name` becomes the empty string from the EOF token, and `PerformStatement.__post_init__`'s own non-empty-string validation raises `ValueError: Perform statement through name must not be empty.` — confirmed to propagate all the way out of `parse_cobol_tokens()` uncaught.
- `PERFORM PARA-A THRU.` (period immediately after THRU): the terminating period is silently consumed as if it were the through-name text, producing `PerformStatement(..., through_name='.')` with zero diagnostics and the real statement terminator gone from the token stream.

Critically, I traced this further myself: `compute_source_diagnostics` (`source_diagnostics.py`, the actual function the live editor's Problems panel and diagnostic underlines are built on) wraps every pipeline stage in a bare `except Exception: return tuple(diagnostics)` specifically so "a crash at any stage just truncates the diagnostic list there rather than breaking the editor" (its own docstring). Confirmed by direct execution: calling `compute_source_diagnostics` on the crash-triggering source above returns `()` — not an error, not a partial diagnostic list, nothing. The parser crash is real, but its actual live-editor consequence is worse than a visible crash: every diagnostic for the rest of the file silently disappears, with no signal to the user that anything went wrong, the moment they type an entirely ordinary, momentary mid-edit state (`PERFORM x THRU` before finishing the through-target name).

### Parser-5. Long sequential `IF ... ELSE IF ...` chains can exceed Python's recursion limit and crash with `RecursionError` — MEDIUM — **[verified: confirmed 300 links parses fine, 350 links raises under the default recursion limit]**

`_parse_if` recurses through the statement-list parser for each `ELSE IF` link with no iterative rewrite and no depth guard. A 300–400-branch sequential code/state dispatch chain is a realistic size for long-maintained or generated legacy COBOL (product/state/tax-code tables), not an adversarial input.

### Parser-6. The synthetic "leading unnamed paragraph"'s span wrongly starts at the enclosing division/section header, not its own first statement — MEDIUM — **[verified]**

Both the procedure-division and procedure-section leading-paragraph construction capture their span's `start` from the position at the very beginning of the enclosing parse function (the `PROCEDURE`/section-name token) rather than the first leading statement. Confirmed: for a two-statement leading paragraph, `paragraphs[0].span` is byte-for-byte identical to the whole `procedure.span`, meaning any "select this node's text"/fold-this-paragraph feature would wrongly include the literal `PROCEDURE DIVISION.` header text.

### Parser-7. The obsolete `STOP literal` form is silently reclassified as an ordinary `StopRunStatement` with the literal discarded — LOW/MEDIUM — **[verified as currently latent — no consumer distinguishes the two today]**

`_parse_stop_run` enters unconditionally on the verb `STOP` and only optionally consumes `RUN`; any trailing operand is swallowed and discarded by the residual-consumption loop. `STOP 'OPERATOR HALT'.` parses with zero diagnostics into a plain `StopRunStatement`, indistinguishable from a real `STOP RUN` — currently harmless since nothing treats `StopRunStatement` specially yet, but a real gap for any future "guaranteed program termination"/unreachable-code analysis.

### Parser-8. Duplicate/conflicting data-description clauses on one item (two `PIC`s, two `VALUE`s) are accepted with no diagnostic — LOW — **[confirmed by code inspection of both the parser's clause loop and the debugger's consumer]**

The clause-parsing loop just appends every clause with no uniqueness check; downstream, `debugger/service.py`'s PICTURE/USAGE resolution iterates in order with no `break`, so the *last* duplicate silently wins — deterministic, but silently accepting genuinely invalid COBOL (two `PIC` clauses on one entry) with zero diagnostic at parse time.

## Semantic analysis / keyword table (`semantic.py`, `keywords.py`)

### Semantic-1. False "duplicate procedure division name" for legitimately reused paragraph names across different sections — HIGH — **[verified]**

`_build_procedure_symbols` tracks `seen_names` as one flat set across the *entire* procedure division, with no scoping by enclosing section. COBOL legally allows the same paragraph name in different sections, disambiguated by `PERFORM x IN section-name` — a common legacy pattern (e.g. a `9999-EXIT`/`COMMON-EXIT` paragraph repeated per section).

Directly reproduced:
```cobol
       PROCEDURE DIVISION.
       SECTION-ONE SECTION.
       COMMON-EXIT.
           DISPLAY 'ONE'.
       SECTION-TWO SECTION.
       COMMON-EXIT.
           DISPLAY 'TWO'.
```
raises `error Duplicate procedure division name: COMMON-EXIT` for valid COBOL. No test covers paragraph-name reuse across sections.

### Semantic-2. MOVE targets qualified with `OF`/`IN` produce a false "Undefined data name" ERROR — HIGH — **[verified — see Parser-3 for the root-cause confirmation from the parser side]**

`_resolve_data_names`, invoked at ERROR severity, tries to resolve every string in a `MoveStatement.target_names` tuple against the data symbol table — including the qualifier word itself, since the parser (Parser-3) never filters it out. Directly reproduced: `MOVE 'A' TO WS-FIELD OF WS-GROUP` raises `error Undefined data name: OF` for perfectly valid, qualified COBOL — the exact construct qualification exists for.

### Semantic-3. No duplicate-name detection at all for DATA DIVISION items — HIGH — **[confirmed]**

`_build_data_symbols` has no analog of the procedure-symbol duplicate check (Semantic-1). Two identically-named subordinate items under the same parent (`05 WS-FIELD PIC X.` / `05 WS-FIELD PIC X(9).` under one `01 WS-GROUP`) are silently accepted as two separate `DataSymbol` entries with zero diagnostics — and if later referenced, resolution only downgrades to a WARNING ("Ambiguous reference"), treating a genuine duplicate declaration as if it were legitimate qualifiable reuse rather than flagging the real defect it is.

### Semantic-4. The cross-reference index never scans DATA DIVISION clauses, under-reporting "Find All References" — MEDIUM — **[confirmed]**

Reference resolution only ever runs against `unit.procedure`; a name used only inside a data-description clause — most notably a `REDEFINES` target — is invisible to the reference index `find_references` (Phase 4's own "Find All References" feature) is built directly on. Confirmed: `01 WS-ALIAS REDEFINES WS-ORIGINAL PIC 9(10).` leaves `find_data_references("WS-ORIGINAL")` returning `()` even though `WS-ALIAS` plainly references it.

### Semantic-5. `find_procedure_symbol` has no ambiguity detection, unlike its data-symbol sibling — MEDIUM — **[confirmed as an inconsistency; currently masked by Semantic-1 turning every such case into a hard error first]**

Unlike the data-name lookup (which explicitly warns on more than one match), an unqualified `PERFORM` name matching more than one procedure symbol would resolve silently to whichever is registered first — currently unreachable in practice only because Semantic-1 already rejects the duplicate outright, but a real, exercisable gap the moment qualified-PERFORM support changes that.

### Semantic-6. `PERFORM name IN section` misroutes its qualifier into a data-name lookup — MEDIUM — **[verified]**

The parser only recognizes `THRU`/`THROUGH` after a PERFORM target; an `IN`/`OF` qualifier falls into `modifier_tokens` instead, and semantic analysis then runs a data-name lookup against those tokens. `PERFORM COMMON-EXIT IN SECTION-ONE` produces a nonsensical `Possibly undefined data name: SECTION-ONE` WARNING — checking a section name as if it might be a data item.

### Semantic-7. Keyword table is missing common GnuCOBOL special registers, causing false "possibly undefined" warnings — MEDIUM — **[verified]**

`ARGUMENT-NUMBER`, `ARGUMENT-VALUE`, `ENVIRONMENT-NAME`, `ENVIRONMENT-VALUE`, and `COMMAND-LINE` are absent from the reserved-word table; since `ACCEPT` has no dedicated grammar rule and falls through to the generic-statement parser, these lex as ordinary identifiers and get scanned for definedness. `ACCEPT WS-ARG-COUNT FROM ARGUMENT-NUMBER` produces a false `Possibly undefined data name: ARGUMENT-NUMBER` warning for an entirely ordinary GnuCOBOL idiom.

### Semantic-8. `SCREEN SECTION` is entirely unrecognized — LOW/MEDIUM — **[confirmed as a table/parser gap; live-triggering impact unconfirmed against real fixtures]**

`SCREEN` is absent from the reserved-word set, and the data-division section parser only recognizes WORKING-STORAGE/LOCAL-STORAGE/LINKAGE — so SCREEN SECTION (common in interactive GnuCOBOL programs) isn't modeled at all. More a parser feature gap than a pure keyword-table miscategorization.

### Semantic-9. RENAMES (66-level) `parent_name` is computed from the wrong item — LOW — **[confirmed; currently inert since nothing consumes RENAMES `parent_name` yet]**

A 66-level entry's `parent_name` is taken from whatever is on top of the level-nesting stack at that point — i.e. the most recently processed *sibling* elementary item, not the enclosing 01-level record that actually owns the renamed range. Confirmed via trace: `66 WS-COMBINED RENAMES WS-A.` (inside `01 WS-RECORD` containing `05 WS-A`/`05 WS-B`) yields `parent_name == "WS-B"` instead of `"WS-RECORD"`. A latent bug for any future feature that consumes RENAMES qualification.

### Semantic-10. Condition-names accepted as MOVE targets with no diagnostic — LOW, arguably out of scope

An 88-level condition-name shares the same symbol table as ordinary data items with no usage-context validation, so `MOVE 'D' TO WS-DONE` (where `WS-DONE` is a condition-name, illegal as a MOVE receiving field) analyzes cleanly with zero diagnostics.

**Test coverage gaps (confirmed):** no dedicated unit test file exists for `keywords.py` at all; and there is zero test coverage for paragraph-name reuse across sections (Semantic-1), DATA DIVISION duplicate names (Semantic-3), `OF`/`IN`-qualified references in either MOVE or PERFORM targets (Semantic-2/6), and REDEFINES-only references (Semantic-4) — every one of the risky, name-collision-adjacent paths found above was untested going in.

## Editor-facing services (`navigation.py`, `hover.py`, `outline.py`, `folding.py`, `rendering.py`, `diagnostics.py`, `source_diagnostics.py`, `quick_fixes.py`, `signature_help.py`, `task_list.py`)

### Editor-Facing-1. Quick Fix silently no-ops on a FIXED-format line with trailing content past column 72 — HIGH — **[reported as directly executed and reproduced]**

`compute_quick_fix` inserts its closing quote at `len(line_text) + 1` — the end of the *raw* line — but the FIXED-format lexer only ever scans columns 8–72 as program text; anything from column 73 onward (the classic sequence-number area) is never read. If the raw line has trailing content past column 72, the fix's insertion point lands outside the window the lexer reads at all, so applying the "fix" leaves the diagnostic completely unchanged — appearing to succeed while doing nothing.

### Editor-Facing-2. Quick Fix's position math uses raw source columns while the diagnostic it's fixing was computed against a tab-expanded line — HIGH — **[reported as directly executed and reproduced; this is the newly-confirmed second half of Lexer-2 above]**

Mirroring Lexer-2's tab-expansion mismatch: `compute_quick_fix` indexes into the raw (non-tab-expanded) source line using the diagnostic's column directly. When a tab precedes the unterminated literal's opening quote on that line, the raw index no longer lines up with the expanded-column position the diagnostic actually points at, the character-match check fails, and `compute_quick_fix` returns `None` — no fix offered at all for a legitimately fixable diagnostic.

### Editor-Facing-3. Nested `FUNCTION` calls always resolve signature help to the outermost function, never the one the cursor is actually inside — MEDIUM — **[reported as directly executed and reproduced]**

The scan returns on the *first* `FUNCTION` token whose paren range contains the cursor, scanning in source order — since an outer call's parens always fully enclose any nested call's parens, the outer match is found first and the function returns immediately without checking for a more specific inner match. `MOVE FUNCTION UPPER-CASE(FUNCTION TRIM(WS-NAME)) TO WS-RESULT` with the cursor on `WS-NAME` returns signature help for `UPPER-CASE`, not `TRIM` — the function the cursor is literally sitting inside the arguments of. Not covered by the existing signature-help tests (which only nest grouping parens, not nested FUNCTION calls).

### Editor-Facing-4. Task List's word-boundary regex treats `-` as a boundary, false-flagging tag words embedded in hyphenated COBOL identifiers — MEDIUM — **[reported as directly executed and reproduced]**

The `\b(TODO|FIXME|HACK|XXX)\b` pattern correctly rejects a tag that's merely a substring of a longer word (`TODOLIST`, `HACKATHON`), but `-` counts as a non-word character for `\b`, and COBOL identifiers are hyphen-delimited — so a hyphen-flanked segment matching a tag word is treated as a whole word. `* See WS-HACK-FLAG for details on this switch.` produces a false `HACK` task-list entry despite the comment containing no actual task marker, just a reference to a data name.

### Editor-Facing-5. Inconsistent "nothing to fold" guard: an empty `IF`/`END-IF` still gets a fold range, but an empty out-of-line `PERFORM` doesn't — LOW — **[reported as directly executed and reproduced]**

`PerformStatement` fold ranges are only added when the body is non-empty, but `IfStatement`/`EvaluateStatement` fold ranges are added unconditionally regardless of whether their branches contain anything — `IF 1 > 0\nEND-IF` (empty in both branches) still yields a fold range hiding zero lines of content, inconsistent with the deliberate empty-PERFORM exclusion in the same file.

**Checked and found correct:** `identifier_at` boundary math (one-before-start, one-after-end, mid-hyphen) is correct; symbol-table lookups throughout `navigation.py`/`semantic.py` are consistently case-insensitive; `signature_help.py`'s paren-depth counter correctly ignores parens inside string-literal arguments (the lexer emits a literal as one token) and correctly handles 3+ levels of nesting; `render_clause_tokens` cannot see a stray `COMMENT` token inside a clause's token list, since the parser cursor filters comments out before clause construction; `compute_source_diagnostics` correctly surfaces every stage's diagnostics for whitespace-only, comments-only, and severely malformed source (aside from the Parser-4 crash-swallowing interaction recorded above) with no duplicate diagnostics observed for one root cause; no `hover.py` documentation-table entry references a word absent from the reserved-word set.

## Cross-cutting observations (Phase 4)

- **The same `OF`/`IN`-qualifier bug was independently rediscovered by two separate review passes** (Parser-3 and Semantic-2) — one by reading the parser's target-collection loop, the other by tracing a false diagnostic back through semantic analysis to the same root cause. This is the second time in this tracker two independent passes have converged on the identical bug (the first was Phase 2's drive-relative-path validator gap) — a strong signal that convergent findings like these are genuinely structural, not reviewer error, and that COBOL's `OF`/`IN` qualification syntax is a systematically under-handled feature across this entire pipeline (MOVE targets, PERFORM targets, and by extension probably any other statement that accepts a qualified data name).
- **`compute_source_diagnostics`'s deliberate blanket exception handling is a double-edged design.** It successfully prevents any single parser/lexer/semantic bug from crashing the editor outright (a genuinely good defensive choice for a live-typing IDE) — but it also means every bug found in this phase that raises an exception (Parser-4, and potentially others not yet found) degrades silently rather than visibly: the user sees fewer diagnostics than they should, with no signal that anything went wrong, rather than an obvious error they could report. The lexer's own tab/comment-interruption bugs are the "wrong diagnostic" flavor of this problem; Parser-4 is the "no diagnostics at all past this point" flavor, which is strictly worse.
- **Legacy-COBOL-specific input keeps being the thing that breaks this pipeline**: numeric paragraph names (Parser-2), D-indicator debug lines (Lexer-5), long sequential IF-ELSE dispatch chains (Parser-5), and SCREEN SECTION (Semantic-8) are all real, historically common patterns in exactly the kind of legacy mainframe source this IDE exists to modernize — these aren't exotic edge cases, they're the target user's actual code.
- **Every one of the "silent, zero-diagnostic" findings in this phase (Lexer-1, Parser-1, Parser-2, Parser-4, Parser-7, Parser-8, Semantic-3) is more dangerous than a visible error would be**, for the same reason repeatedly noted throughout this tracker: a user has no way to discover their COBOL was misinterpreted unless they already suspect it and go looking.
