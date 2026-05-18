# A.R.I.A Memory Subsystem — Three-Tier Architecture
#
# Tier 1: Working Memory   — In-memory session state (fast, volatile)
# Tier 2: Episodic Memory   — Past conversations & outcomes (ChromaDB)
# Tier 3: Procedural Memory — Learned workflows & macros (SQLite + ChromaDB)

from memory.memory_manager import memory_manager

__all__ = ["memory_manager"]
