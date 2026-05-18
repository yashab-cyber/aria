"""
A.R.I.A. Working Memory — Tier 1

In-memory dict-based storage for the current active session.
Handles session tracking, active goals, scratch variables, and entity tracking.
Flushes to Episodic Memory when the session ends or the buffer overflows.
"""

import uuid
import time
from typing import List, Dict, Any, Optional
from datetime import datetime


class WorkingMemory:
    """Fast, volatile memory for the current session."""

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self._session: Dict[str, Any] = {}
        self._start_new_session()

    # ──────────────────────────── Session Lifecycle ─────────────────────────

    def _start_new_session(self):
        """Initialize a fresh session state."""
        self._session = {
            "session_id": str(uuid.uuid4()),
            "started_at": time.time(),
            "messages": [],          # [{role, content, timestamp}]
            "active_goals": [],      # Current objectives being pursued
            "scratch": {},           # Intermediate tool results / state
            "entities": set(),       # Mentioned entities (topics, names, files)
            "tool_calls": [],        # Record of tools invoked this session
            "metadata": {
                "total_user_msgs": 0,
                "total_assistant_msgs": 0,
                "total_tool_calls": 0,
            },
        }

    @property
    def session_id(self) -> str:
        return self._session["session_id"]

    @property
    def started_at(self) -> float:
        return self._session["started_at"]

    @property
    def message_count(self) -> int:
        return len(self._session["messages"])

    @property
    def is_overflow(self) -> bool:
        """True when the message buffer exceeds the configured limit."""
        return self.message_count >= self.max_messages

    # ──────────────────────────── Messages ──────────────────────────────────

    def add_message(self, role: str, content: str) -> Optional[Dict[str, str]]:
        """
        Add a message to the session buffer.
        Returns the evicted message if the buffer overflows, else None.
        """
        msg = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        self._session["messages"].append(msg)

        # Update counters
        if role == "user":
            self._session["metadata"]["total_user_msgs"] += 1
        elif role == "assistant":
            self._session["metadata"]["total_assistant_msgs"] += 1

        # Overflow: evict oldest message and return it for episodic commit
        evicted = None
        if len(self._session["messages"]) > self.max_messages:
            evicted = self._session["messages"].pop(0)

        return evicted

    def get_recent_messages(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        """Return the last N messages (or all if n is None)."""
        msgs = self._session["messages"]
        if n is not None:
            msgs = msgs[-n:]
        # Return role/content only (compatible with LLM history format)
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    # ──────────────────────────── Goals ──────────────────────────────────────

    def set_goal(self, goal: str):
        """Register an active goal for this session."""
        if goal not in self._session["active_goals"]:
            self._session["active_goals"].append(goal)

    def clear_goal(self, goal: str):
        """Mark a goal as completed / remove it."""
        self._session["active_goals"] = [
            g for g in self._session["active_goals"] if g != goal
        ]

    def get_goals(self) -> List[str]:
        return list(self._session["active_goals"])

    # ──────────────────────────── Scratch / State ───────────────────────────

    def set_scratch(self, key: str, value: Any):
        """Store an intermediate result or state variable."""
        self._session["scratch"][key] = value

    def get_scratch(self, key: str, default: Any = None) -> Any:
        return self._session["scratch"].get(key, default)

    def clear_scratch(self, key: str = None):
        if key:
            self._session["scratch"].pop(key, None)
        else:
            self._session["scratch"] = {}

    # ──────────────────────────── Entities ──────────────────────────────────

    def track_entity(self, entity: str):
        """Track a mentioned entity (topic, file, person, etc.)."""
        self._session["entities"].add(entity)

    def get_entities(self) -> List[str]:
        return list(self._session["entities"])

    # ──────────────────────────── Tool Calls ────────────────────────────────

    def record_tool_call(self, tool_name: str, args: dict, result: str):
        """Record a tool execution for potential procedural memory learning."""
        self._session["tool_calls"].append({
            "tool_name": tool_name,
            "args": args,
            "result_preview": str(result)[:500],  # Truncate large results
            "timestamp": time.time(),
        })
        self._session["metadata"]["total_tool_calls"] += 1

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        return list(self._session["tool_calls"])

    # ──────────────────────────── Context Export ────────────────────────────

    def get_session_context(self) -> Dict[str, Any]:
        """Export the full session state (for episodic commit on flush)."""
        return {
            "session_id": self._session["session_id"],
            "started_at": self._session["started_at"],
            "messages": list(self._session["messages"]),
            "active_goals": list(self._session["active_goals"]),
            "entities": list(self._session["entities"]),
            "tool_calls": list(self._session["tool_calls"]),
            "metadata": dict(self._session["metadata"]),
        }

    def get_context_summary(self) -> str:
        """Build a concise context string for LLM augmentation."""
        parts = []

        goals = self.get_goals()
        if goals:
            parts.append("Active Goals: " + ", ".join(goals))

        entities = self.get_entities()
        if entities:
            parts.append("Session Topics: " + ", ".join(list(entities)[:10]))

        meta = self._session["metadata"]
        parts.append(
            f"Session Stats: {meta['total_user_msgs']} user msgs, "
            f"{meta['total_tool_calls']} tool calls"
        )

        return "\n".join(parts) if parts else ""

    # ──────────────────────────── Reset ─────────────────────────────────────

    def flush(self) -> Dict[str, Any]:
        """
        Export session data and reset working memory.
        Returns the full session snapshot for episodic commit.
        """
        snapshot = self.get_session_context()
        snapshot["ended_at"] = time.time()
        snapshot["duration_seconds"] = snapshot["ended_at"] - snapshot["started_at"]
        self._start_new_session()
        return snapshot

    def clear(self):
        """Hard reset without returning data."""
        self._start_new_session()


# Global instance
working_mem = WorkingMemory()
