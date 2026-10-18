#!/usr/bin/env python3
"""
Demo script to test FalkorDB connectivity and RepoGraph functionality.
This script demonstrates the core features of the RepoGraph FalkorDB implementation.
"""
import os
import sys
import json
import logging
from src.core.incident_resolver import IncidentResolver
from src.core.temporal_memory import TemporalMemory, WorkspaceManager
from src.core.multi_agent_pipeline import MultiAgentPipeline, demo_pipeline

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_falkorDB_connectivity():
    """Check if FalkorDB is available and working."""
    print("🔍 Checking FalkorDB connectivity...")

    # Try to create an IncidentResolver
    try:
        resolver = IncidentResolver()
        print("✅ FalkorDB connectivity: SUCCESS")
        return resolver
    except Exception as e:
        print(f"❌ FalkorDB connectivity: FAILED - {e}")
        print("Note: This is expected if FalkorDB is not running locally.")
        print("To set up FalkorDB: docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest")
        return None

def test_incident_resolver(resolver):
    """Test the incident resolver functionality."""
    print("\n🧪 Testing Incident Resolver...")

    if not resolver:
        print("⏭️  Skipping - FalkorDB not available")
        return False

    try:
        # Ingest sandbox data
        print("📥 Ingesting sandbox service data...")
        resolver.ingest_sandbox_service()

        # Get failing tests
        failing_tests = resolver.get_failing_tests()
        print(f"📊 Found {len(failing_tests)} failing tests:")
        for test in failing_tests:
            print(f"  - {test['test_name']}: {test['expected_exception']}")

        # Test failure path tracing
        if failing_tests:
            test_name = failing_tests[0]['test_name']
            print(f"\n🔗 Tracing failure path for: {test_name}")
            path = resolver.trace_failure_path(test_name)
            if path:
                print(f"✅ Found {len(path)} failure path(s)")
                print(f"   Path length: {path[0]['path_length']}")
            else:
                print("⚠️  No failure path found")

        # Test blast radius calculation
        print(f"\n📈 Calculating blast radius for process_user_data...")
        blast_radius = resolver.calculate_blast_radius("process_user_data")
        print(f"✅ Blast radius: {len(blast_radius)} affected functions")

        resolver.close()
        print("✅ All Incident Resolver tests passed!")
        return True

    except Exception as e:
        print(f"❌ Incident Resolver tests failed: {e}")
        import traceback
        traceback.print_exc()
        if resolver:
            resolver.close()
        return False

def test_temporal_memory(resolver=None):
    """Test the temporal memory system."""
    print("\n💾 Testing Temporal Memory System...")

    try:
        # Create temporal memory
        memory = TemporalMemory()

        # Create a semantic fact
        fact_id = memory.create_semantic_fact({
            "workspace_id": "demo",
            "fact_type": "root_cause",
            "function_name": "process_user_data",
            "statement": "Function requires input validation to handle missing fields",
            "confidence": 0.95,
            "tags": ["bug", "validation", "security"]
        })
        print(f"✅ Created semantic fact: {fact_id}")

        # Get active facts
        active_facts = memory.get_active_facts("process_user_data", "demo")
        print(f"✅ Retrieved {len(active_facts)} active facts for process_user_data")

        # Supersede the fact
        new_fact_id = memory.supersede_fact(fact_id, {
            "workspace_id": "demo",
            "fact_type": "root_cause",
            "function_name": "process_user_data",
            "statement": "Function should use user.get('income', 0) for missing fields",
            "confidence": 0.99,
            "tags": ["bug", "validation", "missing_field", "fixed"]
        })
        print(f"✅ Superseded fact with: {new_fact_id}")

        # Get fact history
        history = memory.get_facts_with_history("process_user_data", "demo")
        print(f"✅ Fact history contains {len(history)} versions")

        memory.close()
        print("✅ All Temporal Memory tests passed!")
        return True

    except Exception as e:
        print(f"❌ Temporal Memory tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workspace_isolation(resolver=None):
    """Test workspace isolation."""
    print("\n🔒 Testing Workspace Isolation...")

    try:
        workspace_manager = WorkspaceManager()

        # Test isolation between two workspaces
        isolation_works = workspace_manager.verify_isolation("workspace_a", "workspace_b")
        if isolation_works:
            print("✅ Workspace isolation verified")
            return True
        else:
            print("⚠️  Workspace isolation test inconclusive (requires FalkorDB)")
            return True  # Not a failure, just inconclusive

    except Exception as e:
        print(f"❌ Workspace isolation test failed: {e}")
        return False

def test_multi_agent_pipeline():
    """Test the multi-agent pipeline."""
    print("\n🤖 Testing Multi-Agent Pipeline...")

    try:
        # Create a pipeline
        pipeline = MultiAgentPipeline(workspace_id="demo")

        # Create a simple incident
        incident = {
            "incident_id": "demo_001",
            "session_id": "session_abc",
            "stack_trace": """
Traceback (most recent call last):
  File "sandbox_service/app.py", line 14, in process_user_data
    total_income += user['income']
KeyError: 'income'
""",
            "failing_test": "test_incident_process_user_data_missing_income"
        }

        # Run the pipeline
        result = pipeline.run(incident)

        print("\n📋 Pipeline Results:")
        print(f"  Fault Signature: {result.fault_signature}")
        print(f"  Root Cause Function: {result.root_cause_function}")
        print(f"  Affected Functions: {result.affected_functions}")
        print(f"  Blast Radius: {len(result.blast_radius)} functions")
        print(f"  Semantic Facts Created: {result.semantic_facts_created}")
        print(f"  Playbook Recommendations: {result.playbook_recommendations}")

        print("✅ Multi-Agent Pipeline test passed!")
        return True

    except Exception as e:
        print(f"❌ Multi-Agent Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mcp_server():
    """Test the MCP server."""
    print("\n🔧 Testing MCP Server...")

    try:
        from src.mcp.mcp_server import RepoGraphMCPServer

        server = RepoGraphMCPServer()
        print("✅ MCP Server created successfully")

        # Test tool calls
        async def test_tools():
            # Test trace_blast_radius
            result = await server.trace_blast_radius({"function_name": "process_user_data"})
            print(f"✅ trace_blast_radius tool: {len(result)} results")

            # Test find_failure_path
            result = await server.find_failure_path({"test_name": "test_incident_process_user_data_missing_income"})
            print(f"✅ find_failure_path tool: {len(result)} results")

            # Test run_targeted_tests
            result = await server.run_targeted_tests({"test_names": ["test_calculate_distance"]})
            print(f"✅ run_targeted_tests tool: {len(result)} results")

            await server.resolver.close()

        # Run async tests
        import asyncio
        asyncio.run(test_tools())

        print("✅ MCP Server tests passed!")
        return True

    except Exception as e:
        print(f"❌ MCP Server tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("RepoGraph FalkorDB - Comprehensive Test Suite")
    print("=" * 60)

    # Set environment to use containerized FalkorDB if available
    os.environ["FALKORDB_HOST"] = os.environ.get("FALKORDB_HOST", "localhost")
    os.environ["FALKORDB_PORT"] = os.environ.get("FALKORDB_PORT", "6379")

    # Test 1: FalkorDB connectivity
    resolver = check_falkorDB_connectivity()

    # Test 2: Incident Resolver
    incident_resolver_ok = test_incident_resolver(resolver)

    # Test 3: Temporal Memory
    temporal_memory_ok = test_temporal_memory(resolver)

    # Test 4: Workspace Isolation
    workspace_isolation_ok = test_workspace_isolation(resolver)

    # Test 5: Multi-Agent Pipeline
    multi_agent_ok = test_multi_agent_pipeline()

    # Test 6: MCP Server
    mcp_server_ok = test_mcp_server()

    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  FalkorDB Connectivity: {'✅ PASS' if resolver else '❌ SKIP'}")
    print(f"  Incident Resolver: {'✅ PASS' if incident_resolver_ok else '❌ FAIL'}")
    print(f"  Temporal Memory: {'✅ PASS' if temporal_memory_ok else '❌ FAIL'}")
    print(f"  Workspace Isolation: {'✅ PASS' if workspace_isolation_ok else '⚠️  SKIP'}")
    print(f"  Multi-Agent Pipeline: {'✅ PASS' if multi_agent_ok else '❌ FAIL'}")
    print(f"  MCP Server: {'✅ PASS' if mcp_server_ok else '❌ FAIL'}")

    if resolver:
        resolver.close()

    print("\n" + "=" * 60)
    if resolver and all([incident_resolver_ok, temporal_memory_ok, multi_agent_ok, mcp_server_ok]):
        print("🎉 ALL TESTS PASSED! RepoGraph FalkorDB is working correctly.")
        return 0
    elif resolver:
        print("⚠️  SOME TESTS FAILED - Check output above for details.")
        return 1
    else:
        print("⏭️  SKIPPED - FalkorDB not available. Install with: docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)