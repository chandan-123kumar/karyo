from tools.file_operations import list_files
from tools.file_operations import read_file
from tools.file_operations import write_file
from tools.temporary_files import write_temp_file
from tools.shell import run_shell
from tools.search import search_files
from tools.code_changes import apply_patch, show_diff
from tools.web_search import web_search

TOOL_REGISTRY = {
    "search_files": {
        "handler": search_files,
        "schema": {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search text recursively inside the workspace with ripgrep. Returns file paths, line numbers, and matching lines. Respects ignore files, skips binary files, and defaults to skipping hidden files. Output is capped at 20 KB with a 15-second timeout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regular expression to search for"},
                        "path": {"type": "string", "description": "Search directory or file; defaults to current directory"},
                        "glob": {"type": ["string", "null"], "description": "Optional filename filter, e.g. *.py"},
                        "hidden": {"type": "boolean"},
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            },
        },
    },
    "run_shell": {
        "handler": run_shell,
        "schema": {
            "type": "function",
            "function": {
                "name": "run_shell",
                "description": "Execute a command with /bin/sh using a working directory inside the workspace. Commands still run with the user's permissions. Return bounded stdout/stderr, exit code, truncation flags, and timeout status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": ["string", "null"]},
                        "timeout_seconds": {"type": "number", "exclusiveMinimum": 0},
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        },
    },
    "write_file": {
        "handler": write_file,
        "schema": {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a UTF-8 file inside the workspace. Relative paths use the current directory. Set overwrite=true to replace contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
    },
    "write_temp_file": {
        "handler": write_temp_file,
        "schema": {
            "type": "function",
            "function": {
                "name": "write_temp_file",
                "description": (
                    "Write a temporary UTF-8 file in the active Karyo session's private /tmp directory. "
                    "Files are removed when the session ends. Each file is limited to 1 MB; "
                    "the session writer is limited to 5 MB and 50 managed files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path inside the private session temporary directory."},
                        "content": {"type": "string", "description": "UTF-8 file contents, up to 1 MB."},
                        "overwrite": {"type": "boolean", "description": "Replace a file previously created by this tool; defaults to false."},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
    },
    "read_file": {
        "handler": read_file,
        "schema": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read UTF-8 text from a path inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                }
            }
        }

    },
    "list_files": {
        "handler": list_files,
        "schema": {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List immediate workspace entries, optionally filtered by a filename glob.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "pattern": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
        },
    },
    "apply_patch": {
        "handler": apply_patch,
        "schema": {
            "type": "function",
            "function": {
                "name": "apply_patch",
                "description": "Apply a unified diff inside the workspace after a clean applicability check. The workspace must be the root of a Git repository. Review the result with show_diff.",
                "parameters": {
                    "type": "object",
                    "properties": {"patch": {"type": "string"}},
                    "required": ["patch"],
                    "additionalProperties": False,
                },
            },
        },
    },
    "show_diff": {
        "handler": show_diff,
        "schema": {
            "type": "function",
            "function": {
                "name": "show_diff",
                "description": "Show changed file paths and a bounded diff, including new untracked files, from the workspace Git repository.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
    },
    "web_search": {
        "handler": web_search,
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the public web for external or current information. Do not use this for facts about files in the user's local workspace; use list_files, read_file, or search_files instead. Returns untrusted result titles, URLs, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query, up to 500 characters."},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
    },
}


def get_tool_schemas():
    return [tool["schema"] for tool in TOOL_REGISTRY.values()]
