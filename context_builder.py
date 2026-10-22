"""Build a bounded, model-facing copy of conversation history."""

import json
from copy import deepcopy


def build_context(messages, goal, recent_turns=4, tool_result_max_chars=6000,
                  goal_message_index=None):
    """Keep instructions and recent complete turns, shortening large tool results.

    The input messages are never modified. ``recent_turns`` counts user turns,
    including the current one.
    """
    copied = deepcopy(messages)
    instructions = [(index, message) for index, message in enumerate(copied)
                    if message.get("role") in ("system", "developer")]
    turns = []
    leading = []
    for index, message in enumerate(copied):
        if message.get("role") in ("system", "developer"):
            continue
        if message.get("role") == "user":
            turns.append([(index, message)])
        elif turns:
            turns[-1].append((index, message))
        else:
            leading.append((index, message))

    selected_turns = turns[-recent_turns:] if recent_turns > 0 else []
    selected_indexed = instructions + leading
    selected_indexed.extend(item for turn in selected_turns for item in turn)
    selected = [message for _, message in selected_indexed]
    goal_is_selected = (goal_message_index is not None and
                        any(index == goal_message_index for index, _ in selected_indexed))
    if goal and not goal_is_selected and not any(
            message.get("role") == "user" and message.get("content") == goal
            for message in selected):
        selected.insert(len(instructions), {
            "role": "user", "content": f"Session goal: {goal}"
        })

    for message in selected:
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if isinstance(content, str) and len(content) > tool_result_max_chars:
            message["content"] = json.dumps({
                "truncated": True,
                "original_chars": len(content),
                "excerpt": content[:tool_result_max_chars],
                "note": "Excerpt only. Full result is saved in the session log.",
            })
    return selected
