# Architecture Documentation

## Overview

RepoGraph Investigator is a graph-based dependency analysis tool that models software repositories as interconnected graphs to trace code impact and dependencies.

## Core Components

### 1. Data Layer

#### Graph Database (FalkorDB)
- **Engine**: Redis-backed graph database with Cypher query language
- **Storage**: Persistent graph schema with nodes (Module, Function) and relationships (CALLS, DEFINED_IN)
- **Schema**:
  - `Module`: Source files with metadata
  - `Function`: Code units with signature information
  - `Dependency`: External package references
  - `Test`: Test files with coverage mapping

#### Data Ingestion
- **Source**: Synthetic demo data for demonstration
- **Pipeline**: TypeScript parsers → Graph schema validation → FalkorDB insertion
- **Frequency**: One-time seeding for demo purposes

### 2. Application Layer

#### Core Engine
- **RepoGraph Class**: Main graph interaction and analysis logic
- **InvestigationManager**: Session persistence and retrieval
- **ImpactAnalyzer**: Path calculation and explanation generation

#### CLI Interface
- **Commander.js**: Command-line argument parsing
- **Commands**: `impact`, `save`, `retrieve`, `status`
- **Output**: Formatted explanations with graph evidence levels

### 3. Presentation Layer

#### User Interface
- **Terminal**: Text-based interactive CLI
- **Output**: Color-coded explanations with confidence indicators
- **Navigation**: Command-driven workflow

## Data Flow

```
1. User Command → CLI Parser
2. Graph Query → FalkorDB Cypher
3. Path Calculation → Impact Analysis
4. Evidence Collection → Explanation Generation
5. Session Storage → Investigation Persistence
6. Results → Formatted Output
```

## Graph Schema Details

### Node Properties

#### Module
- `path`: File system path
- `name`: Filename
- `language`: Programming language
- `lines`: Source code line count
- `functions`: Array of Function nodes

#### Function
- `name`: Function identifier
- `module`: Parent module path
- `line`: Line number in source
- `complexity`: Cyclomatic complexity
- `parameters`: Array of parameter names
- `callsTo`: Array of called functions
- `definedIn`: Parent module

### Relationship Types

#### Function Relationships
- `CALLS`: Function-to-function call chain
- `DEFINED_IN`: Function to Module containment
- `CONTAINS`: Module to Function containment

#### Test Relationships
- `COVERS`: Test to Function coverage mapping
- `TESTS_MODULE`: Test to Module association

## Query Patterns

### Impact Analysis
```cypher
MATCH path = (affected:Function)-[:CALLS*]->(changed:Function)
WHERE changed.name = $functionName
RETURN affected.name, path
```

### Dependency Tracing
```cypher
MATCH (func1:Function)-[:CALLS]->(func2:Function)
WHERE func1.module = $sourceModule
RETURN func2.name
```

### Test Coverage
```cypher
MATCH (test:Test)-[:COVERS]->(func:Function)
WHERE func.name = $functionName
RETURN test.path
```

## Track 1 vs Track 2

### Track 1 (Core)
- Dependency ingestion and analysis
- Impact path calculation
- Evidence-backed explanations
- Graph-based reasoning

### Track 2 (Memory)
- Investigation session persistence
- Cross-session retrieval
- Version-aware findings
- Stale detection and validation

## Performance Considerations

1. **Graph Size**: Synthetic data limits demonstration scope
2. **Query Optimization**: Path calculations use indexed graph traversal
3. **Memory Management**: Investigation sessions stored with TTL for cleanup
4. **Caching**: Graph schema cached in Redis connection

## Error Handling

- **Database Failures**: Graceful degradation with informative messages
- **Invalid Queries**: Validation with clear error feedback
- **Missing Data**: Fallback explanations with uncertainty indicators

## Security

- **Data Validation**: Input sanitization for all graph queries
- **Access Control**: Basic connection authentication
- **Data Integrity**: Graph constraints and relationship validation

## Deployment

### Prerequisites
- Node.js 18+
- FalkorDB (Docker or local)

### Setup Commands
```bash
npm install
npm run build
npm run seed
npm run dev
```

### Configuration
- `.env` file for FalkorDB connection parameters
- Environment-specific settings for development/production

## Testing Strategy

### Unit Tests
- Graph query validation
- Impact analysis correctness
- Data structure validation

### E2E Tests
- CLI command verification
- Integration with FalkorDB
- End-to-end workflow testing

### Test Coverage
- Code paths with graph evidence
- Error conditions and edge cases
- Cross-session memory functionality

## Future Enhancements

1. **Real Repository Support**: Replace synthetic data with real repo parsing
2. **Incremental Updates**: Watch for file changes and update graph
3. **Advanced Analytics**: Performance metrics and recommendations
4. **Web UI**: Graphical visualization of dependency graphs
5. **API Integration**: REST/GraphQL endpoints for programmatic access

## Monitoring and Observability

- **Connection Status**: FalkorDB health checks
- **Query Performance**: Graph query timing and optimization
- **Session Tracking**: Investigation lifecycle management
- **Error Rates**: Fault detection and alerting

## Configuration Management

### Environment Variables
```bash
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_PASSWORD=optional
GRAPH_NAME=demo-graph
```

### Graph Configuration
- **Namespace**: Project-specific graph isolation
- **Schema Versioning**: Version-aware graph structures
- **Data Retention**: TTL for temporary investigations

## Migration Guide

### From v1.x to v2.0
- Graph schema updated for enhanced node properties
- New investigation persistence features added
- CLI interface modified with additional commands

### Upgrade Process
1. Backup existing graph data
2. Run `npm run build` for schema migration
3. Update environment variables if needed
4. Seed demo data with `npm run seed`

## Documentation Generation

This architecture document is generated from the codebase structure and serves as:
- **Development Reference**: Component interaction and data flow
- **Onboarding Guide**: New team members understanding
- **Maintenance Manual**: Code evolution and updates
- **Compliance Document**: Architecture validation and verification

## Compliance Notes

- **AI-Assisted Development**: Created with Claude Code assistance
- **Open Source**: MIT license for hackathon contribution
- **Security**: No production credentials or sensitive data in repository
- **Testing**: All functionality verified with comprehensive test suite