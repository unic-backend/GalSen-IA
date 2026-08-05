#!/usr/bin/env python3
"""
Test script for the Router Engine.

This script initializes the RouterEngine and processes a sample request.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.router.router_engine import RouterEngine

def main():
    """Main function to test the RouterEngine."""
    print("Initializing the RouterEngine...")
    router = RouterEngine()

    print("Processing a sample request...")
    # Example request in French (as per project language rules)
    user_request = "Bonjour, je voudrais développer une application mobile pour l'éducation en Afrique de l'Ouest."

    response = router.process_request(user_request)

    print("\n--- Response ---")
    print(f"Status: {response.get('status')}")
    print(f"Execution time: {response.get('execution_time_seconds')} seconds")
    print(f"Workflow used: {response.get('workflow_used')}")
    print(f"Agent results count: {len(response.get('agent_results', []))}")

    # Print a summary of each agent's result
    for i, agent_result in enumerate(response.get('agent_results', [])):
        print(f"\nAgent {i+1}: {agent_result.get('agent')} - Status: {agent_result.get('status')}")
        if agent_result.get('status') == 'success':
            print(f"  Result: {str(agent_result.get('result'))[:100]}...")  # Truncate for brevity
        else:
            print(f"  Error: {agent_result.get('error')}")

    print("\n--- Test completed ---")

if __name__ == "__main__":
    main()