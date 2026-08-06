#!/usr/bin/env python3
"""
Simple test script to verify the APITool works correctly.
"""

import sys
import os

# Add the src directory to the path so we can import from src.tool.base
sys.path.insert(0, os.path.dirname(__file__))

from src.tools.api.tool import APITool

def test_api_tool_creation():
    """Test that we can create an APITool instance."""
    print("Testing APITool creation...")
    tool = APITool()
    assert tool is not None
    print("+ APITool created successfully")

def test_api_tool_inheritance():
    """Test that APITool inherits from BaseTool."""
    print("Testing APITool inheritance...")
    from src.tool.base import BaseTool
    tool = APITool()
    assert isinstance(tool, BaseTool)
    print("+ APITool correctly inherits from BaseTool")

def test_api_tool_config():
    """Test that APITool handles configuration correctly."""
    print("Testing APITool configuration...")
    # Test with default config
    tool1 = APITool()
    assert tool1.timeout == 30
    assert tool1.max_retries == 3
    assert "GalSen IA API Tool" in tool1.user_agent

    # Test with custom config
    custom_config = {
        "timeout": 60,
        "max_retries": 5,
        "user_agent": "Test Agent 1.0"
    }
    tool2 = APITool(custom_config)
    assert tool2.timeout == 60
    assert tool2.max_retries == 5
    assert tool2.user_agent == "Test Agent 1.0"
    print("+ APITool handles configuration correctly")

def test_api_tool_operations():
    """Test that APITool supports the expected operations."""
    print("Testing APITool operations...")
    tool = APITool()

    # Check that the tool has the expected methods
    assert hasattr(tool, 'get')
    assert hasattr(tool, 'post')
    assert hasattr(tool, 'put')
    assert hasattr(tool, 'delete')
    assert hasattr(tool, 'patch')
    assert hasattr(tool, 'request')
    assert hasattr(tool, 'execute')
    print("+ APITool has expected methods")

def test_execute_method():
    """Test the execute method with different operations."""
    print("Testing APITool execute method...")
    tool = APITool()

    # Test that execute method exists and is callable
    assert callable(tool.execute)

    # We won't actually execute HTTP requests in this unit test
    # since we don't want to make external network calls
    print("+ APITool execute method is callable")

if __name__ == "__main__":
    print("Running APITool unit tests...\n")

    try:
        test_api_tool_creation()
        test_api_tool_inheritance()
        test_api_tool_config()
        test_api_tool_operations()
        test_execute_method()

        print("\n* All tests passed!")
    except Exception as e:
        print(f"\n! Test failed: {e}")
        sys.exit(1)