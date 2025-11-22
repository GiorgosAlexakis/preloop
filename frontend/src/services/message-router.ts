/**
 * Message Router with Pub/Sub pattern for WebSocket messages.
 *
 * Allows components to subscribe to specific message topics and
 * automatically routes incoming messages to interested subscribers.
 */

export interface Subscription {
  topic: string;
  filter?: (message: any) => boolean;
  callback: (message: any) => void;
}

export class MessageRouter {
  private subscriptions: Map<string, Set<Subscription>> = new Map();

  /**
   * Subscribe to a specific topic with optional filter.
   *
   * @param topic - Message topic to subscribe to (e.g., 'flow_executions', 'approvals')
   * @param callback - Function called when matching message arrives
   * @param filter - Optional filter function to further refine which messages are delivered
   * @returns Unsubscribe function
   */
  subscribe(
    topic: string,
    callback: (message: any) => void,
    filter?: (message: any) => boolean
  ): () => void {
    const subscription: Subscription = { topic, callback, filter };

    if (!this.subscriptions.has(topic)) {
      this.subscriptions.set(topic, new Set());
    }

    this.subscriptions.get(topic)!.add(subscription);

    // Return unsubscribe function
    return () => {
      this.subscriptions.get(topic)?.delete(subscription);
    };
  }

  /**
   * Route a message to all interested subscribers.
   *
   * @param message - The message to route
   */
  route(message: any): void {
    const topic = this.extractTopic(message);

    if (!topic) {
      console.warn('Message without identifiable topic:', message);
      return;
    }

    // Notify topic-specific subscribers
    const topicSubscribers = this.subscriptions.get(topic) || new Set();
    topicSubscribers.forEach((sub) => {
      if (!sub.filter || sub.filter(message)) {
        try {
          sub.callback(message);
        } catch (error) {
          console.error(
            `Error in subscription callback for topic ${topic}:`,
            error
          );
        }
      }
    });

    // Notify wildcard subscribers (topic: '*')
    const wildcardSubscribers = this.subscriptions.get('*') || new Set();
    wildcardSubscribers.forEach((sub) => {
      if (!sub.filter || sub.filter(message)) {
        try {
          sub.callback(message);
        } catch (error) {
          console.error('Error in wildcard subscription callback:', error);
        }
      }
    });
  }

  /**
   * Extract topic from message based on message type.
   *
   * @param message - Message to extract topic from
   * @returns Topic string or null if unable to determine
   */
  private extractTopic(message: any): string | null {
    const messageType = message.type;

    if (!messageType) {
      return null;
    }

    // Approval-related messages
    if (messageType.startsWith('approval_')) {
      return 'approvals';
    }

    // Flow execution messages
    if (
      messageType === 'execution_started' ||
      messageType === 'status_update' ||
      messageType === 'agent_log_line' ||
      messageType === 'execution_completed' ||
      messageType === 'execution_failed' ||
      messageType === 'tool_call' ||
      messageType === 'mcp_call' ||
      messageType === 'tool_calls_update' ||
      messageType === 'token_usage_update' ||
      messageType === 'budget_update' ||
      messageType === 'model_output' ||
      messageType === 'agent_started' ||
      messageType === 'agent_stopped' ||
      messageType === 'connected'
    ) {
      return 'flow_executions';
    }

    // Activity updates (for admin)
    if (messageType === 'activity_update') {
      return 'activity';
    }

    // System messages
    if (
      messageType === 'ping' ||
      messageType === 'pong' ||
      messageType === 'handshake'
    ) {
      return 'system';
    }

    // Default: use message type as topic
    return messageType;
  }

  /**
   * Get count of active subscriptions for a topic.
   *
   * @param topic - Topic to count subscriptions for
   * @returns Number of active subscriptions
   */
  getSubscriptionCount(topic: string): number {
    return this.subscriptions.get(topic)?.size || 0;
  }

  /**
   * Clear all subscriptions for a topic.
   *
   * @param topic - Topic to clear
   */
  clearTopic(topic: string): void {
    this.subscriptions.delete(topic);
  }

  /**
   * Clear all subscriptions.
   */
  clearAll(): void {
    this.subscriptions.clear();
  }
}
