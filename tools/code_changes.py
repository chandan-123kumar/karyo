"""Workspace-scoped patch application and diff review tools."""

import os
import subprocess
from pathlib import Path

from tools.file_operations import WORKSPACE_ROOT


MAX_PATCH_CHARS = 1_000_000
MAX_DIFF_CHARS = 40_000


def _git(*args, input_text=None):
    return subprocess.run(
        ["git", *args], cwd=WORKSPACE_ROOT, input=input_text,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15, check=False,
    )


def _workspace_is_repo_root():
    result = _git("rev-parse", "--show-toplevel")
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == WORKSPACE_ROOT


def apply_patch(patch):
    """Apply a unified diff after checking it can be applied cleanly."""
    if not isinstance(patch, str) or not patch.strip():
        return {"ok": False, "error": {"code": "invalid_patch"}}
    if len(patch) > MAX_PATCH_CHARS:
        return {"ok": False, "error": {"code": "patch_too_large"}}
    if not _workspace_is_repo_root():
        return {"ok": False, "error": {"code": "workspace_not_repository_root"}}

    checked = _git("apply", "--check", "--", input_text=patch)
    if checked.returncode != 0:
        return {
            "ok": False,
            "error": {"code": "patch_rejected",
                      "detail": (checked.stderr or checked.stdout)[:4000]},
        }
    applied = _git("apply", "--", input_text=patch)
    if applied.returncode != 0:
        return {"ok": False, "error": {"code": "patch_failed",
                                        "detail": (applied.stderr or applied.stdout)[:4000]}}
    return {"ok": True, "message": "Patch applied. Use show_diff to review the changes."}


def show_diff():
    """Return changed paths and a bounded diff, including untracked files."""
    if not _workspace_is_repo_root():
        return {"ok": False, "error": {"code": "workspace_not_repository_root"}}
    status = _git("status", "--porcelain=v1", "-z")
    if status.returncode != 0:
        return {"ok": False, "error": {"code": "git_status_failed"}}
    changed_paths = []
    untracked = []
    for entry in status.stdout.split("\0"):
        if not entry:
            continue
        path = entry[3:]
        changed_paths.append(path)
        if entry[:2] == "??":
            untracked.append(path)

    tracked_diff = _git("diff", "--no-ext-diff", "--no-renames", "HEAD", "--")
    if tracked_diff.returncode not in (0,):
        return {"ok": False, "error": {"code": "git_diff_failed"}}
    parts = [tracked_diff.stdout]
    for path in untracked:
        added = _git("diff", "--no-index", "--no-ext-diff", "--",
                     os.devnull, path)
        if added.returncode not in (0, 1):
            continue
        parts.append(added.stdout)
    full_diff = "".join(parts)
    return {
        "ok": True,
        "changed_files": changed_paths,
        "diff": full_diff[:MAX_DIFF_CHARS],
        "truncated": len(full_diff) > MAX_DIFF_CHARS,
        "original_chars": len(full_diff),
    }
