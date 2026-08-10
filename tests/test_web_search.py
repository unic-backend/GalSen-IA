#!/usr/bin/env python3
"""
Test script for the Web Search Tool.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tool.tool_engine import ToolEngine

def main():
    """Main function to test the ToolEngine with web search."""
    print("Initializing the ToolEngine...")
    # Use the path to the tools registry relative to the project root
    registry_path = os.path.join(os.path.dirname(__file__), '..', 'tools', 'tools.yaml')
    engine = ToolEngine(registry_path)

    print("\n--- Tool Engine Info ---")
    print(f"Number of tools: {len(engine.list_tools())}")
    print(f"Number of enabled tools: {len(engine.list_enabled_tools())}")

    print("\n--- Categories ---")
    for category in engine.get_tool_categories():
        print(f"  - {category}")

    print("\n--- Testing tool info for 'web_search' ---")
    ws_info = engine.get_tool_info('web_search')
    if ws_info:
        print(f"  ID: {ws_info['id']}")
        print(f"  Enabled: {ws_info['enabled']}")
        print(f"  Category: {ws_info['category']}")
        print(f"  Module: {ws_info['module']}")
        print(f"  Class: {ws_info['class']}")
    else:
        print("  Tool 'web_search' not found.")
        return

    print("\n--- Executing web_search for 'test query' ---")
    try:
        result = engine.execute_tool('web_search', 'test query', search_type='web', max_results=3)
        print(f"Search returned {len(result)} results:")
        for i, r in enumerate(result, 1):
            print(f"  {i}. {r['title']}")
            print(f"     URL: {r['url']}")
            print(f"     Snippet: {r['snippet'][:100]}...")
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Test completed ---")

if __name__ == "__main__":
    main()