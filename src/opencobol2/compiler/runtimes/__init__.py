"""Compiler runtime activation contracts and registries."""

from opencobol2.compiler.runtimes.capabilities import (
    LocalCompilationResult,
    LocalCompilerRuntime,
)
from opencobol2.compiler.runtimes.custom_local import (
    CustomLocalCompilerRuntime,
    CustomLocalCompilerRuntimeFactory,
    CustomLocalCompilerTemplateError,
    build_custom_local_compiler_command,
)
from opencobol2.compiler.runtimes.gnucobol import (
    GnuCobolRuntime,
    GnuCobolRuntimeFactory,
    GnuCobolRuntimeUnavailableError,
)
from opencobol2.compiler.runtimes.models import (
    CompilerRuntime,
    CompilerRuntimeFactory,
)
from opencobol2.compiler.runtimes.registry import (
    CompilerRuntimeFactoryAlreadyRegisteredError,
    CompilerRuntimeFactoryNotFoundError,
    CompilerRuntimeFactoryRegistry,
)


__all__ = [
    "CompilerRuntime",
    "CompilerRuntimeFactory",
    "CompilerRuntimeFactoryAlreadyRegisteredError",
    "CompilerRuntimeFactoryNotFoundError",
    "CompilerRuntimeFactoryRegistry",
    "CustomLocalCompilerRuntime",
    "CustomLocalCompilerRuntimeFactory",
    "CustomLocalCompilerTemplateError",
    "GnuCobolRuntime",
    "GnuCobolRuntimeFactory",
    "GnuCobolRuntimeUnavailableError",
    "LocalCompilationResult",
    "LocalCompilerRuntime",
    "build_custom_local_compiler_command",
]