"""File reading, writing, and workspace listing tools."""

from fnmatch import fnmatchcase
from pathlib import Path


WORKSPACE_ROOT = Path.cwd().resolve()


def resolve_workspace_path(path):
    """Resolve a path and reject paths that escape the launch directory."""
    target = (WORKSPACE_ROOT / Path(path).expanduser()).resolve()
    if not target.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("outside_workspace")
    return target


def write_file(path, content, overwrite=False):
    """Write UTF-8 text to a path inside the workspace."""
    if not isinstance(path, str) or not path.strip() or not isinstance(content, str):
        return _error("invalid_argument", "path and content must be strings")
    if not isinstance(overwrite, bool):
        return _error("invalid_argument", "overwrite must be a boolean")
    try:
        target = resolve_workspace_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w" if overwrite else "x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        return _error("file_exists", "Set overwrite=true to replace the file")
    except ValueError:
        return _error("outside_workspace", "path must stay inside the workspace")
    except OSError:
        return _error("write_failed", "Could not write the requested file")
    return {"ok": True, "path": str(target)}


def read_file(path):
    """Read a UTF-8 text file inside the workspace."""
    try:
        target = resolve_workspace_path(path)
        with target.open("r", encoding="utf-8") as f:
            return f.read()
    except ValueError:
        return _error("outside_workspace", "path must stay inside the workspace")
    except (OSError, UnicodeError):
        return _error("read_failed", "Could not read the requested text file")

def list_files(path=".", pattern=None):
    """List immediate directory entries, optionally matching a filename glob.

    Paths are relative to the workspace. Symlinks are listed but not followed.
    Returns a JSON-serializable result suitable for a model tool response.
    """
    if not isinstance(path, str) or not path.strip():
        return _error("invalid_argument", "path must be a non-empty string")
    if pattern is not None and not isinstance(pattern, str):
        return _error("invalid_argument", "pattern must be a string or null")

    try:
        directory = (WORKSPACE_ROOT / path).resolve()
        if not directory.is_relative_to(WORKSPACE_ROOT):
            return _error("outside_workspace", "path must stay inside the workspace")
        if not directory.exists():
            return _error("not_found", "The requested directory does not exist")
        if not directory.is_dir():
            return _error("not_directory", "path must point to a directory")

        entries = []
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            if pattern is not None and not fnmatchcase(entry.name, pattern):
                continue
            if entry.is_symlink():
                entry_type = "symlink"
            elif entry.is_dir():
                entry_type = "directory"
            elif entry.is_file():
                entry_type = "file"
            else:
                entry_type = "other"
            entries.append({
                "path": entry.relative_to(WORKSPACE_ROOT).as_posix(),
                "type": entry_type,
            })

        return {
            "ok": True,
            "path": directory.relative_to(WORKSPACE_ROOT).as_posix(),
            "entries": entries,
        }
    except PermissionError:
        return _error("permission_denied", "Cannot access the requested directory")
    except (ValueError, RuntimeError):
        return _error("invalid_path", "The requested path cannot be resolved")
    except OSError:
        return _error("filesystem_error", "Could not list the requested directory")


def _error(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}
