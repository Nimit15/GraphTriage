# Usage

For the shortest setup path, follow the [root README](../README.md).

## Start FalkorDB

Run a local database and Browser with Docker:

```bash
docker run -d --name graphtriage-db -p 6379:6379 -p 3000:3000 -v graphtriage-data:/var/lib/falkordb/data falkordb/falkordb:latest
```

The database listens on port 6379 and the Browser is at http://localhost:3000. If the container already exists but is stopped, run `docker start graphtriage-db`.

## Configure the Python client

Create a Python virtual environment, install `requirements.txt`, and copy `.env.example` to `.env`. For the local container, use host `127.0.0.1`, port `6379`, blank username/password and `FALKORDB_SSL=false`. For FalkorDB Cloud, use the endpoint, credentials and TLS settings from the Cloud console.

## Run the demo

From the repository root, with the virtual environment active:

```bash
python scripts/run_live_demo.py
```

The demo seeds `graphtriage_demo` and stores temporal records in `graphtriage_demo_memory`. In the Browser, select `graphtriage_demo`. The demo intentionally investigates a failing sandbox test; the targeted test may fail because it represents the bug being diagnosed.

## Run tests

```bash
python -m pytest tests/test_incident_resolver.py tests/test_temporal_memory.py -v --tb=short
```

The tests use uniquely named graphs and delete them during teardown. Use a development database.

## Run the MCP server

With the FalkorDB environment variables configured:

```bash
python -m src.mcp.mcp_server
```

The server uses standard input/output and is intended to be launched by an MCP client. It does not expose an HTTP endpoint.
