"""Git operations wrapper using subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git command fails."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


def _run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}",
            returncode=result.returncode,
        )
    return result


def init(repo_path: Path) -> None:
    """Initialize a new git repository."""
    repo_path.mkdir(parents=True, exist_ok=True)
    _run(["init"], cwd=repo_path)


def is_repo(path: Path) -> bool:
    """Check if a directory is a git repository."""
    result = _run(["rev-parse", "--git-dir"], cwd=path, check=False)
    return result.returncode == 0


def add_all(repo_path: Path) -> None:
    """Stage all changes."""
    _run(["add", "."], cwd=repo_path)


def commit(repo_path: Path, message: str) -> bool:
    """Create a commit. Returns True if a commit was made, False if nothing to commit."""
    result = _run(["commit", "-m", message], cwd=repo_path, check=False)
    if result.returncode == 0:
        return True
    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
        return False
    raise GitError(f"git commit failed: {result.stderr.strip()}", result.returncode)


def push(repo_path: Path) -> None:
    """Push to remote."""
    _run(["push"], cwd=repo_path)


def pull(repo_path: Path) -> None:
    """Pull from remote with rebase."""
    _run(["pull", "--rebase"], cwd=repo_path)


def status(repo_path: Path) -> str:
    """Get git status output."""
    result = _run(["status", "--short"], cwd=repo_path)
    return result.stdout


def has_remote(repo_path: Path) -> bool:
    """Check if the repo has a remote configured."""
    result = _run(["remote"], cwd=repo_path)
    return bool(result.stdout.strip())


def add_remote(repo_path: Path, name: str, url: str) -> None:
    """Add a remote to the repository."""
    _run(["remote", "add", name, url], cwd=repo_path)


def diff_stat(repo_path: Path) -> str:
    """Get diff stat for staged and unstaged changes."""
    result = _run(["diff", "--stat", "HEAD"], cwd=repo_path, check=False)
    return result.stdout
