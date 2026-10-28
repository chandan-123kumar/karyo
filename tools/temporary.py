"""Session-only tools defined by the model and approved by the user."""

import json
from pathlib import Path
import re
import tempfile
import sys

from tools.registry import TOOL_REGISTRY


MAX_TEMP_TOOLS_PER_SESSION = 5
MAX_DESCRIPTION_CHARS = 500
MAX_FIXED_ARGUMENTS_CHARS = 8000
MAX_TEMP_FILE_BYTES = 1_000_000
MAX_TEMP_SESSION_BYTES = 5_000_000
MAX_TEMP_FILES_PER_SESSION = 50
MAX_TOOL_EXECUTION_SECONDS = 30
BOUNDED_TARGETS = ("search_files", "run_shell", "write_temp_file")

DEFINE_TEMPORARY_TOOL = "define_temporary_tool"
DEFINE_TEMPORARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": DEFINE_TEMPORARY_TOOL,
        "description": (
            "Propose a session-only wrapper around search_files, run_shell, or write_temp_file. "
            "The user must approve its definition before it becomes available. "
            "At most five can be created per session; each invocation is limited to 30 seconds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short snake_case name; Karyo adds the temp_ prefix."},
                "description": {"type": "string", "description": "What the temporary tool does."},
                "target_tool": {"type": "string", "enum": list(BOUNDED_TARGETS)},
                "expose_arguments": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Target tool arguments the model can supply when calling this wrapper.",
                },
                "fixed_arguments": {
                    "type": "object", "description": "Target tool arguments fixed by this definition.",
                },
            },
            "required": ["name", "description", "target_tool", "expose_arguments", "fixed_arguments"],
            "additionalProperties": False,
        },
    },
}


def _json_type_matches(value, schema):
    expected = schema.get("type")
    expected_types = expected if isinstance(expected, list) else [expected]
    checks = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: type(item) is int,
        "number": lambda item: type(item) in (int, float),
        "boolean": lambda item: type(item) is bool,
        "array": lambda item: isinstance(item, list),
        "object": lambda item: isinstance(item, dict),
        "null": lambda item: item is None,
    }
    return any(checks.get(kind, lambda _item: False)(value) for kind in expected_types)


class TemporaryToolRegistry:
    """Hold approved wrappers in process memory until the CLI session ends."""

    def __init__(self):
        self._tools = {}
        self._temp_directory = tempfile.TemporaryDirectory(prefix="karyo-session-", dir="/tmp")
        self._temp_root = Path(self._temp_directory.name).resolve()
        self._temp_bytes = 0
        self._temp_files = set()

    @property
    def count(self):
        return len(self._tools)

    @property
    def names(self):
        return set(self._tools)

    def schemas(self):
        return [entry["schema"] for entry in self._tools.values()]

    def clear(self):
        self._tools.clear()
        try:
            self._temp_directory.cleanup()
        except OSError as exc:
            print(f"Could not remove temporary tool files ({type(exc).__name__}).", file=sys.stderr)

    def define(self, proposal, approve):
        if self.count >= MAX_TEMP_TOOLS_PER_SESSION:
            return {"ok": False, "error": {"code": "session_tool_limit_reached", "limit": MAX_TEMP_TOOLS_PER_SESSION}}
        try:
            entry = self._validate(proposal)
        except (TypeError, ValueError, KeyError) as exc:
            return {"ok": False, "error": {"code": "invalid_tool_definition", "detail": str(exc)}}
        name = entry["schema"]["function"]["name"]
        if name in self._tools or name in TOOL_REGISTRY or name == DEFINE_TEMPORARY_TOOL:
            return {"ok": False, "error": {"code": "tool_name_unavailable"}}
        approved = bool(approve({
            "name": name,
            "description": entry["schema"]["function"]["description"],
            "target_tool": entry["target_tool"],
            "expose_arguments": entry["expose_arguments"],
            "fixed_arguments": entry["fixed_arguments"],
            "parameters": entry["schema"]["function"]["parameters"],
        }))
        if not approved:
            return {"ok": False, "error": {"code": "user_denied_tool_creation"}}
        self._tools[name] = entry
        return {"ok": True, "name": name, "scope": "current_session", "remaining": MAX_TEMP_TOOLS_PER_SESSION - self.count}

    def invoke(self, name, arguments):
        entry = self._tools.get(name)
        if entry is None:
            return {"ok": False, "error": {"code": "unknown_temporary_tool"}}
        if not isinstance(arguments, dict):
            return {"ok": False, "error": {"code": "invalid_arguments"}}
        exposed = entry["expose_arguments"]
        if any(key not in exposed for key in arguments):
            return {"ok": False, "error": {"code": "unexpected_argument"}}
        for key in entry["required_arguments"]:
            if key not in arguments:
                return {"ok": False, "error": {"code": "missing_argument", "argument": key}}
        target_name = entry["target_tool"]
        if target_name == "write_temp_file":
            target_parameters = TOOL_REGISTRY[target_name]["schema"]["function"]["parameters"]["properties"]
            target_handler = self.write_temp_file
        else:
            target = TOOL_REGISTRY[target_name]
            target_parameters = target["schema"]["function"]["parameters"]["properties"]
            target_handler = target["handler"]
        for key, value in arguments.items():
            if not _json_type_matches(value, target_parameters[key]):
                return {"ok": False, "error": {"code": "invalid_argument_type", "argument": key}}
        merged = dict(arguments)
        merged.update(entry["fixed_arguments"])
        if target_name == "run_shell":
            requested = merged.get("timeout_seconds", MAX_TOOL_EXECUTION_SECONDS)
            if type(requested) in (int, float):
                # Leave margin below the absolute 30-second ceiling for teardown.
                merged["timeout_seconds"] = min(requested, MAX_TOOL_EXECUTION_SECONDS - 3)
        try:
            result = target_handler(**merged)
        except Exception as exc:
            return {"ok": False, "error": {"code": type(exc).__name__}}
        success = not (isinstance(result, dict) and result.get("ok") is False)
        return {"ok": success, "target_tool": target_name, "result": result}

    def write_temp_file(self, path, content, overwrite=False):
        if (not isinstance(path, str) or not path.strip() or Path(path).is_absolute()
                or not isinstance(content, str) or not isinstance(overwrite, bool)):
            return {"ok": False, "error": {"code": "invalid_argument"}}
        if len(content.encode("utf-8")) > MAX_TEMP_FILE_BYTES:
            return {"ok": False, "error": {"code": "temporary_file_too_large",
                                               "limit_bytes": MAX_TEMP_FILE_BYTES}}
        try:
            target = (self._temp_root / path).resolve()
            if target == self._temp_root or not target.is_relative_to(self._temp_root):
                return {"ok": False, "error": {"code": "outside_temporary_directory"}}
            content_bytes = len(content.encode("utf-8"))
            relative_path = target.relative_to(self._temp_root).as_posix()
            if overwrite and target.exists() and relative_path not in self._temp_files:
                return {"ok": False, "error": {"code": "temporary_file_not_managed"}}
            previous_size = target.stat().st_size if overwrite and target.is_file() else 0
            if (len(self._temp_files) >= MAX_TEMP_FILES_PER_SESSION
                    and relative_path not in self._temp_files):
                return {"ok": False, "error": {"code": "temporary_file_count_limit",
                                                   "limit": MAX_TEMP_FILES_PER_SESSION}}
            if self._temp_bytes - previous_size + content_bytes > MAX_TEMP_SESSION_BYTES:
                return {"ok": False, "error": {"code": "temporary_storage_limit",
                                                   "limit_bytes": MAX_TEMP_SESSION_BYTES}}
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w" if overwrite else "x", encoding="utf-8") as stream:
                stream.write(content)
            self._temp_files.add(relative_path)
            self._temp_bytes = self._temp_bytes - previous_size + content_bytes
        except FileExistsError:
            return {"ok": False, "error": {"code": "file_exists"}}
        except OSError:
            return {"ok": False, "error": {"code": "temporary_write_failed"}}
        return {"ok": True, "path": str(target)}

    @staticmethod
    def _validate(proposal):
        if not isinstance(proposal, dict):
            raise TypeError("definition must be an object")
        allowed_keys = {
            "name", "description", "target_tool", "expose_arguments", "fixed_arguments",
        }
        if set(proposal) != allowed_keys:
            raise ValueError("definition must contain exactly the documented fields")
        short_name = proposal.get("name")
        if not isinstance(short_name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", short_name):
            raise ValueError("name must be lowercase snake_case, up to 40 characters")
        description = proposal.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION_CHARS:
            raise ValueError(f"description must contain 1 to {MAX_DESCRIPTION_CHARS} characters")
        target_name = proposal.get("target_tool")
        if target_name not in BOUNDED_TARGETS:
            raise ValueError("target_tool must be a bounded built-in tool")
        exposed = proposal.get("expose_arguments")
        fixed = proposal.get("fixed_arguments")
        if not isinstance(exposed, list) or not all(isinstance(name, str) for name in exposed):
            raise TypeError("expose_arguments must be a list of argument names")
        if len(exposed) != len(set(exposed)):
            raise ValueError("expose_arguments cannot contain duplicates")
        if not isinstance(fixed, dict):
            raise TypeError("fixed_arguments must be an object")
        if len(json.dumps(fixed, ensure_ascii=False)) > MAX_FIXED_ARGUMENTS_CHARS:
            raise ValueError(f"fixed_arguments must be at most {MAX_FIXED_ARGUMENTS_CHARS} characters")

        parameters = TOOL_REGISTRY[target_name]["schema"]["function"]["parameters"]
        target_properties = parameters["properties"]
        if set(exposed) & set(fixed):
            raise ValueError("an argument cannot be both exposed and fixed")
        if not set(exposed).issubset(target_properties) or not set(fixed).issubset(target_properties):
            raise ValueError("arguments must exist in the target tool schema")
        for key, value in fixed.items():
            if not _json_type_matches(value, target_properties[key]):
                raise ValueError(f"fixed argument {key!r} has the wrong type")
        required = parameters.get("required", [])
        if not set(required).issubset(set(exposed) | set(fixed)):
            raise ValueError("expose or fix every required target argument")

        function_name = f"temp_{short_name}"
        function_schema = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": {key: target_properties[key] for key in exposed},
                    "required": [key for key in required if key in exposed],
                    "additionalProperties": False,
                },
            },
        }
        return {
            "schema": function_schema,
            "target_tool": target_name,
            "expose_arguments": exposed,
            "required_arguments": function_schema["function"]["parameters"]["required"],
            "fixed_arguments": fixed,
        }
