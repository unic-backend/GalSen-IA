"""
Tests for the Metrics tool.
"""

import pytest

from src.tools.metrics.tool import MetricsTool


@pytest.fixture
def metrics_tool():
    """Return a MetricsTool instance with default configuration."""
    return MetricsTool()


def test_metrics_tool_initialization(metrics_tool):
    """Test that the tool initializes."""
    assert metrics_tool is not None


def test_metrics_tool_available_operations(metrics_tool):
    """Test that the available operations are returned correctly."""
    assert set(metrics_tool.available_operations()) == {
        "increment",
        "set_gauge",
        "record_histogram",
        "get_metrics",
        "reset",
    }


def test_metrics_increment(metrics_tool):
    """Test incrementing a counter."""
    result = metrics_tool.execute("increment", "requests", 5)
    assert result["status"] == "success"
    assert result["metric"] == "counter"
    assert result["name"] == "requests"
    assert result["value"] == 5

    # Increment again
    result2 = metrics_tool.execute("increment", "requests", 3)
    assert result2["value"] == 8

    # Default increment of 1
    result3 = metrics_tool.execute("increment", "errors")
    assert result3["value"] == 1


def test_metrics_invalid_increment(metrics_tool):
    """Test invalid inputs for increment."""
    with pytest.raises(ValueError, match="Le nom du compteur doit être une chaîne non vide"):
        metrics_tool.execute("increment", "", 5)
    with pytest.raises(ValueError, match="Le nom du compteur doit être une chaîne non vide"):
        metrics_tool.execute("increment", None, 5)
    with pytest.raises(ValueError, match="La valeur d'incrément doit être un entier"):
        metrics_tool.execute("increment", "test", "not_int")
    with pytest.raises(ValueError, match="Le nom du compteur doit être une chaîne non vide"):
        metrics_tool.execute("increment", "   ", 5)


def test_metrics_set_gauge(metrics_tool):
    """Test setting a gauge."""
    result = metrics_tool.execute("set_gauge", "temperature", 23.5)
    assert result["status"] == "success"
    assert result["metric"] == "gauge"
    assert result["name"] == "temperature"
    assert result["value"] == 23.5

    # Update gauge
    result2 = metrics_tool.execute("set_gauge", "temperature", 25.0)
    assert result2["value"] == 25.0


def test_metrics_invalid_gauge(metrics_tool):
    """Test invalid inputs for gauge."""
    with pytest.raises(ValueError, match="Le nom de la jauge doit être une chaîne non vide"):
        metrics_tool.execute("set_gauge", "", 5.0)
    with pytest.raises(ValueError, match="Le nom de la jauge doit être une chaîne non vide"):
        metrics_tool.execute("set_gauge", None, 5.0)
    with pytest.raises(ValueError, match="La valeur de la jauge doit être un nombre"):
        metrics_tool.execute("set_gauge", "test", "not_number")
    with pytest.raises(ValueError, match="Le nom de la jauge doit être une chaîne non vide"):
        metrics_tool.execute("set_gauge", "   ", 5.0)


def test_metrics_record_histogram(metrics_tool):
    """Test recording a histogram value."""
    result = metrics_tool.execute("record_histogram", "latency", 0.1)
    assert result["status"] == "success"
    assert result["metric"] == "histogram"
    assert result["name"] == "latency"
    assert result["sample_count"] == 1

    result2 = metrics_tool.execute("record_histogram", "latency", 0.2)
    assert result2["sample_count"] == 2


def test_metrics_invalid_histogram(metrics_tool):
    """Test invalid inputs for histogram."""
    with pytest.raises(ValueError, match="Le nom de l'histogramme doit être une chaîne non vide"):
        metrics_tool.execute("record_histogram", "", 5.0)
    with pytest.raises(ValueError, match="Le nom de l'histogramme doit être une chaîne non vide"):
        metrics_tool.execute("record_histogram", None, 5.0)
    with pytest.raises(ValueError, match="La valeur de l'histogramme doit être un nombre"):
        metrics_tool.execute("record_histogram", "test", "not_number")
    with pytest.raises(ValueError, match="Le nom de l'histogramme doit être une chaîne non vide"):
        metrics_tool.execute("record_histogram", "   ", 5.0)


def test_metrics_get_metrics(metrics_tool):
    """Test retrieving all metrics."""
    # Add some data
    metrics_tool.execute("increment", "hits", 10)
    metrics_tool.execute("set_gauge", "queue_length", 5)
    metrics_tool.execute("record_histogram", "process_time", 1.2)
    metrics_tool.execute("record_histogram", "process_time", 1.8)

    result = metrics_tool.execute("get_metrics")
    assert result["status"] == "success"
    assert result["counters"]["hits"] == 10
    assert result["gauges"]["queue_length"] == 5.0
    hist = result["histograms"]["process_time"]
    assert hist["count"] == 2
    assert hist["sum"] == 3.0
    assert hist["min"] == 1.2
    assert hist["max"] == 1.8
    assert hist["mean"] == 1.5


def test_metrics_reset(metrics_tool):
    """Test resetting all metrics."""
    metrics_tool.execute("increment", "x", 1)
    metrics_tool.execute("set_gauge", "y", 2.0)
    metrics_tool.execute("record_histogram", "z", 3.0)

    assert metrics_tool.execute("get_metrics")["counters"]  # non-empty

    reset_result = metrics_tool.execute("reset")
    assert reset_result["status"] == "success"
    assert "remises à zéro" in reset_result["message"]

    # After reset, everything should be empty/default
    after = metrics_tool.execute("get_metrics")
    assert after["counters"] == {}
    assert after["gauges"] == {}
    assert all(v["count"] == 0 for v in after["histograms"].values())


def test_metrics_unknown_operation(metrics_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        metrics_tool.execute("unknown")