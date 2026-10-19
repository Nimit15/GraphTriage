<p align="center">
  <img src="./hero-banner.svg" alt="GraphTriage — graph-grounded incident resolution and temporal memory" width="100%" />
</p>

# GraphTriage

GraphTriage is a graph-backed incident investigation prototype built with FalkorDB. It connects failing tests to the code entities they cover, estimates impact from the relationships available in the graph, and stores incident knowledge for later retrieval.

The repository includes a small Python sandbox with intentional bugs. It lets you explore the workflow without indexing a real application.

<p align="center">
  <a href="https://www.python.org/"><img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://www.falkordb.com/"><img alt="FalkorDB" src="https://img.shields.io/badge/Graph_DB-FalkorDB-FF8101"></a>
  <a href="https://pytest.org/"><img alt="pytest" src="https://img.shields.io/badge/Tests-pytest-0A9EDC"></a>
</p>

## What it does

- Stores sandbox modules, functions and tests as graph nodes.
- Links tests to the functions they cover.
- Checks that a requested entity exists before returning a graph-backed result.
- Calculates impact from the relationships actually present.
- Stores episodic incidents, semantic facts and reusable playbooks.
- Tracks fact validity and supersession over time.
- Exposes investigation tools through an MCP server.

## Architecture

<p align="center">
  <img src="./architecture-flow.svg" alt="GraphTriage incident input, agent stages and FalkorDB graph state" width="100%" />
</p>

TriageAgent extracts incident context, BlastRadiusAgent analyses available graph links, and MemoryCuratorAgent records useful knowledge. FalkorDB holds the code relationships and memory records.

## Graph model

The sandbox ingester creates these node types:

| Label | Purpose |
|---|---|
| `Module` | Source module path and language |
| `Function` | Function name, module, line and complexity |
| `Test` | Test name, module, coverage and status |
| `EpisodicIncident` | Incident context, stack trace and timestamp |
| `SemanticFact` | Learned fact with validity timestamps and status |
| `ProceduralPlaybook` | Reusable remediation steps |

The sandbox ingester creates `DEFINED_IN`, `CONTAINS` and `COVERS` relationships. It does **not** infer function-to-function `CALLS` relationships from Python source yet, so call-chain analysis depends on whether those links already exist in the selected graph.

Example: find tests that cover a function.

```cypher
MATCH (t:Test)-[:COVERS]->(f:Function {name: $function_name})
RETURN t.name, t.status, t.module
```

Example: find the module that defines a function.

```cypher
MATCH (f:Function)-[:DEFINED_IN]->(m:Module)
WHERE f.name = $function_name
RETURN m.name, m.path
```

## Track 1: incident resolution

The resolver validates entity names, identifies tests connected to functions and calculates impact from the graph data available. An unknown entity is reported as unverified rather than treated as evidence.

## Track 2: temporal memory

<p align="center">
  <img src="./temporal-memory-lifecycle.svg" alt="Episodic incidents, semantic facts, playbooks and fact supersession" width="100%" />
</p>

A newer semantic fact can supersede an older one. The newer fact points to the prior record; the old fact remains available as history with its validity interval closed.

## Recorded benchmarks

The values below are stored in [benchmark_results.json](./benchmark_results.json). The original measurement environment was not recorded, so treat them as historical results rather than a performance guarantee.

| Operation | Recorded mean |
|---|---:|
| Failure-path tracing method | 63.20 ms |
| Blast-radius calculation | 29.20 ms |
| Temporal-memory operation sequence | 241.53 ms |
| End-to-end incident pipeline | 2,985.63 ms (about 2.99 s) |
| Test-selection example | 5 selected from an estimated 50 |

The failure-path metric is elapsed time for the current `trace_failure_path` method, which issues multiple graph queries; it is not one native `shortestPath` query. The test-selection figure is an estimated comparison in the benchmark script, not a measurement of time saved.

## Install and run locally

You need Python 3.11 or newer and Docker. Use a **local, disposable FalkorDB instance** for the demo and tests.

### 1. Start FalkorDB

Run this once from PowerShell or a terminal:

```bash
docker run -d --name graphtriage-db -p 6379:6379 -p 3000:3000 -v graphtriage-data:/var/lib/falkordb/data falkordb/falkordb:latest
```

Open the FalkorDB Browser at [http://localhost:3000](http://localhost:3000). If the container already exists but is stopped, run `docker start graphtriage-db`.

### 2. Create a Python environment

**Windows PowerShell**

```powershell
cd path\to\GraphTriage
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

**macOS or Linux**

```bash
cd path/to/GraphTriage
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp -n .env.example .env
```

### 3. Check .env

For the local Docker setup, the file should contain:

```dotenv
FALKORDB_HOST=127.0.0.1
FALKORDB_PORT=6379
FALKORDB_USERNAME=
FALKORDB_PASSWORD=
FALKORDB_SSL=false
GRAPH_NAME=graphtriage
```

For FalkorDB Cloud, use the endpoint, credentials and TLS setting supplied by your Cloud instance. Never commit `.env`.

### 4. Run the tests

```bash
python -m pytest tests/test_incident_resolver.py tests/test_temporal_memory.py -v --tb=short
```

The tests use uniquely named graphs and remove them during teardown. Use a development database, not one containing data you need to preserve.

### 5. Run the demo

```bash
python scripts/run_live_demo.py
```

The demo uses `graphtriage_demo` and `graphtriage_demo_memory`. Select `graphtriage_demo` in the Browser to inspect the seeded code graph. The demo intentionally investigates a failing sandbox test, so that targeted test may fail as part of the scenario.

For more detail, see [Usage](./docs/USAGE.md), [Architecture](./docs/ARCHITECTURE.md) and [Security](./docs/SECURITY.md).

## Limitations

- Data ingestion uses a synthetic inventory; it is not a general-purpose repository parser.
- Function-to-function call relationships are not inferred from source code yet.
- Impact results depend on the relationships present in the graph.
- Benchmark environment metadata is incomplete.
- This is a hackathon prototype, not a hardened production incident-response service.

## AI-use disclosure

AI coding tools assisted with implementation, debugging and documentation. The project owner reviewed the implementation and ran the local test suite.

## License

MIT. See [LICENSE](./LICENSE).
