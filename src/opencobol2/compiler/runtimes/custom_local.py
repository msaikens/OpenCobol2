"""Activated custom local COBOL compiler runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
from types import MappingProxyType
from uuid import UUID

from opencobol2.compiler.custom_local_diagnostics import (
    parse_custom_local_diagnostics,
)
from opencobol2.compiler.custom_local_models import (
    CustomLocalCompilation,
)
from opencobol2.compiler.local_process import (
    collect_compiler_diagnostic_output,
    invoke_local_compiler_process,
)
from opencobol2.compiler.models import (
    CobolSourceFormat,
    CompileRequest,
    CompilerOutputKind,
)
from opencobol2.compiler.providers import (
    CUSTOM_COMPILER_PROVIDER_ID,
    CompilerExecutionKind,
    CompilerProfile,
    CustomLocalCompilerProvider,
    JsonValue,
    resolve_compiler_profile_configuration,
)
from opencobol2.compiler.runtimes.models import (
    CompilerRuntime,
)


class CustomLocalCompilerTemplateError(ValueError):
    """Raised when a custom compiler argument template is invalid."""


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CustomLocalCompilerRuntime:
    """Activated template-driven local COBOL compiler runtime."""

    profile_id: UUID
    display_name: str
    configuration: Mapping[str, JsonValue]
    environment_overrides: Mapping[str, str]
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Normalize and validate custom local runtime state."""

        if not isinstance(
            self.profile_id,
            UUID,
        ):
            raise TypeError(
                "Custom compiler runtime profile ID "
                "must be a UUID."
            )

        if not isinstance(
            self.display_name,
            str,
        ):
            raise TypeError(
                "Custom compiler runtime display name "
                "must be a string."
            )

        normalized_display_name = (
            self.display_name.strip()
        )

        if not normalized_display_name:
            raise ValueError(
                "Custom compiler runtime display name "
                "must not be empty."
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "Custom compiler runtime timeout must be "
                "greater than zero."
            )

        configuration = MappingProxyType(
            dict(
                self.configuration,
            )
        )
        environment_overrides = MappingProxyType(
            dict(
                self.environment_overrides,
            )
        )

        if not all(
            isinstance(
                key,
                str,
            )
            for key in environment_overrides
        ):
            raise TypeError(
                "Custom compiler environment keys "
                "must be strings."
            )

        if not all(
            isinstance(
                value,
                str,
            )
            for value in environment_overrides.values()
        ):
            raise TypeError(
                "Custom compiler environment values "
                "must be strings."
            )

        object.__setattr__(
            self,
            "display_name",
            normalized_display_name,
        )
        object.__setattr__(
            self,
            "configuration",
            configuration,
        )
        object.__setattr__(
            self,
            "environment_overrides",
            environment_overrides,
        )

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the custom local compiler provider identifier."""

        return CUSTOM_COMPILER_PROVIDER_ID

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return the custom compiler execution model."""

        return CompilerExecutionKind.LOCAL_PROCESS

    def process_environment(
        self,
        base_environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Build the compiler process environment."""

        environment = dict(
            os.environ
            if base_environment is None
            else base_environment
        )

        environment.update(
            self.environment_overrides,
        )

        return environment

    def compile(
        self,
        request: CompileRequest,
        *,
        base_environment: Mapping[str, str] | None = None,
    ) -> CustomLocalCompilation:
        """Compile a request with the configured local compiler."""

        command = build_custom_local_compiler_command(
            self.configuration,
            request,
        )

        working_directory_value = (
            self.configuration.get(
                "working_directory",
            )
        )

        working_directory = (
            None
            if working_directory_value is None
            else Path(
                _require_string(
                    working_directory_value,
                    "working_directory",
                )
            )
        )

        process_result = invoke_local_compiler_process(
            request=request,
            command=command,
            timeout_seconds=self.timeout_seconds,
            compiler_name=self.display_name,
            working_directory=working_directory,
            environment=self.process_environment(
                base_environment,
            ),
        )

        diagnostic_format = _require_string(
            self.configuration[
                "diagnostic_format"
            ],
            "diagnostic_format",
        )

        diagnostics = parse_custom_local_diagnostics(
            collect_compiler_diagnostic_output(
                process_result,
            ),
            diagnostic_format,
        )

        success_return_codes = _require_integer_tuple(
            self.configuration[
                "success_return_codes"
            ],
            "success_return_codes",
        )

        return CustomLocalCompilation(
            process_result=process_result,
            diagnostics=diagnostics,
            success_return_codes=success_return_codes,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CustomLocalCompilerRuntimeFactory:
    """Activates custom local compiler runtimes from profiles."""

    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        """Validate custom local runtime factory settings."""

        if self.timeout_seconds <= 0:
            raise ValueError(
                "Custom compiler runtime timeout must be "
                "greater than zero."
            )

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the supported compiler provider identifier."""

        return CUSTOM_COMPILER_PROVIDER_ID

    def create_runtime(
        self,
        profile: CompilerProfile,
    ) -> CompilerRuntime:
        """Create an activated custom local compiler runtime."""

        if not isinstance(
            profile,
            CompilerProfile,
        ):
            raise TypeError(
                "Profile must be CompilerProfile."
            )

        provider = CustomLocalCompilerProvider()

        configuration = (
            resolve_compiler_profile_configuration(
                provider,
                profile,
            )
        )

        return CustomLocalCompilerRuntime(
            profile_id=profile.profile_id,
            display_name=profile.display_name,
            configuration=configuration,
            environment_overrides=(
                profile.environment_overrides
            ),
            timeout_seconds=self.timeout_seconds,
        )


def build_custom_local_compiler_command(
    configuration: Mapping[str, JsonValue],
    request: CompileRequest,
) -> tuple[str, ...]:
    """Build a custom local compiler command from templates."""

    if not isinstance(
        request,
        CompileRequest,
    ):
        raise TypeError(
            "Request must be CompileRequest."
        )

    executable_path = _require_string(
        configuration[
            "executable_path"
        ],
        "executable_path",
    )

    command: list[str] = [
        executable_path,
    ]

    source_output_values = {
        "source": str(
            request.source_path,
        ),
        "output": str(
            request.output_path,
        ),
    }

    command.extend(
        _format_argument_sequence(
            _require_string_tuple(
                configuration[
                    "compile_arguments"
                ],
                "compile_arguments",
            ),
            source_output_values,
            "compile_arguments",
        )
    )

    output_configuration_key = (
        "executable_output_arguments"
        if (
            request.output_kind
            is CompilerOutputKind.EXECUTABLE
        )
        else "module_output_arguments"
    )

    command.extend(
        _format_argument_sequence(
            _require_string_tuple(
                configuration[
                    output_configuration_key
                ],
                output_configuration_key,
            ),
            source_output_values,
            output_configuration_key,
        )
    )

    if request.source_format is not None:
        source_format_configuration_key = (
            "fixed_format_arguments"
            if (
                request.source_format
                is CobolSourceFormat.FIXED
            )
            else "free_format_arguments"
        )

        command.extend(
            _format_argument_sequence(
                _require_string_tuple(
                    configuration[
                        source_format_configuration_key
                    ],
                    source_format_configuration_key,
                ),
                source_output_values,
                source_format_configuration_key,
            )
        )

    standard_template = configuration.get(
        "standard_argument_template",
    )

    if (
        request.standard is not None
        and standard_template is not None
    ):
        command.append(
            _format_argument(
                _require_string(
                    standard_template,
                    "standard_argument_template",
                ),
                {
                    "standard": request.standard,
                },
                "standard_argument_template",
            )
        )

    _append_directory_arguments(
        command,
        request.copy_directories,
        configuration.get(
            "copy_directory_argument_template",
        ),
        "copy_directory_argument_template",
    )

    _append_directory_arguments(
        command,
        request.library_directories,
        configuration.get(
            "library_directory_argument_template",
        ),
        "library_directory_argument_template",
    )

    library_template = configuration.get(
        "library_argument_template",
    )

    if library_template is not None:
        normalized_library_template = _require_string(
            library_template,
            "library_argument_template",
        )

        for library in request.libraries:
            command.append(
                _format_argument(
                    normalized_library_template,
                    {
                        "library": library,
                    },
                    "library_argument_template",
                )
            )

    command.extend(
        request.additional_arguments,
    )
    command.extend(
        str(
            input_path,
        )
        for input_path in request.additional_inputs
    )

    return tuple(
        command,
    )


def _append_directory_arguments(
    command: list[str],
    directories: tuple[Path, ...],
    template_value: JsonValue | None,
    template_name: str,
) -> None:
    """Append formatted directory arguments."""

    if template_value is None:
        return

    template = _require_string(
        template_value,
        template_name,
    )

    for directory in directories:
        command.append(
            _format_argument(
                template,
                {
                    "directory": str(
                        directory,
                    ),
                },
                template_name,
            )
        )


def _format_argument_sequence(
    templates: tuple[str, ...],
    values: Mapping[str, str],
    template_name: str,
) -> tuple[str, ...]:
    """Format an argument-template sequence."""

    return tuple(
        _format_argument(
            template,
            values,
            template_name,
        )
        for template in templates
    )


def _format_argument(
    template: str,
    values: Mapping[str, str],
    template_name: str,
) -> str:
    """Format one compiler argument template."""

    try:
        return template.format_map(
            values,
        )
    except KeyError as error:
        missing_placeholder = error.args[0]

        raise CustomLocalCompilerTemplateError(
            f"Unknown placeholder "
            f"{missing_placeholder!r} in "
            f"{template_name}."
        ) from error
    except ValueError as error:
        raise CustomLocalCompilerTemplateError(
            f"Invalid compiler argument template "
            f"in {template_name}: {error}"
        ) from error


def _require_string(
    value: JsonValue,
    name: str,
) -> str:
    """Require a string configuration value."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"Custom compiler configuration "
            f"{name!r} must be a string."
        )

    return value


def _require_string_tuple(
    value: JsonValue,
    name: str,
) -> tuple[str, ...]:
    """Require a tuple containing only strings."""

    if not isinstance(
        value,
        tuple,
    ):
        raise TypeError(
            f"Custom compiler configuration "
            f"{name!r} must be a string list."
        )

    if not all(
        isinstance(
            item,
            str,
        )
        for item in value
    ):
        raise TypeError(
            f"Custom compiler configuration "
            f"{name!r} must contain only strings."
        )

    return value


def _require_integer_tuple(
    value: JsonValue,
    name: str,
) -> tuple[int, ...]:
    """Require a tuple containing only non-boolean integers."""

    if not isinstance(
        value,
        tuple,
    ):
        raise TypeError(
            f"Custom compiler configuration "
            f"{name!r} must be an integer list."
        )

    if not all(
        isinstance(
            item,
            int,
        )
        and not isinstance(
            item,
            bool,
        )
        for item in value
    ):
        raise TypeError(
            f"Custom compiler configuration "
            f"{name!r} must contain only integers."
        )

    return value