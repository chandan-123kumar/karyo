# Karyo

A terminal coding assistant using `Qwen/Qwen3-Coder-Next` through Hugging Face's
Featherless AI provider by default. Includes conversation memory, file operations, shell execution,
recursive text search, public web search, workspace-scoped patch application, and diff review.

## Install

On **macOS, Linux, or Windows with WSL**, run:

```sh
curl -fsSL https://raw.githubusercontent.com/chandan-123kumar/karyo/main/install.sh | sh
```

The installer installs [uv](https://docs.astral.sh/uv/), provisions Python 3.13
if needed, installs the `karyo` command, and opens a browser setup page.
Paste your own [Hugging Face token](https://huggingface.co/settings/tokens) with
**Make calls to Inference Providers** permission and click **Save token and continue**.
Hugging Face inference credits/billing are required.

Open a new terminal after installation:

```sh
cd your-project
karyo
```

Type `/exit` or press Ctrl+C to quit. File tools and patch application are limited
to the launch workspace. Shell commands still run with your user permissions and
can access other locations; use Karyo in projects you trust and keep backups.
Native Windows is not supported by the shell tool; use WSL.

Already have uv? Install directly:

```sh
uv tool install --python 3.13 --from https://github.com/chandan-123kumar/karyo/archive/refs/heads/main.zip karyo
uv tool update-shell
```

The browser setup opens automatically on first launch if no token is configured.
If a browser cannot open, use the local URL printed in your terminal or run:

```sh
karyo login --terminal
```

## Token usage

Choose a provider or model explicitly when needed:

```sh
uv run karyo --provider featherless-ai --model Qwen/Qwen3-Coder-Next --trace-content
```

The packaged default is Featherless AI. If it returns HTTP 404, the model or route may be
unavailable there even if the Hugging Face catalog still lists it. Provider
selection is explicit; Karyo does not silently switch providers. Failed traces
include safe error type, HTTP status, and guidance, without raw error bodies.

Each model request prints provider-reported input, output, and total token counts.
Type `/usage` to see session totals; `/exit` also prints the summary.
Input usage includes the conversation context sent again on each request, not
just your latest message. Tool follow-up calls count as separate model requests.
These counts come from the provider's response `usage` field, not a local tokenizer.

## Session recording and local viewer

Every interactive `karyo` launch immediately creates a session file in
`~/.local/share/karyo/traces` (or `$XDG_DATA_HOME/karyo/traces`). No tracing flag
is required. Login, logout and viewer commands do not create chat sessions.

Each session stores numbered user turns, full LLM request/response snapshots,
model responses, tool calls and tool results, token counts, timing, and session
start/end events. Requests are written before inference; tool calls are written
before execution and results immediately afterward. Graceful exit, Ctrl+C and
errors record a closing status. A forced process kill can leave an open session
or pending call; those statuses do not prove the process is still running.

Start Karyo in one terminal:

```sh
uv run karyo
```

Open the dashboard in another:

```sh
uv run karyo trace serve
```

Select a session's **Conversation** entry for the chronological user/model/tool
history. Select a model call for input/output snapshots, raw JSON, token counts,
and messages added since the preceding request. The viewer refreshes every second.
Empty sessions appear immediately, before a user enters a question.

Use `--trace traces/session.jsonl` to select a different output file, and
`karyo trace serve --directory traces` to view that directory. `--trace-content`
remains accepted for compatibility; full content is now recorded by default.
Files append across runs with distinct session IDs. New files use owner-only
permissions. Prompts and tool results may contain private data; authentication
headers are not recorded, but secrets within conversation content are not redacted.

Each JSONL line is an event. Match `session_id`, `turn`, `request`, and tool call
IDs to relate events. Failed requests include safe diagnostic metadata. Missing
usage is `null`, not zero. Inputs are SDK-level arguments, not the provider's
internal prompt template. `jq . path/to/session.jsonl` provides a readable view.

The viewer is read-only, binds to `127.0.0.1`, and requires its temporary secret
URL. `--no-browser` disables automatic opening and `--port 8765` chooses a port.
Ctrl+C stops the viewer independently of Karyo. It reads `.jsonl` files directly
in the selected directory, supports older traces, and skips incomplete lines.
This first version reloads files on each poll; separate large archives into
another directory. Recording sessions does not automatically resume conversation
memory when Karyo restarts.

## Credentials

Previously installed as `ai-harness`? Run the installer above to install `karyo`,
then optionally run `uv tool uninstall ai-harness`. Your previously saved token
is still recognized. `karyo logout` removes both the current and legacy token files.

The setup page runs only on `127.0.0.1`, closes after a successful submission,
and expires after five minutes. Tokens are sent to Hugging Face to validate them;
Karyo has no hosted token collection service. The saved token lives in
`~/.config/karyo/token` (or `$XDG_CONFIG_HOME/karyo/token`) with owner-only
file permissions. This file is plaintext, not an encrypted keychain.

`HF_TOKEN` from the environment takes precedence, followed by a `.env` in the
current working directory, followed by the saved token. Tokens are not included
in the installed package. Token validation confirms the account credential;
provider permission, model availability, and billing are checked when inference runs.

```sh
karyo login     # Replace the saved token through the browser
karyo logout    # Delete the saved token (does not unset HF_TOKEN or edit .env)
```

## Update or uninstall

To update an installation made from GitHub, run:

```sh
karyo --update
```

This fetches the latest version from `main`. You can also run the underlying
`uv tool install --refresh --reinstall ...` command if needed. Your saved
Hugging Face token and Karyo configuration remain in place.

To uninstall:

```sh
uv tool uninstall karyo
```

Run `karyo logout` before uninstalling to remove the saved credential.
Install [ripgrep](https://github.com/BurntSushi/ripgrep#installation) for the search
tool (`brew install ripgrep` on macOS or `sudo apt install ripgrep` on Ubuntu/WSL).
Other tools work without it.

## Development

Python 3.10+ is supported. The installer selects Python 3.13.

```sh
uv sync --locked
uv run karyo
uv run python -m unittest discover -v
uv build
```

The CLI operates in the directory where you launch it. Conversation memory lasts
for the current session.

Karyo keeps the first nonempty request as the session goal and includes it in
model context after it falls outside the recent four-turn window. Use `/goal` to
view it or `/goal <new goal>` to replace it. Model requests keep complete recent
turns and shorten tool results longer than 6,000 characters; full conversation
history and tool results remain in memory and session traces.

## MCP tools

Karyo supports Streamable HTTP MCP servers. Configure servers in
`~/.config/karyo/mcp.json` (or `$XDG_CONFIG_HOME/karyo/mcp.json`). Every server
must have an explicit `allow_tools` list; only those tools are sent to the model
and can be called. For example, to expose AWS documentation search and reading:

```json
{
  "servers": {
    "aws-docs": {
      "transport": "streamable_http",
      "url": "https://aws-mcp.us-east-1.api.aws/mcp",
      "allow_tools": [
        "aws___search_documentation",
        "aws___read_documentation"
      ]
    }
  }
}
```

AWS documentation tools do not need AWS credentials. This first version supports
unauthenticated HTTPS MCP servers; HTTP auth and local stdio servers are not
configured yet.

## Temporary tools

During a session, Karyo can propose a temporary wrapper around `search_files`,
`run_shell`, or `write_temp_file`. The CLI shows the proposed name, description,
target, arguments, and fixed values, then requires explicit user approval before
adding it to the model's tool catalog. Approved wrappers remain in memory until
the session ends; no tool code or definition is persisted. A session can create
at most five temporary tools, and each invocation is capped at 30 seconds.
The bounded `write_temp_file` tool is also available directly for scratch files;
it uses the same session-owned temporary directory.
Temporary tools use bounded handlers; they do not execute model-generated
Python code. `write_temp_file` writes only inside a private session directory
under `/tmp`, limits each file to 1 MB, total temporary storage to 5 MB, and the
writer to 50 managed files. Karyo removes the directory when the session ends.
Shell wrappers still run with the user's permissions.

Configuration loads in this order (later values override earlier ones):

1. Packaged `karyo_config/defaults.json`.
2. `~/.config/karyo/config.json` (or `$XDG_CONFIG_HOME/karyo/config.json`).
3. `config.json` in the current directory, or the file supplied with `--config`.
4. Explicit `--provider` and `--model` options.

```json
{
  "provider": "featherless-ai",
  "model": "Qwen/Qwen3-Coder-Next",
  "max_tokens": 256,
  "timeout_seconds": 60
}
```

Overrides can contain just the keys you want to change. `max_tokens` limits each
model response; increase it if longer answers or tool arguments are needed.
Tokens remain in the credential store or environment, not this configuration.
