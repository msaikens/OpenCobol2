"""Local Git repository domain and process contracts."""

from opencobol2.git.branches import (
    parse_git_branch_for_each_ref_output,
)
from opencobol2.git.history import (
    parse_git_log_output,
)
from opencobol2.git.models import (
    GitBranch,
    GitBranchCreateResult,
    GitBranchDeleteResult,
    GitBranchSwitchResult,
    GitChange,
    GitChangeStatus,
    GitCommandExecutionStatus,
    GitCommandResult,
    GitCommitLogEntry,
    GitCommitResult,
    GitFetchResult,
    GitPullResult,
    GitPushResult,
    GitRemote,
    GitRemoteAddResult,
    GitRemoteRemoveResult,
    GitRemoteRenameResult,
    GitRepositoryCloneResult,
    GitRepositoryCreateResult,
    GitRepositoryStatus,
    GitTag,
    GitTagCreateResult,
    GitTagDeleteResult,
)
from opencobol2.git.process import (
    invoke_git_process,
)
from opencobol2.git.remotes import (
    parse_git_remote_v_output,
)
from opencobol2.git.status import (
    parse_git_status_porcelain_v2,
)
from opencobol2.git.tags import (
    parse_git_tag_for_each_ref_output,
)


__all__ = [
    "GitBranch",
    "GitBranchCreateResult",
    "GitBranchDeleteResult",
    "GitBranchSwitchResult",
    "GitChange",
    "GitChangeStatus",
    "GitCommandExecutionStatus",
    "GitCommandResult",
    "GitCommitLogEntry",
    "GitCommitResult",
    "GitFetchResult",
    "GitPullResult",
    "GitPushResult",
    "GitRemote",
    "GitRemoteAddResult",
    "GitRemoteRemoveResult",
    "GitRemoteRenameResult",
    "GitRepositoryCloneResult",
    "GitRepositoryCreateResult",
    "GitRepositoryStatus",
    "GitTag",
    "GitTagCreateResult",
    "GitTagDeleteResult",
    "invoke_git_process",
    "parse_git_branch_for_each_ref_output",
    "parse_git_log_output",
    "parse_git_remote_v_output",
    "parse_git_status_porcelain_v2",
    "parse_git_tag_for_each_ref_output",
]