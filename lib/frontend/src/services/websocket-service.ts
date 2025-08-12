class WebSocketService {
  private ws?: WebSocket;
  private onMessageCallback?: (message: any) => void;
  private heartbeatInterval?: number;

  connect(url: string, onMessageCallback: (message: any) => void) {
    this.ws = new WebSocket(url);
    this.onMessageCallback = onMessageCallback;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message === 'ping') {
        this.ws?.send('pong');
        return;
      }
      if (this.onMessageCallback) {
        this.onMessageCallback(message);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.stopHeartbeat();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  private startHeartbeat() {
    this.heartbeatInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('pong'); // Respond to keep-alive
      }
    }, 30000); // 30 seconds
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected. Cannot send data.');
    }
  }
}

export const webSocketService = new WebSocketService();
