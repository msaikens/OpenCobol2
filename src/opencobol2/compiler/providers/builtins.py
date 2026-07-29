"""Built-in OpenCobol2 compiler providers."""

from __future__ import annotations

from opencobol2.compiler.providers.models import (
    CompilerConfigurationField,
    CompilerConfigurationFieldKind,
    CompilerExecutionKind,
    CompilerProfile,
    _normalize_nonempty_string,
    _validate_configuration_value,
)
from opencobol2.compiler.providers.registry import (
    CompilerProviderRegistry,
)


GNUCOBOL_PROVIDER_ID = "opencobol2.gnucobol"

CUSTOM_COMPILER_PROVIDER_ID = (
    "opencobol2.custom-local"
)


class _DeclarativeCompilerProvider:
    """Base implementation for field-described compiler providers."""

    __slots__ = (
        "_provider_id",
        "_display_name",
        "_execution_kind",
        "_configuration_fields",
    )

    def __init__(
        self,
        *,
        provider_id: str,
        display_name: str,
        execution_kind: CompilerExecutionKind,
        configuration_fields: tuple[
            CompilerConfigurationField,
            ...,
        ],
    ) -> None:
        field_keys = tuple(
            field.key
            for field in configuration_fields
        )

        if len(
            set(
                field_keys,
            )
        ) != len(
            field_keys,
        ):
            raise ValueError(
                "Compiler provider configuration field keys "
                "must be unique."
            )

        # Editor §CompilerAbstraction-4: normalized the same way
        # `CompilerProfile.provider_id` already is, so the registry's
        # own stripped dict key, the profile's normalized provider_id,
        # and this provider's own `provider_id` property can never
        # disagree by whitespace alone -- `validate_profile`'s
        # identity check below compares them directly.
        self._provider_id = _normalize_nonempty_string(
            provider_id,
            "Compiler provider ID",
        )
        self._display_name = _normalize_nonempty_string(
            display_name,
            "Compiler provider display name",
        )
        self._execution_kind = execution_kind
        self._configuration_fields = configuration_fields

    @property
    def provider_id(
        self,
    ) -> str:
        """Return the stable provider identifier."""

        return self._provider_id

    @property
    def display_name(
        self,
    ) -> str:
        """Return the user-facing provider name."""

        return self._display_name

    @property
    def execution_kind(
        self,
    ) -> CompilerExecutionKind:
        """Return how this provider performs compilation."""

        return self._execution_kind

    @property
    def configuration_fields(
        self,
    ) -> tuple[CompilerConfigurationField, ...]:
        """Return provider configuration field definitions."""

        return self._configuration_fields

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        """Validate one compiler profile."""

        if profile.provider_id != self.provider_id:
            raise ValueError(
                "Compiler profile provider "
                f"{profile.provider_id!r} does not match "
                f"{self.provider_id!r}."
            )

        fields_by_key = {
            field.key: field
            for field in self.configuration_fields
        }

        unknown_keys = tuple(
            sorted(
                set(
                    profile.configuration,
                )
                - set(
                    fields_by_key,
                )
            )
        )

        if unknown_keys:
            raise ValueError(
                "Unknown compiler configuration fields: "
                + ", ".join(
                    unknown_keys,
                )
                + "."
            )

        for field in self.configuration_fields:
            if field.key not in profile.configuration:
                if (
                    field.required
                    and field.default is None
                ):
                    raise ValueError(
                        "Required compiler configuration field "
                        "is missing: "
                        f"{field.key}."
                    )

                continue

            value = profile.configuration[
                field.key
            ]

            _validate_configuration_value(
                field.kind,
                value,
                field.key,
                field.choices,
            )


class GnuCobolCompilerProvider(
    _DeclarativeCompilerProvider,
):
    """Built-in compiler provider for GnuCOBOL."""

    def __init__(
        self,
    ) -> None:
        super().__init__(
            provider_id=GNUCOBOL_PROVIDER_ID,
            display_name="GnuCOBOL",
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            configuration_fields=(
                CompilerConfigurationField(
                    key="compiler_path",
                    title="Compiler executable",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                    description=(
                        "Explicit path to cobc when automatic "
                        "discovery is insufficient."
                    ),
                ),
                CompilerConfigurationField(
                    key="config_directory",
                    title="Configuration directory",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                    description=(
                        "Optional GnuCOBOL configuration directory."
                    ),
                ),
                CompilerConfigurationField(
                    key="copy_directory",
                    title="Default copybook directory",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                    description=(
                        "Optional default GnuCOBOL copybook directory."
                    ),
                ),
                CompilerConfigurationField(
                    key="library_path",
                    title="Runtime library path",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                    description=(
                        "Optional GnuCOBOL library path."
                    ),
                ),
            ),
        )


class CustomLocalCompilerProvider(
    _DeclarativeCompilerProvider,
):
    """Built-in escape-hatch provider for local COBOL compilers."""

    def __init__(
        self,
    ) -> None:
        super().__init__(
            provider_id=CUSTOM_COMPILER_PROVIDER_ID,
            display_name="Custom local COBOL compiler",
            execution_kind=(
                CompilerExecutionKind.LOCAL_PROCESS
            ),
            configuration_fields=(
                CompilerConfigurationField(
                    key="executable_path",
                    title="Compiler executable",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                    required=True,
                ),
                CompilerConfigurationField(
                    key="working_directory",
                    title="Working directory",
                    kind=(
                        CompilerConfigurationFieldKind.PATH
                    ),
                ),
                CompilerConfigurationField(
                    key="version_arguments",
                    title="Version probe arguments",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(
                        "--version",
                    ),
                ),
                CompilerConfigurationField(
                    key="compile_arguments",
                    title="Compile argument template",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(
                        "{source}",
                        "-o",
                        "{output}",
                    ),
                ),
                CompilerConfigurationField(
                    key="executable_output_arguments",
                    title="Executable output arguments",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(),
                ),
                CompilerConfigurationField(
                    key="module_output_arguments",
                    title="Module output arguments",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(),
                ),
                CompilerConfigurationField(
                    key="fixed_format_arguments",
                    title="Fixed-format arguments",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(),
                ),
                CompilerConfigurationField(
                    key="free_format_arguments",
                    title="Free-format arguments",
                    kind=(
                        CompilerConfigurationFieldKind.STRING_LIST
                    ),
                    default=(),
                ),
                CompilerConfigurationField(
                    key="standard_argument_template",
                    title="Dialect argument template",
                    kind=(
                        CompilerConfigurationFieldKind.STRING
                    ),
                ),
                CompilerConfigurationField(
                    key="copy_directory_argument_template",
                    title="Copybook directory argument template",
                    kind=(
                        CompilerConfigurationFieldKind.STRING
                    ),
                ),
                CompilerConfigurationField(
                    key="library_directory_argument_template",
                    title="Library directory argument template",
                    kind=(
                        CompilerConfigurationFieldKind.STRING
                    ),
                ),
                CompilerConfigurationField(
                    key="library_argument_template",
                    title="Library argument template",
                    kind=(
                        CompilerConfigurationFieldKind.STRING
                    ),
                ),
                CompilerConfigurationField(
                    key="diagnostic_format",
                    title="Diagnostic format",
                    kind=(
                        CompilerConfigurationFieldKind.CHOICE
                    ),
                    default="gcc",
                    choices=(
                        "gcc",
                        "msvc",
                        "none",
                    ),
                ),
                CompilerConfigurationField(
                    key="success_return_codes",
                    title="Successful return codes",
                    kind=(
                        CompilerConfigurationFieldKind.INTEGER_LIST
                    ),
                    default=(
                        0,
                    ),
                ),
            ),
        )

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        """Validate one compiler profile, including argument templates.

        Editor §CompilerAbstraction-7: the inherited field-kind check
        alone accepts a syntactically broken template (unbalanced
        braces, a placeholder name that doesn't exist) with no error
        at profile-save time -- it would only fail later, at actual
        compile-invocation time in `runtimes/custom_local.py`, with a
        different and less helpful error than anything the profile
        dialog showed. Each template field is dry-run formatted here
        against the same placeholder names the real compile-time
        formatter (`_format_argument`) supplies, without importing
        that runtime module directly (which would create a circular
        import: `runtimes.custom_local` already imports from this
        `providers` package).
        """

        super().validate_profile(
            profile,
        )

        for (
            field_key,
            sample_values,
        ) in _TEMPLATE_FIELD_SAMPLE_VALUES.items():
            value = profile.configuration.get(
                field_key,
            )

            if value is None:
                continue

            templates = (
                value
                if isinstance(
                    value,
                    (
                        list,
                        tuple,
                    ),
                )
                else (
                    value,
                )
            )

            for template in templates:
                if not isinstance(
                    template,
                    str,
                ):
                    # Already caught by the inherited field-kind
                    # check above.
                    continue

                _validate_argument_template(
                    template,
                    sample_values,
                    field_key,
                )


_TEMPLATE_FIELD_SAMPLE_VALUES: dict[
    str,
    dict[str, str],
] = {
    "compile_arguments": {
        "source": "",
        "output": "",
    },
    "executable_output_arguments": {
        "source": "",
        "output": "",
    },
    "module_output_arguments": {
        "source": "",
        "output": "",
    },
    "fixed_format_arguments": {
        "source": "",
        "output": "",
    },
    "free_format_arguments": {
        "source": "",
        "output": "",
    },
    "standard_argument_template": {
        "standard": "",
    },
    "copy_directory_argument_template": {
        "directory": "",
    },
    "library_directory_argument_template": {
        "directory": "",
    },
    "library_argument_template": {
        "library": "",
    },
}


def _validate_argument_template(
    template: str,
    sample_values: dict[str, str],
    field_key: str,
) -> None:
    """Dry-run one argument template with placeholder stand-ins.

    Mirrors `runtimes/custom_local.py::_format_argument`'s own
    `str.format_map()` call and error handling, but raises a plain
    `ValueError` (this validation layer's own established error type)
    instead of that module's `CustomLocalCompilerTemplateError`, to
    avoid importing the runtime layer here.
    """

    try:
        template.format_map(
            sample_values,
        )
    except KeyError as error:
        raise ValueError(
            f"Unknown placeholder {error.args[0]!r} in "
            f"{field_key}."
        ) from error
    except ValueError as error:
        raise ValueError(
            "Invalid compiler argument template in "
            f"{field_key}: {error}"
        ) from error


def create_builtin_compiler_provider_registry(
) -> CompilerProviderRegistry:
    """Create the registry containing OpenCobol2 built-in providers."""

    registry = CompilerProviderRegistry()

    for provider in (
        GnuCobolCompilerProvider(),
        CustomLocalCompilerProvider(),
    ):
        registry.register(
            provider,
        )

    return registry