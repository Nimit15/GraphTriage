"""
Multi-Agent Pipeline for Incident Resolution.

Three-stage handoff pipeline:
1. TriageAgent -> Analyzes incident, extracts fault signature
2. BlastRadiusAgent -> Traces failure path, calculates blast radius
3. MemoryCuratorAgent -> Creates/updates semantic facts, finds playbooks

Each agent operates in workspace isolation via db.select_graph().
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from .temporal_memory import TemporalMemory, WorkspaceManager
from .incident_resolver import IncidentResolver

logger = logging.getLogger(__name__)


@dataclass
class AgentHandoff:
    """Data structure passed between agents in the pipeline."""
    workspace_id: str
    incident_id: str
    session_id: str
    stack_trace: str
    failing_test: str
    fault_signature: Optional[str] = None
    root_cause_function: Optional[str] = None
    affected_functions: List[str] = None
    blast_radius: List[Dict] = None
    playbook_recommendations: List[str] = None
    semantic_facts_created: List[str] = None

    def __post_init__(self):
        if self.affected_functions is None:
            self.affected_functions = []
        if self.blast_radius is None:
            self.blast_radius = []
        if self.playbook_recommendations is None:
            self.playbook_recommendations = []
        if self.semantic_facts_created is None:
            self.semantic_facts_created = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentHandoff':
        return cls(**data)


class TriageAgent:
    """
    Stage 1: Analyzes raw incident data and extracts fault signature.

    Responsibilities:
    - Parse stack trace to identify exception type and message
    - Extract fault signature (e.g., "KeyError: missing_field")
    - Identify the failing test name
    - Pass handoff to BlastRadiusAgent
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.memory = TemporalMemory(graph_name=f"repograph_ws_{workspace_id}")

    def analyze_incident(self, handoff: AgentHandoff) -> AgentHandoff:
        """
        Analyze incident and extract fault signature.

        Args:
            handoff: Incoming handoff with incident data

        Returns:
            Updated handoff with fault_signature populated
        """
        logger.info(f"[TriageAgent] Analyzing incident {handoff.incident_id}")

        # Parse stack trace to extract fault signature
        fault_signature = self._extract_fault_signature(handoff.stack_trace)
        handoff.fault_signature = fault_signature

        # Record the incident in episodic memory
        incident_data = {
            "id": handoff.incident_id,
            "workspace_id": self.workspace_id,
            "session_id": handoff.session_id,
            "stack_trace": handoff.stack_trace,
            "failing_test": handoff.failing_test,
            "exception_type": self._extract_exception_type(fault_signature),
            "exception_message": self._extract_exception_message(fault_signature),
            "commit_sha": "HEAD",  # Could be passed in handoff
            "metadata": {"source": "multi_agent_pipeline"}
        }

        self.memory.record_incident(incident_data)
        logger.info(f"[TriageAgent] Recorded incident with fault signature: {fault_signature}")

        return handoff

    def _extract_fault_signature(self, stack_trace: str) -> str:
        """Extract fault signature from stack trace."""
        lines = stack_trace.strip().split('\n')

        # Look for exception line (usually last line or contains ':')
        for line in reversed(lines):
            if ':' in line and ('Error' in line or 'Exception' in line or 'KeyError' in line or 'TypeError' in line):
                # Extract signature like "KeyError: 'income'"
                parts = line.split(':', 1)
                if len(parts) >= 2:
                    exc_type = parts[0].strip()
                    exc_msg = parts[1].strip()
                    return f"{exc_type}: {exc_msg}"

        # Fallback: return first line that looks like an error
        for line in lines:
            if 'Error' in line or 'Exception' in line:
                return line.strip()

        return "UnknownError: unable to parse"

    def _extract_exception_type(self, signature: str) -> str:
        """Extract exception type from signature."""
        if ':' in signature:
            return signature.split(':')[0].strip()
        return signature.split()[0] if signature else "Unknown"

    def _extract_exception_message(self, signature: str) -> str:
        """Extract exception message from signature."""
        if ':' in signature:
            parts = signature.split(':', 1)
            return parts[1].strip() if len(parts) > 1 else ""
        return ""


class BlastRadiusAgent:
    """
    Stage 2: Traces failure path and calculates blast radius.

    Responsibilities:
    - Use IncidentResolver to trace failure path from test to root cause
    - Calculate blast radius using PageRank algorithm
    - Identify all affected functions
    - Pass handoff to MemoryCuratorAgent
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        # Use workspace-specific graph
        graph_name = f"repograph_ws_{workspace_id}"
        self.resolver = IncidentResolver(graph_name=graph_name)

    def analyze_blast_radius(self, handoff: AgentHandoff) -> AgentHandoff:
        """
        Trace failure path and calculate blast radius.

        Args:
            handoff: Incoming handoff with fault_signature

        Returns:
            Updated handoff with root_cause_function, affected_functions, blast_radius
        """
        logger.info(f"[BlastRadiusAgent] Analyzing blast radius for {handoff.failing_test}")

        try:
            # Trace failure path from test to root cause
            failure_paths = self.resolver.trace_failure_path(
                handoff.failing_test,
                max_hops=6
            )

            if failure_paths:
                # Extract nodes from path segments
                nodes = []
                for segment in failure_paths:
                    node = segment.get("node")
                    if node and node.get("name"):
                        nodes.append(node)

                # Last node in shortest path is typically the root cause
                if nodes:
                    handoff.root_cause_function = nodes[-1].get("name", "unknown")
                    handoff.affected_functions = [n.get("name") for n in nodes if n.get("name")]

                logger.info(f"[BlastRadiusAgent] Found root cause: {handoff.root_cause_function}")

            # Calculate blast radius using PageRank
            if handoff.root_cause_function:
                blast_radius = self.resolver.calculate_blast_radius(
                    handoff.root_cause_function
                )
                handoff.blast_radius = blast_radius[:10]  # Top 10
                logger.info(f"[BlastRadiusAgent] Blast radius: {len(blast_radius)} functions affected")

        except Exception as e:
            logger.error(f"[BlastRadiusAgent] Error: {e}")
            # Continue pipeline even if blast radius analysis fails

        return handoff


class MemoryCuratorAgent:
    """
    Stage 3: Creates semantic facts and finds applicable playbooks.

    Responsibilities:
    - Create semantic fact linking root cause to function
    - Find existing playbooks for the fault signature
    - Create new playbook if none exists
    - Close temporal edges for superseded facts
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.memory = TemporalMemory(graph_name=f"repograph_ws_{workspace_id}")

    def curate_memory(self, handoff: AgentHandoff) -> AgentHandoff:
        """
        Create semantic facts and find playbooks.

        Args:
            handoff: Incoming handoff with analysis results

        Returns:
            Updated handoff with playbook_recommendations, semantic_facts_created
        """
        logger.info(f"[MemoryCuratorAgent] Curating memory for workspace {self.workspace_id}")

        # Create semantic fact for root cause
        if handoff.root_cause_function and handoff.fault_signature:
            fact_data = {
                "workspace_id": self.workspace_id,
                "fact_type": "root_cause",
                "function_name": handoff.root_cause_function,
                "module": "sandbox_service/app.py",  # Could be extracted from stack trace
                "statement": f"{handoff.root_cause_function} fails with {handoff.fault_signature}",
                "evidence": {
                    "incident_id": handoff.incident_id,
                    "failing_test": handoff.failing_test,
                    "fault_signature": handoff.fault_signature,
                    "affected_functions": handoff.affected_functions
                },
                "confidence": 0.95,
                "commit_sha": "HEAD",
                "tags": ["incident", "root_cause", handoff.fault_signature.split(':')[0]]
            }
            fact_id = self.memory.create_semantic_fact(fact_data)
            handoff.semantic_facts_created.append(fact_id)
            logger.info(f"[MemoryCuratorAgent] Created semantic fact: {fact_id}")

        # Find applicable playbooks
        if handoff.fault_signature:
            playbooks = self.memory.find_applicable_playbooks(
                handoff.fault_signature
            )

            if playbooks:
                handoff.playbook_recommendations = [p["name"] for p in playbooks]
                logger.info(f"[MemoryCuratorAgent] Found {len(playbooks)} applicable playbooks")
            else:
                # Create a new playbook for this fault signature
                playbook_id = self._create_playbook_for_signature(handoff)
                handoff.playbook_recommendations.append(playbook_id)
                logger.info(f"[MemoryCuratorAgent] Created new playbook: {playbook_id}")

        return handoff

    def _create_playbook_for_signature(self, handoff: AgentHandoff) -> str:
        """Create a new playbook for a fault signature."""
        playbook_data = {
            "workspace_id": self.workspace_id,
            "fault_signature": handoff.fault_signature,
            "name": f"Fix {handoff.fault_signature.split(':')[0]} in {handoff.root_cause_function or 'unknown'}",
            "description": f"Remediation playbook for {handoff.fault_signature}",
            "steps": self._generate_remediation_steps(handoff),
            "applicability": {
                "exception_type": handoff.fault_signature.split(':')[0] if handoff.fault_signature else "",
                "functions": handoff.affected_functions
            }
        }

        return self.memory.create_playbook(playbook_data)

    def _generate_remediation_steps(self, handoff: AgentHandoff) -> List[str]:
        """Generate remediation steps based on fault signature."""
        steps = []
        exc_type = handoff.fault_signature.split(':')[0] if handoff.fault_signature else ""

        if "KeyError" in exc_type:
            steps = [
                "1. Identify the missing key from the error message",
                "2. Add input validation using .get() method with default value",
                "3. Add schema validation at API boundary",
                "4. Run targeted tests to verify fix",
                "5. Update semantic fact with new validity timestamp"
            ]
        elif "TypeError" in exc_type:
            steps = [
                "1. Identify the type mismatch from error details",
                "2. Add type hints and runtime type checking",
                "3. Fix operator usage (e.g., ** instead of ^)",
                "4. Run targeted tests to verify fix",
                "5. Update semantic fact with new validity timestamp"
            ]
        elif "AssertionError" in exc_type:
            steps = [
                "1. Review the assertion that failed",
                "2. Check calculation logic for correctness",
                "3. Verify expected vs actual values",
                "4. Fix the implementation",
                "5. Run targeted tests to verify fix"
            ]
        else:
            steps = [
                "1. Analyze stack trace to identify root cause",
                "2. Review code at failure location",
                "3. Implement fix based on fault pattern",
                "4. Run targeted tests to verify",
                "5. Update semantic facts and playbooks"
            ]

        return steps


class MultiAgentPipeline:
    """
    Orchestrates the three-agent handoff pipeline.

    Usage:
        pipeline = MultiAgentPipeline(workspace_id="alpha")
        result = pipeline.run(incident_data)
    """

    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self.triage_agent = TriageAgent(workspace_id)
        self.blast_radius_agent = BlastRadiusAgent(workspace_id)
        self.memory_curator_agent = MemoryCuratorAgent(workspace_id)

    def run(self, incident_data: Dict[str, Any]) -> AgentHandoff:
        """
        Run the full three-agent pipeline.

        Args:
            incident_data: Dict with:
                - incident_id: Unique identifier
                - session_id: Session identifier
                - stack_trace: Full stack trace
                - failing_test: Name of failing test

        Returns:
            Final handoff with all analysis results
        """
        logger.info(f"[Pipeline] Starting incident resolution for workspace {self.workspace_id}")

        # Initialize handoff
        handoff = AgentHandoff(
            workspace_id=self.workspace_id,
            incident_id=incident_data.get("incident_id", "unknown"),
            session_id=incident_data.get("session_id", "unknown"),
            stack_trace=incident_data.get("stack_trace", ""),
            failing_test=incident_data.get("failing_test", "")
        )

        # Stage 1: Triage
        logger.info("[Pipeline] Stage 1/3: TriageAgent")
        handoff = self.triage_agent.analyze_incident(handoff)

        # Stage 2: Blast Radius Analysis
        logger.info("[Pipeline] Stage 2/3: BlastRadiusAgent")
        handoff = self.blast_radius_agent.analyze_blast_radius(handoff)

        # Stage 3: Memory Curation
        logger.info("[Pipeline] Stage 3/3: MemoryCuratorAgent")
        handoff = self.memory_curator_agent.curate_memory(handoff)

        logger.info(f"[Pipeline] Pipeline completed. Facts created: {len(handoff.semantic_facts_created)}")
        return handoff


def demo_pipeline():
    """Demo the multi-agent pipeline."""
    # Example incident
    incident = {
        "incident_id": "incident_001",
        "session_id": "session_abc",
        "stack_trace": """
Traceback (most recent call last):
  File "sandbox_service/app.py", line 14, in process_user_data
    total_income += user['income']
KeyError: 'income'
""",
        "failing_test": "test_incident_process_user_data_missing_income"
    }

    pipeline = MultiAgentPipeline(workspace_id="alpha")
    # Ingest sandbox service data for this workspace
    pipeline.blast_radius_agent.resolver.ingest_sandbox_service()
    result = pipeline.run(incident)

    print("\n=== Pipeline Results ===")
    print(f"Fault Signature: {result.fault_signature}")
    print(f"Root Cause Function: {result.root_cause_function}")
    print(f"Affected Functions: {result.affected_functions}")
    print(f"Blast Radius: {len(result.blast_radius)} functions")
    print(f"Semantic Facts Created: {result.semantic_facts_created}")
    print(f"Playbook Recommendations: {result.playbook_recommendations}")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo_pipeline()
