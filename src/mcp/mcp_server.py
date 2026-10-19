"""
MCP server for GraphTriage.

Exposes three tools:
1. trace_blast_radius - Trace failure path and calculate blast radius
2. find_failure_path - Find the exact fault propagation chain
3. run_targeted_tests - Execute targeted pytest tests

Uses the Python MCP SDK over standard input/output.
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
    MCP server for GraphTriage.
    Provides tools for fault tracing, blast radius analysis, and targeted testing.
    """

    def __init__(self):
        # Use connection factory for central connection management
        from src.core.db_connection import get_falkordb_client
        self.resolver = IncidentResolver()
        self._ensure_data_ingested()

    def _ensure_data_ingested(self):
        """Seed the sandbox only when the selected graph is empty.

        Do not clear an existing graph just because it has no nodes labeled
        as failing tests; it may contain user-managed graph data.
        """
        try:
            failing_tests = self.resolver.get_failing_tests()
            if failing_tests:
                return

            count_result = self.resolver.graph.query("MATCH (n) RETURN count(n)")
            node_count = count_result.result_set[0][0] if count_result.result_set else 0
            if node_count == 0:
                logger.info("The selected graph is empty; seeding sandbox metadata")
                self.resolver.ingest_sandbox_service()
            else:
                logger.info(
                    "The selected graph already contains data; leaving it untouched "
                    "because no failing-test records were found."
                )
        except Exception:
            logger.exception("Could not verify the graph before sandbox seeding; leaving it untouched.")

    async def trace_blast_radius(self, arguments: Dict[str, Any]) -> List[Any]:
        """Return graph-supported impact for a function name."""
        function_name = arguments.get("function_name", "")
        max_hops = arguments.get("max_hops", 6)
        if not function_name:
            return [TextContent(type="text", text="Error: function_name is required")]

        try:
            analysis = self.resolver.analyze_impact(function_name)
            if analysis.get("status") != "COMPLETED":
                return [TextContent(type="text", text=json.dumps(analysis, indent=2))]

            # trace_failure_path expects a failing test name, not a function name.
            test_result = self.resolver.graph.query(
                """
                MATCH (t:Test {status: 'failing'})-[:COVERS]->(f:Function {name: $function_name})
                RETURN t.name
                LIMIT 1
                """,
                {"function_name": function_name},
            )
            if not test_result.result_set:
                test_result = self.resolver.graph.query(
                    """
                    MATCH (t:Test)-[:COVERS]->(f:Function {name: $function_name})
                    RETURN t.name
                    LIMIT 1
                    """,
                    {"function_name": function_name},
                )

            path = []
            if test_result.result_set:
                path = self.resolver.trace_failure_path(
                    test_result.result_set[0][0], max_hops=max_hops
                )

            response = {
                "function_name": function_name,
                "failure_path": path,
                "blast_radius": analysis.get("blast_radius", [])[:10],
                "affected_count": len(analysis.get("blast_radius", [])),
                "status": "completed",
            }
            return [TextContent(type="text", text=json.dumps(response, indent=2))]
        except Exception as e:
            logger.error("Error in trace_blast_radius: %s", e)
            return [TextContent(type="text", text=json.dumps({"error": str(e), "status": "failed"}))]

    async def find_failure_path(self, arguments: Dict[str, Any]) -> List[Any]:
        """Trace a failing test through the relationships currently stored in the graph."""
        test_name = arguments.get("test_name", "")
        max_hops = arguments.get("max_hops", 6)
        if not test_name:
            return [TextContent(type="text", text="Error: test_name is required")]

        try:
            path = self.resolver.trace_failure_path(test_name, max_hops=max_hops)
            if not path:
                response = {
                    "test_name": test_name,
                    "failure_path": [],
                    "path_length": 0,
                    "message": f"No graph path found for test: {test_name}",
                    "status": "not_found",
                }
            else:
                response = {
                    "test_name": test_name,
                    "failure_path": path,
                    "root_cause": path[-1].get("node"),
                    "path_length": len(path),
                    "status": "found",
                }
            return [TextContent(type="text", text=json.dumps(response, indent=2))]
        except Exception as e:
            logger.error("Error in find_failure_path: %s", e)
            return [TextContent(type="text", text=json.dumps({"error": str(e), "status": "failed"}))]

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
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )

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