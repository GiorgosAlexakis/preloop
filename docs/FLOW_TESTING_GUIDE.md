## Flow Execution Testing Guide

This guide explains how to test the Event-Driven Agentic Flows feature, including invoking flows via API and inspecting running containers.

### Prerequisites

1. **Docker**: Ensure Docker is running and accessible
2. **NATS**: NATS server should be running (for event bus)
3. **Database**: PostgreSQL with all migrations applied
4. **Environment Variables**:
   ```bash
   export SPACEBRIDGE_URL="http://localhost:8000"
   export OPENHANDS_IMAGE="ghcr.io/all-hands-ai/openhands:latest"
   export AGENT_NETWORK_MODE="bridge"
   ```

### Setup

1. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Start services**:
   ```bash
   # Start NATS
   docker-compose up nats -d

   # Start SpaceBridge API
   python -m spacebridge.server
   ```

### Creating a Test Flow

#### Via API

```bash
# 1. Create an AI Model configuration
curl -X POST http://localhost:8000/api/v1/ai-models \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-4 for Flows",
    "provider_name": "openai",
    "model_identifier": "gpt-4",
    "api_key": "YOUR_OPENAI_API_KEY"
  }'

# 2. Create a Flow
curl -X POST http://localhost:8000/api/v1/flows \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Flow",
    "description": "Test flow for debugging",
    "trigger_event_source": "github",
    "trigger_event_type": "push",
    "trigger_config": {"branch": "main"},
    "prompt_template": "Analyze this commit: {{trigger_event.payload.commit.message}}",
    "ai_model_id": "AI_MODEL_UUID",
    "agent_type": "openhands",
    "agent_config": {
      "agent_type": "CodeActAgent",
      "max_iterations": 10
    },
    "allowed_mcp_servers": ["spacebridge-mcp"],
    "allowed_mcp_tools": [
      {"server_name": "spacebridge-mcp", "tool_name": "search_issues"},
      {"server_name": "spacebridge-mcp", "tool_name": "get_issue"}
    ],
    "is_enabled": true
  }'
```

### Triggering a Flow

#### Option 1: Via Webhook Event

```bash
# Simulate a GitHub push event
curl -X POST http://localhost:8000/api/v1/private/webhooks/github/YOUR_ORG \
  -H "X-GitHub-Event: push" \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "refs/heads/main",
    "commits": [{
      "id": "abc123",
      "message": "Fix authentication bug",
      "author": {
        "email": "dev@example.com"
      }
    }]
  }'
```

#### Option 2: Via Direct Flow Execution (for testing)

```python
# test_flow_execution.py
import asyncio
from sqlalchemy.orm import Session
from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator
from spacesync.services.event_bus import get_nats_client

async def test_flow():
    # Get DB session
    db = get_db_session()

    # Trigger event data
    event_data = {
        "source": "github",
        "type": "push",
        "account_id": "YOUR_ACCOUNT_ID",
        "payload": {
            "commit": {
                "sha": "abc123",
                "message": "Fix authentication bug"
            }
        }
    }

    # Get NATS client
    nats_client = await get_nats_client()

    # Create and run orchestrator
    orchestrator = FlowExecutionOrchestrator(
        db=db,
        flow_id="YOUR_FLOW_UUID",
        trigger_event_data=event_data,
        nats_client=nats_client
    )

    await orchestrator.run()

asyncio.run(test_flow())
```

### Inspecting Running Containers

#### Using the Inspection Script

```bash
# List all flow execution containers
python scripts/inspect_flow_containers.py --list

# Get logs from a specific container
python scripts/inspect_flow_containers.py --logs CONTAINER_ID --tail 200

# Full inspection of a container
python scripts/inspect_flow_containers.py --inspect CONTAINER_ID

# JSON output
python scripts/inspect_flow_containers.py --list --json
```

#### Using Docker CLI

```bash
# List all SpaceBridge agent containers
docker ps --filter "label=spacebridge.agent_type"

# Get logs from a container
docker logs -f CONTAINER_ID

# Inspect a container
docker inspect CONTAINER_ID

# Enter a running container (for debugging)
docker exec -it CONTAINER_ID /bin/bash
```

### Monitoring Flow Executions

#### Via Database

```sql
-- List recent flow executions
SELECT
    fe.id,
    fe.flow_id,
    fe.status,
    fe.start_time,
    fe.end_time,
    fe.agent_session_reference,
    f.name as flow_name
FROM flow_execution fe
JOIN flow f ON f.id = fe.flow_id
ORDER BY fe.start_time DESC
LIMIT 10;

-- Get execution details with logs
SELECT
    id,
    status,
    resolved_input_prompt,
    model_output_summary,
    actions_taken_summary,
    mcp_usage_logs,
    error_message
FROM flow_execution
WHERE id = 'EXECUTION_UUID';
```

#### Via API

```bash
# List flow executions
curl http://localhost:8000/api/v1/flows/FLOW_ID/executions \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get specific execution details
curl http://localhost:8000/api/v1/flow-executions/EXECUTION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get execution logs
curl http://localhost:8000/api/v1/flow-executions/EXECUTION_ID/logs \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Real-Time Updates via WebSocket

```javascript
// Connect to WebSocket for real-time flow updates
const ws = new WebSocket('ws://localhost:8000/ws/flow-executions/EXECUTION_ID');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Update:', message);

  // Message types:
  // - status_update: Flow status changed
  // - log: Agent log output
  // - tool_call: MCP tool called
  // - agent_status: Agent status update
};
```

### Integration Tests

Run the integration test suite:

```bash
# Run all integration tests
pytest tests/integration/test_flow_execution.py -v

# Run specific test
pytest tests/integration/test_flow_execution.py::TestFlowExecution::test_flow_trigger_from_event -v

# Run with logging
pytest tests/integration/test_flow_execution.py -v -s
```

### Debugging Common Issues

#### 1. Container not starting

```bash
# Check Docker daemon
docker ps

# Check image availability
docker images | grep openhands

# Pull image manually
docker pull ghcr.io/all-hands-ai/openhands:latest

# Check container logs
docker logs CONTAINER_ID
```

#### 2. MCP authentication failing

- Verify account API token is set correctly
- Check `SPACEBRIDGE_API_TOKEN` environment variable in container
- Verify token has necessary permissions

```bash
# Test MCP endpoint directly
curl http://localhost:8000/api/v1/mcp/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

#### 3. Prompt resolution issues

```python
# Test prompt resolution manually
from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator

orchestrator = FlowExecutionOrchestrator(...)
resolved = await orchestrator._resolve_prompt()
print(f"Resolved prompt: {resolved}")
```

#### 4. Agent execution hangs

- Check agent logs for errors
- Verify AI model API key is valid
- Check resource limits (CPU, memory)
- Ensure network connectivity to LLM APIs

```bash
# Check container resource usage
docker stats CONTAINER_ID

# Check container network
docker exec CONTAINER_ID ping -c 3 api.openai.com
```

### Performance Testing

```bash
# Test with multiple concurrent flows
python scripts/load_test_flows.py --flows 5 --duration 60

# Monitor system resources
docker stats

# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

### Security Considerations

1. **API Tokens**: Each flow execution uses the account's API token for SpaceBridge MCP access
2. **Container Isolation**: Agents run in isolated Docker containers with resource limits
3. **Network Access**: Configure `AGENT_NETWORK_MODE` appropriately for production
4. **MCP Restrictions**: Only allowed MCP servers and tools can be accessed
5. **AI Model Keys**: Store securely, consider using OpenBAO for production

### Cleanup

```bash
# Stop all flow containers
docker ps --filter "label=spacebridge.agent_type" -q | xargs docker stop

# Remove stopped containers
docker ps -a --filter "label=spacebridge.agent_type" -q | xargs docker rm

# Clean up executions (via API)
curl -X DELETE http://localhost:8000/api/v1/flow-executions/cleanup \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"older_than_days": 7}'
```
