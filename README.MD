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

## Planned architecture milestones

Before committing the application structure to a GUI, OpenCobol2 is establishing contracts for the following systems.

### Settings

Persistent, typed settings will cover:

* Explicit compiler and toolchain paths.
* Toolchain environment overrides.
* Editor fonts and spacing.
* Automatic indentation preferences.
* Code folding preferences.
* COBOL fixed-format guide visibility.
* Syntax theme customization.
* Git behavior.
* Plugin enablement.
* Non-secret remote connection profiles.

Secrets and authentication tokens will not be stored as plain application settings.

### Commands and menus

OpenCobol2 will use a command registry rather than hardcoding application behavior directly into menus.

The planned primary menu surface is:

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

Application commands and plugin-contributed commands will also be searchable through a command search interface.

### COBOL editor services

Planned COBOL language and editor services include:

* Configurable syntax highlighting.
* Fixed-format column and coding-area guides.
* Sequence-area visualization.
* Indicator-column visualization.
* Area A and Area B visualization.
* Reference-margin visibility.
* Automatic indentation.
* Division, section, paragraph, data-group, and structured-statement folding.
* COBOL-aware source navigation.

These language services will be testable independently from the Qt editor widget.

### Git and GitHub

Git and GitHub are planned as separate but integrated subsystems.

Git support is expected to include repository discovery, status, branches, staging, commits, diffs, history, remotes, fetch, pull, and push workflows.

GitHub integration is expected to include authenticated GitHub account and repository workflows, with pull request and issue integration planned as the project develops.

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

The project is deliberately building compiler, document, settings, command, language-service, plugin, source-control, and remote-resource boundaries before committing those systems to a desktop GUI architecture.

This is intended to prevent the successor application from becoming a thin modern shell around decade-old implementation patterns.

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
