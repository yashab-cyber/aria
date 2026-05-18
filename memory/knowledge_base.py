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

kb = KnowledgeBase()
