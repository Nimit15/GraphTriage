"""
Temporal Memory System for RepoGraph FalkorDB.

Implements three-tier graph memory schema:
1. EpisodicIncident - session ID, stack trace, failing test, timestamp
2. SemanticFact - root-cause and architectural truths with temporal lifecycle
3. ProceduralPlaybook - reusable multi-step remediation patterns

Includes temporal edge management with valid_from/valid_to timestamps
and SUPERSEDED relationship for fact evolution.
"""
import os
import json
import hashlib
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from falkordb import FalkorDB
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
class TemporalMemory:
    """
    Three-tier temporal memory system for incident resolution.

    Memory tiers:
    - EpisodicIncident: Raw incident data (stack traces, timestamps)
    - SemanticFact: Derived architectural truths with temporal validity
    - ProceduralPlaybook: Reusable remediation patterns
    """

    def __init__(self, graph_name: str = "graphtriage_memory"):
        """
        Initialize temporal memory system.

        Args:
            host: FalkorDB host
            port: FalkorDB port
            graph_name: Graph name for memory isolation
            username: FalkorDB username (defaults to FALKORDB_USERNAME env var)
            password: FalkorDB password (defaults to FALKORDB_PASSWORD env var)
            ssl: Use SSL connection (defaults to FALKORDB_SSL env var)
        """
        # Use connection factory for central connection management
        from .db_connection import get_falkordb_client
        self.db = get_falkordb_client()
        self.graph = self.db.select_graph(graph_name)

        # Initialize schema only if we can connect successfully
        self._ensure_memory_schema()

    def _ensure_memory_schema(self):
        """Ensure memory schema exists with all three tiers and indices."""
        try:
            # Check if EpisodicIncident nodes exist
            result = self.graph.query("MATCH (e:EpisodicIncident) RETURN count(e) as count")
            node_count = result.result_set[0][0] if result.result_set else 0

            if node_count == 0:
                logger.info("Initializing temporal memory schema")
                self._create_memory_schema()
        except Exception as e:
            logger.warning(f"Could not check memory state: {e}")
            # Only create schema if we can connect to the database
            try:
                self._create_memory_schema()
            except Exception as e2:
                # If we can't create schema, log warning but continue
                logger.warning(f"Could not initialize temporal memory schema: {e2}")

    def _create_memory_schema(self):
        """Create the three-tier memory schema with indices and constraints."""
        schema_queries = [
            # EpisodicIncident indices
            "CREATE INDEX FOR (e:EpisodicIncident) ON (e.id)",
            "CREATE INDEX FOR (e:EpisodicIncident) ON (e.timestamp)",
            "CREATE INDEX FOR (e:EpisodicIncident) ON (e.failing_test)",
            "CREATE INDEX FOR (e:EpisodicIncident) ON (e.workspace_id)",

            # SemanticFact indices
            "CREATE INDEX FOR (f:SemanticFact) ON (f.id)",
            "CREATE INDEX FOR (f:SemanticFact) ON (f.valid_from)",
            "CREATE INDEX FOR (f:SemanticFact) ON (f.valid_to)",
            "CREATE INDEX FOR (f:SemanticFact) ON (f.status)",
            "CREATE INDEX FOR (f:SemanticFact) ON (f.function_name)",
            "CREATE INDEX FOR (f:SemanticFact) ON (f.workspace_id)",

            # ProceduralPlaybook indices
            "CREATE INDEX FOR (p:ProceduralPlaybook) ON (p.id)",
            "CREATE INDEX FOR (p:ProceduralPlaybook) ON (p.fault_signature)",
            "CREATE INDEX FOR (p:ProceduralPlaybook) ON (p.workspace_id)",

            # Constraints
            "CREATE CONSTRAINT FOR (e:EpisodicIncident) REQUIRE e.id IS UNIQUE IF NOT EXISTS",
            "CREATE CONSTRAINT FOR (f:SemanticFact) REQUIRE f.id IS UNIQUE IF NOT EXISTS",
            "CREATE CONSTRAINT FOR (p:ProceduralPlaybook) REQUIRE p.id IS UNIQUE IF NOT EXISTS",
        ]

        for query in schema_queries:
            try:
                self.graph.query(query)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Schema query failed: {query} - {e}")

    # ============================================================
    # EPISODIC INCIDENT MANAGEMENT
    # ============================================================

    def record_incident(self, incident_data: Dict[str, Any]) -> str:
        """
        Record a new episodic incident.

        Args:
            incident_data: Dict with:
                - workspace_id: Workspace identifier
                - session_id: Session identifier
                - stack_trace: Full stack trace string
                - failing_test: Name of failing test
                - exception_type: Type of exception
                - exception_message: Exception message
                - commit_sha: Git commit SHA at time of incident
                - metadata: Additional metadata dict

        Returns:
            Incident ID
        """
        incident_id = incident_data.get("id") or self._generate_id("incident")
        timestamp = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (e:EpisodicIncident {
            id: $id,
            workspace_id: $workspace_id,
            session_id: $session_id,
            stack_trace: $stack_trace,
            failing_test: $failing_test,
            exception_type: $exception_type,
            exception_message: $exception_message,
            commit_sha: $commit_sha,
            timestamp: $timestamp,
            metadata: $metadata
        })
        """

        self.graph.query(query, {
            "id": incident_id,
            "workspace_id": incident_data.get("workspace_id", "default"),
            "session_id": incident_data.get("session_id", "default"),
            "stack_trace": incident_data.get("stack_trace", ""),
            "failing_test": incident_data.get("failing_test", ""),
            "exception_type": incident_data.get("exception_type", ""),
            "exception_message": incident_data.get("exception_message", ""),
            "commit_sha": incident_data.get("commit_sha", ""),
            "timestamp": timestamp,
            "metadata": json.dumps(incident_data.get("metadata", {}))
        })

        logger.info(f"Recorded incident: {incident_id}")
        return incident_id

    def get_incidents_by_test(self, failing_test: str, workspace_id: str = "default", graph_name: str = None) -> List[Dict]:
        """Get all incidents for a specific failing test."""
        query = """
        MATCH (e:EpisodicIncident {failing_test: $failing_test, workspace_id: $workspace_id})
        RETURN e
        ORDER BY e.timestamp DESC
        """

        # Use workspace-specific graph if graph_name provided
        if graph_name:
            self.graph = self.db.select_graph(graph_name)

        result = self.graph.query(query, {
            "failing_test": failing_test,
            "workspace_id": workspace_id
        })

        return [self._node_to_dict(record[0]) for record in result.result_set]

    def get_incidents_by_workspace(self, workspace_id: str, graph_name: str = None) -> List[Dict]:
        """Get all incidents for a workspace."""
        query = """
        MATCH (e:EpisodicIncident {workspace_id: $workspace_id})
        RETURN e
        ORDER BY e.timestamp DESC
        """

        # Use workspace-specific graph if graph_name provided
        if graph_name:
            self.graph = self.db.select_graph(graph_name)

        result = self.graph.query(query, {"workspace_id": workspace_id})
        return [self._node_to_dict(record[0]) for record in result.result_set]

    # ============================================================
    # SEMANTIC FACT MANAGEMENT (with temporal lifecycle)
    # ============================================================

    def create_semantic_fact(self, fact_data: Dict[str, Any]) -> str:
        """
        Create a new semantic fact with temporal properties.

        Args:
            fact_data: Dict with:
                - workspace_id: Workspace identifier
                - fact_type: Type of fact (e.g., "root_cause", "architectural_truth")
                - function_name: Associated function name
                - module: Module path
                - statement: The factual statement
                - evidence: Supporting evidence (Cypher query result, test output, etc.)
                - confidence: Confidence score (0.0-1.0)
                - commit_sha: Commit SHA when fact was discovered
                - tags: List of tags for categorization

        Returns:
            Fact ID
        """
        fact_id = fact_data.get("id") or self._generate_id("fact")
        timestamp = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (f:SemanticFact {
            id: $id,
            workspace_id: $workspace_id,
            fact_type: $fact_type,
            function_name: $function_name,
            module: $module,
            statement: $statement,
            evidence: $evidence,
            confidence: $confidence,
            commit_sha: $commit_sha,
            tags: $tags,
            valid_from: $valid_from,
            valid_to: $valid_to,
            status: $status
        })
        """

        self.graph.query(query, {
            "id": fact_id,
            "workspace_id": fact_data.get("workspace_id", "default"),
            "fact_type": fact_data.get("fact_type", "root_cause"),
            "function_name": fact_data.get("function_name", ""),
            "module": fact_data.get("module", ""),
            "statement": fact_data.get("statement", ""),
            "evidence": json.dumps(fact_data.get("evidence", {})),
            "confidence": fact_data.get("confidence", 1.0),
            "commit_sha": fact_data.get("commit_sha", ""),
            "tags": json.dumps(fact_data.get("tags", [])),
            "valid_from": timestamp,
            "valid_to": None,
            "status": "ACTIVE"
        })

        logger.info(f"Created semantic fact: {fact_id}")
        return fact_id

    def supersede_fact(self, old_fact_id: str, new_fact_data: Dict[str, Any]) -> str:
        """
        Supersede an old fact with a new one.
        Closes the old fact (sets valid_to, status=SUPERSEDED)
        and creates SUPERSEDED relationship to new fact.

        Args:
            old_fact_id: ID of the fact to supersede
            new_fact_data: Data for the new fact (same schema as create_semantic_fact)

        Returns:
            New fact ID
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        new_fact_id = self._generate_id("fact")

        # First, create the new fact
        new_fact_data["id"] = new_fact_id
        self.create_semantic_fact(new_fact_data)

        # Then, close the old fact and create SUPERSEDED relationship
        close_query = """
        MATCH (old:SemanticFact {id: $old_id})
        SET old.valid_to = $now,
            old.status = 'SUPERSEDED'
        """

        self.graph.query(close_query, {
            "old_id": old_fact_id,
            "now": timestamp
        })

        # Create SUPERSEDED relationship
        supersede_query = """
        MATCH (new:SemanticFact {id: $new_id})
        MATCH (old:SemanticFact {id: $old_id})
        CREATE (new)-[:SUPERSEDED {superseded_at: $now}]->(old)
        """

        self.graph.query(supersede_query, {
            "new_id": new_fact_id,
            "old_id": old_fact_id,
            "now": timestamp
        })

        logger.info(f"Superseded fact {old_fact_id} with {new_fact_id}")
        return new_fact_id

    def get_active_facts(self, function_name: str = None, workspace_id: str = "default",
                         max_hops: int = 2) -> List[Dict]:
        """
        Fast-Loop Read: Get only active facts within max_hops of function.

        Args:
            function_name: Filter by function name (optional)
            workspace_id: Workspace to search in
            max_hops: Maximum graph distance

        Returns:
            List of active semantic facts
        """
        if function_name:
            query = """
            MATCH (f:SemanticFact {workspace_id: $workspace_id, status: 'ACTIVE'})
            WHERE f.valid_to IS NULL AND f.function_name = $function_name
            RETURN f
            ORDER BY f.confidence DESC
            """

            result = self.graph.query(query, {
                "function_name": function_name,
                "workspace_id": workspace_id
            })
        else:
            query = """
            MATCH (f:SemanticFact {workspace_id: $workspace_id, status: 'ACTIVE'})
            WHERE f.valid_to IS NULL
            RETURN f
            ORDER BY f.confidence DESC
            """

            result = self.graph.query(query, {"workspace_id": workspace_id})

        return [self._node_to_dict(record[0]) for record in result.result_set]

    def get_facts_with_history(self, function_name: str, workspace_id: str = "default") -> List[Dict]:
        """
        Get all facts for a function including superseded ones (for audit trail).

        Returns:
            List of all facts with their SUPERSEDED relationships
        """
        query = """
        MATCH (f:SemanticFact {workspace_id: $workspace_id, function_name: $function_name})
        OPTIONAL MATCH (f)-[:SUPERSEDED]->(old:SemanticFact)
        RETURN f, collect(old) as superseded_facts
        ORDER BY f.valid_from DESC
        """

        result = self.graph.query(query, {
            "function_name": function_name,
            "workspace_id": workspace_id
        })

        facts = []
        for record in result.result_set:
            fact = self._node_to_dict(record[0])

            # Ensure the fact has temporal properties
            if "valid_from" not in fact:
                fact["valid_from"] = datetime.now(timezone.utc).isoformat()
            if "valid_to" not in fact:
                fact["valid_to"] = None
            if "status" not in fact:
                fact["status"] = "ACTIVE"

            superseded = []
            if record[1]:
                for s in record[1]:
                    if s:
                        subsumed_fact = self._node_to_dict(s)
                        # Ensure subsumed facts also have temporal properties
                        if "valid_from" not in subsumed_fact:
                            subsumed_fact["valid_from"] = datetime.now(timezone.utc).isoformat()
                        if "valid_to" not in subsumed_fact:
                            subsumed_fact["valid_to"] = None
                        if "status" not in subsumed_fact:
                            subsumed_fact["status"] = "SUPERSEDED"
                        superseded.append(subsumed_fact)

            fact["superseded_by"] = superseded
            facts.append(fact)

        return facts

    # ============================================================
    # PROCEDURAL PLAYBOOK MANAGEMENT
    # ============================================================

    def create_playbook(self, playbook_data: Dict[str, Any]) -> str:
        """
        Create a procedural playbook for recurring fault patterns.

        Args:
            playbook_data: Dict with:
                - workspace_id: Workspace identifier
                - fault_signature: Pattern identifying the fault (e.g., "KeyError: missing_field")
                - name: Human-readable name
                - description: Description of the remediation pattern
                - steps: List of remediation steps
                - applicability: Conditions when this playbook applies

        Returns:
            Playbook ID
        """
        playbook_id = playbook_data.get("id") or self._generate_id("playbook")

        query = """
        CREATE (p:ProceduralPlaybook {
            id: $id,
            workspace_id: $workspace_id,
            fault_signature: $fault_signature,
            name: $name,
            description: $description,
            steps: $steps,
            applicability: $applicability,
            created_at: $created_at,
            usage_count: 0
        })
        """

        self.graph.query(query, {
            "id": playbook_id,
            "workspace_id": playbook_data.get("workspace_id", "default"),
            "fault_signature": playbook_data.get("fault_signature", ""),
            "name": playbook_data.get("name", ""),
            "description": playbook_data.get("description", ""),
            "steps": json.dumps(playbook_data.get("steps", [])),
            "applicability": json.dumps(playbook_data.get("applicability", {})),
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        logger.info(f"Created playbook: {playbook_id}")
        return playbook_id

    def find_applicable_playbooks(self, fault_signature: str, workspace_id: str = "default") -> List[Dict]:
        """Find playbooks applicable to a given fault signature."""
        query = """
        MATCH (p:ProceduralPlaybook {workspace_id: $workspace_id})
        WHERE p.fault_signature = $fault_signature
        RETURN p
        ORDER BY p.usage_count DESC
        """

        result = self.graph.query(query, {
            "fault_signature": fault_signature,
            "workspace_id": workspace_id
        })

        playbooks = []
        for record in result.result_set:
            pb = self._node_to_dict(record[0])
            pb["steps"] = json.loads(pb.get("steps", "[]"))
            pb["applicability"] = json.loads(pb.get("applicability", "{}"))
            playbooks.append(pb)

        return playbooks

    def record_playbook_usage(self, playbook_id: str):
        """Increment usage count for a playbook."""
        query = """
        MATCH (p:ProceduralPlaybook {id: $id})
        SET p.usage_count = p.usage_count + 1
        """

        self.graph.query(query, {"id": playbook_id})

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        timestamp = str(time.time()).encode()
        random_bytes = os.urandom(8)
        return f"{prefix}_{hashlib.sha256(timestamp + random_bytes).hexdigest()[:16]}"

    def _node_to_dict(self, node) -> Dict:
        """Convert FalkorDB node to dict."""
        if hasattr(node, 'properties'):
            node_dict = dict(node.properties)
            # Ensure temporal properties exist
            if 'valid_from' not in node_dict:
                node_dict['valid_from'] = datetime.now(timezone.utc).isoformat()
            if 'valid_to' not in node_dict:
                node_dict['valid_to'] = None
            if 'status' not in node_dict:
                node_dict['status'] = 'ACTIVE'
            return node_dict
        return dict(node)

    def close(self):
        """Close the FalkorDB connection."""
        if hasattr(self, 'db'):
            self.db.close()


# ============================================================
# WORKSPACE ISOLATION
# ============================================================

class WorkspaceManager:
    """
    Manages multi-tenant workspace isolation using FalkorDB's
    graph selection mechanism (db.select_graph).
    """

    def __init__(self, host: str = None, port: int = 6379, base_name: str = "repograph"):
        self.base_name = base_name
        # Use the centralized connection factory for cloud credentials support
        from .db_connection import get_falkordb_client
        self.db = get_falkordb_client()

    def get_workspace_graph(self, workspace_id: str):
        """
        Get a graph handle for a specific workspace.
        Creates the graph if it doesn't exist.
        """
        graph_name = f"{self.base_name}_ws_{workspace_id}"
        return self.db.select_graph(graph_name)

    def list_workspaces(self) -> List[str]:
        """List all available workspaces."""
        try:
            # Query system to find graphs with our prefix
            # This is a workaround since FalkorDB doesn't have a direct list graphs API
            return []
        except Exception:
            return []

    def verify_isolation(self, workspace_a: str, workspace_b: str) -> bool:
        """
        Verify that data in workspace_a is unreachable from workspace_b.
        """
        try:
            graph_a = self.get_workspace_graph(workspace_a)
            graph_b = self.get_workspace_graph(workspace_b)

            # Add a test fact to workspace_a
            test_id = f"test_{int(time.time())}"
            graph_a.query(
                "CREATE (t:TestNode {id: $id, workspace: $ws})",
                {"id": test_id, "ws": workspace_a}
            )

            # Try to query it from workspace_b
            result = graph_b.query(
                "MATCH (n {id: $id}) RETURN n",
                {"id": test_id}
            )

            # Should not find it
            found = len(result.result_set) > 0 if result.result_set else False

            # Clean up
            graph_a.query("MATCH (n {id: $id}) DETACH DELETE n", {"id": test_id})

            return not found  # Isolation works if NOT found in other workspace

        except Exception as e:
            logger.error(f"Isolation test failed: {e}")
            return False

    def close(self):
        """Close the connection."""
        if hasattr(self, 'db'):
            self.db.close()


if __name__ == "__main__":
    # Demo usage
    memory = TemporalMemory()

    # Record an incident
    incident_id = memory.record_incident({
        "workspace_id": "alpha",
        "session_id": "session_001",
        "stack_trace": "KeyError: 'income' at process_user_data:23",
        "failing_test": "test_incident_process_user_data_missing_income",
        "exception_type": "KeyError",
        "exception_message": "'income'",
        "commit_sha": "abc123",
        "metadata": {"source": "pytest"}
    })

    # Create a semantic fact
    fact_id = memory.create_semantic_fact({
        "workspace_id": "alpha",
        "fact_type": "root_cause",
        "function_name": "process_user_data",
        "module": "sandbox_service/app.py",
        "statement": "process_user_data assumes all users have 'income' field",
        "evidence": {"test": "test_incident_process_user_data_missing_income", "exception": "KeyError"},
        "confidence": 0.95,
        "commit_sha": "abc123",
        "tags": ["bug", "validation", "missing_field"]
    })

    # Get active facts
    active = memory.get_active_facts("process_user_data", "alpha")
    print(f"Active facts for process_user_data: {len(active)}")

    # Supersede the fact
    new_fact_id = memory.supersede_fact(fact_id, {
        "workspace_id": "alpha",
        "fact_type": "root_cause",
        "function_name": "process_user_data",
        "module": "sandbox_service/app.py",
        "statement": "process_user_data should use user.get('income', 0) for missing fields",
        "evidence": {"test": "test_incident_process_user_data_missing_income", "fix": "use .get()"},
        "confidence": 0.99,
        "commit_sha": "def456",
        "tags": ["bug", "validation", "missing_field", "fixed"]
    })

    # Get history
    history = memory.get_facts_with_history("process_user_data", "alpha")
    print(f"Fact history length: {len(history)}")
    for f in history:
        print(f"  - {f['statement']} (status: {f['status']})")
        if f.get('superseded_by'):
            for s in f['superseded_by']:
                print(f"    SUPERSEDED by: {s['statement']}")

    memory.close()