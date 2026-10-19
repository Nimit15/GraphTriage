#!/usr/bin/env python3
"""Measure GraphTriage operation durations against a disposable FalkorDB dataset.

The benchmark aborts if the database is unavailable; it never writes simulated
numbers over the recorded results.
"""
import json
import os
import statistics
import time
import uuid
import sys
from typing import Any, Dict

# Allow running this file directly from the repository root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.incident_resolver import IncidentResolver
from src.core.temporal_memory import TemporalMemory
from src.core.multi_agent_pipeline import MultiAgentPipeline


def measure_failure_path_trace(resolver: IncidentResolver, iterations: int = 10) -> Dict[str, float]:
    """Measure elapsed time for trace_failure_path (multiple graph queries)."""
    times = []
    test_name = "test_incident_process_user_data_missing_income"
    for _ in range(iterations):
        start = time.perf_counter()
        resolver.trace_failure_path(test_name)
        times.append((time.perf_counter() - start) * 1000)
    return summarize(times)


def measure_blast_radius(resolver: IncidentResolver, iterations: int = 10) -> Dict[str, float]:
    """Measure elapsed time for blast-radius calculation."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        resolver.calculate_blast_radius("process_user_data")
        times.append((time.perf_counter() - start) * 1000)
    return summarize(times)


def summarize(times) -> Dict[str, float]:
    return {
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def measure_end_to_end(iterations: int = 5) -> Dict[str, float]:
    """Measure full pipeline duration, including workspace setup and ingestion."""
    times = []
    incident = {
        "incident_id": "bench_001",
        "session_id": "bench_session",
        "stack_trace": "KeyError: 'income' at process_user_data:14",
        "failing_test": "test_incident_process_user_data_missing_income",
    }

    for _ in range(iterations):
        workspace_id = f"benchmark_{uuid.uuid4().hex[:8]}"
        pipeline = None
        graph = None
        try:
            start = time.perf_counter()
            pipeline = MultiAgentPipeline(workspace_id=workspace_id)
            graph = pipeline.blast_radius_agent.resolver.graph
            pipeline.blast_radius_agent.resolver.ingest_sandbox_service()
            pipeline.run(incident)
            times.append((time.perf_counter() - start) * 1000)
        finally:
            try:
                if graph is not None:
                    graph.delete()
            finally:
                if pipeline is not None:
                    pipeline.triage_agent.memory.close()
                    pipeline.blast_radius_agent.resolver.close()
                    pipeline.memory_curator_agent.memory.close()

    return summarize(times)


def measure_temporal_memory(iterations: int = 10) -> Dict[str, float]:
    """Measure create, retrieve and supersede operations on dedicated graphs."""
    times = []
    for _ in range(iterations):
        memory = None
        try:
            graph_name = f"graphtriage_benchmark_memory_{uuid.uuid4().hex[:8]}"
            memory = TemporalMemory(graph_name=graph_name)
            start = time.perf_counter()
            fact_id = memory.create_semantic_fact({
                "workspace_id": "benchmark",
                "fact_type": "root_cause",
                "function_name": "benchmark_function",
                "statement": "Benchmark statement",
                "confidence": 0.95,
            })
            memory.get_active_facts("benchmark_function", "benchmark")
            memory.supersede_fact(fact_id, {
                "workspace_id": "benchmark",
                "fact_type": "root_cause",
                "function_name": "benchmark_function",
                "statement": "Updated benchmark statement",
                "confidence": 0.99,
            })
            memory.get_facts_with_history("benchmark_function", "benchmark")
            times.append((time.perf_counter() - start) * 1000)
        finally:
            if memory is not None:
                try:
                    memory.graph.delete()
                finally:
                    memory.close()
    return summarize(times)


def test_selection_estimate() -> Dict[str, Any]:
    """Return the illustrative count estimate used in the original report."""
    full = 50
    selected = 5
    return {
        "full_test_count": full,
        "targeted_test_count": selected,
        "reduction_percentage": round((full - selected) / full * 100, 1),
        "tests_saved": full - selected,
        "note": "Illustrative count estimate, not measured wall-clock savings.",
    }


def run_benchmarks():
    graph_name = f"graphtriage_benchmark_base_{uuid.uuid4().hex[:8]}"
    resolver = None
    try:
        resolver = IncidentResolver(graph_name=graph_name)
        resolver.ingest_sandbox_service()
        print("FalkorDB connection and sandbox setup: OK")
        results = {
            "failure_path_trace": measure_failure_path_trace(resolver),
            "blast_radius": measure_blast_radius(resolver),
            "end_to_end": measure_end_to_end(),
            "temporal_memory": measure_temporal_memory(),
            "test_reduction": test_selection_estimate(),
            "notes": {
                "failure_path_trace": "Elapsed time for trace_failure_path, which performs multiple graph queries; not one native shortestPath query.",
                "test_reduction": "Estimated count comparison, not measured wall-clock savings.",
                "measurement_environment": "Not captured in the original benchmark record.",
            },
        }
    except Exception as exc:
        raise SystemExit(
            f"Benchmark aborted; FalkorDB setup or a measured operation failed. "
            f"No benchmark file was written. Error: {exc}"
        ) from exc
    finally:
        if resolver is not None:
            try:
                resolver.graph.delete()
            finally:
                resolver.close()

    print("\nRecorded operation means:")
    print(f"  Failure-path trace method: {results['failure_path_trace']['mean_ms']:.2f} ms")
    print(f"  Blast-radius calculation: {results['blast_radius']['mean_ms']:.2f} ms")
    print(f"  End-to-end pipeline: {results['end_to_end']['mean_ms']:.2f} ms")
    print(f"  Temporal-memory sequence: {results['temporal_memory']['mean_ms']:.2f} ms")
    print("  Test-selection comparison: estimate only")

    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "benchmark_results.json"))
    with open(output_file, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
        handle.write("\n")
    print(f"Results saved to {output_file}")
    return results


if __name__ == "__main__":
    run_benchmarks()
