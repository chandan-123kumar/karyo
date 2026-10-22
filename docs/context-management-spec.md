# Karyo: simple context management

Status: implemented · 2026-10-22

## Goal

Send less conversation history to the LLM while continuing to save the complete session locally.

## First version

Before each LLM call:

1. Include the current user goal.
2. Keep the current user turn and the previous three user turns.
3. Shorten tool results longer than 6,000 characters in the outgoing request.
4. Send this reduced context to the model. Keep original messages unchanged in memory and session logs.

A turn includes a user query and all following assistant messages, tool calls, and tool results until the next user query. Select whole turns so tool calls and their results stay together. Preserve any system/developer instructions separately.

This is a recent-history window, not semantic relevance search. Older details may be unavailable to the model. It also does not guarantee a strict token limit: a single turn can still be large.

## User goal

Use the first nonempty user query as the session goal, stored verbatim in
`Memory.goal`. Do not use an LLM to infer or summarize it.

Keep the goal in every request, including tool follow-up requests. If its original
message is already selected, do not duplicate it. Otherwise insert a user-role
message labeled `Session goal:` before the recent turns and after any system or
developer instructions. Do not elevate user text to a system instruction.

Support `/goal <new goal>` to explicitly replace it and record a `goal_updated`
session event. `/goal` alone displays the current goal. Normal follow-up messages
do not silently replace it; later user corrections still take precedence.

## Implementation

Add one module: `context_builder.py`.

```python
def build_context(messages, goal, recent_turns=4, tool_result_max_chars=6000):
    # Copy messages so stored history is never changed.
    # Keep instructions and the latest complete turn groups.
    # Include the goal once, even when its original turn is omitted.
    # Shorten large tool results in the copy.
    return selected_messages
```

In `cli.py`, replace:

```python
"messages": memory.get_memory()
```

with:

```python
"messages": build_context(memory.get_memory(), goal=memory.goal)
```

For shortened tool results, preserve `role` and `tool_call_id`. Replace only the content with valid JSON containing an excerpt and an explicit truncation marker:

```json
{
  "truncated": true,
  "original_chars": 24000,
  "excerpt": "...",
  "note": "Excerpt only. Full result is saved in the session log."
}
```

Do not shorten user queries, assistant tool-call arguments, or instructions. Do not change tool handlers or original session events. The existing request trace will capture exactly what was sent to the LLM.

Add `goal` and its originating message reference to `Memory`, plus the small `/goal` handler in `cli.py`. Use the function's two limits as defaults initially. Include the new module in `pyproject.toml`. No new dependencies or configuration system changes are needed.

## Tests

- The latest four turns are sent, with instructions and the user goal preserved.
- The goal remains present after its original turn leaves the window, without duplication.
- `/goal` changes are recorded and used on subsequent requests, including tool follow-ups.
- Tool calls and matching results remain together, including multiple calls in one response.
- Large results are shortened and clearly marked; small results remain unchanged.
- Original memory and session records are unchanged.
- The CLI sends the context builder's output to the model.

## Later, if needed

Add summaries, keyword retrieval, token budgets, and context details in the dashboard after this basic version works. They are not part of this implementation.
