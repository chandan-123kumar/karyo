# Karyo

A terminal assistant with coding, general, and investing profiles, using `Qwen/Qwen3-Coder-Next` through Hugging Face's
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
uv tool install --no-cache --refresh --reinstall --python 3.13 --from https://github.com/chandan-123kumar/karyo/archive/refs/heads/main.zip karyo
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

The viewer binds to `127.0.0.1` and requires its temporary secret URL. Its replay
button starts inference only when clicked. `--no-browser` disables automatic
opening and `--port 8765` chooses a port.
Ctrl+C stops the viewer independently of Karyo. It reads `.jsonl` files directly
in the selected directory, supports older traces, and skips incomplete lines.
This first version reloads files on each poll; separate large archives into
another directory. Conversation history is also saved in a local SQLite database
at `~/.local/share/karyo/memory.sqlite3` (or `$XDG_DATA_HOME/karyo/memory.sqlite3`).
Histories are scoped to the project directory and stored with owner-only file
permissions. Use `/resume` at the start of a Karyo session to load the latest
conversation for the current project. New turns are saved automatically. The
database stays local and is separate from JSONL traces. Retrieved facts are sent
to the configured model as part of its request, and may also appear in traces.

The same database stores durable memories separately from conversations.
`/remember <fact>` saves a project-specific fact; `/remember --global <fact>`
saves a preference shared across projects. `/memories` lists visible facts and
`/forget <id>` deletes one. Karyo can also propose a durable fact when one may
help future sessions, but asks before saving it. Relevant project facts and
global preferences are added to model context as reference data.
The terminal shows a `/help` hint at startup and suggests relevant commands when
you ask about saved memories or resuming. Phrases such as “remember that I prefer
...” trigger a project/global/skip prompt before Karyo handles the request.

Select a session's **Conversation** view and click **Replay questions in a new
session** to run its recorded user questions in order with fresh conversation
memory. Replay uses the current workspace tools and saved provider credentials,
and can incur provider charges or perform actions through tools. It writes a new
trace linked from the original session. Start the trace viewer from the original
session's project directory; replay is disabled for traces from other projects.
Replays use the provider/model captured in the original session when available.

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
for the current session unless you load a saved project conversation with
`/resume`. Durable memories are loaded separately when relevant.

Karyo keeps the first nonempty request as the session goal and includes it in
model context after it falls outside the recent four-turn window. Use `/goal` to
view it or `/goal <new goal>` to replace it. Model requests keep complete recent
turns and shorten tool results longer than 6,000 characters; full conversation
history and tool results remain in memory and session traces.

## Task profiles

Choose a profile at launch (the default is `coding`):

```sh
karyo --profile coding
karyo --profile general
karyo --profile investing
```

`coding` focuses on code changes and verification. `general` supports research,
planning, analysis, and writing. `investing` focuses on sourced investment
research, screening, portfolio analysis, and calculations, with explicit data
dates and assumptions. It instructs the model not to execute trades or move funds.
Profiles use the same existing tools and model; they do not add market-data or
brokerage integrations, change credentials, or enforce shell permissions.

Set a default and optional parameters in `config.json` or
`~/.config/karyo/config.json` (or `$XDG_CONFIG_HOME/karyo/config.json`):

```json
{
  "profile": "investing",
  "profiles": {
    "investing": {
      "market": "India",
      "currency": "INR",
      "objective": "long-term research",
      "horizon_years": 5,
      "risk_tolerance": "moderate",
      "screen": {
        "max_debt_to_equity": 0.5,
        "min_revenue_growth_pct": 10
      }
    },
    "general": {"language": "English"}
  }
}
```

These are illustrative research criteria, not recommended investments. Parameters
are flexible JSON reference data for the model, not an executable screening
engine; only the selected profile's parameters are sent. Never put credentials
in parameters, which appear in traces. Configuration precedence is packaged
defaults, user configuration, then project configuration (or `--config PATH`).
Parameter keys merge within each profile; nested values such as `screen` are
replaced as a whole. `--profile` overrides the configured profile. The active
profile appears at startup and is recorded with its parameters for trace replay.
You can activate and configure investing directly in the terminal:

```text
>> /investing setup
```

The guided menu offers market (India, US, or another market), currency, holding
period (intraday, several days, several weeks, or long-term), experience, capital,
and total portfolio loss limit. Enter keeps a setting; `/cancel` discards setup.
Amounts use the selected currency. Capital must be positive when supplied; the
loss limit can be zero and cannot exceed supplied capital. Use `clear` to unset
an amount. Changing currency clears previous amounts without converting them.
These are research inputs, not an enforced loss cap or permission to trade.

`/investing` shows the settings. After confirming setup, the investing profile
becomes active for subsequent questions. Changes stay in the session until you
run `/investing save`, which writes to `--config PATH` or the current project's
`config.json`, preserving other settings and profiles. It also makes investing
the default in that file. No model requests are needed to configure settings.
Existing screening parameters are retained. Settings and subsequent changes are
recorded in session traces and respected during replay.

Use `--profile` at launch for other profiles; `/resume` loads the previous
conversation into the currently selected profile.

For the offline investing engine evaluation, see the
[backtesting comparison prototype](experiments/backtesting_comparison/README.md).
It verifies Backtesting.py on synthetic data in an optional isolated environment;
it does not connect to a broker or demonstrate investment returns.

## GitHub through gh

Karyo can use GitHub CLI through its existing shell tool when a suitable GitHub
MCP tool is unavailable, or when you explicitly ask it to use `gh`. Install
[GitHub CLI](https://cli.github.com/), then authenticate in your own terminal:

```sh
gh auth login
gh auth status
```

Launch Karyo from a terminal where `gh` is on PATH. For example, ask "List my
GitHub repositories" or "Read issue 42 in OWNER/REPO using gh". Karyo is
instructed to check availability and authentication, discover your username,
use structured results, and distinguish owned repositories from all repositories
your account can access. No MCP configuration or separate Karyo token is needed.
Interactive login and permission changes must be completed in your own terminal.

This routing and confirmation guidance is model-driven, not a shell permission
boundary. The shell tool retains your user permissions and does not enforce
per-command approval. Do not expose credentials in commands or tool output,
which are recorded in session traces.

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
  "max_tokens": 1024,
  "timeout_seconds": 60
}
```

Overrides can contain just the keys you want to change. `max_tokens` limits each
model response; increase it if longer answers or tool arguments are needed.
Tokens remain in the credential store or environment, not this configuration.
