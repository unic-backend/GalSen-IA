#!/usr/bin/env python3
"""
Test script for the Memory Engine.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem, MemoryType, MemoryPriority


def main():
    """Test the memory manager."""
    print("Initializing MemoryManager...")
    mm = MemoryManager()

    print("Testing save and get...")
    # Create a memory item
    item1 = MemoryItem(
        content="Ceci est un test de mémoire à court terme.",
        memory_type=MemoryType.SHORT_TERM,
        user_id="user1",
        session_id="session1",
        agent_id="planner",
        tags=["test", "french"],
        priority=MemoryPriority.HIGH
    )
    item_id1 = mm.save_memory(item1)
    print(f"Saved item with ID: {item_id1}")

    # Retrieve it
    retrieved = mm.get_memory(item_id1)
    assert retrieved is not None, "Failed to retrieve item"
    assert retrieved.content == item1.content, "Content mismatch"
    print("Retrieved item successfully.")

    print("Testing update...")
    # Update the item
    retrieved.content = "Ceci est un contenu mis à jour."
    updated = mm.update_memory(retrieved)
    assert updated, "Failed to update item"
    # Get it again to verify
    updated_item = mm.get_memory(item_id1)
    assert updated_item.content == "Ceci est un contenu mis à jour.", "Update not reflected"
    print("Updated item successfully.")

    print("Testing search...")
    # Save another item for search
    item2 = MemoryItem(
        content="Un autre élément de mémoire en anglais pour tester la recherche.",
        memory_type=MemoryType.LONG_TERM,
        user_id="user1",
        session_id="session2",
        agent_id="researcher",
        tags=["test", "english"],
        priority=MemoryPriority.MEDIUM
    )
    mm.save_memory(item2)

    # Search for French items
    results = mm.search_memory("mémoire", memory_type=MemoryType.SHORT_TERM, limit=5)
    print(f"Found {len(results)} results for 'mémoire' in short-term memory")
    assert len(results) > 0, "Should find at least one result"
    # The first result should be our updated item
    assert results[0][0].content == "Ceci est un contenu mis à jour.", "Search result mismatch"

    print("Testing ranking...")
    # Get all items and rank them
    all_items = mm._store.list_items(limit=100)
    ranked = mm._ranker.rank(all_items)
    print(f"Ranked {len(ranked)} items")
    assert len(ranked) == 2, "Should have two items ranked"
    # The high priority item should be ranked higher than medium priority
    # (assuming other factors are similar)
    assert ranked[0][0].priority.value >= ranked[1][0].priority.value, "Ranking order incorrect"

    print("Testing deletion...")
    deleted = mm.delete_memory(item_id1)
    assert deleted, "Failed to delete item"
    # Try to get it again
    deleted_item = mm.get_memory(item_id1)
    assert deleted_item is None, "Deleted item should not be retrievable"
    print("Deleted item successfully.")

    print("Testing clear...")
    # Clear all items for user1
    cleared = mm._store.clear(user_id="user1")
    print(f"Cleared {cleared} items for user1")
    # Now search should return nothing
    results = mm.search_memory("test", limit=5)
    assert len(results) == 0, "Should have no results after clear"
    print("Clear successful.")

    print("All tests passed!")


if __name__ == "__main__":
    main()