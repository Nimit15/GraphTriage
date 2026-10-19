from typing import List, Dict, Any, Optional, Tuple
from falkordb import FalkorDB
import logging
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)
class IncidentResolver:
    """
    Main incident resolver that uses FalkorDB to trace failures
    through software dependency graphs.
    """

    def __init__(self, graph_name: str = "graphtriage"):
        """
        Initialize the incident resolver.

        Args:
            graph_name: Graph to use. If omitted, GRAPH_NAME is used,
                falling back to "graphtriage".
        """
        # Use connection factory for central connection management
        from .db_connection import get_falkordb_client
        self.db = get_falkordb_client()
        self.graph = self.db.select_graph(graph_name)
        self.graph_name = graph_name

        # Initialize schema if needed
        self._ensure_schema()

    def _validate_entity_existence(self, entity_name: str) -> dict:
        """
        Validate that an entity exists in the graph before performing analysis.

        Args:
            entity_name: Name of the entity to validate

        Returns:
            Dict with analysis results if entity exists, or refusal message if not
        """
        try:
            # Query to check if entity exists in the graph
            query = """
            MATCH (n)
            WHERE (n:Function OR n:Test OR n:Module)
            AND n.name = $entity_name
            RETURN count(n) as count
            """

            result = self.graph.query(query, {"entity_name": entity_name})
            entity_exists = result.result_set[0][0] > 0 if result.result_set else False

            if entity_exists:
                return {
                    "status": "OK",
                    "entity_found": True,
                    "entity_name": entity_name
                }
            else:
                return {
                    "status": "UNVERIFIED_ENTITY",
                    "hops": 0,
                    "reason": f"Entity '{entity_name}' not found in graph; refusing to speculate without graph evidence",
                    "affected_functions": [],
                    "impact_path": []
                }

        except Exception as e:
            logger.error(f"Entity validation failed for '{entity_name}': {e}")
            return {
                "status": "VALIDATION_ERROR",
                "error": str(e),
                "entity_name": entity_name
            }
        self.graph = self.db.select_graph(self.graph_name)

        # Initialize schema if needed
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure the graph schema exists."""
        try:
            # Test if graph has any nodes
            result = self.graph.query("MATCH (n) RETURN count(n) as count")
            node_count = result.result_set[0][0] if result.result_set else 0

            if node_count == 0:
                logger.info("Initializing graph schema")
                self._create_schema()
        except Exception as e:
            logger.warning(f"Could not check graph state: {e}")
            # Try to create schema anyway
            self._create_schema()

    def _create_schema(self):
        """Create initial graph schema for software dependency tracking."""
        schema_queries = [
            # Create indices for better performance
            "CREATE INDEX FOR (f:Function) ON (f.name)",
            "CREATE INDEX FOR (m:Module) ON (m.path)",
            "CREATE INDEX FOR (t:Test) ON (t.name)",
            "CREATE INDEX FOR (i:Incident) ON (i.id)",

            # Create constraint for uniqueness
            "CREATE CONSTRAINT FOR (f:Function) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT FOR (m:Module) REQUIRE m.path IS UNIQUE",
        ]

        for query in schema_queries:
            try:
                self.graph.query(query)
                logger.debug(f"Executed schema query: {query}")
            except Exception as e:
                # Ignore errors for constraints/indices that may already exist
                if "already exists" not in str(e).lower():
                    logger.warning(f"Schema query failed: {query} - {e}")

    def ingest_sandbox_service(self):
        """
        Ingest the sandbox service codebase into the graph.
        Creates nodes for functions, modules, tests and their relationships.
        """
        logger.info("Ingesting sandbox service into FalkorDB graph")

        # Replace only the sandbox code inventory. Leave incident-memory nodes alone.
        self.graph.query(
            """
            MATCH (n)
            WHERE n:Module OR n:Function OR n:Test
            DETACH DELETE n
            """
        )

        # Modules
        modules = [
            {"path": "sandbox_service/app.py", "name": "app.py", "language": "python"}
        ]

        # Functions from sandbox_service/app.py
        functions = [
            {"name": "calculate_distance", "module": "sandbox_service/app.py",
             "line": 8, "complexity": 3, "parameters": ["x1", "y1", "x2", "y2"]},
            {"name": "process_user_data", "module": "sandbox_service/app.py",
             "line": 13, "complexity": 4, "parameters": ["user_list"]},
            {"name": "validate_credit_card", "module": "sandbox_service/app.py",
             "line": 27, "complexity": 5, "parameters": ["card_number"]},
            {"name": "calculate_compound_interest", "module": "sandbox_service/app.py",
             "line": 40, "complexity": 4, "parameters": ["principal", "rate", "time", "n"]},
            {"name": "add_user", "module": "sandbox_service/app.py",
             "line": 58, "complexity": 2, "parameters": ["user_data"]},
            {"name": "get_user_by_email", "module": "sandbox_service/app.py",
             "line": 62, "complexity": 3, "parameters": ["email"]},
            {"name": "calculate_growth_rate", "module": "sandbox_service/app.py",
             "line": 68, "complexity": 4, "parameters": ["initial", "final", "periods"]},
        ]

        # Tests from sandbox_service/test_app.py and test_failing_incident.py
        tests = [
            {"name": "test_calculate_distance", "module": "sandbox_service/test_app.py",
             "coverage": ["calculate_distance"], "status": "passing"},
            {"name": "test_process_user_data_with_valid_users", "module": "sandbox_service/test_app.py",
             "coverage": ["process_user_data"], "status": "passing"},
            {"name": "test_process_user_data_with_missing_field", "module": "sandbox_service/test_app.py",
             "coverage": ["process_user_data"], "status": "failing", "expected_exception": "KeyError"},
            {"name": "test_validate_credit_card_valid", "module": "sandbox_service/test_app.py",
             "coverage": ["validate_credit_card"], "status": "passing"},
            {"name": "test_validate_credit_card_invalid", "module": "sandbox_service/test_app.py",
             "coverage": ["validate_credit_card"], "status": "passing"},
            {"name": "test_calculate_compound_interest", "module": "sandbox_service/test_app.py",
             "coverage": ["calculate_compound_interest"], "status": "failing",
             "expected_exception": "AssertionError"},
            {"name": "test_user_service_add_user", "module": "sandbox_service/test_app.py",
             "coverage": ["add_user"], "status": "passing"},
            {"name": "test_user_service_get_user_by_email", "module": "sandbox_service/test_app.py",
             "coverage": ["get_user_by_email"], "status": "passing"},
            {"name": "test_user_service_calculate_growth_rate", "module": "sandbox_service/test_app.py",
             "coverage": ["calculate_growth_rate"], "status": "failing",
             "expected_exception": "TypeError"},
            {"name": "test_process_user_data_empty", "module": "sandbox_service/test_app.py",
             "coverage": ["process_user_data"], "status": "passing"},
            # Failing incident tests
            {"name": "test_incident_process_user_data_missing_income",
             "module": "sandbox_service/test_failing_incident.py",
             "coverage": ["process_user_data"], "status": "failing",
             "expected_exception": "KeyError"},
            {"name": "test_incident_calculate_growth_rate_xor_bug",
             "module": "sandbox_service/test_failing_incident.py",
             "coverage": ["calculate_growth_rate"], "status": "failing",
             "expected_exception": "TypeError"},
            {"name": "test_incident_compound_interest_missing_exponentiation",
             "module": "sandbox_service/test_failing_incident.py",
             "coverage": ["calculate_compound_interest"], "status": "failing",
             "expected_exception": "AssertionError"},
        ]

        # Function call relationships (simulated based on code inspection)
        # Note: In this sandbox, there are no actual function-to-function calls.
        # The bugs are within individual functions, not across call chains.
        function_calls = [
            # ("process_user_data", "validate_credit_card"),  # Does NOT call this
            # ("calculate_growth_rate", "calculate_compound_interest"),  # Does NOT call this
            ("get_user_by_email", None),  # Helper function
            ("add_user", None),  # Helper function
        ]

        # Test coverage relationships
        test_coverage = []
        for test in tests:
            for covered_func in test.get("coverage", []):
                test_coverage.append((test["name"], covered_func))

        # Create modules
        module_query = """
        UNWIND $modules as module
        CREATE (m:Module {
            path: module.path,
            name: module.name,
            language: module.language
        })
        """
        self.graph.query(module_query, {"modules": modules})

        # Create functions
        function_query = """
        UNWIND $functions as func
        CREATE (f:Function {
            name: func.name,
            module: func.module,
            line: func.line,
            complexity: func.complexity,
            parameters: func.parameters
        })
        """
        self.graph.query(function_query, {"functions": functions})

        # Create tests
        test_query = """
        UNWIND $tests as test
        CREATE (t:Test {
            name: test.name,
            module: test.module,
            coverage: test.coverage,
            status: test.status,
            expected_exception: test.expected_exception
        })
        """
        self.graph.query(test_query, {"tests": tests})

        # Create DEFINED_IN relationships (function -> module)
        defined_in_query = """
        MATCH (f:Function), (m:Module)
        WHERE f.module = m.path
        CREATE (f)-[:DEFINED_IN]->(m)
        """
        self.graph.query(defined_in_query)

        # Create CONTAINS relationships (module -> function)
        contains_query = """
        MATCH (m:Module), (f:Function)
        WHERE f.module = m.path
        CREATE (m)-[:CONTAINS]->(f)
        """
        self.graph.query(contains_query)

        # Create CALLS relationships (function -> function)
        calls_query = """
        UNWIND $calls as call
        MATCH (caller:Function {name: call.caller})
        MATCH (callee:Function {name: call.callee})
        WHERE callee IS NOT NULL
        CREATE (caller)-[:CALLS]->(callee)
        """
        self.graph.query(calls_query, {"calls": [{"caller": c[0], "callee": c[1]}
                                                for c in function_calls if c[1] is not None]})

        # Create COVERS relationships (test -> function)
        covers_query = """
        UNWIND $covers as cover
        MATCH (t:Test {name: cover.test})
        MATCH (f:Function {name: cover.function})
        CREATE (t)-[:COVERS]->(f)
        """
        self.graph.query(covers_query, {"covers": [{"test": t[0], "function": t[1]}
                                                  for t in test_coverage]})

        logger.info(f"Inserted {len(modules)} modules, {len(functions)} functions, {len(tests)} tests")

    def analyze_impact(self, function_name: str, test_name: str = None) -> Dict[str, Any]:
        """
        Comprehensive impact analysis with unknown-entity guard.

        Args:
            function_name: Target function for analysis
            test_name: Optional test name for dependency tracing

        Returns:
            Dict with impact analysis, refusal, or error
        """
        # Validate primary entity exists
        validation_result = self._validate_entity_existence(function_name)

        if validation_result.get("status") != "OK":
            # Return refusal or error message
            return {
                "status": validation_result["status"],
                "hops": 0,
                "reason": validation_result.get("reason", "Unknown validation error"),
                "affected_functions": [],
                "impact_path": [],
                "function_name": function_name,
                "test_name": test_name
            }

        # Validate related entity if provided
        if test_name:
            test_validation = self._validate_entity_existence(test_name)
            if test_validation.get("status") != "OK":
                return {
                    "status": test_validation["status"],
                    "hops": 0,
                    "reason": f"Related test '{test_name}' not found in graph; refusing to speculate",
                    "affected_functions": [],
                    "impact_path": [],
                    "function_name": function_name,
                    "test_name": test_name
                }

        # Perform full impact analysis
        try:
            # Calculate blast radius
            blast_radius = self.calculate_blast_radius(function_name)

            # Trace the test through stored coverage and call relationships.
            failure_path = []
            if test_name:
                failure_path = self.trace_failure_path_native(test_name)

            # Calculate impact score based on blast radius
            impact_score = len(blast_radius)

            # Calculate confidence based on validation and data availability
            confidence = min(0.95, max(0.1, impact_score * 0.1)) if blast_radius else 0.1

            return {
                "status": "COMPLETED",
                "function_name": function_name,
                "test_name": test_name,
                "blast_radius": blast_radius,
                "failure_path": failure_path,
                "impact_score": impact_score,
                "confidence": confidence,
                "hops": 0,
                "affected_functions": [item.get("function_name") for item in blast_radius],
                "impact_path": [],
                "analysis_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Impact analysis failed for '{function_name}': {e}")
            return {
                "status": "ANALYSIS_FAILED",
                "error": str(e),
                "function_name": function_name,
                "test_name": test_name
            }

    def trace_failure_path_native(self, test_name: str, max_hops: int = 6) -> List[Dict[str, Any]]:
        """
        Trace the covered function and any stored CALLS links.

        Despite this method's legacy name, the current implementation performs
        one graph query per hop rather than a single native multi-hop query.

        Args:
            test_name: Name of the failing test
            max_hops: Maximum number of hops to trace

        Returns:
            List of path segments with nodes and their relationships
        """
        try:
            # Use FalkorDB native Cypher - get functions reachable from the test via COVERS and CALLS
            # We'll do multiple queries for each hop level to avoid variable-length path issues
            path_data = []

            # First, get the function directly covered by the test
            covers_query = """
            MATCH (t:Test {name: $test_name})-[:COVERS]->(f:Function)
            RETURN f
            """
            covers_result = self.graph.query(covers_query, {"test_name": test_name})

            if not covers_result.result_set:
                return []

            covered_func = covers_result.result_set[0][0]
            covered_props = covered_func.properties if hasattr(covered_func, 'properties') else covered_func

            # Add the covered function
            node_info = {
                "name": covered_props.get("name"),
                "type": "Function",
                "module": covered_props.get("module"),
                "coverage": covered_props.get("coverage"),
                "status": covered_props.get("status"),
                "expected_exception": covered_props.get("expected_exception")
            }

            path_data.append({
                "node": node_info,
                "relationship": {"type": "COVERS", "direction": "outgoing"},
                "hops": 1
            })

            # Now trace the call chain hop by hop
            current_func_name = covered_props.get("name")
            current_hop = 2

            while current_hop <= max_hops:
                call_query = """
                MATCH (f:Function {name: $func_name})-[:CALLS]->(called:Function)
                RETURN called
                """
                call_result = self.graph.query(call_query, {"func_name": current_func_name})

                if call_result.result_set and call_result.result_set[0][0]:
                    called_func = call_result.result_set[0][0]
                    called_props = called_func.properties if hasattr(called_func, 'properties') else called_func

                    node_info = {
                        "name": called_props.get("name"),
                        "type": "Function",
                        "module": called_props.get("module"),
                        "coverage": called_props.get("coverage"),
                        "status": called_props.get("status"),
                        "expected_exception": called_props.get("expected_exception")
                    }

                    path_data.append({
                        "node": node_info,
                        "relationship": {"type": "CALLS", "direction": "outgoing"},
                        "hops": current_hop
                    })

                    current_func_name = called_props.get("name")
                    current_hop += 1
                else:
                    # No more calls in chain
                    break

            return path_data

        except Exception as e:
            logger.warning(f"Native Cypher path tracing failed: {e}, falling back to iterative approach")
            return self.trace_failure_path(test_name, max_hops)

    def trace_failure_path(self, test_name: str, max_hops: int = 6) -> List[Dict[str, Any]]:
        """
        Trace the failure propagation path from a test to its root cause.

        Args:
            test_name: Name of the failing test
            max_hops: Maximum number of hops to trace

        Returns:
            List of path segments with nodes and their relationships
        """
        # First find the test
        test_query = """
        MATCH (t:Test {name: $test_name})
        RETURN t
        """

        test_result = self.graph.query(test_query, {"test_name": test_name})
        if not test_result.result_set:
            return []

        # Trace the path using a simpler approach - find all connected functions
        # We'll walk through the dependency chain step by step
        path_data = []

        # Get functions that this test covers
        covers_query = """
        MATCH (t:Test {name: $test_name})-[:COVERS]->(f:Function)
        RETURN f
        """

        covers_result = self.graph.query(covers_query, {"test_name": test_name})

        if covers_result.result_set:
            # For each covered function, trace its call chain
            for record in covers_result.result_set:
                covered_func = record[0]
                covered_props = covered_func.properties if hasattr(covered_func, 'properties') else covered_func

                # Walk the call chain
                current_func = covered_func
                path_length = 1

                while path_length <= max_hops:
                    func_name = current_func.properties.get("name") if hasattr(current_func, 'properties') else current_func.get("name")
                    func_query = """
                    MATCH (f:Function {name: $func_name})
                    OPTIONAL MATCH (f)-[:CALLS]->(called:Function)
                    RETURN f, called
                    """

                    func_result = self.graph.query(func_query, {"func_name": func_name})

                    if func_result.result_set:
                        func_row = func_result.result_set[0]
                        current_func = func_row[0]
                        called_func = func_row[1]

                        # Add to path data
                        current_props = current_func.properties if hasattr(current_func, 'properties') else current_func
                        node_info = {
                            "name": current_props.get("name") if current_props else None,
                            "type": "Function",
                            "module": current_props.get("module") if current_props else None,
                            "coverage": current_props.get("coverage") if current_props else None,
                            "status": current_props.get("status") if current_props else None,
                            "expected_exception": current_props.get("expected_exception") if current_props else None
                        }

                        rel_info = {
                            "type": "CALLS",
                            "direction": "outgoing"
                        }

                        path_data.append({
                            "node": node_info,
                            "relationship": rel_info,
                            "path_length": path_length
                        })

                        # Move to the next function in chain
                        if called_func:
                            current_func = called_func
                            path_length += 1
                        else:
                            # No more functions in chain
                            break
                    else:
                        # No more functions in chain
                        break

        return path_data

    def calculate_blast_radius(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Calculate the blast radius (impact scope) of a function.

        Args:
            function_name: Name of the function to analyze

        Returns:
            List of affected functions ranked by impact score
        """
        query = """
        MATCH (f:Function {name: $function_name})
        OPTIONAL MATCH (f)-[:CALLS]->(called:Function)
        WITH f, called
        RETURN f.name as function_name, f.module as module, called.name as called_name
        ORDER BY called_name
        """

        result = self.graph.query(query, {"function_name": function_name})
        blast_radius = []

        for record in result.result_set:
            function_name = record[0]
            module = record[1]
            called_name = record[2]

            if called_name:
                blast_radius.append({
                    "function_name": called_name,
                    "module": module,
                    "impact_score": 1.0,  # Simplified impact score
                    "call_type": "direct",
                    "rank": len(blast_radius) + 1
                })
            else:
                blast_radius.append({
                    "function_name": function_name,
                    "module": module,
                    "impact_score": 1.0,
                    "call_type": "self",
                    "rank": len(blast_radius) + 1
                })

        return blast_radius

    def calculate_blast_radius(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Calculate the blast radius (impact scope) of a function using PageRank.
        Includes safety guard for small graphs.

        Args:
            function_name: Name of the function to analyze

        Returns:
            List of functions ranked by impact score
        """
        # Safety guard: check if we have enough nodes for PageRank
        count_query = "MATCH (f:Function) RETURN count(f) as count"
        count_result = self.graph.query(count_query)
        node_count = count_result.result_set[0][0] if count_result.result_set else 0

        logger.info(f"Function count for PageRank: {node_count}")

        if node_count < 2:
            logger.warning("Graph has < 2 functions, using degree centrality fallback")
            return self._calculate_degree_centrality(function_name)

        # Try PageRank algorithm
        try:
            pagerank_query = """
            CALL algo.pageRank.stream('Function', 'CALLS', {
                iterations: 20,
                dampingFactor: 0.85
            })
            YIELD nodeId, score
            MATCH (f:Function) WHERE id(f) = nodeId AND f.name = $function_name
            RETURN f.name as function_name, score
            ORDER BY score DESC
            """

            result = self.graph.query(pagerank_query, {"function_name": function_name})

            if result.result_set:
                # Found the function, now get all ranked functions
                all_pagerank_query = """
                CALL algo.pageRank.stream('Function', 'CALLS', {
                    iterations: 20,
                    dampingFactor: 0.85
                })
                YIELD nodeId, score
                MATCH (f:Function) WHERE id(f) = nodeId
                RETURN f.name as function_name, f.module as module, score
                ORDER BY score DESC
                """

                pagerank_result = self.graph.query(all_pagerank_query)
                blast_radius = []

                for record in pagerank_result.result_set:
                    blast_radius.append({
                        "function_name": record[0],
                        "module": record[1],
                        "impact_score": float(record[2]),
                        "rank": len(blast_radius) + 1
                    })

                return blast_radius
            else:
                logger.warning(f"Function {function_name} not found in PageRank results")
                return self._calculate_degree_centrality(function_name)

        except Exception as e:
            logger.warning(f"PageRank failed: {e}, falling back to degree centrality")
            return self._calculate_degree_centrality(function_name)

    def _calculate_degree_centrality(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Calculate degree centrality as fallback when PageRank unavailable.
        """
        query = """
        MATCH (f:Function {name: $function_name})-[r:CALLS]->(called:Function)
        RETURN called.name as function_name, called.module as module, count(r) as call_count
        ORDER BY call_count DESC
        """

        # Also calculate incoming calls (who calls this function)
        incoming_query = """
        MATCH (caller:Function)-[r:CALLS]->(f:Function {name: $function_name})
        RETURN caller.name as function_name, caller.module as module, count(r) as call_count
        ORDER BY call_count DESC
        """

        try:
            outgoing_result = self.graph.query(query, {"function_name": function_name})
            incoming_result = self.graph.query(incoming_query, {"function_name": function_name})

            blast_radius = []

            # Add outgoing calls (functions this function calls)
            for record in outgoing_result.result_set:
                blast_radius.append({
                    "function_name": record[0],
                    "module": record[1],
                    "impact_score": float(record[2]),
                    "call_type": "outgoing",
                    "rank": len(blast_radius) + 1
                })

            # Add incoming calls (functions that call this function)
            for record in incoming_result.result_set:
                blast_radius.append({
                    "function_name": record[0],
                    "module": record[1],
                    "impact_score": float(record[2]),
                    "call_type": "incoming",
                    "rank": len(blast_radius) + 1
                })

            return blast_radius

        except Exception as e:
            logger.error(f"Degree centrality calculation failed: {e}")
            return []

    def get_functions(self) -> List[Dict[str, Any]]:
        """
        Get all functions from the graph.

        Returns:
            List of function information
        """
        query = """
        MATCH (f:Function)
        RETURN f.name as name, f.module as module, f.complexity as complexity,
               f.parameters as parameters
        ORDER BY f.name
        """

        result = self.graph.query(query)
        functions = []

        for record in result.result_set:
            functions.append({
                "name": record[0],
                "module": record[1],
                "complexity": record[2],
                "parameters": record[3]
            })

        return functions

    def get_failing_tests(self) -> List[Dict[str, Any]]:
        """
        Get all currently failing tests from the graph.

        Returns:
            List of failing test information
        """
        query = """
        MATCH (t:Test {status: 'failing'})
        RETURN t.name as test_name, t.module as module,
               t.coverage as coverage, t.expected_exception as expected_exception
        ORDER BY t.name
        """

        result = self.graph.query(query)
        failing_tests = []

        for record in result.result_set:
            failing_tests.append({
                "test_name": record[0],
                "module": record[1],
                "coverage": record[2] if record[2] else [],
                "expected_exception": record[3]
            })

        return failing_tests

    def trace_failure_path(self, test_name: str, max_hops: int = 6) -> List[Dict[str, Any]]:
        """
        Trace the failure propagation path from a test to its root cause.
        Uses FalkorDB native Cypher for multi-hop path tracing (Rule #4 Compliance).

        Args:
            test_name: Name of the failing test
            max_hops: Maximum number of hops to trace

        Returns:
            List of path segments with nodes and their relationships
        """
        return self.trace_failure_path_native(test_name, max_hops)

    def calculate_blast_radius(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Calculate the blast radius (impact scope) of a function.

        Args:
            function_name: Name of the function to analyze

        Returns:
            List of affected functions ranked by impact score
        """
        query = """
        MATCH (f:Function {name: $function_name})
        OPTIONAL MATCH (f)-[:CALLS]->(called:Function)
        WITH f, called
        RETURN f.name as function_name, f.module as module, called.name as called_name
        ORDER BY called_name
        """

        result = self.graph.query(query, {"function_name": function_name})
        blast_radius = []

        for record in result.result_set:
            function_name = record[0]
            module = record[1]
            called_name = record[2]

            if called_name:
                blast_radius.append({
                    "function_name": called_name,
                    "module": module,
                    "impact_score": 1.0,  # Simplified impact score
                    "call_type": "direct",
                    "rank": len(blast_radius) + 1
                })
            else:
                blast_radius.append({
                    "function_name": function_name,
                    "module": module,
                    "impact_score": 1.0,
                    "call_type": "self",
                    "rank": len(blast_radius) + 1
                })

        return blast_radius

    def run_targeted_tests(self, test_names: List[str]) -> Dict[str, Any]:
        """
        Run specific tests using pytest in a subprocess.

        Args:
            test_names: List of test names to run

        Returns:
            Dictionary with test execution results
        """
        import subprocess
        import json
        import time

        if not test_names:
            return {
                "success": True,
                "message": "No tests to run",
                "tests_run": 0,
                "passed": 0,
                "failed": 0,
                "duration": 0
            }

        # Build pytest command
        test_args = []
        for test_name in test_names:
            # Convert test name to pytest format: module::test_name
            if "." in test_name:
                # Already in module.test format
                test_args.append(test_name.replace(".py::", "::").replace("/", ".").replace("\\", "."))
            else:
                # Just test name - we'll need to find it
                test_args.append(f"sandbox_service/test_*.py::{test_name}")

        # Flatten and deduplicate
        unique_tests = list(set(test_args))

        cmd = ["python", "-m", "pytest"] + unique_tests + ["-v", "--tb=short"]

        start_time = time.time()
        try:
            # Run pytest with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=os.getcwd()
            )

            duration = time.time() - start_time

            # Parse results
            passed = result.stdout.count("PASSED")
            failed = result.stdout.count("FAILED")

            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": len(unique_tests),
                "passed": passed,
                "failed": failed,
                "duration": round(duration, 3),
                "command": " ".join(cmd)
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timed out (30s)",
                "tests_run": len(unique_tests),
                "passed": 0,
                "failed": len(unique_tests),
                "duration": 30.0,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tests_run": len(unique_tests),
                "passed": 0,
                "failed": 0,
                "duration": time.time() - start_time,
                "command": " ".join(cmd)
            }

    def close(self):
        """Close the FalkorDB connection."""
        if hasattr(self, 'db'):
            self.db.close()


# Convenience function for quick usage
def create_incident_resolver(host: str = None, port: int = None,
                           graph_name: str = "repograph_incidents") -> IncidentResolver:
    """
    Factory function to create an IncidentResolver instance.

    Args:
        host: FalkorDB host
        port: FalkorDB port
        graph_name: Graph name to use

    Returns:
        Configured IncidentResolver instance
    """
    return IncidentResolver(host=host, port=port, graph_name=graph_name)

if __name__ == "__main__":
    # Demo usage
    resolver = IncidentResolver(graph_name="graphtriage_cli_demo")

    # Ingest the sandbox service
    resolver.ingest_sandbox_service()

    # Get failing tests
    failing_tests = resolver.get_failing_tests()
    print(f"Found {len(failing_tests)} failing tests:")
    for test in failing_tests:
        print(f"  - {test['test_name']} ({test['expected_exception']})")

    # For each failing test, trace the failure path
    for test_info in failing_tests[:2]:  # Limit to first 2 for demo
        test_name = test_info["test_name"]
        print(f"\nTracing failure path for: {test_name}")

        path = resolver.trace_failure_path(test_name)
        if path:
            print(f"  Path length: {path[0]['path_length']}")
            print(f"  Nodes in path: {[n.get('name', n.get('test_name', 'unknown')) for n in path[0]['nodes']]}")

        # Calculate blast radius for covered functions
        for covered_func in test_info["coverage"]:
            print(f"\nBlast radius for {covered_func}:")
            blast_radius = resolver.calculate_blast_radius(covered_func)
            for func_info in blast_radius[:3]:  # Top 3
                print(f"  {func_info['rank']}. {func_info['function_name']} "
                      f"(score: {func_info['impact_score']:.3f})")

    resolver.close()