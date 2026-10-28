"""Dispatch a registered temporary-file tool to the active CLI session."""

from contextvars import ContextVar


_active_writer = ContextVar("karyo_temporary_file_writer", default=None)


def bind_temporary_file_writer(writer):
    """Bind the current session's writer and return a token for reset()."""
    return _active_writer.set(writer)


def reset_temporary_file_writer(token):
    _active_writer.reset(token)


def write_temp_file(path, content, overwrite=False):
    """Write within the private temporary directory for the active session."""
    writer = _active_writer.get()
    if writer is None:
        return {"ok": False, "error": {"code": "temporary_file_session_unavailable"}}
    return writer(path, content, overwrite)
