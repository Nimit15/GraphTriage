# Security and data handling

GraphTriage is a hackathon prototype. Evaluate it with local or disposable graph data.

## Credentials

- Keep connection details in a local `.env` file or a deployment environment.
- `.env` is ignored by Git. `.env.example` contains blank credential fields.
- Do not put credentials in source code, screenshots, issues or logs.
- If a credential is exposed, rotate it with the provider before cleaning repository history.

## Graph data

Incident records may contain stack traces, test names, function names and error messages. Review or redact sensitive information before sending production incident data to a graph database.

The sandbox ingester replaces only Module, Function and Test nodes in the selected graph before seeding. It leaves other node labels alone. The demo uses `graphtriage_demo`; automated tests use unique test graph names and delete those graphs during teardown. Do not aim the sandbox ingester at a graph containing data you need to preserve.

## Local versus hosted databases

For local development, expose only the ports you need and stop the container when finished. For FalkorDB Cloud, use the endpoint and TLS settings supplied by the Cloud console. Keep credentials out of Dockerfiles and Compose files.

Workspace-specific graph names separate data logically, but they are not a substitute for database permissions, network controls or a production tenant-isolation design.

## Reporting a problem

For a suspected security issue, contact the repository maintainer privately through GitHub before sharing exploit details publicly.
