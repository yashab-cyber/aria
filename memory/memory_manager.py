"""
A.R.I.A. Memory Manager — Intelligent Memory Lifecycle Orchestrator

The brain of the three-tier memory system. Handles:
- Context assembly from all three tiers (working, episodic, procedural)
- Automatic commit decisions based on importance scoring
- Session lifecycle management (start → flush → commit)
- Old session summarization to prevent context bloat
- Workflow learning from successful multi-step plans
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from rich.console import Console

console = Console()


class MemoryManager:
    """Orchestrates Working, Episodic, and Procedural memory tiers."""

    # ── Importance scoring weights ──
    TOOL_CALL_WEIGHT = 0.3
    MESSAGE_LENGTH_WEIGHT = 0.1
    GOAL_WEIGHT = 0.2
    MULTI_STEP_WEIGHT = 0.4

    # ── Workflow learning threshold ──
    WORKFLOW_LEARN_MIN_STEPS = 2
    WORKFLOW_SIMILARITY_THRESHOLD = 0.75

    def __init__(self):
        # Lazy imports to avoid circular dependencies at module load
        self._working = None
        self._episodic = None
        self._procedural = None
        self._knowledge = None
        self._session_active = False

    # ──────────────────────────── Lazy Tier Access ─────────────────────────

    @property
    def working(self):
        if self._working is None:
            from memory.working_memory import working_mem
            self._working = working_mem
        return self._working

    @property
    def episodic(self):
        if self._episodic is None:
            from memory.episodic_memory import episodic_mem
            self._episodic = episodic_mem
        return self._episodic

    @property
    def procedural(self):
        if self._procedural is None:
            from memory.procedural_memory import procedural_mem
            self._procedural = procedural_mem
        return self._procedural

    @property
    def knowledge(self):
        if self._knowledge is None:
            from memory.knowledge_base import kb
            self._knowledge = kb
        return self._knowledge

    # ──────────────────────────── Session Lifecycle ─────────────────────────

    def start_session(self):
        """Initialize a new working memory session."""
        if not self._session_active:
            self.working.clear()
            self._session_active = True
            console.print("[bold green]⟐ Memory session started[/bold green]")

    async def end_session(self):
        """
        Flush working memory → summarize → commit to episodic.
        Called on WebSocket disconnect or explicit session end.
        """
        if not self._session_active:
            return

        self._session_active = False

        # 1. Get session snapshot
        snapshot = self.working.flush()
        messages = snapshot.get("messages", [])

        if not messages:
            console.print("[dim]Empty session — nothing to commit.[/dim]")
            return

        # 2. Score the session importance
        importance = self.score_importance(snapshot)
        console.print(f"[cyan]Session importance score: {importance:.2f}[/cyan]")

        # 3. Generate summary (use LLM for important sessions, basic for trivial)
        if importance >= 0.3:
            summary = await self.episodic.summarize_session_with_llm(snapshot)
        else:
            summary = self.episodic._build_basic_summary(snapshot)

        # 4. Commit to episodic memory
        self.episodic.commit_session(snapshot, summary=summary)
        console.print(
            f"[green]✓ Session committed to episodic memory "
            f"({len(messages)} msgs, importance={importance:.2f})[/green]"
        )

        # 5. Check for workflow learning opportunities
        tool_calls = snapshot.get("tool_calls", [])
        if len(tool_calls) >= self.WORKFLOW_LEARN_MIN_STEPS:
            await self._try_learn_workflow(snapshot)

    # ──────────────────────────── Context Assembly ─────────────────────────

    def get_context(self, current_query: str) -> str:
        """
        Build rich context by querying all three memory tiers.
        This is the main entry point used by the orchestrator.
        """
        context_parts = []

        # ── Tier 1: Working Memory ──
        working_ctx = self.working.get_context_summary()
        if working_ctx:
            context_parts.append(f"[Working Memory]\n{working_ctx}")

        # ── Tier 2: Episodic Memory ──
        past_items = self.episodic.recall_similar(
            current_query, n_results=3, type_filter="session_summary"
        )
        if past_items:
            episodes = []
            for item in past_items:
                score = item.get("relevance_score", 0)
                if score > 0.3:  # Only include reasonably relevant episodes
                    episodes.append(f"  • {item['content']}")
            if episodes:
                context_parts.append(
                    "[Episodic Memory — Relevant Past Sessions]\n" + "\n".join(episodes)
                )

        # Past conversation messages (more granular recall)
        past_msgs = self.episodic.recall_similar(
            current_query, n_results=2, type_filter="message"
        )
        if past_msgs:
            msg_lines = []
            for item in past_msgs:
                score = item.get("relevance_score", 0)
                if score > 0.4:
                    role = item.get("metadata", {}).get("role", "unknown")
                    msg_lines.append(f"  [{role}]: {item['content'][:200]}")
            if msg_lines:
                context_parts.append(
                    "[Episodic Memory — Relevant Messages]\n" + "\n".join(msg_lines)
                )

        # ── Tier 3: Procedural Memory ──
        matching_workflows = self.procedural.find_matching_workflow(current_query, n_results=2)
        if matching_workflows:
            wf_lines = []
            for wf in matching_workflows:
                if wf.get("relevance_score", 0) > 0.4 and wf.get("success_rate", 0) > 0.5:
                    wf_lines.append(
                        f"  • \"{wf['name']}\" (success rate: {wf['success_rate']:.0%}, "
                        f"used {wf['success_count']}x) — {wf['description']}"
                    )
            if wf_lines:
                context_parts.append(
                    "[Procedural Memory — Matching Workflows]\n" + "\n".join(wf_lines)
                )

        # ── Knowledge Base (existing) ──
        try:
            from memory.vector_store import store
            kb_results = store.search_collection("knowledge_base", current_query, n_results=3)
            if kb_results and kb_results.get("documents") and kb_results["documents"][0]:
                kb_items = [f"  • {doc}" for doc in kb_results["documents"][0]]
                context_parts.append(
                    "[Knowledge Base]\n" + "\n".join(kb_items)
                )
        except Exception:
            pass

        return "\n\n".join(context_parts) if context_parts else ""

    # ──────────────────────────── Message Handling ─────────────────────────

    def add_message(self, role: str, content: str):
        """
        Add a message to working memory.
        Overflow messages are auto-committed to episodic memory.
        """
        if not self._session_active:
            self.start_session()

        evicted = self.working.add_message(role, content)

        # If working memory evicted an old message, send it to episodic
        if evicted:
            self.episodic.commit_single_message(
                role=evicted["role"],
                content=evicted["content"],
                session_id=self.working.session_id,
            )

    def get_recent_context(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        """Get recent messages from working memory (LLM history format)."""
        return self.working.get_recent_messages(n)

    def record_tool_call(self, tool_name: str, args: dict, result: str):
        """Record a tool call in working memory for potential workflow learning."""
        self.working.record_tool_call(tool_name, args, result)

    # ──────────────────────────── Importance Scoring ───────────────────────

    def score_importance(self, session_snapshot: Dict[str, Any]) -> float:
        """
        Score the importance of a session (0.0 → 1.0).
        Higher scores mean the session is more worth preserving in detail.

        Heuristics:
        - Tool calls → user was doing real work
        - Goals set → user had clear objectives
        - Long messages → substantive conversation
        - Multi-step execution → complex task
        """
        score = 0.0
        meta = session_snapshot.get("metadata", {})

        # Tool call density
        tool_calls = meta.get("total_tool_calls", 0)
        if tool_calls > 0:
            score += min(tool_calls / 5, 1.0) * self.TOOL_CALL_WEIGHT

        # Message substance (average message length)
        messages = session_snapshot.get("messages", [])
        if messages:
            avg_len = sum(len(m.get("content", "")) for m in messages) / len(messages)
            score += min(avg_len / 200, 1.0) * self.MESSAGE_LENGTH_WEIGHT

        # Goals
        goals = session_snapshot.get("active_goals", [])
        if goals:
            score += min(len(goals) / 3, 1.0) * self.GOAL_WEIGHT

        # Multi-step detection (many tool calls in sequence = complex workflow)
        if tool_calls >= 3:
            score += self.MULTI_STEP_WEIGHT

        return min(score, 1.0)

    # ──────────────────────────── Auto-Commit ──────────────────────────────

    async def auto_commit(self, plan_results: Dict = None, plan_steps: List = None):
        """
        Intelligent auto-commit after significant events.
        Called after plan execution or major tool operations.
        
        Decides whether to:
        - Learn a new workflow (procedural memory)
        - Store key facts (knowledge base)
        """
        if plan_results and plan_steps:
            # Check if the plan was mostly successful
            total = len(plan_results)
            successes = sum(
                1 for r in plan_results.values()
                if not str(r).startswith("Error")
            )

            if successes >= total * 0.7 and total >= self.WORKFLOW_LEARN_MIN_STEPS:
                # This is a workflow learning candidate
                await self._learn_workflow_from_plan(plan_steps, plan_results)

    async def _try_learn_workflow(self, session_snapshot: Dict[str, Any]):
        """Check if session tool calls form a learnable workflow pattern."""
        tool_calls = session_snapshot.get("tool_calls", [])
        if len(tool_calls) < self.WORKFLOW_LEARN_MIN_STEPS:
            return

        # Build workflow description from tool sequence
        steps = []
        for tc in tool_calls:
            steps.append({
                "tool_name": tc["tool_name"],
                "description": f"Execute {tc['tool_name']}",
                "args_template": tc["args"],
            })

        # Check if a similar workflow already exists
        description = " → ".join(tc["tool_name"] for tc in tool_calls)
        existing = self.procedural.find_matching_workflow(description, n_results=1)

        if existing and existing[0].get("relevance_score", 0) > self.WORKFLOW_SIMILARITY_THRESHOLD:
            # Similar workflow exists — update its stats
            self.procedural.update_usage_stats(
                existing[0]["id"],
                success=True,
                session_id=session_snapshot.get("session_id", ""),
            )
            console.print(
                f"[blue]↻ Updated existing workflow: \"{existing[0]['name']}\"[/blue]"
            )
        else:
            # New workflow — learn it
            entities = session_snapshot.get("entities", [])
            goals = session_snapshot.get("active_goals", [])

            name = goals[0] if goals else f"Workflow: {description[:50]}"
            trigger = ""
            user_msgs = [
                m for m in session_snapshot.get("messages", [])
                if m.get("role") == "user"
            ]
            if user_msgs:
                trigger = user_msgs[0].get("content", "")[:200]

            wf_id = self.procedural.save_workflow(
                name=name,
                description=f"Learned workflow: {description}",
                trigger_pattern=trigger,
                steps=steps,
                tags=list(entities)[:5],
            )
            console.print(
                f"[green]✦ Learned new workflow: \"{name}\" (id: {wf_id[:8]}...)[/green]"
            )

    async def _learn_workflow_from_plan(self, plan_steps: List, plan_results: Dict):
        """Learn a workflow from a successfully executed plan."""
        steps = []
        for step in plan_steps:
            step_dict = step if isinstance(step, dict) else step.__dict__ if hasattr(step, '__dict__') else {}
            steps.append({
                "tool_name": step_dict.get("tool_name", "unknown"),
                "description": step_dict.get("description", ""),
                "args_template": step_dict.get("tool_args", {}),
            })

        description = " → ".join(s["tool_name"] for s in steps)
        name = steps[0].get("description", "Learned Plan")[:60] if steps else "Learned Plan"

        existing = self.procedural.find_matching_workflow(description, n_results=1)
        if existing and existing[0].get("relevance_score", 0) > self.WORKFLOW_SIMILARITY_THRESHOLD:
            self.procedural.update_usage_stats(existing[0]["id"], success=True)
            return

        self.procedural.save_workflow(
            name=name,
            description=f"Plan workflow: {description}",
            trigger_pattern=name,
            steps=steps,
        )
        console.print(f"[green]✦ Learned plan workflow: \"{name}\"[/green]")

    # ──────────────────────────── Consolidation ────────────────────────────

    async def consolidate_old_memories(self, max_age_days: int = None):
        """
        Periodic cleanup: summarize and compress old episodic entries.
        Should be called periodically (e.g., on startup or via scheduled task).
        """
        if max_age_days is None:
            from config import config
            max_age_days = config.memory_summarize_after_days

        summarized = await self.episodic.summarize_old_sessions(max_age_days)
        if summarized > 0:
            console.print(
                f"[yellow]♻ Consolidated {summarized} old sessions "
                f"(older than {max_age_days} days)[/yellow]"
            )

    # ──────────────────────────── Introspection ────────────────────────────

    def get_memory_status(self) -> Dict[str, Any]:
        """Return status of all memory tiers (for the /api/memory/status endpoint)."""
        working_status = {
            "session_id": self.working.session_id,
            "session_active": self._session_active,
            "message_count": self.working.message_count,
            "active_goals": self.working.get_goals(),
            "entities_tracked": len(self.working.get_entities()),
            "tool_calls_this_session": len(self.working.get_tool_calls()),
        }

        episodic_status = {
            "recent_sessions": len(self.episodic.get_session_summaries(n=20)),
        }

        procedural_status = {
            "total_workflows": self.procedural.get_workflow_count(),
            "top_workflows": [
                {"name": wf["name"], "success_rate": wf["success_rate"]}
                for wf in self.procedural.get_top_workflows(n=5)
            ],
        }

        return {
            "working_memory": working_status,
            "episodic_memory": episodic_status,
            "procedural_memory": procedural_status,
        }


# Global instance
memory_manager = MemoryManager()
