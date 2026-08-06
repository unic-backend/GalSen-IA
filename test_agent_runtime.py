#!/usr/bin/env python3
"""
Test script for the Agent Runtime.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from src.agent.runtime import AgentRuntime

def main():
    """Main function to test the AgentRuntime."""
    print("Initializing the AgentRuntime...")
    runtime = AgentRuntime()

    print("Processing a sample task...")
    # Example task input (in French as per project language rules)
    task_input = "Bonjour, je voudrais développer une application mobile pour l'éducation en Afrique de l'Ouest."

    result = runtime.execute_task(task_input)

    print("\n--- Response ---")
    print(f"Status: {result.get('status')}")
    print(f"Execution time: {result.get('execution_time_seconds')} seconds")
    print(f"Workflow used: {result.get('workflow_used')}")
    print(f"Agent results count: {len(result.get('agent_results', []))}")

    # Print a summary of each agent's result
    for i, agent_result in enumerate(result.get('agent_results', [])):
        print(f"\nAgent {i+1}: {agent_result.get('agent')} - Status: {agent_result.get('status')}")
        if agent_result.get('status') == 'success':
            print(f"  Result: {str(agent_result.get('result'))[:100]}...")  # Truncate for brevity
        else:
            print(f"  Error: {agent_result.get('error')}")

    print("\n--- Test completed ---")

if __name__ == "__main__":
    main()