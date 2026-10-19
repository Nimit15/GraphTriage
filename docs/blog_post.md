# From a failing test to graph-backed context

GraphTriage explores a practical debugging question: when a test fails, how can the surrounding code and earlier incident knowledge be made easier to inspect?

The prototype stores a hand-authored sandbox inventory in FalkorDB. Modules, functions and tests become nodes. The ingester creates relationships for module containment, function definitions and test coverage. That lets the resolver ask specific questions with Cypher instead of relying only on stack-trace text.

A guard checks whether requested entities exist in the graph. If an entity is missing, the resolver returns an unverified result rather than inventing evidence. The graph is the source of the relationships it reports.

## Keeping incident memory

The memory layer separates three kinds of records:

- `EpisodicIncident` stores a particular failure and its context.
- `SemanticFact` stores a learned statement, such as a suspected root cause.
- `ProceduralPlaybook` stores reusable remediation steps.

Semantic facts carry validity timestamps and a status. When new knowledge supersedes an older fact, the new record points to the previous one and the previous record's validity interval is closed. The old fact remains available as history.

A three-stage pipeline passes a structured handoff from triage to impact analysis to memory curation. Each stage has a narrow responsibility and uses the graph-backed context available to it.

## What the graph can show today

The inventory is synthetic rather than a parser for arbitrary repositories. It creates `DEFINED_IN`, `CONTAINS` and `COVERS` links. It does not infer function-to-function `CALLS` relationships from source code yet. A caller chain cannot be assumed to exist in a freshly seeded graph.

This boundary matters: impact analysis is only as useful as the stored relationships. Keeping the graph schema explicit makes missing evidence easier to spot and gives future ingestion work a clear target—parse actual Python function definitions and call sites, then test the resulting relationships against known examples.

## Reading the benchmark file

The checked-in benchmark results record timings for the failure-path tracing method, blast-radius calculation, temporal-memory operations and the full incident pipeline. The failure-path metric is elapsed time for the Python method as implemented; it should not be described as one native shortest-path query. The environment that produced the recording was not captured, so the numbers are a historical reference rather than a performance guarantee.

The script's test-selection comparison is illustrative: 50 tests is an estimated suite size and 5 tests is a typical targeted selection. The 90% figure is a reduction in the number of tests selected for that example, not a measured wall-clock speedup.

GraphTriage remains a hackathon prototype. The next meaningful step is real source ingestion with verified call edges, followed by evaluation against repositories with known dependency paths.
