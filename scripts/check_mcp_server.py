"""Quick local check that GraphTriage's MCP handlers can initialize.

Requires a reachable FalkorDB instance configured through environment variables.
"""
import sys

from src.mcp.mcp_server import RepoGraphMCPServer


def main() -> int:
    server = None
    try:
        server = RepoGraphMCPServer()
        required = ("trace_blast_radius", "find_failure_path", "run_targeted_tests")
        missing = [name for name in required if not callable(getattr(server, name, None))]
        if missing:
            print("Missing MCP handlers: " + ", ".join(missing))
            return 1
        print("MCP handlers initialized.")
        return 0
    except Exception as exc:
        print(f"MCP setup check failed: {exc}")
        return 1
    finally:
        if server is not None:
            server.resolver.close()


if __name__ == "__main__":
    sys.exit(main())
