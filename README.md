<p align="center">
  <img src="./hero-banner.svg" alt="GraphTriage — graph-grounded incident resolution and temporal memory" width="100%" />
</p>

# GraphTriage

Graph-grounded incident investigation and temporal memory built with FalkorDB.

<p align="center">
  <a href="https://www.python.org/"><img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://www.falkordb.com/"><img alt="FalkorDB" src="https://img.shields.io/badge/Graph_DB-FalkorDB-FF8101"></a>
  <a href="https://pytest.org/"><img alt="pytest" src="https://img.shields.io/badge/Tests-pytest-0A9EDC"></a>
</p>

GraphTriage takes a failing test and incident context, uses a graph to identify related code entities and potential impact, and records incident knowledge for later retrieval. The repository includes a sandbox service with intentional bugs so the workflow can be exercised without connecting a real codebase.

## What it does

- Records incident context, including stack traces and failing tests.
- Links sandbox modules, functions and tests in FalkorDB.
- Checks whether requested entities exist before presenting graph-backed findings.
- Calculates impact from the available graph relationships and identifies relevant tests.
- Stores episodic incidents, semantic facts and reusable remediation playbooks.
- Tracks semantic-fact validity and supersession over time.

## Architecture

<p align="center">
  <img src="./architecture-flow.svg" alt="GraphTriage incident input, three agent stages and FalkorDB graph state" width="100%" />
</p>

A structured incident handoff passes through triage, impact analysis and memory curation. FalkorDB stores the code relationships and memory records used by these stages.

## Graph model

The sandbox ingestion models modules, functions and tests. It creates both `DEFINED_IN` and `CONTAINS` relationships between functions and modules, and `COVERS` relationships from tests to functions. The memory layer uses `EpisodicIncident`, `SemanticFact` and `ProceduralPlaybook` nodes, with temporal properties on semantic facts.

| Node label | Purpose |
|---|---|
| `Module` | Source module path and language |
| `Function` | Function name, source module, line and complexity |
| `Test` | Test name, module, coverage and status |
| `EpisodicIncident` | Incident context, stack trace and timestamp |
| `SemanticFact` | Learned fact with `valid_from`, `valid_to` and `status` |
| `ProceduralPlaybook` | Reusable remediation steps and fault signature |

Relationships used by sandbox ingestion include `(:Function)-[:DEFINED_IN]->(:Module)`, `(:Module)-[:CONTAINS]->(:Function)`, and `(:Test)-[:COVERS]->(:Function)`. The current sandbox fixture does not infer function-to-function `CALLS` links, so call-chain results depend on whether such links are present in the selected graph.

### Example queries

Find tests that cover a function:

```cypher
MATCH (t:Test)-[:COVERS]->(f:Function {name: $function_name})
RETURN t.name, t.status, t.module
```

Find the module for a function:

```cypher
MATCH (f:Function)-[:DEFINED_IN]->(m:Module)
WHERE f.name = $function_name
RETURN m.name, m.path
```

## Track 1 — Incident resolution

GraphTriage checks entities against available graph data, identifies tests connected to functions, and calculates impact from the relationships present in the selected graph. Unknown entities are returned as unverified rather than being treated as graph-backed facts.

## Track 2 — Temporal memory

<p align="center">
  <img src="./temporal-memory-lifecycle.svg" alt="Episodic incidents, semantic facts, procedural playbooks and semantic fact supersession" width="100%" />
</p>

A semantic fact can be superseded by newer knowledge while the previous fact remains available as history. The implementation records validity timestamps and a `SUPERSEDED` relationship from the newer fact to the older fact.

## Recorded benchmarks

The checked-in `benchmark_results.json` records the following mean timings. The file does not include enough environment metadata to independently reproduce the measurements, so treat these as recorded results rather than a portable performance guarantee.

| Operation | Recorded mean |
|---|---:|
| Shortest-path query | 63.20 ms |
| Blast-radius query | 29.20 ms |
| Temporal-memory query | 241.53 ms |
| End-to-end pipeline | 2,985.63 ms (about 2.99 s) |
| Targeted test selection | 5 of 50 tests (90% fewer tests) |

## Get started

### Requirements

- Python 3.11 or newer
- Docker
- The dependencies in `requirements.txt`

### Start FalkorDB

```bash
docker run --rm -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

Open the FalkorDB browser at `http://localhost:3000`. If you map different host ports, use those port values in your environment configuration.

### Install the project

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_USERNAME`, `FALKORDB_PASSWORD` and `FALKORDB_SSL` in the local `.env` file as appropriate for your instance. Do not commit `.env`.

### Run the tests

```powershell
python -m pytest tests/test_incident_resolver.py tests/test_temporal_memory.py -v --tb=short
```

The tests use FalkorDB and should run against an isolated development database. Some ingestion fixtures clear their selected graph before re-seeding; do not point them at a graph containing data you need to preserve.

## Limitations

- Ingestion uses synthetic sandbox data; it is not a general-purpose repository parser.
- The sandbox fixture does not currently infer function-to-function call edges.
- Recorded benchmark timings are specific to the environment in which they were measured.
- The project is a hackathon prototype and is not a hardened production service.

## AI-use disclosure

AI coding tools assisted with implementation, debugging and documentation. The project owner reviewed the project and ran the documented local test suite.

## License

MIT. See [LICENSE](./LICENSE).
