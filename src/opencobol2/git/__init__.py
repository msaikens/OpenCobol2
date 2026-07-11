"""Local Git repository domain and process contracts."""

from opencobol2.git.models import (
    GitChange,
    GitChangeStatus,
    GitCommandExecutionStatus,
    GitCommandResult,
    GitCommitResult,
    GitRepositoryStatus,
)
from opencobol2.git.process import (
    invoke_git_process,
)
from opencobol2.git.status import (
    parse_git_status_porcelain_v2,
)


__all__ = [
    "GitChange",
    "GitChangeStatus",
    "GitCommandExecutionStatus",
    "GitCommandResult",
    "GitCommitResult",
    "GitRepositoryStatus",
    "invoke_git_process",
    "parse_git_status_porcelain_v2",
]