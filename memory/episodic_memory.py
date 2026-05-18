"""
A.R.I.A. Episodic Memory — Tier 2

Session-aware long-term storage for past conversations and outcomes.
Uses ChromaDB for semantic search across session summaries and individual messages.
Supports LLM-powered summarization to compress old sessions and avoid context bloat.
"""

import time
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime


class EpisodicMemory:
    """Persistent memory for past sessions, conversations, and outcomes."""

    def __init__(self):
        # Lazy-loaded to avoid circular imports with vector_store
        self._store = None

    @property
    def store(self):
        if self._store is None:
            from memory.vector_store import store
            self._store = store
        return self._store

    # ──────────────────────────── Session Commit ────────────────────────────

    def commit_session(self, session_snapshot: Dict[str, Any], summary: str = ""):
        """
        Commit a completed working memory session to episodic storage.
        
        Args:
            session_snapshot: Full session data from WorkingMemory.flush()
            summary: LLM-generated session summary (if available)
        """
        session_id = session_snapshot.get("session_id", str(uuid.uuid4()))
        started_at = session_snapshot.get("started_at", time.time())
        ended_at = session_snapshot.get("ended_at", time.time())
        duration = session_snapshot.get("duration_seconds", 0)
        entities = session_snapshot.get("entities", [])
        metadata = session_snapshot.get("metadata", {})

        # 1. Store the session summary as a top-level document
        topic_tags = ", ".join(entities[:10]) if entities else "general"

        summary_text = summary or self._build_basic_summary(session_snapshot)

        self.store.add_to_collection(
            collection_name="conversations",
            texts=[summary_text],
            metadatas=[{
                "type": "session_summary",
                "session_id": session_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration,
                "topic_tags": topic_tags,
                "total_user_msgs": metadata.get("total_user_msgs", 0),
                "total_tool_calls": metadata.get("total_tool_calls", 0),
                "timestamp": time.time(),
            }],
            ids=[f"session_{session_id}"],
        )

        # 2. Store individual messages with session linkage
        messages = session_snapshot.get("messages", [])
        if messages:
            self._commit_messages(messages, session_id, topic_tags)

    def _commit_messages(self, messages: List[Dict], session_id: str, topic_tags: str):
        """Batch-commit individual messages from a session."""
        texts = []
        metas = []
        ids = []

        for msg in messages:
            content = msg.get("content", "")
            if not content or not isinstance(content, str) or len(content.strip()) < 5:
                continue  # Skip empty or trivially short messages

            texts.append(content)
            metas.append({
                "type": "message",
                "role": msg.get("role", "unknown"),
                "session_id": session_id,
                "topic_tags": topic_tags,
                "timestamp": msg.get("timestamp", time.time()),
            })
            ids.append(f"msg_{session_id}_{uuid.uuid4().hex[:8]}")

        if texts:
            self.store.add_to_collection(
                collection_name="conversations",
                texts=texts,
                metadatas=metas,
                ids=ids,
            )

    def commit_single_message(self, role: str, content: str, session_id: str = "overflow"):
        """
        Commit a single overflow message from working memory.
        Used when working memory's buffer evicts old messages.
        """
        if not content or not isinstance(content, str):
            return

        self.store.add_to_collection(
            collection_name="conversations",
            texts=[content],
            metadatas=[{
                "type": "message",
                "role": role,
                "session_id": session_id,
                "topic_tags": "overflow",
                "timestamp": time.time(),
            }],
        )

    def _build_basic_summary(self, session_snapshot: Dict[str, Any]) -> str:
        """Build a simple summary without LLM (fallback)."""
        meta = session_snapshot.get("metadata", {})
        entities = session_snapshot.get("entities", [])
        goals = session_snapshot.get("active_goals", [])
        duration = session_snapshot.get("duration_seconds", 0)

        parts = [f"Session lasted {duration:.0f}s."]

        if goals:
            parts.append(f"Goals: {', '.join(goals)}.")

        if entities:
            parts.append(f"Topics discussed: {', '.join(entities[:8])}.")

        parts.append(
            f"Stats: {meta.get('total_user_msgs', 0)} user messages, "
            f"{meta.get('total_tool_calls', 0)} tool calls."
        )

        # Include first and last user message for context
        messages = session_snapshot.get("messages", [])
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if user_msgs:
            parts.append(f"Started with: \"{user_msgs[0]['content'][:100]}\"")
            if len(user_msgs) > 1:
                parts.append(f"Ended with: \"{user_msgs[-1]['content'][:100]}\"")

        return " ".join(parts)

    # ──────────────────────────── Recall ────────────────────────────────────

    def recall_similar(
        self,
        query: str,
        n_results: int = 5,
        type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across episodic memory.
        
        Args:
            query: Search query
            n_results: Max results
            type_filter: Optional filter — 'session_summary' or 'message'
        """
        where = None
        if type_filter:
            where = {"type": type_filter}

        results = self.store.search_collection(
            "conversations", query, n_results=n_results, where=where
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        # Zip documents with their metadata for richer recall
        items = []
        docs = results["documents"][0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            items.append({
                "content": doc,
                "metadata": meta,
                "relevance_score": 1.0 - dist if dist else 0.0,
            })

        return items

    def recall_past_conversations(self, query: str, n: int = 3) -> List[str]:
        """Simple recall returning just document texts (backward-compatible)."""
        results = self.store.search_collection("conversations", query, n_results=n)
        if results and results.get("documents") and results["documents"][0]:
            return results["documents"][0]
        return []

    def get_session_summaries(self, n: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the most recent session summaries."""
        # ChromaDB doesn't have native ordering, so we search with a broad query
        results = self.store.search_collection(
            "conversations",
            "session summary conversation",
            n_results=n,
            where={"type": "session_summary"},
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        items = []
        for doc, meta in zip(results["documents"][0], results.get("metadatas", [[]])[0]):
            items.append({"summary": doc, "metadata": meta})

        return items

    # ──────────────────────────── Summarization ────────────────────────────

    async def summarize_session_with_llm(self, session_snapshot: Dict[str, Any]) -> str:
        """
        Use the LLM to generate a rich summary of a completed session.
        Called by MemoryManager when a session ends.
        """
        messages = session_snapshot.get("messages", [])
        if not messages:
            return self._build_basic_summary(session_snapshot)

        # Build a conversation transcript for the LLM
        transcript_lines = []
        for msg in messages[-30:]:  # Last 30 messages to avoid token overflow
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")[:300]
            transcript_lines.append(f"{role}: {content}")

        transcript = "\n".join(transcript_lines)

        goals = session_snapshot.get("active_goals", [])
        entities = session_snapshot.get("entities", [])

        prompt = f"""Summarize this A.R.I.A. assistant session in 2-4 sentences. Focus on:
- What the user wanted to accomplish
- What actions were taken
- The outcome (success/failure/partial)

Session context:
- Goals: {', '.join(goals) if goals else 'None set'}
- Topics: {', '.join(entities) if entities else 'General'}
- Tool calls made: {session_snapshot.get('metadata', {}).get('total_tool_calls', 0)}

Conversation transcript (last 30 messages):
{transcript}

Summary:"""

        try:
            from core.llm_engine import llm
            response = ""
            async for chunk in llm.chat_stream(
                [{"role": "user", "content": prompt}]
            ):
                response += chunk
            return response.strip() if response.strip() else self._build_basic_summary(session_snapshot)
        except Exception as e:
            print(f"[EpisodicMemory] LLM summarization failed: {e}")
            return self._build_basic_summary(session_snapshot)

    async def summarize_old_sessions(self, max_age_days: int = 7) -> int:
        """
        Find old detailed messages and replace them with compressed summaries.
        Returns the number of sessions summarized.
        """
        cutoff = time.time() - (max_age_days * 86400)
        summarized = 0

        # Get session summaries older than cutoff
        summaries = self.get_session_summaries(n=50)
        for item in summaries:
            meta = item.get("metadata", {})
            if meta.get("ended_at", time.time()) < cutoff:
                session_id = meta.get("session_id", "")
                if session_id:
                    # Delete individual messages for this old session
                    # (keep only the summary)
                    try:
                        self.store.delete_from_collection(
                            "conversations",
                            where={"session_id": session_id, "type": "message"},
                        )
                        summarized += 1
                    except Exception as e:
                        print(f"[EpisodicMemory] Cleanup failed for session {session_id}: {e}")

        return summarized


# Global instance
episodic_mem = EpisodicMemory()
