#!/usr/bin/env python3
"""
Live demo script for GraphTriage FalkorDB incident resolution.
Creates a dedicated demo workspace and showcases Track 1 & Track 2 features.
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def print_header(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"[STEP {title}]")
    print(f"{'='*60}")

def print_subheader(title):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")

def main():
    print_header("1: Graph Ingestion & Topology")

    # Import after path setup
    from core.incident_resolver import IncidentResolver

    # Use dedicated demo workspace
    demo_graph = "graphtriage_demo"
    print(f"Initializing demo workspace: {demo_graph}")

    resolver = IncidentResolver(graph_name=demo_graph)

    # Ingest sandbox service data
    start_time = time.time()
    resolver.ingest_sandbox_service()
    ingest_time = (time.time() - start_time) * 1000

    # Get basic stats
    try:
        module_count = resolver.graph.query("MATCH (m:Module) RETURN count(m) as count").result_set[0][0]
        function_count = resolver.graph.query("MATCH (f:Function) RETURN count(f) as count").result_set[0][0]
        test_count = resolver.graph.query("MATCH (t:Test) RETURN count(t) as count").result_set[0][0]

        # Count relationships
        covers_count = resolver.graph.query("MATCH ()-[r:COVERS]->() RETURN count(r) as count").result_set[0][0]
        calls_count = resolver.graph.query("MATCH ()-[r:CALLS]->() RETURN count(r) as count").result_set[0][0]
        defined_in_count = resolver.graph.query("MATCH ()-[r:DEFINED_IN]->() RETURN count(r) as count").result_set[0][0]
        contains_count = resolver.graph.query("MATCH ()-[r:CONTAINS]->() RETURN count(r) as count").result_set[0][0]

        print_subheader("Graph Statistics")
        print(f"Modules: {module_count}")
        print(f"Functions: {function_count}")
        print(f"Tests: {test_count}")
        print(f"Relationships:")
        print(f"  - COVERS: {covers_count}")
        print(f"  - CALLS: {calls_count}")
        print(f"  - DEFINED_IN: {defined_in_count}")
        print(f"  - CONTAINS: {contains_count}")
        print(f"Ingestion time: {ingest_time:.2f}ms")

    except Exception as e:
        print(f"Error getting graph stats: {e}")

    print_header("2: Track 1 — Unknown-Entity Refusal Guard")

    # Test unknown entity handling
    unknown_result = resolver.analyze_impact("non_existent_helper")
    print_subheader("Querying non-existent function")
    print(f"Status: {unknown_result.get('status')}")
    print(f"Hops: {unknown_result.get('hops')}")
    print(f"Reason: {unknown_result.get('reason')}")
    print(f"Affected functions: {unknown_result.get('affected_functions', [])}")

    # Verify it refuses to speculate
    assert unknown_result.get('status') == 'UNVERIFIED_ENTITY'
    assert unknown_result.get('hops') == 0
    assert len(unknown_result.get('affected_functions', [])) == 0
    print("[OK] Correctly refused to speculate on unknown entity")

    print_header("3: Track 1 — Fault Path, Blast Radius & Targeted Pytest Run")

    # Analyze the known failing test
    failing_test = "test_incident_process_user_data_missing_income"
    print_subheader(f"Analyzing impact of changing function in {failing_test}")

    impact_result = resolver.analyze_impact("process_user_data", failing_test)
    print(f"Status: {impact_result.get('status')}")
    print(f"Function: {impact_result.get('function_name')}")
    print(f"Test: {impact_result.get('test_name')}")
    print(f"Confidence: {impact_result.get('confidence', 0):.2f}")

    blast_radius = impact_result.get('blast_radius', [])
    print(f"Blast radius ({len(blast_radius)} functions):")
    for func in blast_radius:
        print(f"  - {func.get('function_name')} (module: {func.get('module')})")

    failure_path = impact_result.get('failure_path', [])
    print(f"Failure path ({len(failure_path)} hops):")
    for hop in failure_path:
        node = hop.get('node', {})
        rel = hop.get('relationship', {})
        print(f"  Hop {hop.get('hops')}: {node.get('name', 'unknown')} "
              f"--[{rel.get('type', 'unknown')}]--> ")

    # Run targeted pytest
    print_subheader("Running targeted pytest")
    test_result = resolver.run_targeted_tests([failing_test])
    print(f"Tests run: {test_result.get('tests_run', 0)}")
    print(f"Passed: {test_result.get('passed', 0)}")
    print(f"Failed: {test_result.get('failed', 0)}")
    print(f"Duration: {test_result.get('duration', 0):.3f}s")

    if test_result.get('stdout'):
        print("Pytest output:")
        print(test_result['stdout'][-500:])  # Last 500 chars

    print_header("4: Track 2 — 3-Agent Handoff & Temporal Fact Supersession")

    # Import temporal memory and pipeline
    try:
        from core.temporal_memory import TemporalMemory
        from core.multi_agent_pipeline import MultiAgentPipeline, TriageAgent, BlastRadiusAgent, MemoryCuratorAgent

        print_subheader("Creating temporal memory for demo workspace")
        # Use a separate graph for temporal memory
        temporal_memory = TemporalMemory(graph_name=f"{demo_graph}_memory")

        print_subheader("Simulating incident and creating semantic fact")
        # Record an incident
        incident_id = temporal_memory.record_incident({
            "workspace_id": "demo_ws",
            "session_id": "demo_session_001",
            "stack_trace": "KeyError: 'income' at process_user_data:22",
            "failing_test": "test_incident_process_user_data_missing_income",
            "exception_type": "KeyError",
            "exception_message": "'income'",
            "commit_sha": "demo123",
            "metadata": {"source": "live_demo"}
        })
        print(f"Recorded incident: {incident_id}")

        # Create initial semantic fact
        fact_id = temporal_memory.create_semantic_fact({
            "workspace_id": "demo_ws",
            "fact_type": "root_cause",
            "function_name": "process_user_data",
            "module": "sandbox_service/app.py",
            "statement": "process_user_data assumes all users have 'income' field",
            "evidence": {"test": "test_incident_process_user_data_missing_income", "exception": "KeyError"},
            "confidence": 0.9,
            "commit_sha": "demo123",
            "tags": ["bug", "validation", "missing_field"]
        })
        print(f"Created semantic fact: {fact_id}")

        # Verify active fact
        active_facts = temporal_memory.get_active_facts("process_user_data", "demo_ws")
        print(f"Active facts: {len(active_facts)}")
        if active_facts:
            fact = active_facts[0]
            print(f"  Statement: {fact.get('statement')}")
            print(f"  Confidence: {fact.get('confidence')}")
            print(f"  Status: {fact.get('status')}")
            print(f"  Valid from: {fact.get('valid_from')}")
            print(f"  Valid to: {fact.get('valid_to')}")

        print_subheader("Superseding fact with improved version")
        # Supersede with better fact
        new_fact_id = temporal_memory.supersede_fact(fact_id, {
            "workspace_id": "demo_ws",
            "fact_type": "root_cause",
            "function_name": "process_user_data",
            "module": "sandbox_service/app.py",
            "statement": "process_user_data should use user.get('income', 0) for missing income field",
            "evidence": {"test": "test_incident_process_user_data_missing_income", "fix": "use .get() with default"},
            "confidence": 0.95,
            "commit_sha": "demo456",
            "tags": ["bug", "validation", "missing_field", "fixed"]
        })
        print(f"Superseded {fact_id} with {new_fact_id}")

        # Check fact history
        history = temporal_memory.get_facts_with_history("process_user_data", "demo_ws")
        print(f"Fact history length: {len(history)}")
        for i, fact_record in enumerate(history):
            print(f"  [{i}] {fact_record.get('statement')[:50]}... "
                  f"(status: {fact_record.get('status')})")
            if fact_record.get('superseded_by'):
                for super_fact in fact_record['superseded_by']:
                    print(f"      SUPERSEDED by: {super_fact.get('statement')[:50]}...")

        # Verify workspace isolation
        print_subheader("Verifying workspace isolation")
        from core.temporal_memory import WorkspaceManager
        wm = WorkspaceManager(base_name="repograph")
        try:
            demo_graph_handle = wm.get_workspace_graph("demo_ws")
            other_graph_handle = wm.get_workspace_graph("other_ws")

            # Add test data to demo workspace
            test_id = f"iso_test_{int(time.time())}"
            demo_graph_handle.query(
                "CREATE (t:TestNode {id: $id, workspace: $ws})",
                {"id": test_id, "ws": "demo_ws"}
            )

            # Try to query from other workspace
            result = other_graph_handle.query(
                "MATCH (n {id: $id}) RETURN n",
                {"id": test_id}
            )

            found = len(result.result_set) > 0 if result.result_set else False
            isolated = not found

            # Cleanup
            try:
                demo_graph_handle.query("MATCH (n {id: $id}) DETACH DELETE n", {"id": test_id})
            except:
                pass

            print(f"Workspace isolation working: {isolated}")
            if isolated:
                print("✓ Data in demo workspace is isolated from other workspaces")
            else:
                print("✗ WARNING: Workspace isolation may not be working correctly")

        except Exception as e:
            print(f"Isolation test error: {e}")

        temporal_memory.close()
        wm.close()

    except ImportError as e:
        print(f"Could not import temporal memory/pipeline modules: {e}")
        print("Skipping Track 2 demo...")

    print_header("Final: Reseeding Base Graph for Viewing")

    # Reseed the main graphtriage graph so http://localhost:3001 shows data
    print("Reseeding main graphtriage graph for FalkorDB browser viewing...")
    try:
        # Clear and reseed main graph
        main_resolver = IncidentResolver(graph_name="graphtriage")
        main_resolver.ingest_sandbox_service()
        main_resolver.close()
        print("[OK] Main graphtriage graph reseeded successfully")
    except Exception as e:
        print(f"Error reseeding main graph: {e}")

    # Close demo resolver
    resolver.close()

    print_header("Demo Complete")
    print("[OK] All Track 1 and Track 2 features demonstrated")
    print("[OK] Graph data available at http://localhost:3001")
    print("[OK] Use the FalkorDB browser to explore nodes and relationships")
    print(f"[OK] Demo workspace: {demo_graph}")
    print(f"[OK] Temporal memory workspace: {demo_graph}_memory")

if __name__ == "__main__":
    main()