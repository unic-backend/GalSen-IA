#!/usr/bin/env python3
"""
Tests simples pour l'outil de mémoire.
"""

import os
import sys

# Add the src directory to the path so we can import from src.tool.base
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.tools.memory.tool import MemoryTool


def test_memory_tool_creation():
    """Test que l'on peut créer une instance de MemoryTool."""
    tool = MemoryTool()
    assert tool is not None
    print("+ MemoryTool created successfully")


def test_store_and_retrieve():
    """Test le stockage et la récupération d'un élément de mémoire."""
    tool = MemoryTool()
    try:
        # Store a simple item
        item_data = {
            "content": "Bonjour le monde",
            "memory_type": "short_term",
            "user_id": "user123",
            "tags": ["salut", "test"],
        }
        store_result = tool.execute("store", item_data)
        assert "id" in store_result
        item_id = store_result["id"]
        print(f"+ Item stored with id: {item_id}")

        # Retrieve the item
        retrieved = tool.execute("retrieve", item_id)
        assert retrieved is not None
        assert retrieved["content"] == "Bonjour le monde"
        assert retrieved["memory_type"] == "short_term"
        assert retrieved["user_id"] == "user123"
        assert set(retrait := retrieved["tags"]) == {"salut", "test"}
        print("+ Item retrieved correctly")

        # Search for the item
        search_results = tool.execute(
            "search", "bonjour", memory_type="short_term", limit=5
        )
        assert len(search_results) > 0
        found = any(r["id"] == item_id for r in search_results)
        assert found
        print("+ Item found in search")

        # Update the item
        update_data = {
            "id": item_id,
            "content": "Bonjour le monde mis à jour",
            "memory_type": "short_term",
            "user_id": "user123",
            "tags": ["mis à jour"],
        }
        update_result = tool.execute("update", update_data)
        assert update_result["updated"] is True
        print("+ Item updated")

        # Retrieve again to verify update
        retrieved_updated = tool.execute("retrieve", item_id)
        assert retrieved_updated["content"] == "Bonjour le monde mis à jour"
        assert retrieved_updated["tags"] == ["mis à jour"]
        print("+ Updated item retrieved correctly")

        # Delete the item
        delete_result = tool.execute("delete", item_id)
        assert delete_result["deleted"] is True
        print("+ Item deleted")

        # Verify deletion
        deleted_item = tool.execute("retrieve", item_id)
        assert deleted_item is None
        print("+ Deletion verified")

        # List items (should be empty or not contain the deleted item)
        list_result = tool.execute("list", user_id="user123")
        # Ensure our item is not in the list
        assert not any(item["id"] == item_id for item in list_result)
        print("+ Item not present in list after deletion")

    finally:
        # Clean up (no explicit cleanup needed for in-memory)
        pass


def test_error_handling():
    """Test la gestion d'erreurs de base."""
    tool = MemoryTool()
    try:
        # Unknown operation
        try:
            tool.execute("unknown_operation")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Opération 'unknown_operation' inconnue" in str(e)
            print("+ Unknown operation triggers ValueError")

        # Store with missing required fields? Actually content is not required but we can test invalid enum
        try:
            tool.execute(
                "store",
                {"content": "test", "memory_type": "invalid_type"},
            )
            assert False, "Should have raised ValueError for invalid memory_type"
        except ValueError as e:
            assert "Type de mémoire invalide" in str(e)
            print("+ Invalid memory_type triggers ValueError")

        # Retrieve with empty ID
        try:
            tool.execute("retrieve", "")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "L'ID de l'élément doit être une chaîne non vide" in str(e)
            print("+ Empty ID triggers ValueError")

        # Search with empty query
        try:
            tool.execute("search", "", limit=5)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "La requête de recherche doit être une chaîne non vide" in str(e)
            print("+ Empty query triggers ValueError")

    finally:
        pass


if __name__ == "__main__":
    print("Running MemoryTool unit tests...")
    try:
        test_memory_tool_creation()
        test_store_and_retrieve()
        test_error_handling()
        print("\n* All tests passed!")
    except Exception as e:
        print(f"\n! Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)