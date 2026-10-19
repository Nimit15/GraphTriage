"""Tests for temporal memory and multi-agent pipeline."""
import pytest
import time
import uuid
from src.core.temporal_memory import TemporalMemory, WorkspaceManager
from src.core.multi_agent_pipeline import (
    MultiAgentPipeline,
    TriageAgent,
    BlastRadiusAgent,
    MemoryCuratorAgent,
    AgentHandoff
)


@pytest.fixture
def workspace_manager():
    """Create a workspace manager for isolation tests."""
    manager = WorkspaceManager()
    try:
        yield manager
    finally:
        manager.close()


@pytest.fixture
def temporal_memory():
    """Create a disposable graph for each temporal-memory test."""
    graph_name = f"graphtriage_test_memory_{uuid.uuid4().hex[:10]}"
    memory = TemporalMemory(graph_name=graph_name)
    try:
        yield memory
    finally:
        try:
            memory.graph.delete()
        finally:
            memory.close()


class TestTemporalMemory:
    """Test three-tier memory schema."""

    def test_record_incident(self, temporal_memory):
        """Test recording episodic incident."""
        incident_id = temporal_memory.record_incident({
            "workspace_id": "test_ws",
            "session_id": "test_session",
            "stack_trace": "KeyError: 'income' at process_user_data:14",
            "failing_test": "test_missing_income",
            "exception_type": "KeyError",
            "exception_message": "'income'",
            "commit_sha": "abc123",
            "metadata": {"source": "test"}
        })

        assert incident_id.startswith("incident_")

        # Verify we can retrieve it
        incidents = temporal_memory.get_incidents_by_test("test_missing_income", "test_ws")
        assert len(incidents) == 1
        assert incidents[0]["exception_type"] == "KeyError"

    def test_create_semantic_fact(self, temporal_memory):
        """Test creating semantic fact with temporal properties."""
        fact_id = temporal_memory.create_semantic_fact({
            "workspace_id": "test_ws",
            "fact_type": "root_cause",
            "function_name": "process_user_data",
            "module": "sandbox_service/app.py",
            "statement": "process_user_data assumes all users have 'income' field",
            "evidence": {"test": "test_missing_income"},
            "confidence": 0.95,
            "commit_sha": "abc123",
            "tags": ["bug", "validation"]
        })

        assert fact_id.startswith("fact_")

        # Verify active facts
        active = temporal_memory.get_active_facts("process_user_data", "test_ws")
        assert len(active) == 1
        assert active[0]["status"] == "ACTIVE"
        assert active[0]["valid_to"] is None

    def test_supersede_fact(self, temporal_memory):
        """Test superseding a fact with temporal lifecycle."""
        # Create initial fact
        old_fact_id = temporal_memory.create_semantic_fact({
            "workspace_id": "test_ws",
            "fact_type": "root_cause",
            "function_name": "test_function",
            "statement": "Initial statement",
            "confidence": 0.9,
            "commit_sha": "abc123"
        })

        # Supersede with new fact
        new_fact_id = temporal_memory.supersede_fact(old_fact_id, {
            "workspace_id": "test_ws",
            "fact_type": "root_cause",
            "function_name": "test_function",
            "statement": "Updated statement with fix",
            "confidence": 0.99,
            "commit_sha": "def456"
        })

        # Verify old fact is superseded
        history = temporal_memory.get_facts_with_history("test_function", "test_ws")

        # Should have both facts
        assert len(history) >= 2

        # Find the old fact and verify it's superseded
        old_fact = next((f for f in history if f["id"] == old_fact_id), None)
        assert old_fact is not None
        assert old_fact["status"] == "SUPERSEDED"
        assert old_fact["valid_to"] is not None

    def test_create_playbook(self, temporal_memory):
        """Test creating procedural playbook."""
        playbook_id = temporal_memory.create_playbook({
            "workspace_id": "test_ws",
            "fault_signature": "KeyError: missing_field",
            "name": "Fix KeyError for missing_field",
            "description": "Add input validation with .get() method",
            "steps": [
                "1. Identify missing key",
                "2. Use .get() with default",
                "3. Add schema validation"
            ],
            "applicability": {"exception_type": "KeyError"}
        })

        assert playbook_id.startswith("playbook_")

        # Verify we can find it
        playbooks = temporal_memory.find_applicable_playbooks(
            "KeyError: missing_field",
            "test_ws"
        )
        assert len(playbooks) == 1
        assert playbooks[0]["name"] == "Fix KeyError for missing_field"


class TestWorkspaceIsolation:
    """Test workspace isolation via db.select_graph()."""

    def test_workspace_isolation(self, workspace_manager):
        """Test that workspace_alpha facts are unreachable from workspace_beta."""
        ws_alpha = f"workspace_alpha_{uuid.uuid4().hex[:8]}"
        ws_beta = f"workspace_beta_{uuid.uuid4().hex[:8]}"
        try:
            is_isolated = workspace_manager.verify_isolation(ws_alpha, ws_beta)
            assert is_isolated, "Workspace isolation failed - data leaked between workspaces"
        finally:
            workspace_manager.get_workspace_graph(ws_alpha).delete()
            workspace_manager.get_workspace_graph(ws_beta).delete()

    def test_get_workspace_graph(self, workspace_manager):
        """Test getting workspace-specific graph."""
        ws_id = f"test_isolation_ws_{uuid.uuid4().hex[:8]}"
        graph = workspace_manager.get_workspace_graph(ws_id)
        try:
            result = graph.query("MATCH (n) RETURN count(n) as count")
            assert result.result_set is not None
        finally:
            graph.delete()


class TestMultiAgentPipeline:
    """Test three-stage multi-agent handoff pipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create a pipeline with data in a unique graph."""
        workspace_id = f"pipeline_test_{uuid.uuid4().hex[:8]}"
        instance = MultiAgentPipeline(workspace_id=workspace_id)
        try:
            instance.blast_radius_agent.resolver.ingest_sandbox_service()
            yield instance
        finally:
            try:
                instance.blast_radius_agent.resolver.graph.delete()
            finally:
                instance.triage_agent.memory.close()
                instance.blast_radius_agent.resolver.close()
                instance.memory_curator_agent.memory.close()

    def test_triage_agent_extract_signature(self):
        """Test TriageAgent fault signature extraction."""
        workspace_id = f"triage_signature_{uuid.uuid4().hex[:8]}"
        agent = TriageAgent(workspace_id=workspace_id)
        try:
            stack_trace = """
Traceback (most recent call last):
  File "app.py", line 14, in process_user_data
    total_income += user['income']
KeyError: 'income'
"""
            signature = agent._extract_fault_signature(stack_trace)
            assert "KeyError" in signature
            assert "income" in signature
        finally:
            try:
                agent.memory.graph.delete()
            finally:
                agent.memory.close()

    def test_full_pipeline(self, pipeline):
        """Test complete three-agent handoff pipeline."""
        incident = {
            "incident_id": "test_incident_001",
            "session_id": "test_session",
            "stack_trace": """
Traceback (most recent call last):
  File "sandbox_service/app.py", line 14
KeyError: 'income'
""",
            "failing_test": "test_incident_process_user_data_missing_income"
        }

        result = pipeline.run(incident)

        # Verify handoff contains expected data
        assert result.fault_signature is not None
        assert "KeyError" in result.fault_signature
        assert result.semantic_facts_created is not None
        assert len(result.semantic_facts_created) > 0
        assert result.playbook_recommendations is not None
        assert len(result.playbook_recommendations) > 0

    def test_agent_handoff_data_structure(self):
        """Test AgentHandoff data structure."""
        handoff = AgentHandoff(
            workspace_id="test",
            incident_id="test_001",
            session_id="session_abc",
            stack_trace="Test trace",
            failing_test="test_failing"
        )

        # Verify defaults
        assert handoff.affected_functions == []
        assert handoff.blast_radius == []
        assert handoff.playbook_recommendations == []
        assert handoff.semantic_facts_created == []

        # Verify serialization
        data = handoff.to_dict()
        restored = AgentHandoff.from_dict(data)
        assert restored.workspace_id == handoff.workspace_id
        assert restored.incident_id == handoff.incident_id


class TestTemporalEdgeManagement:
    """Test temporal edge closing with valid_to timestamps."""

    def test_fact_temporal_properties(self, temporal_memory):
        """Test that facts have correct temporal properties."""
        fact_id = temporal_memory.create_semantic_fact({
            "workspace_id": "test_ws",
            "fact_type": "architectural_truth",
            "function_name": "temp_test_func",
            "statement": "Test statement",
            "confidence": 1.0
        })

        # Get the fact and verify temporal properties
        facts = temporal_memory.get_active_facts("temp_test_func", "test_ws")
        assert len(facts) == 1

        fact = facts[0]
        assert "valid_from" in fact
        assert fact["valid_from"] is not None
        assert fact["valid_to"] is None  # Active facts have null valid_to
        assert fact["status"] == "ACTIVE"
        assert "commit_sha" in fact

    def test_superseded_chain(self, temporal_memory):
        """Test SUPERSEDED relationship chain."""
        # Create initial fact
        fact_v1_id = temporal_memory.create_semantic_fact({
            "workspace_id": "test_ws",
            "fact_type": "root_cause",
            "function_name": "versioned_func",
            "statement": "Version 1",
            "confidence": 0.9,
            "commit_sha": "v1"
        })

        # Supersede with v2
        fact_v2_id = temporal_memory.supersede_fact(fact_v1_id, {
            "workspace_id": "test_ws",
            "fact_type": "root_cause",
            "function_name": "versioned_func",
            "statement": "Version 2",
            "confidence": 0.95,
            "commit_sha": "v2"
        })

        # Get history
        history = temporal_memory.get_facts_with_history("versioned_func", "test_ws")

        # Verify we can trace the supersession chain
        v1_fact = next((f for f in history if f["id"] == fact_v1_id), None)
        v2_fact = next((f for f in history if f["id"] == fact_v2_id), None)

        assert v1_fact is not None
        assert v2_fact is not None
        assert v1_fact["status"] == "SUPERSEDED"
        assert v2_fact["status"] == "ACTIVE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])