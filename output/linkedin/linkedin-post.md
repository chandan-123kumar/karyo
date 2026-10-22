I started with a Python script that called an LLM. Now I’m building Karyo—a terminal coding assistant whose actions I can inspect.

The most interesting part hasn’t been getting a response from the model. It’s understanding everything that happens around that response.

So far, I’ve built:

• A one-command installer and a `karyo` CLI.
• A local browser setup flow for a Hugging Face token.
• Configurable models and inference providers.
• File operations, search, and shell tools in an agent loop.
• Input/output token accounting for each model call.
• Automatic session recording: user queries, model responses, tool calls, and tool results, linked by session and turn.
• A local browser dashboard to inspect the conversation, individual LLM calls, timing, and raw JSON.

One lesson came from a real failure: a generic “check your token” message hid a provider’s MODEL_NOT_FOUND response. Recording the right diagnostics made the problem visible—and led me to make provider selection configurable.

The architecture is deliberately small: a Python CLI, hosted inference through Hugging Face, local JSONL session logs, and a read-only localhost viewer. The logs stay on the user’s machine; inference prompts still go to the selected provider.

The CLI and installer are public. The latest session-recording and dashboard work is on my local feature branch as I prepare it for a commit.

Still an early project, but building the agent loop and the tracing together has taught me a lot about how coding assistants work.

What would you want to inspect first in an agent trace: tool execution, changes in context, token usage, or failures?

https://github.com/chandan-123kumar/karyo

#BuildInPublic #Python #AIAgents #OpenSource #LLM
