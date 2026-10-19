# Architecture

GraphTriage is a Python prototype that uses FalkorDB as the graph store for sandbox code metadata and incident memory.

## Components

- **IncidentResolver** ingests the sandbox inventory, checks entity existence, finds tests linked to functions and calculates impact from available relationships.
- **TriageAgent** extracts a fault signature and records an episodic incident.
- **BlastRadiusAgent** analyses code-graph relationships and assembles an impact result.
- **MemoryCuratorAgent** stores semantic facts and finds or creates procedural playbooks.
- **MCP server** exposes investigation operations as tools over standard input/output.

## Code graph

The sandbox ingester creates `Module`, `Function` and `Test` nodes with these relationships:

- `(Function)-[:DEFINED_IN]->(Module)`
- `(Module)-[:CONTAINS]->(Function)`
- `(Test)-[:COVERS]->(Function)`

The inventory is hand-authored. It is not a general-purpose Python parser and does not infer function-to-function `CALLS` edges. A call-chain query can only follow those relationships if they have been added to the selected graph.

## Memory graph

The memory layer stores three node types:

- `EpisodicIncident`: incident context, stack trace and timestamp.
- `SemanticFact`: learned knowledge with `valid_from`, `valid_to` and `status`.
- `ProceduralPlaybook`: reusable remediation steps.

When a fact is superseded, the new fact points to the older fact using `SUPERSEDED`; the old record remains available with its validity interval closed.

## Workspace separation

Agents select workspace-specific graph names through the FalkorDB client. Separate graph names isolate records logically, but are not by themselves a production-grade tenant security boundary. Database credentials and network access must still be controlled.

## Deployment boundary

The repository contains a command-line demo and an MCP server; it does not provide a verified HTTP API or web UI. The Docker image runs the demo process, not a long-running web service.
