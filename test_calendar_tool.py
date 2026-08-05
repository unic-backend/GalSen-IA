"""
Tests for the Calendar tool.
"""

from unittest.mock import patch

import pytest

from src.tools.calendar.tool import CalendarTool


@pytest.fixture
def calendar_tool():
    """Return a CalendarTool instance with default configuration."""
    return CalendarTool()


def test_calendar_tool_initialization(calendar_tool):
    """Test that the tool initializes."""
    assert calendar_tool is not None


def test_calendar_tool_available_operations(calendar_tool):
    """Test that the available operations are returned correctly."""
    assert set(calendar_tool.available_operations()) == {"get_events", "add_event", "delete_event"}


def test_calendar_tool_get_events(calendar_tool):
    """Test getting events returns a list of events."""
    result = calendar_tool.execute("get_events")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Réunion d'équipe"
    assert result[1]["title"] == "Déjeuner avec client"


def test_calendar_tool_add_event_success(calendar_tool):
    """Test adding an event successfully."""
    result = calendar_tool.execute(
        "add_event",
        title="Test Event",
        start="2026-08-01T10:00:00",
        end="2026-08-01T11:00:00",
    )
    assert result["status"] == "success"
    assert "événement" in result["message"].lower()
    assert "event_id" in result


def test_calendar_tool_add_event_invalid_title(calendar_tool):
    """Test that a ValueError is raised for invalid title."""
    with pytest.raises(ValueError, match="Le titre de l'événement doit être une chaîne non vide"):
        calendar_tool.execute(
            "add_event",
            title="",
            start="2026-08-01T10:00:00",
            end="2026-08-01T11:00:00",
        )

    with pytest.raises(ValueError, match="Le titre de l'événement doit être une chaîne non vide"):
        calendar_tool.execute(
            "add_event",
            title=None,
            start="2026-08-01T10:00:00",
            end="2026-08-01T11:00:00",
        )


def test_calendar_tool_add_event_invalid_start(calendar_tool):
    """Test that a ValueError is raised for invalid start time."""
    with pytest.raises(ValueError, match="La date de début doit être une chaîne non vide"):
        calendar_tool.execute(
            "add_event",
            title="Test Event",
            start="",
            end="2026-08-01T11:00:00",
        )


def test_calendar_tool_add_event_invalid_end(calendar_tool):
    """Test that a ValueError is raised for invalid end time."""
    with pytest.raises(ValueError, match="La date de fin doit être une chaîne non vide"):
        calendar_tool.execute(
            "add_event",
            title="Test Event",
            start="2026-08-01T10:00:00",
            end="",
        )


def test_calendar_tool_delete_event_success(calendar_tool):
    """Test deleting an event successfully."""
    result = calendar_tool.execute("delete_event", event_id="event123")
    assert result["status"] == "success"
    assert "événement" in result["message"].lower()
    assert "event123" in result["message"]


def test_calendar_tool_delete_event_invalid_id(calendar_tool):
    """Test that a ValueError is raised for invalid event ID."""
    with pytest.raises(ValueError, match="L'identifiant de l'événement doit être une chaîne non vide"):
        calendar_tool.execute("delete_event", event_id="")

    with pytest.raises(ValueError, match="L'identifiant de l'événement doit être une chaîne non vide"):
        calendar_tool.execute("delete_event", event_id=None)


def test_calendar_tool_unknown_operation(calendar_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue. Opérations disponibles: get_events, add_event, delete_event"):
        calendar_tool.execute("unknown")