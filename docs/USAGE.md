# Usage Guide

## Quick Start

RepoGraph Investigator is designed to be simple to use while providing powerful dependency analysis capabilities.

## Basic Operations

### 1. Check Environment Status

```bash
npm run db:check
```

This verifies your FalkorDB connection and tests basic graph functionality.

### 2. Seed Demo Data

```bash
npm run seed
```

Loads synthetic repository data into your graph database for demonstration.

### 3. Start the CLI

```bash
npm run dev
```

This launches the interactive command-line interface.

## Command Reference

### Impact Analysis

Analyze what could break if you change a specific function:

```bash
repograph impact -m src/auth/login.ts -f parseCredentials
```

**Options:**
- `-m, --module`: Module path (e.g., `src/auth/login.ts`)
- `-f, --function`: Function name (e.g., `parseCredentials`)

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 IMPACT ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Module: src/auth/login.ts
Function: parseCredentials

📊 Explanation:
✅ Graph Evidence: 3 direct CALLS relationships detected in graph
⚠️ Uncertain Inferences: Potential indirect dependencies not modeled in graph
📈 Impact: 3 entities affected
🚨 Code changes will impact 3 downstream functions

Affected Functions:
1. src/auth/login.ts:parseCredentials (line 12)
2. src/api/users.ts:getUserById (line 23)
3. src/utils/helpers.ts:formatResponse (line 30)

Impact Path:
1. src/auth/login.ts:parseCredentials → src/api/users.ts:getUserById
2. src/api/users.ts:getUserById → src/utils/helpers.ts:formatResponse
3. src/utils/helpers.ts:formatResponse → src/payment/processor.ts:processPayment
```

### Save Investigation

Store your findings in the graph database for later retrieval:

```bash
repograph save -i inv-001 -q "What breaks if parseCredentials changes?" -r '{"affected": ["getUserById", "validateSession"]}' -c 0.95 -p /my/repo
```

**Options:**
- `-i, --id`: Unique investigation ID
- `-q, --query`: The investigation question
- `-r, --result`: JSON result data
- `-c, --confidence`: Confidence score (0-1)
- `-p, --path`: Repository path

### Retrieve Investigations

Load previously saved investigations:

```bash
repograph retrieve

# With filters:
repograph retrieve -p /my/repo -v v1.0
```

**Options:**
- `-p, --path`: Filter by repository path
- `-v, --version`: Filter by version

### Environment Status

Check your graph database connection:

```bash
repograph status
```

## Advanced Usage

### Working with Different Repositories

Track multiple repositories using different graph namespaces:

```bash
# Environment setup
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
GRAPH_NAME=my-project-graph
REPO_PATH=/path/to/repo

# Different namespace for each repo
npm run db:check
```

### Custom Query Examples

For complex analysis, you can execute custom Cypher queries:

```typescript
import { RepoGraph } from './src/core/repo-graph';

const graph = new RepoGraph();
await graph.connect();

// Find all callers of a function
const callers = await graph.client.graph.query(graph.graphName, `
  MATCH (caller:Function)-[:CALLS]->(target:Function {name: $funcName})
  RETURN caller.name, caller.module
`, { funcName: 'parseCredentials' });

// Get full dependency tree
const tree = await graph.client.graph.query(graph.graphName, `
  MATCH path = (func:Function {name: $funcName})<-[:CALLS*]-(ancestor:Function)
  RETURN func, ancestor, length(path) as distance
`, { funcName: 'parseCredentials' });
```

### Session Management

Track investigation sessions with version control:

```bash
# Save with version
repograph save -i inv-002 -q "Analyze payment module" -r '...data...' -c 0.88 -p /repo -v v2.1

# Retrieve by version
repograph retrieve -p /repo -v v2.1
```

### Error Handling

Common issues and solutions:

1. **FalkorDB Not Running**
   ```bash
   # Start with Docker
   docker run -p 6379:6379 falkordb/falkordb:latest
   ```

2. **Connection Refused**
   ```bash
   # Check FalkorDB is accessible
   telnet localhost 6379
   ```

3. **Invalid Module Path**
   ```bash
   # Use correct paths
   repograph impact -m src/auth/login.ts -f parseCredentials
   ```

4. **Graph Not Seeded**
   ```bash
   # Seed demo data
   npm run seed
   ```

## Output Formatting

The CLI uses color coding to distinguish information types:

- 🔍 **Blue**: Information messages
- ✅ **Green**: Success indicators
- ⚠️ **Yellow**: Warnings
- ❌ **Red**: Error messages
- 📊 **Cyan**: Technical details
- 📈 **White**: Main content

## Scripting

For automation and integration:

```bash
#!/bin/bash

# Analyze a function
module="$1"
function="$2"

echo "Analyzing impact of ${function} in ${module}"
node dist/cli/index.js impact -m "${module}" -f "${function}"

# Save the investigation
investigation_id="analysis-$(date +%s)"
echo "Saving investigation ${investigation_id}"
node dist/cli/index.js save \
  -i "${investigation_id}" \
  -q "Analyze ${function}" \
  -r '{"status": "completed"}' \
  -c 1.0 \
  -p "$(pwd)"
```

## Integration with Other Tools

### Git Integration

Track investigations alongside your repository:

```bash
# Before making a change
repograph impact -m "$(git diff --name-only HEAD~1)" -f "changedFunction"

# After making changes
repograph save -i "post-change-analysis-$COMMIT" -q "Analyze changes from $COMMIT" -r '...data...' -c 0.92 -p "$(pwd)"
```

### CI/CD Integration

Add impact analysis to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Analyze Code Impact
  run: |
    npm run db:check
    repograph impact -m src/api/service.ts -f processData
    repograph save -i "ci-analysis-$GITHUB_RUN_ID" -q "CI impact analysis" -r '...data...' -c 1.0 -p "$GITHUB_WORKSPACE"
```

## Troubleshooting

### Common Issues

1. **"Connection refused" error**
   - Ensure FalkorDB is running
   - Check environment variables
   - Verify network configuration

2. **"Graph does not exist" error**
   - Seed demo data: `npm run seed`
   - Ensure graph name matches configuration

3. **"No module found" error**
   - Verify module paths exist in the graph
   - Run `npm run seed` to load demo data

### Debug Commands

```bash
# Check database status
npm run db:check

# Verify data in graph
node -e "
const { execSync } = require('child_process');
execSync('npm run db:check', { stdio: 'pipe' });
"

# Check if data was loaded
node -e "
const redis = require('redis');
const client = redis.createClient();
client.on('error', err => console.error('Redis Error:', err));
client.graph.roQuery('demo-graph', 'MATCH (n) RETURN count(n) as count')
  .then(res => console.log('Total nodes:', res.data[0].count))
  .catch(err => console.error('Query failed:', err));
client.quit();
"
```

## Support and Documentation

For issues, questions, or feature requests:

1. **Check the docs**: Review this USAGE.md and ARCHITECTURE.md
2. **Run examples**: Use `npm run dev` to explore interactively
3. **Report bugs**: Submit issues with detailed reproduction steps
4. **Contribute**: Fork and submit pull requests with clear commit messages

## Next Steps

1. **Install and run**: `npm install && npm run seed && npm run dev`
2. **Try basic analysis**: `repograph impact -m src/auth/login.ts -f parseCredentials`
3. **Save findings**: Use the `save` command to track important analyses
4. **Explore data**: Use the `retrieve` command to access past investigations
5. **Customize**: Modify the CLI commands or add new analysis functions

RepoGraph Investigator provides a foundation for dependency analysis that you can extend and customize for your specific needs. Start simple and build complexity as you understand the data and requirements better.