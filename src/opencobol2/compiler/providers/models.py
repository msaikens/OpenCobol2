"""Compiler provider domain models.

Defines the shapes shared by every compiler provider integration: the
`JsonValue` alias for configuration data, the `CompilerExecutionKind`
and `CompilerConfigurationFieldKind` enums, the `CompilerConfigurationField`
and `CompilerProfile` dataclasses (both of which validate and freeze
their contents in `__post_init__` so a constructed instance is always
immutable and well-formed), and the `CompilerProvider` protocol that
concrete providers implement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import math
from types import MappingProxyType
from typing import Protocol, TypeAlias
from uuid import UUID, uuid4


JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | tuple["JsonValue", ...]
    | Mapping[str, "JsonValue"]
)


class CompilerExecutionKind(StrEnum):
    """Describes how a compiler provider performs compilation.

    :cvar LOCAL_PROCESS: Compilation runs as a local subprocess (e.g. an
        installed `cobc` executable).
    :cvar REMOTE_JOB: Compilation is dispatched to a remote job runner
        rather than executed on this machine.
    """

    LOCAL_PROCESS = "local-process"
    REMOTE_JOB = "remote-job"


class CompilerConfigurationFieldKind(StrEnum):
    """Describes a provider configuration field's value type.

    :cvar STRING: A single free-form string value.
    :cvar PATH: A single filesystem path string.
    :cvar BOOLEAN: A true/false flag.
    :cvar STRING_LIST: An ordered list of strings.
    :cvar STRING_MAP: A mapping of string keys to string values.
    :cvar INTEGER_LIST: An ordered list of integers.
    :cvar CHOICE: A single string constrained to one of a fixed set of
        `choices`.
    """

    STRING = "string"
    PATH = "path"
    BOOLEAN = "boolean"
    STRING_LIST = "string-list"
    STRING_MAP = "string-map"
    INTEGER_LIST = "integer-list"
    CHOICE = "choice"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerConfigurationField:
    """Describes one user-configurable compiler provider setting.

    :ivar key: The stable, non-empty identifier used to look this field
        up in a `CompilerProfile.configuration` mapping.
    :ivar title: The user-facing label for this setting.
    :ivar kind: The value type this field holds, which determines how
        `default` and any assigned value are validated.
    :ivar required: Whether a profile must supply a value for this
        field.
    :ivar description: Optional user-facing help text, stripped of
        leading/trailing whitespace.
    :ivar default: The field's default value, if any, validated and
        frozen the same way an assigned value would be.
    :ivar choices: The fixed set of allowed values when `kind` is
        :attr:`CompilerConfigurationFieldKind.CHOICE`; empty for every
        other kind.
    """

    key: str
    title: str
    kind: CompilerConfigurationFieldKind
    required: bool = False
    description: str = ""
    default: JsonValue = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the configuration field.

        :returns: None. Normalizes `key`, `title`, `kind`, `description`,
            `choices`, and `default` in place via `object.__setattr__`
            (the dataclass is frozen, so this is the only way to
            normalize fields after construction).
        :raises TypeError: If `description` or `required` has the wrong
            type, or if `default` is not a valid value for `kind`.
        :raises ValueError: If `choices` contains a duplicate, if `kind`
            is :attr:`CompilerConfigurationFieldKind.CHOICE` with no
            `choices`, if `kind` is any other kind but `choices` is
            non-empty, or if `default` is not a valid value for `kind`.
        """
        key = _normalize_nonempty_string(
            self.key,
            "Compiler configuration field key",
        )

        title = _normalize_nonempty_string(
            self.title,
            "Compiler configuration field title",
        )

        if not isinstance(
            self.description,
            str,
        ):
            raise TypeError(
                "Compiler configuration field description "
                "must be a string."
            )

        if not isinstance(
            self.required,
            bool,
        ):
            raise TypeError(
                "Compiler configuration field required flag "
                "must be a boolean."
            )

        kind = CompilerConfigurationFieldKind(
            self.kind,
        )

        choices = tuple(
            _normalize_nonempty_string(
                choice,
                "Compiler configuration choice",
            )
            for choice in self.choices
        )

        if len(
            set(
                choices,
            )
        ) != len(
            choices,
        ):
            raise ValueError(
                "Compiler configuration choices must be unique."
            )

        if (
            kind is CompilerConfigurationFieldKind.CHOICE
            and not choices
        ):
            raise ValueError(
                "Choice configuration fields require choices."
            )

        if (
            kind is not CompilerConfigurationFieldKind.CHOICE
            and choices
        ):
            raise ValueError(
                "Only choice configuration fields "
                "may define choices."
            )

        if self.default is not None:
            _validate_configuration_value(
                kind,
                self.default,
                key,
                choices,
            )

        object.__setattr__(
            self,
            "key",
            key,
        )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "kind",
            kind,
        )

        object.__setattr__(
            self,
            "description",
            self.description.strip(),
        )

        object.__setattr__(
            self,
            "choices",
            choices,
        )

        object.__setattr__(
            self,
            "default",
            _freeze_json_value(
                self.default,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerProfile:
    """Describes one configured compiler provider instance.

    :ivar provider_id: The identifier of the :class:`CompilerProvider`
        this profile configures.
    :ivar display_name: The user-facing name for this profile.
    :ivar profile_id: The stable unique identifier for this profile
        instance, generated automatically if not supplied.
    :ivar configuration: The provider-specific configuration values for
        this profile, keyed by :attr:`CompilerConfigurationField.key`.
        Frozen into an immutable mapping of frozen JSON-compatible
        values.
    :ivar environment_overrides: Extra environment variables to apply
        when this profile compiles, frozen into an immutable mapping.
    """

    provider_id: str
    display_name: str
    profile_id: UUID = field(
        default_factory=uuid4,
    )
    configuration: Mapping[str, JsonValue] = field(
        default_factory=dict,
    )
    environment_overrides: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        """Validate and freeze compiler profile configuration.

        :returns: None. Normalizes `provider_id` and `display_name`,
            and freezes `configuration` and `environment_overrides`
            into immutable mappings, in place via `object.__setattr__`
            (the dataclass is frozen, so this is the only way to
            normalize fields after construction).
        :raises TypeError: If `provider_id` or `display_name` is not a
            string, if `profile_id` is not a `UUID`, or if
            `configuration` or `environment_overrides` is not a mapping
            of the expected shape.
        :raises ValueError: If `provider_id` or `display_name` is an
            empty (or whitespace-only) string.
        """
        provider_id = _normalize_nonempty_string(
            self.provider_id,
            "Compiler provider ID",
        )

        display_name = _normalize_nonempty_string(
            self.display_name,
            "Compiler profile display name",
        )

        if not isinstance(
            self.profile_id,
            UUID,
        ):
            raise TypeError(
                "Compiler profile ID must be a UUID."
            )

        configuration = _freeze_configuration(
            self.configuration,
        )

        environment_overrides = _freeze_environment(
            self.environment_overrides,
        )

        object.__setattr__(
            self,
            "provider_id",
            provider_id,
        )

        object.__setattr__(
            self,
            "display_name",
            display_name,
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


class CompilerProvider(Protocol):
    """Contract implemented by compiler provider integrations.

    Any object exposing this shape (whether via inheritance or simple
    structural conformance, since this is a `Protocol`) can be
    registered and used wherever a compiler provider is expected.
    """

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier.

        :returns: The provider's stable, non-empty identifier string.
        """
        ...

    @property
    def display_name(self) -> str:
        """Return the user-facing provider name.

        :returns: The provider's user-facing display name.
        """
        ...

    @property
    def execution_kind(self) -> CompilerExecutionKind:
        """Return how the provider performs compilation.

        :returns: The :class:`CompilerExecutionKind` describing whether
            this provider compiles locally or dispatches a remote job.
        """
        ...

    @property
    def configuration_fields(
        self,
    ) -> tuple[CompilerConfigurationField, ...]:
        """Return the provider's configurable settings.

        :returns: Every :class:`CompilerConfigurationField` a
            `CompilerProfile` for this provider may or must supply.
        """
        ...

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        """Validate a compiler profile for this provider.

        :param profile: The profile to validate against this
            provider's `configuration_fields`.
        :returns: None. Implementations signal an invalid profile by
            raising rather than by a return value.
        :raises ValueError: If implementations determine `profile` is
            not a valid configuration for this provider.
        """
        ...


def _freeze_configuration(
    configuration: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    """Validate and freeze compiler profile configuration.

    :param configuration: The raw configuration mapping to validate.
    :returns: An immutable `MappingProxyType` with every key normalized
        and every value frozen via `_freeze_json_value`.
    :raises TypeError: If `configuration` is not a mapping, if any key
        is not a non-empty string, or if any value is not a supported
        JSON-compatible type.
    :raises ValueError: If any key is an empty (or whitespace-only)
        string.
    """
    if not isinstance(
        configuration,
        Mapping,
    ):
        raise TypeError(
            "Compiler profile configuration must be a mapping."
        )

    normalized: dict[str, JsonValue] = {}

    for key, value in configuration.items():
        normalized_key = _normalize_nonempty_string(
            key,
            "Compiler profile configuration key",
        )

        normalized[
            normalized_key
        ] = _freeze_json_value(
            value,
        )

    return MappingProxyType(
        normalized,
    )


def _freeze_environment(
    environment: Mapping[str, str],
) -> Mapping[str, str]:
    """Validate and freeze compiler environment overrides.

    :param environment: The raw environment variable mapping to
        validate.
    :returns: An immutable `MappingProxyType` with every key
        normalized.
    :raises TypeError: If `environment` is not a mapping, if any key is
        not a non-empty string, or if any value is not a string.
    :raises ValueError: If any key is an empty (or whitespace-only)
        string.
    """
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "Compiler environment overrides must be a mapping."
        )

    normalized: dict[str, str] = {}

    for name, value in environment.items():
        normalized_name = _normalize_nonempty_string(
            name,
            "Compiler environment variable name",
        )

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "Compiler environment variable values "
                "must be strings."
            )

        normalized[
            normalized_name
        ] = value

    return MappingProxyType(
        normalized,
    )


def _freeze_json_value(
    value: JsonValue,
) -> JsonValue:
    """Validate and freeze one JSON-compatible configuration value.

    Recurses into mappings and sequences so a nested structure is
    frozen all the way down.

    :param value: The value to validate and freeze. Must be `None`, a
        `str`, `bool`, `int`, a finite `float`, a `Mapping`, or a
        `list`/`tuple`.
    :returns: `value` unchanged if it is already an immutable scalar
        type; otherwise an immutable `MappingProxyType` (for a mapping)
        or `tuple` (for a list or tuple) with every element likewise
        frozen.
    :raises ValueError: If `value` is a non-finite `float` (`nan` or
        infinity), or if a nested mapping key is an empty (or
        whitespace-only) string.
    :raises TypeError: If `value` is not one of the supported JSON-
        compatible types, or if a nested mapping key is not a string.
    """
    if (
        value is None
        or isinstance(
            value,
            (
                str,
                bool,
                int,
            ),
        )
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        if not math.isfinite(
            value,
        ):
            raise ValueError(
                "Compiler configuration numbers must be finite."
            )

        return value

    if isinstance(
        value,
        Mapping,
    ):
        normalized: dict[
            str,
            JsonValue,
        ] = {}

        for key, item_value in value.items():
            normalized_key = _normalize_nonempty_string(
                key,
                "Compiler configuration object key",
            )

            normalized[
                normalized_key
            ] = _freeze_json_value(
                item_value,
            )

        return MappingProxyType(
            normalized,
        )

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return tuple(
            _freeze_json_value(
                item,
            )
            for item in value
        )

    raise TypeError(
        "Unsupported compiler configuration value type: "
        f"{type(value).__name__}."
    )


def _normalize_nonempty_string(
    value: str,
    name: str,
) -> str:
    """Validate and normalize one required string.

    :param value: The value to validate. Must be a non-empty (after
        stripping) string.
    :param name: A human-readable label for `value`, used to build the
        error message when validation fails.
    :returns: `value` with leading/trailing whitespace stripped.
    :raises TypeError: If `value` is not a string.
    :raises ValueError: If `value` is empty or contains only
        whitespace.
    """
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized


def _validate_configuration_value(
    kind: CompilerConfigurationFieldKind,
    value: JsonValue,
    key: str,
    choices: tuple[str, ...],
) -> None:
    """Validate one provider configuration field value.

    Dispatches to the type check appropriate for `kind`: a non-empty
    string for `STRING`/`PATH`, a `bool` for `BOOLEAN`, a list of
    strings for `STRING_LIST`, a mapping of strings for `STRING_MAP`,
    a list of non-bool integers for `INTEGER_LIST`, and a string drawn
    from `choices` for `CHOICE`.

    :param kind: The configuration field kind that determines which
        shape `value` must have.
    :param value: The value to validate.
    :param key: The configuration field's key, used to build error
        messages.
    :param choices: The allowed values when `kind` is `CHOICE`; unused
        for every other kind.
    :returns: None. Raises on an invalid `value`; returns silently
        otherwise.
    :raises TypeError: If `value` does not match the shape required by
        `kind`.
    :raises ValueError: If `kind` is `CHOICE` and `value` is not one of
        `choices`, or if `kind` is `STRING`/`PATH`/`CHOICE` and `value`
        is an empty (or whitespace-only) string.
    :raises AssertionError: If `kind` is not one of the known
        :class:`CompilerConfigurationFieldKind` members (unreachable in
        practice, since `kind` is itself validated to be a member of
        that enum before this function is called).
    """
    if kind in {
        CompilerConfigurationFieldKind.STRING,
        CompilerConfigurationFieldKind.PATH,
    }:
        _normalize_nonempty_string(
            value,  # type: ignore[arg-type]
            f"Compiler configuration value {key!r}",
        )

        return

    if kind is CompilerConfigurationFieldKind.BOOLEAN:
        if not isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"Compiler configuration value {key!r} "
                "must be a boolean."
            )

        return

    if kind is CompilerConfigurationFieldKind.STRING_LIST:
        if (
            not isinstance(
                value,
                (
                    list,
                    tuple,
                ),
            )
            or not all(
                isinstance(
                    item,
                    str,
                )
                for item in value
            )
        ):
            raise TypeError(
                f"Compiler configuration value {key!r} "
                "must be a string list."
            )

        return

    if kind is CompilerConfigurationFieldKind.STRING_MAP:
        if (
            not isinstance(
                value,
                Mapping,
            )
            or not all(
                isinstance(
                    item_key,
                    str,
                )
                and isinstance(
                    item_value,
                    str,
                )
                for item_key, item_value in value.items()
            )
        ):
            raise TypeError(
                f"Compiler configuration value {key!r} "
                "must be a string mapping."
            )

        return

    if kind is CompilerConfigurationFieldKind.INTEGER_LIST:
        if (
            not isinstance(
                value,
                (
                    list,
                    tuple,
                ),
            )
            or not all(
                isinstance(
                    item,
                    int,
                )
                and not isinstance(
                    item,
                    bool,
                )
                for item in value
            )
        ):
            raise TypeError(
                f"Compiler configuration value {key!r} "
                "must be an integer list."
            )

        return

    if kind is CompilerConfigurationFieldKind.CHOICE:
        normalized_value = _normalize_nonempty_string(
            value,  # type: ignore[arg-type]
            f"Compiler configuration value {key!r}",
        )

        if normalized_value not in choices:
            raise ValueError(
                f"Compiler configuration value {key!r} "
                "must be one of: "
                f"{', '.join(choices)}."
            )

        return

    raise AssertionError(
        "Unhandled compiler configuration field kind: "
        f"{kind}."
    )