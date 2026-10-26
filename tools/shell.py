import math
import os
import signal
import subprocess
import tempfile

from tools.file_operations import resolve_workspace_path


MAX_OUTPUT_CHARS = 20000


def run_shell(command, cwd=None, timeout_seconds=30):
    """Execute a command using /bin/sh and capture its output."""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a non-empty string")
    if cwd is not None and not isinstance(cwd, str):
        raise ValueError("cwd must be a string or null")
    if cwd is not None and not cwd.strip():
        raise ValueError("cwd must be a non-empty path or null")
    if (isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        raise ValueError("timeout_seconds must be positive and finite")

    try:
        working_directory = resolve_workspace_path(cwd or ".")
    except ValueError:
        return {"ok": False, "error": {"code": "outside_workspace"}}
    if not working_directory.is_dir():
        return {"ok": False, "error": {"code": "not_directory"}}

    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        with subprocess.Popen(
            command, shell=True, executable="/bin/sh", cwd=working_directory,
            stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file,
            start_new_session=True,
        ) as process:
            timed_out = False
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read(MAX_OUTPUT_CHARS + 1).decode("utf-8", errors="replace")
        stderr = stderr_file.read(MAX_OUTPUT_CHARS + 1).decode("utf-8", errors="replace")
        stdout_truncated = len(stdout) > MAX_OUTPUT_CHARS
        stderr_truncated = len(stderr) > MAX_OUTPUT_CHARS
        stdout = stdout[:MAX_OUTPUT_CHARS]
        stderr = stderr[:MAX_OUTPUT_CHARS]

    return {
        "ok": process.returncode == 0 and not timed_out,
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "timed_out": timed_out,
    }
