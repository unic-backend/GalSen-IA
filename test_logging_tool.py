"""
Tests for the Logging tool.
"""

from unittest.mock import MagicMock

import pytest

from src.tools.logging.tool import LoggingTool


@pytest.fixture
def logging_tool():
    """Return a LoggingTool instance with default configuration."""
    return LoggingTool()


def test_logging_tool_initialization(logging_tool):
    """Test that the tool initializes."""
    assert logging_tool is not None


def test_logging_tool_available_operations(logging_tool):
    """Test that the available operations are returned correctly."""
    assert set(logging_tool.available_operations()) == {
        "list_logs",
        "add_log",
        "clear_logs",
    }


def test_logging_tool_list_logs_empty(logging_tool):
    """Test listing logs when empty returns an empty list."""
    result = logging_tool.execute("list_logs")
    assert isinstance(result, list)
    assert len(result) == 0


def test_logging_tool_add_log_success(logging_tool):
    """Test adding a log entry returns success."""
    result = logging_tool.execute("add_log", message="Test message", level="INFO")
    assert result["status"] == "success"
    assert "ajoutée" in result["message"].lower()
    assert result["log_id"] == 1

    # Verify the log is stored
    logs = logging_tool.execute("list_logs")
    assert len(logs) == 1
    assert logs[0]["message"] == "Test message"
    assert logs[0]["level"] == "INFO"
    assert "id" in logs[0]
    assert "timestamp" in logs[0]


def test_logging_tool_add_log_invalid_message(logging_tool):
    """Test that adding a log with invalid message raises ValueError."""
    with pytest.raises(ValueError, match="Le message du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message="", level="INFO")

    with pytest.raises(ValueError, match="Le message du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message=None, level="INFO")

    with pytest.raises(ValueError, match="Le message du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message="   ", level="INFO")


def test_logging_tool_add_log_invalid_level(logging_tool):
    """Test that adding a log with invalid level raises ValueError."""
    with pytest.raises(ValueError, match="Le niveau du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message="Test", level="")

    with pytest.raises(ValueError, match="Le niveau du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message="Test", level=None)

    with pytest.raises(ValueError, match="Le niveau du journal doit être une chaîne non vide"):
        logging_tool.execute("add_log", message="Test", level="   ")


def test_logging_tool_list_logs_with_filter(logging_tool):
    """Test listing logs with level filter."""
    # Add a few logs
    logging_tool.execute("add_log", message="Info message", level="INFO")
    logging_tool.execute("add_log", message="Error message", level="ERROR")
    logging_tool.execute("add_log", message="Another info", level="INFO")

    # Filter by INFO level
    result = logging_tool.execute("list_logs", level="INFO")
    assert isinstance(result, list)
    assert len(result) == 2  # two? Actually we added two INFO logs.
    # Should be most recent first
    assert result[0]["message"] == "Another info"
    assert result[1]["message"] == "Info message"
    assert all(log["level"] == "INFO" for log in result)


def test_logging_tool_list_logs_limit(logging_tool):
    """Test listing logs with limit."""
    # Add 5 logs
    for i in range(5):
        logging_tool.execute("add_log", message=f"Message {i}", level="INFO")

    # Limit to 3
    result = logging_tool.execute("list_logs", limit=3)
    assert len(result) == 3
    # Should be the three most recent: messages 4,3,2
    assert result[0]["message"] == "Message 4"
    assert result[1]["message"] == "Message 3"
    assert result[2]["message"] == "Message 2"


def test_logging_tool_clear_logs(logging_tool):
    """Test clearing logs."""
    # Add a log
    logging_tool.execute("add_log", message="To be cleared", level="INFO")
    assert len(logging_tool.execute("list_logs")) == 1

    # Clear
    result = logging_tool.execute("clear_logs")
    assert result["status"] == "success"
    assert "effacés" in result["message"].lower()

    # Verify logs are empty
    assert logging_tool.execute("list_logs") == []


def test_logging_tool_unknown_operation(logging_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        logging_tool.execute("unknown")