"""
MCP Server for RepoGraph FalkorDB Incident Resolver.

Exposes three tools:
1. trace_blast_radius - Trace failure path and calculate blast radius
2. find_failure_path - Find the exact fault propagation chain
3. run_targeted_tests - Execute targeted pytest tests

Uses the official MCP SDK / FastMCP pattern.
"""
import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional

# Use mcp SDK if available, otherwise define a minimal implementation
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    logging.warning("MCP SDK not available. Install with: pip install mcp")

from src.core.incident_resolver import IncidentResolver

logger = logging.getLogger(__name__)


class RepoGraphMCPServer:
    """
    MCP Server for RepoGraph FalkorDB incident resolution.
    Provides tools for fault tracing, blast radius analysis, and targeted testing.
    """

    def __init__(self):
        # Use connection factory for central connection management
        from src.core.db_connection import get_falkordb_client
        self.resolver = IncidentResolver()
        self._ensure_data_ingested()

    def _ensure_data_ingested(self):
        """Ensure sandbox service data is ingested into FalkorDB."""
        try:
            # Check if we have data
            failing_tests = self.resolver.get_failing_tests()
            if not failing_tests:
                logger.info("Ingesting sandbox service data into graph")
                self.resolver.ingest_sandbox_service()
        except Exception as e:
            logger.warning(f"Could not ensure data ingested: {e}")
            try:
                self.resolver.ingest_sandbox_service()
            except Exception as e2:
                logger.error(f"Failed to ingest data: {e2}")

    async def trace_blast_radius(self, arguments: Dict[str, Any]) -> List[Any]:
        """
        Trace the blast radius of a function change.
        Returns affected functions ranked by impact score.
        """
        function_name = arguments.get("function_name", "")
        max_hops = arguments.get("max_hops", 6)

        if not function_name:
            return [TextContent(type="text",
                                text="Error: function_name is required")]

        try:
            # First trace failure path if function is connected to tests
            path = self.resolver.trace_failure_path(function_name, max_hops=max_hops)

            # Calculate blast radius
            blast_radius = self.resolver.calculate_blast_radius(function_name)

            response = {
                "function_name": function_name,
                "failure_path": path[:1] if path else [],  # Top path
                "blast_radius": blast_radius[:10],  # Top 10 affected functions
                "affected_count": len(blast_radius),
                "status": "completed"
            }

            return [TextContent(type="text", text=json.dumps(response, indent=2))]

        except Exception as e:
            logger.error(f"Error in trace_blast_radius: {e}")
            return [TextContent(type="text",
                                text=json.dumps({"error": str(e), "status": "failed"}))]

    async def find_failure_path(self, arguments: Dict[str, Any]) -> List[Any]:
        """
        Find the exact failure propagation chain from a failing test to root cause.
        Uses shortestPath Cypher query through FalkorDB.
        """
        test_name = arguments.get("test_name", "")
        max_hops = arguments.get("max_hops", 6)

        if not test_name:
            return [TextContent(type="text",
                                text="Error: test_name is required")]

        try:
            path = self.resolver.trace_failure_path(test_name, max_hops=max_hops)

            if not path:
                response = {
                    "test_name": test_name,
                    "failure_path": None,
                    "message": f"No failure path found for test: {test_name}",
                    "status": "not_found"
                }
                return [TextContent(type="text", text=json.dumps(response, indent=2))]

            path_data = path[0]

            # Get the root cause function
            nodes = path_data.get("nodes", [])
            root_cause = nodes[-1] if nodes else None  # Last node in shortest path is root cause

            response = {
                "test_name": test_name,
                "failure_path": path_data,
                "root_cause": root_cause,
                "path_length": path_data.get("path_length", 0),
                "status": "found"
            }

            return [TextContent(type="text", text=json.dumps(response, indent=2))]

        except Exception as e:
            logger.error(f"Error in find_failure_path: {e}")
            return [TextContent(type="text",
                                text=json.dumps({"error": str(e), "status": "failed"}))]

    async def run_targeted_tests(self, arguments: Dict[str, Any]) -> List[Any]:
        """
        Run targeted pytest tests instead of full test suite.
        Returns test execution results.
        """
        test_names = arguments.get("test_names", [])
        test_pattern = arguments.get("test_pattern", "")

        if not test_names and not test_pattern:
            return [TextContent(type="text",
                                text="Error: either test_names or test_pattern is required")]

        try:
            if test_pattern:
                # Use pytest pattern matching
                import subprocess
                import time

                cmd = ["python", "-m", "pytest", test_pattern, "-v", "--tb=short"]
                start_time = time.time()

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.getcwd() if "os" in dir() else None
                )

                duration = time.time() - start_time

                response = {
                    "pattern": test_pattern,
                    "command": " ".join(cmd),
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration": round(duration, 3),
                    "status": "completed"
                }
            else:
                response = self.resolver.run_targeted_tests(test_names)

            return [TextContent(type="text", text=json.dumps(response, indent=2))]

        except Exception as e:
            logger.error(f"Error in run_targeted_tests: {e}")
            return [TextContent(type="text",
                                text=json.dumps({"error": str(e), "status": "failed"}))]


def main():
    """Run the MCP server via stdio."""
    import os  # needed for cwd

    server = RepoGraphMCPServer()

    if HAS_MCP:
        # Use official MCP server
        mcp_server = Server("graphtriage")

        @mcp_server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="trace_blast_radius",
                    description="Trace the blast radius of a function change through the dependency graph",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "function_name": {
                                "type": "string",
                                "description": "Name of the function to analyze"
                            },
                            "max_hops": {
                                "type": "integer",
                                "description": "Maximum hops for path tracing",
                                "default": 6
                            }
                        },
                        "required": ["function_name"]
                    }
                ),
                Tool(
                    name="find_failure_path",
                    description="Find the exact failure propagation chain from a failing test to root cause",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "test_name": {
                                "type": "string",
                                "description": "Name of the failing test"
                            },
                            "max_hops": {
                                "type": "integer",
                                "description": "Maximum hops for path tracing",
                                "default": 6
                            }
                        },
                        "required": ["test_name"]
                    }
                ),
                Tool(
                    name="run_targeted_tests",
                    description="Run targeted pytest tests instead of full test suite",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "test_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of test names to run"
                            },
                            "test_pattern": {
                                "type": "string",
                                "description": "Pytest pattern to match tests"
                            }
                        }
                    }
                )
            ]

        @mcp_server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]):
            if name == "trace_blast_radius":
                return await server.trace_blast_radius(arguments)
            elif name == "find_failure_path":
                return await server.find_failure_path(arguments)
            elif name == "run_targeted_tests":
                return await server.run_targeted_tests(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                # Use initialization_options as required by newer MCP SDK
                from mcp.server.models import InitializationOptions
                await mcp_server.run(read_stream, write_stream, InitializationOptions())

        asyncio.run(run())
    else:
        # Fallback: run as standalone script with CLI
        import sys

        if len(sys.argv) < 2:
            print("Usage: python -m src.mcp.mcp_server <tool_name> [args_json]")
            print("Available tools: trace_blast_radius, find_failure_path, run_targeted_tests")
            sys.exit(1)

        tool_name = sys.argv[1]
        arguments = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

        async def run_fallback():
            if tool_name == "trace_blast_radius":
                result = await server.trace_blast_radius(arguments)
            elif tool_name == "find_failure_path":
                result = await server.find_failure_path(arguments)
            elif tool_name == "run_targeted_tests":
                result = await server.run_targeted_tests(arguments)
            else:
                print(f"Unknown tool: {tool_name}")
                sys.exit(1)

            for content in result:
                print(content.text)

        asyncio.run(run_fallback())


if __name__ == "__main__":
    main()