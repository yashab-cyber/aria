"""
A.R.I.A. Procedural Memory — Tier 3

SQLite-backed storage for learned workflows, macros, and repeatable patterns.
Workflow descriptions are also indexed in ChromaDB for semantic matching.
Allows ARIA to learn from past multi-step executions and replay them.
"""

import sqlite3
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from config import config


class ProceduralMemory:
    """Persistent storage for learned workflows and execution patterns."""

    def __init__(self):
        self.db_path = config.sqlite_db_path
        self._store = None
        self._init_db()

    @property
    def store(self):
        if self._store is None:
            from memory.vector_store import store
            self._store = store
        return self._store

    def _get_conn(self) -> sqlite3.Connection:
        """Get a SQLite connection (creates DB file if needed)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create the workflows table if it doesn't exist."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    trigger_pattern TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_used_at REAL,
                    tags TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    executed_at REAL NOT NULL,
                    duration_seconds REAL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ──────────────────────────── Save / Update ─────────────────────────────

    def save_workflow(
        self,
        name: str,
        description: str,
        trigger_pattern: str,
        steps: List[Dict[str, Any]],
        tags: List[str] = None,
    ) -> str:
        """
        Save a learned workflow to SQLite and index in ChromaDB.
        
        Args:
            name: Human-readable workflow name
            description: What this workflow does
            trigger_pattern: Example user input that triggers this workflow
            steps: List of step dicts [{tool_name, tool_args, description}, ...]
            tags: Optional tags for categorization
            
        Returns:
            The workflow ID
        """
        workflow_id = str(uuid.uuid4())
        now = time.time()
        tags_str = ",".join(tags) if tags else ""

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO workflows 
                   (id, name, description, trigger_pattern, steps_json, 
                    success_count, fail_count, created_at, last_used_at, tags)
                   VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?)""",
                (
                    workflow_id, name, description, trigger_pattern,
                    json.dumps(steps), now, now, tags_str,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # Index in ChromaDB for semantic search
        embed_text = f"{name}: {description}. Triggered by: {trigger_pattern}"
        self.store.add_to_collection(
            collection_name="workflows",
            texts=[embed_text],
            metadatas=[{
                "workflow_id": workflow_id,
                "name": name,
                "tags": tags_str,
                "timestamp": now,
            }],
            ids=[f"wf_{workflow_id}"],
        )

        return workflow_id

    def update_usage_stats(self, workflow_id: str, success: bool,
                           session_id: str = "", duration: float = 0):
        """Record a workflow execution and update stats."""
        conn = self._get_conn()
        try:
            if success:
                conn.execute(
                    "UPDATE workflows SET success_count = success_count + 1, last_used_at = ? WHERE id = ?",
                    (time.time(), workflow_id),
                )
            else:
                conn.execute(
                    "UPDATE workflows SET fail_count = fail_count + 1, last_used_at = ? WHERE id = ?",
                    (time.time(), workflow_id),
                )

            # Log the execution
            conn.execute(
                """INSERT INTO workflow_executions 
                   (id, workflow_id, session_id, success, executed_at, duration_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), workflow_id, session_id, int(success), time.time(), duration),
            )
            conn.commit()
        finally:
            conn.close()

    # ──────────────────────────── Recall ────────────────────────────────────

    def find_matching_workflow(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Semantic search for workflows matching a user request.
        Returns workflows ranked by relevance with their full step definitions.
        """
        results = self.store.search_collection(
            "workflows", query, n_results=n_results
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        workflows = []
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, dist in zip(metas, distances):
            wf_id = meta.get("workflow_id", "")
            if not wf_id:
                continue

            # Fetch full workflow from SQLite
            wf_data = self._get_workflow_by_id(wf_id)
            if wf_data:
                wf_data["relevance_score"] = 1.0 - dist if dist else 0.0
                workflows.append(wf_data)

        return workflows

    def _get_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single workflow from SQLite by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()

            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "trigger_pattern": row["trigger_pattern"],
                    "steps": json.loads(row["steps_json"]),
                    "success_count": row["success_count"],
                    "fail_count": row["fail_count"],
                    "created_at": row["created_at"],
                    "last_used_at": row["last_used_at"],
                    "tags": row["tags"].split(",") if row["tags"] else [],
                    "success_rate": (
                        row["success_count"] / max(row["success_count"] + row["fail_count"], 1)
                    ),
                }
            return None
        finally:
            conn.close()

    def get_top_workflows(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the most successful/frequently used workflows."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM workflows 
                   ORDER BY success_count DESC, last_used_at DESC 
                   LIMIT ?""",
                (n,),
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "success_count": row["success_count"],
                    "fail_count": row["fail_count"],
                    "success_rate": (
                        row["success_count"] / max(row["success_count"] + row["fail_count"], 1)
                    ),
                    "last_used_at": row["last_used_at"],
                    "tags": row["tags"].split(",") if row["tags"] else [],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_workflow_count(self) -> int:
        """Return total number of stored workflows."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM workflows").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def delete_workflow(self, workflow_id: str) -> bool:
        """Remove a workflow from both SQLite and ChromaDB."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            conn.execute("DELETE FROM workflow_executions WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
        finally:
            conn.close()

        # Remove from ChromaDB
        try:
            self.store.delete_from_collection("workflows", ids=[f"wf_{workflow_id}"])
        except Exception:
            pass

        return True


# Global instance
procedural_mem = ProceduralMemory()
