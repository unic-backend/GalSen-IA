#!/usr/bin/env python3
"""
Simple test script to verify the BrowserTool works correctly.
"""

import sys
import os

# Add the src directory to the path so we can import from src.tool.base
sys.path.insert(0, os.path.dirname(__file__))

from src.tools.browser.tool import BrowserTool

def test_browser_tool_creation():
    """Test that we can create a BrowserTool instance."""
    print("Testing BrowserTool creation...")
    tool = BrowserTool()
    assert tool is not None
    print("+ BrowserTool created successfully")

def test_browser_tool_inheritance():
    """Test that BrowserTool inherits from BaseTool."""
    print("Testing BrowserTool inheritance...")
    from src.tool.base import BaseTool
    tool = BrowserTool()
    assert isinstance(tool, BaseTool)
    print("+ BrowserTool correctly inherits from BaseTool")

def test_browser_tool_config():
    """Test that BrowserTool handles configuration correctly."""
    print("Testing BrowserTool configuration...")
    # Test with default config
    tool1 = BrowserTool()
    assert tool1.timeout == 30
    assert tool1.max_retries == 3
    assert "Mozilla/5.0" in tool1.user_agent

    # Test with custom config
    custom_config = {
        "timeout": 60,
        "max_retries": 5,
        "user_agent": "Test Agent 1.0"
    }
    tool2 = BrowserTool(custom_config)
    assert tool2.timeout == 60
    assert tool2.max_retries == 5
    assert tool2.user_agent == "Test Agent 1.0"
    print("+ BrowserTool handles configuration correctly")

def test_browser_tool_operations():
    """Test that BrowserTool supports the expected operations."""
    print("Testing BrowserTool operations...")
    tool = BrowserTool()

    # Check that the tool has the expected methods
    assert hasattr(tool, 'visit')
    assert hasattr(tool, 'get_text')
    assert hasattr(tool, 'get_links')
    assert hasattr(tool, 'get_title')
    assert hasattr(tool, 'execute')
    print("+ BrowserTool has expected methods")

def test_execute_method():
    """Test the execute method with different operations."""
    print("Testing BrowserTool execute method...")
    tool = BrowserTool()

    # Test that execute method exists and is callable
    assert callable(tool.execute)

    # We won't actually execute web requests in this unit test
    # since we don't want to make external network calls
    print("+ BrowserTool execute method is callable")

if __name__ == "__main__":
    print("Running BrowserTool unit tests...\n")

    try:
        test_browser_tool_creation()
        test_browser_tool_inheritance()
        test_browser_tool_config()
        test_browser_tool_operations()
        test_execute_method()

        print("\n* All tests passed!")
    except Exception as e:
        print(f"\n! Test failed: {e}")
        sys.exit(1)