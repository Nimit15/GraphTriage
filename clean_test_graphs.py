#!/usr/bin/env python3
"""
Clean up temporary test graphs from FalkorDB, keeping only graphtriage and graphtriage_memory.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.db_connection import get_falkordb_client

def clean_test_graphs():
    """Connect to FalkorDB and remove temporary test graphs."""
    try:
        client = get_falkordb_client()
        print(f"Connected to FalkorDB at {client.connection.host}:{client.connection.port}")

        # Try to list graphs
        try:
            graphs = client.list_graphs()
            print(f"Found {len(graphs)} graphs: {graphs}")
        except Exception as e:
            print(f"Could not list graphs: {e}")
            # Try to use GRAPH.LIST
            try:
                result = client.execute_command("GRAPH.LIST")
                print(f"GRAPH.LIST result: {result}")
            except Exception as e2:
                print(f"GRAPH.LIST also failed: {e2}")

        # Try to delete known test graph patterns
        test_patterns = [
            'graphtriage_test',
            'graphtriage_smoketest',
            'graphtriage_ws_test',
            'repograph_test_memory',
            'repograph_ws_test',
        ]

        for pattern in test_patterns:
            try:
                graph = client.select_graph(pattern)
                graph.query("MATCH (n) DETACH DELETE n")
                print(f"Cleared nodes from graph: {pattern}")
            except Exception as e:
                pass  # Graph might not exist

        # Also try to drop graphs if the command is supported
        for pattern in test_patterns:
            try:
                graph = client.select_graph(pattern)
                graph.query(f"CALL db.dropGraph('{pattern}')")
                print(f"Dropped graph: {pattern}")
            except Exception as e:
                pass

        print("Cleanup complete. Kept: graphtriage, graphtriage_memory")
        return True

    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

def clean_cloud_instance():
    """Try to connect to cloud instance and clean up if credentials available."""
    cloud_host = os.getenv("FALKORDB_CLOUD_HOST", "r-6jissuruar.instance-b8qwn0ea0.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud")
    cloud_port = int(os.getenv("FALKORDB_CLOUD_PORT", "57210"))
    cloud_user = os.getenv("FALKORDB_CLOUD_USERNAME", "")
    cloud_pass = os.getenv("FALKORDB_CLOUD_PASSWORD", "")

    if not cloud_user or not cloud_pass:
        print("Cloud credentials not available, skipping cloud cleanup")
        return

    try:
        from falkordb import FalkorDB
        client = FalkorDB(
            host=cloud_host,
            port=cloud_port,
            username=cloud_user,
            password=cloud_pass,
            ssl=True
        )
        print(f"Connected to Cloud FalkorDB at {cloud_host}:{cloud_port}")

        test_patterns = [
            'graphtriage_test',
            'graphtriage_smoketest',
            'graphtriage_ws_test',
            'repograph_test_memory',
            'repograph_ws_test',
        ]

        for pattern in test_patterns:
            try:
                graph = client.select_graph(pattern)
                graph.query("MATCH (n) DETACH DELETE n")
                print(f"Cleared nodes from cloud graph: {pattern}")
            except Exception as e:
                pass

        for pattern in test_patterns:
            try:
                graph = client.select_graph(pattern)
                graph.query(f"CALL db.dropGraph('{pattern}')")
                print(f"Dropped cloud graph: {pattern}")
            except Exception as e:
                pass

        print("Cloud cleanup complete. Kept: graphtriage, graphtriage_memory")

    except Exception as e:
        print(f"Cloud cleanup error (expected if no access): {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Cleaning up test graphs from local FalkorDB...")
    print("=" * 60)
    clean_test_graphs()

    print("\n" + "=" * 60)
    print("Attempting cloud FalkorDB cleanup...")
    print("=" * 60)
    clean_cloud_instance()

    print("\nDone!")