"""Compiler provider domain models."""

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
    """Describes how a compiler provider performs compilation."""

    LOCAL_PROCESS = "local-process"
    REMOTE_JOB = "remote-job"


class CompilerConfigurationFieldKind(StrEnum):
    """Describes a provider configuration field's value type."""

    STRING = "string"
    PATH = "path"
    BOOLEAN = "boolean"
    STRING_LIST = "string-list"
    STRING_MAP = "string-map"
    INTEGER_LIST = "integer-list"
    CHOICE = "choice"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerConfigurationField:
    """Describes one user-configurable compiler provider setting."""

    key: str
    title: str
    kind: CompilerConfigurationFieldKind
    required: bool = False
    description: str = ""
    default: JsonValue = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the configuration field."""
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
    """Describes one configured compiler provider instance."""

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
        """Validate and freeze compiler profile configuration."""
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
    """Contract implemented by compiler provider integrations."""

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier."""
        ...

    @property
    def display_name(self) -> str:
        """Return the user-facing provider name."""
        ...

    @property
    def execution_kind(self) -> CompilerExecutionKind:
        """Return how the provider performs compilation."""
        ...

    @property
    def configuration_fields(
        self,
    ) -> tuple[CompilerConfigurationField, ...]:
        """Return the provider's configurable settings."""
        ...

    def validate_profile(
        self,
        profile: CompilerProfile,
    ) -> None:
        """Validate a compiler profile for this provider."""
        ...


def _freeze_configuration(
    configuration: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    """Validate and freeze compiler profile configuration."""
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
    """Validate and freeze compiler environment overrides."""
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
    """Validate and freeze one JSON-compatible configuration value."""
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
    """Validate and normalize one required string."""
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
    """Validate one provider configuration field value."""
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