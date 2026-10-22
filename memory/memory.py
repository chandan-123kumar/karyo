from copy import deepcopy


class Memory:
    id = 0
    def __init__(self):
        self.messages = []
        self.goal = None
        self.goal_message_index = None
       

    def prepare_message(self, role, content):
        return {
            "role": role,
            "content": content
        }
    def  save_to_memory(self, role, message):
        message = self.prepare_message(role, message)
        if (role == "user" and isinstance(message["content"], str)
                and message["content"].strip() and self.goal is None):
            self.goal = message["content"]
            self.goal_message_index = len(self.messages)
        self.messages.append(message)

    def save_message(self, message):
        """Preserve complete messages, including tool calls and result IDs."""
        self.messages.append(deepcopy(message))


    def get_memory(self):
        return self.messages

    def update_goal(self, goal):
        self.goal = goal.strip()
        self.goal_message_index = None


