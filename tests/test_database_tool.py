#!/usr/bin/env python3
"""
Tests simples pour l'outil de base de données.
"""

import os
import sys

import pytest

# Add the src directory to the path so we can import from src.tool.base
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.database.tool import DatabaseTool


def test_database_tool_creation():
    """Test que l'on peut créer une instance de DatabaseTool."""
    tool = DatabaseTool()
    assert tool is not None
    print("+ DatabaseTool created successfully")


def test_database_tool_custom_path():
    """Test que l'on peut spécifier un chemin personnalisé."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        tool = DatabaseTool({"database_path": tmp_path})
        assert tool.database_path == tmp_path
        # Clean up
        tool.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    print("+ DatabaseTool handles custom path correctly")


def test_create_table_and_insert():
    """Test la création d'une table, l'insertion et la récupération de données."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        tool = DatabaseTool({"database_path": db_path})

        # Create table
        result = tool.execute(
            "run",
            "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)",
        )
        # For DDL statements, rowcount is -1 (unknown); we just ensure no exception
        # No assertions on lastrowid or rowcount
        print("+ Table created")

        # Insert a row
        result = tool.execute(
            "run",
            "INSERT INTO test (name, age) VALUES (?, ?)",
            ("Alice", 30),
        )
        assert result["rowcount"] == 1
        assert result["lastrowid"] == 1
        print("+ Row inserted")

        # Insert another row
        result = tool.execute(
            "run",
            "INSERT INTO test (name, age) VALUES (?, ?)",
            ("Bob", 25),
        )
        assert result["rowcount"] == 1
        assert result["lastrowid"] == 2
        print("+ Second row inserted")

        # Select all rows
        result = tool.execute("run", "SELECT * FROM test ORDER BY id")
        assert result["rowcount"] == 2
        rows = result["rows"]
        assert len(rows) == 2
        assert rows[0] == (1, "Alice", 30)
        assert rows[1] == (2, "Bob", 25)
        print("+ Rows retrieved correctly")

        # Update a row
        result = tool.execute(
            "run",
            "UPDATE test SET age = ? WHERE name = ?",
            (31, "Alice"),
        )
        assert result["rowcount"] == 1
        print("+ Row updated")

        # Select after update
        result = tool.execute("run", "SELECT * FROM test WHERE name = ?", ("Alice",))
        assert result["rowcount"] == 1
        assert result["rows"][0] == (1, "Alice", 31)
        print("+ Updated row retrieved")

        # Delete a row
        result = tool.execute(
            "run",
            "DELETE FROM test WHERE name = ?",
            ("Bob",),
        )
        assert result["rowcount"] == 1
        print("+ Row deleted")

        # Verify deletion
        result = tool.execute("run", "SELECT * FROM test")
        assert result["rowcount"] == 1
        assert result["rows"][0] == (1, "Alice", 31)
        print("+ Deletion verified")

        # List tables
        tables = tool.execute("tables")
        assert "test" in tables
        print("+ Tables list includes 'test'")

        # Get schema
        schema = tool.execute("schema", "test")
        assert isinstance(schema, list)
        # Should have columns: id, name, age
        col_names = [col["name"] for col in schema]
        assert set(col_names) == {"id", "name", "age"}
        print("+ Schema retrieved correctly")
    finally:
        # Ensure tool is closed before deleting file
        try:
            tool.close()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_error_handling():
    """Test la gestion d'erreurs de base."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        tool = DatabaseTool({"database_path": db_path})

        # SQL malformed
        # Ce bloc ne pouvait pas échouer : `assert False` levait une
        # `AssertionError` que le `except Exception` rattrapait, et la garde
        # cherchait le mot « error » dans le message… de l'assertion elle-même.
        with pytest.raises(Exception) as capture:
            tool.execute("run", "INSERT INTO")
        erreur = capture.value
        assert "sqlite3" in str(type(erreur)).lower() or "error" in str(erreur).lower()
        print("+ Malformed SQL triggers exception")

        # Unknown operation
        with pytest.raises(ValueError, match="Operation 'unknown_operation' inconnue"):
            tool.execute("unknown_operation")
        print("+ Unknown operation triggers ValueError")
    finally:
        try:
            tool.close()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    print("Running DatabaseTool unit tests...")
    try:
        test_database_tool_creation()
        test_database_tool_custom_path()
        test_create_table_and_insert()
        test_error_handling()
        print("\n* All tests passed!")
    except Exception as e:
        print(f"\n! Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)