# Unified WebSocket Services

This directory contains the unified WebSocket infrastructure for Preloop Console.

## Overview

The unified WebSocket system provides:
- **Single persistent connection** that survives page navigation
- **Automatic reconnection** with exponential backoff
- **Pub/sub message routing** for clean component integration
- **Activity tracking** for user behavior analytics
- **Support for authenticated and anonymous users**

## Components

### UnifiedWebSocketManager

Main WebSocket connection manager that handles the lifecycle of the connection.

```typescript
import { unifiedWebSocketManager, ConnectionState } from './unified-websocket-manager';

// Connect (automatically called in main.ts)
await unifiedWebSocketManager.connect();

// Subscribe to messages
const unsubscribe = unifiedWebSocketManager.subscribe(
  'flow_executions',
  (message) => {
    console.log('Flow execution update:', message);
  },
  (message) => message.execution_id === 'some-id' // Optional filter
);

// Send messages
unifiedWebSocketManager.send({
  type: 'command',
  command: 'stop',
  execution_id: 'some-id'
});

// Monitor connection state
unifiedWebSocketManager.onStateChange((state: ConnectionState) => {
  console.log('Connection state:', state);
});

// Cleanup
unsubscribe();
```

### MessageRouter

Pub/sub router that distributes messages to interested subscribers based on topics.

**Available Topics:**
- `flow_executions` - Flow execution updates (status_update, agent_log_line, execution_completed, etc.)
- `approvals` - Approval request updates (approval_*)
- `activity` - Activity updates (for admin dashboard)
- `system` - System messages (ping, pong, handshake)
- `*` - Wildcard topic (receives all messages)

```typescript
import { unifiedWebSocketManager } from './unified-websocket-manager';

// Subscribe to all flow execution messages
const unsubscribe = unifiedWebSocketManager.subscribe(
  'flow_executions',
  (message) => {
    // Handle message
  }
);

// Subscribe to specific execution
const unsubscribe2 = unifiedWebSocketManager.subscribe(
  'flow_executions',
  (message) => {
    console.log('Execution update:', message);
  },
  (message) => message.execution_id === this.executionId // Filter
);
```

### ActivityTracker

Tracks user activity and sends it through the WebSocket connection.

```typescript
import { activityTracker } from './activity-tracker';

// Track page view (automatically tracked on route change)
activityTracker.trackPageView('/console/flows');

// Track user action
activityTracker.trackAction('create_flow', {
  flow_name: 'My Flow',
  trigger_type: 'manual'
});

// Track conversion
activityTracker.trackConversion('subscription_started', 29.99);

// Automatic tracking with data attributes
// <button data-track="signup_button">Sign Up</button>
// <form data-track-form="login_form">...</form>
activityTracker.initializeAutoTracking(); // Called in main.ts
```

## Usage in Lit Components

### Example: Dashboard View

```typescript
import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { unifiedWebSocketManager } from '../services/unified-websocket-manager';

@customElement('dashboard-view')
export class DashboardView extends LitElement {
  @state()
  private executions: any[] = [];

  private unsubscribe?: () => void;

  connectedCallback() {
    super.connectedCallback();

    // Subscribe to flow execution updates
    this.unsubscribe = unifiedWebSocketManager.subscribe(
      'flow_executions',
      (message) => {
        if (message.type === 'execution_started') {
          // Add new execution to list
          this.executions = [...this.executions, message];
        }
      },
      // Optional: filter for specific types
      (message) => message.type === 'execution_started'
    );
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    // Unsubscribe when component unmounts
    this.unsubscribe?.();
  }

  render() {
    return html`
      <div>
        <h2>Recent Executions</h2>
        ${this.executions.map(exec => html`
          <div>${exec.execution_id}</div>
        `)}
      </div>
    `;
  }
}
```

### Example: Flow Execution View

```typescript
import { LitElement, html } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unifiedWebSocketManager } from '../services/unified-websocket-manager';
import { activityTracker } from '../services/activity-tracker';

@customElement('flow-execution-view')
export class FlowExecutionView extends LitElement {
  @property() executionId?: string;
  @state() private logs: string[] = [];

  private unsubscribe?: () => void;

  connectedCallback() {
    super.connectedCallback();

    // Subscribe to specific execution updates
    this.unsubscribe = unifiedWebSocketManager.subscribe(
      'flow_executions',
      (message) => {
        if (message.type === 'agent_log_line') {
          this.logs = [...this.logs, message.line];
        }
      },
      (message) => message.execution_id === this.executionId
    );

    // Track that user viewed this execution
    activityTracker.trackAction('view_execution', {
      execution_id: this.executionId
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribe?.();
  }

  private async stopExecution() {
    // Send stop command through unified connection
    unifiedWebSocketManager.send({
      type: 'command',
      target: 'flow_execution',
      execution_id: this.executionId,
      command: 'stop'
    });

    // Track action
    activityTracker.trackAction('stop_execution', {
      execution_id: this.executionId
    });
  }

  render() {
    return html`
      <div>
        <h2>Execution: ${this.executionId}</h2>
        <button @click=${this.stopExecution}>Stop</button>
        <div class="logs">
          ${this.logs.map(log => html`<div>${log}</div>`)}
        </div>
      </div>
    `;
  }
}
```

## Migration from Old WebSocket Service

If you're migrating from the old `webSocketService`:

### Before:
```typescript
import { webSocketService } from './services/websocket-service';

webSocketService.connectToFlowUpdates((message) => {
  // Handle message
});
```

### After:
```typescript
import { unifiedWebSocketManager } from './services/unified-websocket-manager';

const unsubscribe = unifiedWebSocketManager.subscribe(
  'flow_executions',
  (message) => {
    // Handle message
  }
);

// Don't forget to unsubscribe!
unsubscribe();
```

## Key Differences

1. **No manual connect/disconnect per component** - Connection is managed globally
2. **Automatic reconnection** - No need to handle reconnection logic
3. **Subscription-based** - Use subscribe/unsubscribe pattern instead of callbacks
4. **Connection survives navigation** - WebSocket stays open across page changes
5. **Activity tracking built-in** - Automatic page view and action tracking

## Benefits

- **Reduced connection overhead** - One connection instead of many
- **Better user experience** - Real-time updates work consistently across all views
- **Improved reliability** - Automatic reconnection with exponential backoff
- **Better analytics** - Built-in activity tracking for user behavior
- **Cleaner code** - Pub/sub pattern simplifies message handling
