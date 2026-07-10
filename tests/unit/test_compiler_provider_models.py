"""Unit tests for compiler provider domain models."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler.providers import (
    CompilerConfigurationField,
    CompilerConfigurationFieldKind,
    CompilerProfile,
)


def test_configuration_field_normalizes_values() -> None:
    field = CompilerConfigurationField(
        key=" path ",
        title=" Compiler ",
        kind="path",
        description=" explicit path ",
    )

    assert field.key == "path"
    assert field.title == "Compiler"
    assert (
        field.kind
        is CompilerConfigurationFieldKind.PATH
    )
    assert field.description == "explicit path"


def test_choice_field_requires_choices() -> None:
    with pytest.raises(
        ValueError,
        match="require choices",
    ):
        CompilerConfigurationField(
            key="mode",
            title="Mode",
            kind=CompilerConfigurationFieldKind.CHOICE,
        )


def test_non_choice_field_rejects_choices() -> None:
    with pytest.raises(
        ValueError,
        match="Only choice",
    ):
        CompilerConfigurationField(
            key="path",
            title="Path",
            kind=CompilerConfigurationFieldKind.PATH,
            choices=(
                "one",
            ),
        )


def test_profile_normalizes_and_freezes_configuration() -> None:
    configuration = {
        "paths": [
            "one",
            "two",
        ],
        "nested": {
            "enabled": True,
        },
    }

    environment = {
        "COBDIR": "one",
    }

    profile = CompilerProfile(
        provider_id=" provider ",
        display_name=" Profile ",
        configuration=configuration,
        environment_overrides=environment,
    )

    configuration[
        "paths"
    ].append(
        "three",
    )

    environment[
        "COBDIR"
    ] = "two"

    assert profile.provider_id == "provider"
    assert profile.display_name == "Profile"

    assert profile.configuration[
        "paths"
    ] == (
        "one",
        "two",
    )

    assert profile.configuration[
        "nested"
    ][
        "enabled"
    ] is True

    assert profile.environment_overrides[
        "COBDIR"
    ] == "one"

    with pytest.raises(
        TypeError,
    ):
        profile.configuration[
            "new"
        ] = "value"  # type: ignore[index]


def test_profile_rejects_unsupported_configuration_value() -> None:
    with pytest.raises(
        TypeError,
        match="Unsupported compiler configuration",
    ):
        CompilerProfile(
            provider_id="provider",
            display_name="Profile",
            configuration={
                "path": Path(
                    "compiler",
                ),
            },  # type: ignore[dict-item]
        )


def test_profile_rejects_empty_provider_id() -> None:
    with pytest.raises(
        ValueError,
        match="provider ID must not be empty",
    ):
        CompilerProfile(
            provider_id=" ",
            display_name="Profile",
        )


def test_profile_rejects_nonstring_environment_value() -> None:
    with pytest.raises(
        TypeError,
        match="values must be strings",
    ):
        CompilerProfile(
            provider_id="provider",
            display_name="Profile",
            environment_overrides={
                "COMPILER_HOME": 1,
            },  # type: ignore[dict-item]
        )