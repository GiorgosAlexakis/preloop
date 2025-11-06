class WebSocketService {
  private connections: Map<string, WebSocket> = new Map();
  private heartbeatIntervals: Map<string, number> = new Map();

  /**
   * Connect to a WebSocket endpoint
   * @param key Unique identifier for this connection
   * @param url WebSocket URL
   * @param onMessageCallback Callback for incoming messages
   * @param onOpenCallback Optional callback when connection opens
   * @param onCloseCallback Optional callback when connection closes
   */
  connect(
    key: string,
    url: string,
    onMessageCallback: (message: any) => void,
    onOpenCallback?: () => void,
    onCloseCallback?: () => void
  ) {
    // Disconnect existing connection if any
    this.disconnect(key);

    const ws = new WebSocket(url);
    this.connections.set(key, ws);

    ws.onopen = () => {
      console.log(`WebSocket connected: ${key}`);
      this.startHeartbeat(key);
      if (onOpenCallback) {
        onOpenCallback();
      }
    };

    ws.onmessage = (event) => {
      if (event.data === 'ping') {
        ws.send('pong');
        return;
      }

      try {
        const message = JSON.parse(event.data);
        onMessageCallback(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      console.log(`WebSocket disconnected: ${key}`);
      this.stopHeartbeat(key);
      this.connections.delete(key);
      if (onCloseCallback) {
        onCloseCallback();
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error (${key}):`, error);
    };
  }

  /**
   * Connect to a flow execution WebSocket for real-time updates
   */
  connectToExecution(
    executionId: string,
    onMessageCallback: (message: any) => void,
    onOpenCallback?: () => void,
    onCloseCallback?: () => void
  ) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;

    // Get access token from localStorage for authentication
    const token = localStorage.getItem('accessToken');
    if (!token) {
      console.error('No access token found for WebSocket connection');
      if (onCloseCallback) {
        onCloseCallback();
      }
      return;
    }

    // Include token as query parameter
    const url = `${protocol}://${host}/api/v1/ws/flow-executions/${executionId}?token=${encodeURIComponent(token)}`;

    this.connect(
      `execution-${executionId}`,
      url,
      onMessageCallback,
      onOpenCallback,
      onCloseCallback
    );
  }

  /**
   * Connect to general WebSocket for all flow updates
   */
  connectToFlowUpdates(
    onMessageCallback: (message: any) => void,
    onOpenCallback?: () => void,
    onCloseCallback?: () => void
  ) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;

    // Get access token from localStorage for authentication
    const token = localStorage.getItem('accessToken');
    if (!token) {
      console.error('No access token found for WebSocket connection');
      if (onCloseCallback) {
        onCloseCallback();
      }
      return;
    }

    // Include token as query parameter
    const url = `${protocol}://${host}/api/v1/ws?token=${encodeURIComponent(token)}`;

    this.connect(
      'flow-updates',
      url,
      onMessageCallback,
      onOpenCallback,
      onCloseCallback
    );
  }

  private startHeartbeat(key: string) {
    const interval = window.setInterval(() => {
      const ws = this.connections.get(key);
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send('pong');
      }
    }, 30000); // 30 seconds

    this.heartbeatIntervals.set(key, interval);
  }

  private stopHeartbeat(key: string) {
    const interval = this.heartbeatIntervals.get(key);
    if (interval) {
      clearInterval(interval);
      this.heartbeatIntervals.delete(key);
    }
  }

  disconnect(key: string) {
    const ws = this.connections.get(key);
    if (ws) {
      ws.close();
      this.connections.delete(key);
    }
    this.stopHeartbeat(key);
  }

  /**
   * Disconnect from execution WebSocket
   */
  disconnectFromExecution(executionId: string) {
    this.disconnect(`execution-${executionId}`);
  }

  /**
   * Disconnect from general flow updates WebSocket
   */
  disconnectFromFlowUpdates() {
    this.disconnect('flow-updates');
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll() {
    for (const key of this.connections.keys()) {
      this.disconnect(key);
    }
  }

  /**
   * Send data to a specific WebSocket connection
   */
  send(key: string, data: any) {
    const ws = this.connections.get(key);
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    } else {
      console.warn(`WebSocket not connected (${key}). Cannot send data.`);
    }
  }

  /**
   * Send command to execution
   */
  sendToExecution(executionId: string, data: any) {
    this.send(`execution-${executionId}`, data);
  }
}

export const webSocketService = new WebSocketService();
