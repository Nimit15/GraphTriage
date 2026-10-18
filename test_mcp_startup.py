#!/usr/bin/env python3
"""
MCP Server startup test script.
Tests MCP server initialization and tool listing without database connection.
"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.mcp.mcp_server import RepoGraphMCPServer

async def test_mcp_startup():
    """Test MCP server startup and tool listing."""
    print("Testing MCP server startup...")

    try:
        # Create MCP server instance
        server = RepoGraphMCPServer()
        print("MCP server initialized successfully")

        # Test tool listing
        if hasattr(server, 'resolver'):
            # Check if tools are available
            tools = [
                "trace_blast_radius",
                "find_failure_path",
                "run_targeted_tests"
            ]

            for tool_name in tools:
                if hasattr(server, tool_name):
                    print(f"Tool '{tool_name}' available")
                else:
                    print(f"Tool '{tool_name}' missing")

        print("\nMCP server startup test completed!")
        return True

    except Exception as e:
        print(f"MCP server startup failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_startup())
    sys.exit(0 if success else 1)