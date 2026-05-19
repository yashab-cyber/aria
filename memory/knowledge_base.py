from memory.vector_store import store
import time
from core.tool_registry import aria_tool

class KnowledgeBase:
    @aria_tool(name="remember_fact", description="Save an important fact or user preference to long-term memory")
    async def remember_fact(self, fact: str, category: str = "general") -> str:
        """Stores a fact in the ChromaDB knowledge base."""
        store.add_to_collection(
            collection_name="knowledge_base",
            texts=[fact],
            metadatas=[{"category": category, "timestamp": time.time(), "type": "fact"}]
        )
        return f"Fact remembered: {fact}"

    @aria_tool(name="search_knowledge", description="Search the knowledge base for a specific topic or fact")
    async def search_knowledge(self, query: str) -> str:
        """Searches the knowledge base using semantic search."""
        results = store.search_collection("knowledge_base", query, n_results=3)
        if results and results["documents"] and results["documents"][0]:
            found_facts = "\n".join([f"- {doc}" for doc in results["documents"][0]])
            return f"Found knowledge:\n{found_facts}"
        return "No relevant knowledge found."

    async def extract_and_store_facts(self, messages: list):
        """
        Uses the LLM to extract persistent facts from the session and stores them.
        """
        if not messages:
            return

        transcript_lines = []
        for msg in messages[-30:]:  # Last 30 messages
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")[:300]
            transcript_lines.append(f"{role}: {content}")
        
        transcript = "\n".join(transcript_lines)
        
        prompt = f"""Analyze this conversation and extract any persistent facts, user preferences, or important details about the user (e.g., name, relationships, likes/dislikes, personal info) that an AI assistant should remember for future sessions.
Only extract clear, explicit facts. If there are none, return nothing.
Format each fact on a new line starting with a dash (-).

Conversation:
{transcript}

Facts:"""

        try:
            from core.llm_engine import llm
            response = ""
            async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
                response += chunk
            
            facts = [line.strip("- ").strip() for line in response.split("\n") if line.strip().startswith("-")]
            for fact in facts:
                if fact and len(fact) > 5:
                    print(f"[KnowledgeBase] Auto-extracted fact: {fact}")
                    await self.remember_fact(fact, category="auto_extracted")
        except Exception as e:
            print(f"[KnowledgeBase] Fact extraction failed: {e}")

kb = KnowledgeBase()
