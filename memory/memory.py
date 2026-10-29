from copy import deepcopy
from pathlib import Path
import json
import os
import sqlite3
import uuid
import re


def default_database_path():
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "karyo" / "memory.sqlite3"


class MemoryStore:
    """Small SQLite store for project-scoped conversation histories."""
    def __init__(self, path=None, project=None):
        self.path = Path(path or default_database_path()).expanduser()
        self.project = str(Path(project or Path.cwd()).resolve())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                goal TEXT, goal_message_index INTEGER
            );
            CREATE TABLE IF NOT EXISTS messages (
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                position INTEGER NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY (conversation_id, position)
            );
            CREATE INDEX IF NOT EXISTS conversations_project_created
                ON conversations(project, created_at DESC);
            CREATE TABLE IF NOT EXISTS durable_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS durable_memories_scope
                ON durable_memories(scope, id DESC);
        """)
        self.connection.commit()
        self.conversation_id = uuid.uuid4().hex
        self.connection.execute("INSERT INTO conversations (id, project) VALUES (?, ?)",
                                (self.conversation_id, self.project))
        self.connection.commit()

    def append(self, message, position):
        self.connection.execute("INSERT INTO messages VALUES (?, ?, ?)",
                                (self.conversation_id, position,
                                 json.dumps(message, ensure_ascii=False)))
        self.connection.commit()

    def update_goal(self, goal, message_index):
        self.connection.execute("UPDATE conversations SET goal=?, goal_message_index=? WHERE id=?",
                                (goal, message_index, self.conversation_id))
        self.connection.commit()

    def latest(self):
        row = self.connection.execute(
            "SELECT id, goal, goal_message_index FROM conversations WHERE project=? AND id<>? "
            "AND EXISTS (SELECT 1 FROM messages WHERE messages.conversation_id=conversations.id) "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (self.project, self.conversation_id)
        ).fetchone()
        if row is None:
            return None
        messages = [json.loads(item[0]) for item in self.connection.execute(
            "SELECT body FROM messages WHERE conversation_id=? ORDER BY position", (row[0],)
        )]
        return {"messages": messages, "goal": row[1], "goal_message_index": row[2]}

    def close(self):
        self.connection.close()

    @property
    def project_scope(self):
        return "project:" + self.project

    def add_fact(self, content, global_scope=False):
        content = content.strip()
        if not content:
            raise ValueError("Memory cannot be empty")
        if len(content) > 2000:
            raise ValueError("Memory must be 2,000 characters or fewer")
        scope = "global" if global_scope else self.project_scope
        existing = self.connection.execute(
            "SELECT id FROM durable_memories WHERE scope=? AND content=?", (scope, content)
        ).fetchone()
        if existing:
            return existing[0]
        cursor = self.connection.execute(
            "INSERT INTO durable_memories (scope, content) VALUES (?, ?)", (scope, content)
        )
        self.connection.commit()
        return cursor.lastrowid

    def list_facts(self):
        return self.connection.execute(
            "SELECT id, scope, content FROM durable_memories "
            "WHERE scope IN ('global', ?) ORDER BY id DESC", (self.project_scope,)
        ).fetchall()

    def delete_fact(self, memory_id):
        cursor = self.connection.execute(
            "DELETE FROM durable_memories WHERE id=? AND scope IN ('global', ?)",
            (memory_id, self.project_scope),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def find_facts(self, query, limit=6):
        rows = self.list_facts()
        terms = set(re.findall(r"[\w'-]{3,}", query.lower()))
        scored = []
        for memory_id, scope, content in rows:
            if scope == "global":
                scored.append((0, memory_id, scope, content))
                continue
            words = set(re.findall(r"[\w'-]{3,}", content.lower()))
            overlap = len(terms & words)
            if overlap:
                scored.append((overlap, memory_id, scope, content))
        globals_ = sorted((item for item in scored if item[2] == "global"),
                          key=lambda item: item[1], reverse=True)[:4]
        projects = sorted((item for item in scored if item[2] != "global"),
                          key=lambda item: (item[0], item[1]), reverse=True)
        scored = globals_ + projects[:max(0, limit - len(globals_))]
        return [{"id": item[1], "scope": item[2], "content": item[3]}
                for item in scored[:limit]]


class Memory:
    def __init__(self, store=None):
        self.store = store
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
        if self.store:
            self.store.append(message, len(self.messages) - 1)
            self.store.update_goal(self.goal, self.goal_message_index)

    def save_message(self, message):
        """Preserve complete messages, including tool calls and result IDs."""
        self.messages.append(deepcopy(message))
        if self.store:
            self.store.append(self.messages[-1], len(self.messages) - 1)


    def get_memory(self):
        return self.messages

    def update_goal(self, goal):
        self.goal = goal.strip()
        self.goal_message_index = None
        if self.store:
            self.store.update_goal(self.goal, None)

    def resume_latest(self):
        """Load the previous conversation for this project, if one exists."""
        saved = self.store.latest() if self.store else None
        if saved is None:
            return False
        self.messages = saved["messages"]
        self.goal = saved["goal"]
        self.goal_message_index = saved["goal_message_index"]
        for position, message in enumerate(self.messages):
            self.store.append(message, position)
        self.store.update_goal(self.goal, self.goal_message_index)
        return True

    def remember(self, content, global_scope=False):
        return self.store.add_fact(content, global_scope=global_scope)

    def forget(self, memory_id):
        return self.store.delete_fact(memory_id)

    def memories(self):
        return self.store.list_facts()

    def relevant_memories(self, query):
        return self.store.find_facts(query)


