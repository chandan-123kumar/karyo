import shutil
import subprocess
import tempfile
from tools.file_operations import resolve_workspace_path


def search_files(pattern, path=".", glob=None, hidden=False):
    """Search file contents recursively using ripgrep; pattern is a regex."""
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    if glob is not None and not isinstance(glob, str):
        raise ValueError("glob must be a string or null")
    if not isinstance(hidden, bool):
        raise ValueError("hidden must be a boolean")
    executable = shutil.which("rg")
    if executable is None:
        return {"ok": False, "error": {"code": "ripgrep_not_installed"}}

    command = [executable, "--no-config", "--line-number", "--with-filename",
               "--no-heading", "--color", "never"]
    if glob is not None:
        command.extend(["--glob", glob])
    if hidden:
        command.append("--hidden")
    try:
        search_path = resolve_workspace_path(path)
    except ValueError:
        return {"ok": False, "error": {"code": "outside_workspace"}}
    command.extend(["--", pattern, str(search_path)])

    # Spool output to disk so broad searches don't fill Python's memory.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        timed_out = False
        try:
            process = subprocess.run(command, stdout=output, stderr=errors,
                                     stdin=subprocess.DEVNULL, timeout=15)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            timed_out, exit_code = True, None
        output.seek(0)
        text = output.read(20001)
        errors.seek(0)
        return {
            "ok": exit_code in (0, 1) and not timed_out,
            "matches": text[:20000].decode("utf-8", errors="replace"),
            "stderr": errors.read(2000).decode("utf-8", errors="replace"),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": len(text) > 20000,
        }
