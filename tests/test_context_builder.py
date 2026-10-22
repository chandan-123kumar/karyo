import json
import unittest
from copy import deepcopy

from context_builder import build_context
from memory.memory import Memory


class ContextBuilderTests(unittest.TestCase):
    def test_keeps_instructions_recent_complete_turns_and_goal(self):
        memory = Memory()
        memory.save_message({"role": "system", "content": "Follow repo rules."})
        memory.save_to_memory("user", "Original goal")
        memory.save_message({"role": "assistant", "content": "Looking."})
        memory.save_to_memory("user", "Turn two")
        memory.save_message({"role": "assistant", "tool_calls": [{"id": "c1"}]})
        memory.save_message({"role": "tool", "tool_call_id": "c1", "content": "result"})
        memory.save_to_memory("user", "Turn three")
        memory.save_message({"role": "assistant", "content": "Done"})

        context = build_context(memory.get_memory(), memory.goal, recent_turns=2,
                                goal_message_index=memory.goal_message_index)
        self.assertEqual(context[0]["role"], "system")
        self.assertEqual([item.get("content") for item in context if item["role"] == "user"],
                         ["Session goal: Original goal", "Turn two", "Turn three"])
        assistant_call = next(item for item in context
                              if item["role"] == "assistant" and "tool_calls" in item)
        tool_result = next(item for item in context if item["role"] == "tool")
        self.assertEqual(assistant_call["tool_calls"][0]["id"], tool_result["tool_call_id"])

    def test_truncates_tool_result_without_mutating_memory(self):
        messages = [
            {"role": "user", "content": "Goal"},
            {"role": "assistant", "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "tool_call_id": "call-1", "content": "abcdefghij"},
        ]
        original = deepcopy(messages)
        context = build_context(messages, "Goal", tool_result_max_chars=5)
        result = json.loads(context[-1]["content"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["original_chars"], 10)
        self.assertEqual(result["excerpt"], "abcde")
        self.assertEqual(context[-1]["tool_call_id"], "call-1")
        self.assertEqual(messages, original)

    def test_updated_goal_is_included_without_replacing_user_history(self):
        memory = Memory()
        memory.save_to_memory("user", "First request")
        memory.update_goal("New goal")
        context = build_context(memory.get_memory(), memory.goal,
                                goal_message_index=memory.goal_message_index)
        self.assertEqual(context[0], {"role": "user", "content": "Session goal: New goal"})
        self.assertEqual(memory.get_memory()[0]["content"], "First request")


if __name__ == "__main__":
    unittest.main()
