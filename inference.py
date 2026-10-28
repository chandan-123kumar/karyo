from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from harness_auth import read_token, login
from karyo_config import load_config


def error_details(exc):
    """Safe diagnostics: never include request headers, credentials or raw bodies."""
    # SDKs may wrap the HTTP exception (or raise a parsing error while handling
    # it). Walk the exception chain so an underlying 401/403 isn't lost.
    current = exc
    seen = set()
    status = None
    cause_type = None
    network_error = False
    network_types = {
        "RequestError", "NetworkError", "TransportError", "ConnectError",
        "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
        "TimeoutException",
    }
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        candidate = getattr(response, "status_code", None)
        if isinstance(candidate, int):
            status = candidate
            break
        if cause_type is None and current is not exc:
            cause_type = type(current).__name__
        if any(cls.__name__ in network_types for cls in type(current).mro()):
            network_error = True
        current = current.__cause__ or current.__context__

    messages = {
        400: "The provider rejected the request. Check model settings and tool schemas.",
        401: "Authentication failed. Run karyo login and check HF_TOKEN overrides.",
        402: "Inference credits or billing are required on your Hugging Face account.",
        403: "Access denied. Check token inference permissions and model access.",
        404: "The model or endpoint was not found on this provider. Try --provider or --model.",
        429: "The provider rate limit was reached. Retry later.",
    }
    message = messages.get(status)
    if message is None:
        if isinstance(status, int) and status >= 500:
            message = "The inference service failed. Retry later."
        elif network_error or isinstance(exc, OSError):
            message = "Could not reach Hugging Face or the selected provider. Check network access and proxy settings."
        else:
            message = "Request failed. Check the error type and trace for the failing call."
    details = {"type": type(exc).__name__, "http_status": status, "message": message}
    if cause_type is not None:
        details["cause_type"] = cause_type
    return details

def create_client(provider=None, timeout=None):
    if provider is None or timeout is None:
        config = load_config()
        provider = config['provider'] if provider is None else provider
        timeout = config['timeout_seconds'] if timeout is None else timeout
    load_dotenv(Path.cwd() / ".env", override=False)
    token = read_token()
    if not token:
        token = login()

    return InferenceClient(provider=provider, api_key=token, timeout=timeout)
