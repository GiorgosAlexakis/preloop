import { LitElement, css, html, unsafeCSS } from 'lit';
import { Router } from '@vaadin/router';
import { styleMap } from 'lit/directives/style-map.js';
import { customElement, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio-button/radio-button.js';
import '../../components/view-header.ts';
import {
  getAccountAgents,
  removeAccountAgent,
  type ManagedAgentListParams,
} from '../../api';
import type {
  AccountManagedAgentListResponse,
  ManagedAgentSummary,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';

@customElement('agents-view')
export class AgentsView extends LitElement {
  @state() private agents: AccountManagedAgentListResponse | null = null;
  @state() private loading = true;
  @state() private error: string | null = null;
  @state() private searchQuery = '';
  @state() private sessionSourceType = 'all';
  @state() private status = 'all';
  @state() private actionAgentId: string | null = null;
  @state() private liveActivity: Record<
    string,
    {
      modelCalls: number;
      toolCalls: number;
      lastActivityAt: string | null;
      lastMessagePreview?: string;
      lastMessageSource?: string;
    }
  > = {};

  // Switcher state
  @state() private currentView: 'cards' | 'canvas' = 'canvas';

  // Canvas Viewport State
  @state() private scale = 1;
  @state() private translateX = 0;
  @state() private translateY = 0;

  // Node Dragging State
  @state() private nodePositions: Record<string, { x: number; y: number }> = {};
  private draggingNodeId: string | null = null;
  private nodeStartX = 0;
  private nodeStartY = 0;
  private dragHasMoved = false;

  // Viewport Dragging State
  private isDragging = false;
  private startX = 0;
  private startY = 0;
  private initialPinchDistance = 0;
  private initialPinchScale = 1;
  private activePointers = new Map<number, PointerEvent>();

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
        height: 100%;
      }
      .page {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
        height: 100%;
        overflow-y: auto;
      }
      .filters {
        display: flex;
        gap: var(--sl-spacing-medium);
        flex-wrap: wrap;
        align-items: end;
      }
      .filters sl-input,
      .filters sl-select {
        min-width: 180px;
      }
      .filters sl-input {
        flex: 1 1 280px;
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: var(--sl-spacing-large);
        padding: 0 24px 24px 24px;
      }
      .agent-card::part(base) {
        height: 100%;
      }
      .agent-card {
        max-width: 400px;
      }
      .agent-card.live::part(base) {
        border-color: var(--sl-color-primary-500);
        box-shadow: 0 0 15px rgba(var(--sl-color-primary-500-rgb), 0.2);
      }
      @keyframes glow-pulse {
        0% {
          box-shadow: 0 0 25px 5px rgba(var(--sl-color-success-500-rgb), 0.6);
          border-color: var(--sl-color-success-500);
        }
        100% {
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          border-color: var(--sl-color-neutral-200);
        }
      }
      .agent-card.glowing::part(base) {
        animation: glow-pulse 1.5s ease-out;
      }
      .card-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
      }
      .title-row,
      .metric-row,
      .action-row {
        display: flex;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        align-items: center;
      }
      .title-row {
        align-items: start;
        border-bottom: 1px solid var(--sl-color-neutral-200);
        padding-bottom: var(--sl-spacing-small);
      }
      .agent-name {
        font-weight: 700;
        font-size: 1.15rem;
        letter-spacing: -0.01em;
      }
      .agent-meta {
        opacity: 0.7;
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-3x-small);
        overflow-wrap: anywhere;
      }
      .label {
        opacity: 0.7;
        font-size: 0.85rem;
        font-weight: 500;
      }
      .value {
        font-weight: 600;
        font-size: 0.95rem;
        text-align: right;
      }
      .action-row {
        border-top: 1px solid var(--sl-color-neutral-200);
        padding-top: var(--sl-spacing-medium);
        margin-top: var(--sl-spacing-small);
      }
      .empty-state {
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-large);
        color: var(--sl-color-neutral-600);
        background: var(--sl-color-neutral-0);
      }
      :host(:host-context(.sl-theme-dark)) .title-row,
      :host(:host-context(.sl-theme-dark)) .action-row {
        border-color: var(--sl-color-neutral-800);
      }

      .agent-speech-bubble {
        position: absolute;
        bottom: calc(100% + 12px);
        left: 50%;
        transform: translateX(-50%);
        background: var(--sl-color-neutral-900);
        color: var(--sl-color-neutral-0);
        padding: 8px 12px;
        border-radius: var(--sl-border-radius-medium);
        font-size: var(--sl-font-size-small);
        width: max-content;
        max-width: 280px;
        box-shadow: var(--sl-shadow-large);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.5s ease;
        z-index: 200;
      }
      .agent-speech-bubble::after {
        content: '';
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: var(--sl-color-neutral-900) transparent transparent
          transparent;
      }
      .agent-speech-bubble.visible {
        opacity: 1;
        animation: bubble-bounce 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
      }
      @keyframes bubble-bounce {
        0% {
          transform: translateX(-50%) translateY(10px) scale(0.9);
          opacity: 0;
        }
        100% {
          transform: translateX(-50%) translateY(0) scale(1);
          opacity: 1;
        }
      }
      .speech-source {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.7;
        margin-bottom: 2px;
      }
      .speech-text {
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        line-height: 1.4;
      }

      /* Canvas specific styles */
      .page-canvas-wrapper {
        display: flex;
        flex-direction: column;
        height: 100%;
        width: 100%;
        position: relative;
        overflow: hidden;
      }
      .canvas-container {
        flex: 1;
        min-height: 500px;
        position: relative;
        overflow: hidden;
        background-color: transparent;
        border-top: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
      }
      .canvas-viewport {
        width: 100%;
        height: 100%;
        touch-action: none;
        user-select: none;
        position: absolute;
        inset: 0;
        cursor: grab;
      }
      .canvas-viewport:active {
        cursor: grabbing;
      }
      .canvas-content {
        position: absolute;
        inset: 0;
        transform-origin: 0 0;
        will-change: transform;
      }
      .gateway-node {
        position: absolute;
        left: 0;
        top: 0;
        transform: translate(-50%, -50%);
        display: flex;
        flex-direction: column;
        align-items: center;
        z-index: 10;
        pointer-events: none;
      }
      .gateway-icon {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background-color: var(--sl-color-primary-600);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 40px;
        box-shadow: var(--sl-shadow-large);
        position: relative;
      }
      .gateway-icon.pulsing::after {
        content: '';
        position: absolute;
        inset: -10px;
        border-radius: 50%;
        border: 2px solid var(--sl-color-primary-500);
        animation: gateway-pulse 2s infinite;
      }
      @keyframes gateway-pulse {
        0% {
          transform: scale(0.8);
          opacity: 0.8;
        }
        100% {
          transform: scale(1.5);
          opacity: 0;
        }
      }
      .gateway-label {
        margin-top: 12px;
        background-color: var(
          --sl-panel-background-color,
          var(--sl-color-neutral-0)
        );
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        color: var(--sl-color-primary-600);
        box-shadow: var(--sl-shadow-medium);
        border: 1px solid var(--sl-color-neutral-200);
        letter-spacing: 1px;
      }
      .agent-node {
        position: absolute;
        transform: translate(-50%, -50%);
        z-index: 5;
        width: 250px;
        touch-action: none;
        cursor: pointer;
      }
      .agent-node.dragging {
        z-index: 100;
        cursor: grabbing;
      }
      .agent-node sl-card {
        width: 100%;
        pointer-events: auto;
        transition:
          transform 0.2s,
          box-shadow 0.2s;
      }
      .agent-node:not(.dragging) sl-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--sl-shadow-large);
      }
      .controls-overlay {
        position: absolute;
        bottom: 24px;
        right: 24px;
        z-index: 20;
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: var(--sl-panel-background-color, var(--sl-color-neutral-0));
        padding: 8px;
        border-radius: var(--sl-border-radius-large);
        box-shadow: var(--sl-shadow-large);
        border: 1px solid var(--sl-color-neutral-200);
      }
      .connection-line {
        position: absolute;
        left: 0;
        top: 0;
        overflow: visible;
        pointer-events: none;
        transform: translate(-50%, -50%);
        width: 1px;
        height: 1px;
      }
      @media (prefers-color-scheme: dark) {
        .canvas-container {
          border-color: var(--sl-color-neutral-800);
        }
        .gateway-label {
          border-color: var(--sl-color-neutral-700);
          color: var(--sl-color-primary-400);
        }
        .controls-overlay {
          border-color: var(--sl-color-neutral-800);
        }
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    void this.loadAgents();
    this.connectRealtime();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribeRealtime?.();
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private connectRealtime(): void {
    const scheduleRefresh = () => this.scheduleRefresh();
    const unsubscribers = [
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('gateway_activity', (message) =>
        this.handleGatewayActivity(message)
      ),
    ];
    this.unsubscribeRealtime = () => {
      for (const unsubscribe of unsubscribers) {
        unsubscribe();
      }
    };
    void unifiedWebSocketManager.connect();
  }

  private scheduleRefresh(): void {
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
    }
    this.refreshTimer = window.setTimeout(() => {
      this.refreshTimer = null;
      void this.loadAgents();
    }, 250);
  }

  private async loadAgents(): Promise<void> {
    this.loading = true;
    this.error = null;

    const params: ManagedAgentListParams = {
      status: this.status as 'all' | 'active' | 'ended',
      limit: 50,
    };
    if (this.searchQuery.trim()) params.query = this.searchQuery.trim();
    if (this.sessionSourceType !== 'all')
      params.sessionSourceType = this.sessionSourceType;

    try {
      this.agents = await getAccountAgents(params);
      this.initializeNodePositions();
    } catch (error) {
      console.error('Failed to load managed agents:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load managed agents';
    } finally {
      this.loading = false;
    }
  }

  private initializeNodePositions() {
    if (!this.agents) return;
    const items = this.agents.items;
    let didChange = false;
    const newPositions = { ...this.nodePositions };

    items.forEach((agent, index) => {
      if (!newPositions[agent.id]) {
        didChange = true;
        const totalNodes = items.length;
        const angle = (index / totalNodes) * Math.PI * 2;
        const baseOrbit = 350;
        const orbitExpander = Math.floor(index / 12) * 200;
        const radius = baseOrbit + orbitExpander;
        newPositions[agent.id] = {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
        };
      }
    });

    if (didChange) {
      this.nodePositions = newPositions;
    }
  }

  private handleSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery = target.value;
  }

  private handleSourceTypeChange(event: CustomEvent): void {
    this.sessionSourceType = event.detail.value || 'all';
    void this.loadAgents();
  }

  private handleStatusChange(event: CustomEvent): void {
    this.status = event.detail.value || 'all';
    void this.loadAgents();
  }

  private handleSearchSubmit(event: Event): void {
    event.preventDefault();
    void this.loadAgents();
  }

  private getSourceLabel(sourceType: string | null | undefined): string {
    switch (sourceType) {
      case 'claude_code':
        return 'Claude Code';
      case 'claude_desktop':
        return 'Claude Desktop';
      case 'codex':
        return 'Codex';
      case 'openclaw':
        return 'OpenClaw';
      case 'desktop_agent':
        return 'Desktop Agent';
      case 'custom':
        return 'Custom Agent';
      default:
        return sourceType || 'Unknown';
    }
  }

  private formatMoney(amount: number | null | undefined): string {
    return `$${(amount || 0).toFixed(2)}`;
  }

  private formatDateTime(value: string | null | undefined): string {
    if (!value) return 'None';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  }

  private getLifecycleVariant(agent: ManagedAgentSummary): string {
    if (agent.lifecycle_state === 'decommissioned') return 'danger';
    if (agent.lifecycle_state === 'suspended') return 'warning';
    if (agent.activity_status === 'active_now') return 'success';
    if (agent.activity_status === 'recently_active') return 'primary';
    if (agent.ended_at) return 'neutral';
    return 'primary';
  }

  private getLifecycleLabel(agent: ManagedAgentSummary): string {
    if (agent.lifecycle_state === 'decommissioned') return 'Decommissioned';
    if (agent.lifecycle_state === 'suspended') return 'Suspended';
    if (agent.activity_status === 'active_now') return 'Active now';
    if (agent.activity_status === 'recently_active') return 'Recently active';
    if (agent.ended_at) return 'Ended';
    return 'Idle';
  }

  private getOnboardingVariant(agent: ManagedAgentSummary): string {
    if (agent.onboarding_state === 'fully_onboarded') return 'success';
    if (agent.onboarding_state === 'mcp_proxy_only') return 'warning';
    if (agent.onboarding_state === 'gateway_only') return 'warning';
    return 'neutral';
  }

  private getOnboardingLabel(agent: ManagedAgentSummary): string {
    if (agent.onboarding_state === 'fully_onboarded') return 'Fully onboarded';
    if (agent.onboarding_state === 'mcp_proxy_only') return 'Proxy only';
    if (agent.onboarding_state === 'gateway_only') return 'Gateway only';
    return 'Incomplete';
  }

  private getLiveValidationVariant(agent: ManagedAgentSummary): string {
    if (!agent.live_validation_supported) return 'neutral';
    if (agent.live_validation_status === 'passed') return 'success';
    if (agent.live_validation_status === 'failed') return 'danger';
    return 'warning';
  }

  private getLiveValidationLabel(agent: ManagedAgentSummary): string {
    if (!agent.live_validation_supported) return 'No live check';
    if (agent.live_validation_status === 'passed') return 'Live validated';
    if (agent.live_validation_status === 'failed') return 'Live check failed';
    return 'Live check pending';
  }

  private handleGatewayActivity(message: any): void {
    const payload = message?.payload ?? {};
    const agentId = payload.managed_agent_id;
    if (!agentId || !this.agents) return;
    const type = message?.type;

    let preview = undefined;
    let source = undefined;
    if (
      type === 'model_gateway_call' &&
      payload.conversation_preview?.messages?.length > 0
    ) {
      const messages = payload.conversation_preview.messages;
      const last = messages[messages.length - 1];
      preview = last.text;
      source = last.source === 'request' ? 'Agent' : 'AI Model';
    }

    const previous = this.liveActivity[agentId] ?? {
      modelCalls: 0,
      toolCalls: 0,
      lastActivityAt: null,
    };
    const next = {
      modelCalls: previous.modelCalls + (type === 'model_gateway_call' ? 1 : 0),
      toolCalls: previous.toolCalls + (type === 'mcp_call' ? 1 : 0),
      lastActivityAt:
        payload.timestamp ??
        payload.last_activity_at ??
        previous.lastActivityAt ??
        new Date().toISOString(),
      lastMessagePreview: preview ?? previous.lastMessagePreview,
      lastMessageSource: source ?? previous.lastMessageSource,
    };
    this.liveActivity = { ...this.liveActivity, [agentId]: next };
    this.agents = {
      ...this.agents,
      items: this.agents.items.map((agent) =>
        agent.id !== agentId
          ? agent
          : {
              ...agent,
              activity_status: 'active_now',
              last_seen_at: next.lastActivityAt ?? agent.last_seen_at,
              last_activity_at: next.lastActivityAt ?? agent.last_activity_at,
              last_request_at:
                type === 'model_gateway_call'
                  ? (next.lastActivityAt ?? agent.last_request_at)
                  : agent.last_request_at,
            }
      ),
    };
  }

  private async removeAgent(agent: ManagedAgentSummary): Promise<void> {
    if (
      !window.confirm(
        `Remove ${agent.display_name} from the managed agents list? This only removes the Preloop registry record.`
      )
    )
      return;
    this.actionAgentId = agent.id;
    try {
      await removeAccountAgent(agent.id);
      await this.loadAgents();
    } catch (error) {
      console.error('Failed to remove managed agent:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to remove managed agent';
    } finally {
      this.actionAgentId = null;
    }
  }

  // --- CANVAS VIEWPORT LOGIC ---
  private handleWheel(e: WheelEvent) {
    if (this.currentView !== 'canvas') return;
    e.preventDefault();
    const zoomSensitivity = 0.001;
    const delta = -e.deltaY * zoomSensitivity;
    this.zoom(delta, e.clientX, e.clientY);
  }

  private zoom(delta: number, clientX: number, clientY: number) {
    const minScale = 0.2;
    const maxScale = 3;
    const newScale = Math.min(
      Math.max(this.scale + this.scale * delta, minScale),
      maxScale
    );

    const bounds = this.shadowRoot
      ?.querySelector('.canvas-viewport')
      ?.getBoundingClientRect();
    if (bounds) {
      const offsetX = clientX - bounds.left;
      const offsetY = clientY - bounds.top;
      this.translateX =
        offsetX - (offsetX - this.translateX) * (newScale / this.scale);
      this.translateY =
        offsetY - (offsetY - this.translateY) * (newScale / this.scale);
    }
    this.scale = newScale;
  }

  private handlePointerDown(e: PointerEvent) {
    this.activePointers.set(e.pointerId, e);
    const canvasViewport = this.shadowRoot?.querySelector(
      '.canvas-viewport'
    ) as HTMLElement;
    if (canvasViewport) {
      canvasViewport.setPointerCapture(e.pointerId);
    }

    if (this.activePointers.size === 1) {
      this.isDragging = false;
      this.startX = e.clientX - this.translateX;
      this.startY = e.clientY - this.translateY;
    } else if (this.activePointers.size === 2) {
      this.isDragging = false;
      const pointers = Array.from(this.activePointers.values());
      this.initialPinchDistance = Math.hypot(
        pointers[0].clientX - pointers[1].clientX,
        pointers[0].clientY - pointers[1].clientY
      );
      this.initialPinchScale = this.scale;
    }
  }

  private handlePointerMove(e: PointerEvent) {
    if (!this.activePointers.has(e.pointerId)) return;
    this.activePointers.set(e.pointerId, e);

    if (this.activePointers.size === 1) {
      if (
        Math.abs(e.clientX - this.startX - this.translateX) > 3 ||
        Math.abs(e.clientY - this.startY - this.translateY) > 3
      ) {
        this.isDragging = true;
      }
      if (this.isDragging) {
        this.translateX = e.clientX - this.startX;
        this.translateY = e.clientY - this.startY;
      }
    } else if (this.activePointers.size === 2) {
      const pointers = Array.from(this.activePointers.values());
      const currentDistance = Math.hypot(
        pointers[0].clientX - pointers[1].clientX,
        pointers[0].clientY - pointers[1].clientY
      );
      const centerX = (pointers[0].clientX + pointers[1].clientX) / 2;
      const centerY = (pointers[0].clientY + pointers[1].clientY) / 2;

      const scaleDelta = currentDistance / this.initialPinchDistance - 1;
      this.scale = this.initialPinchScale;
      this.zoom(scaleDelta, centerX, centerY);

      this.initialPinchDistance = currentDistance;
      this.initialPinchScale = this.scale;
    }
  }

  private handlePointerUp(e: PointerEvent) {
    this.activePointers.delete(e.pointerId);
    if (this.activePointers.size < 2) {
      this.initialPinchDistance = 0;
    }
    if (this.activePointers.size === 1) {
      const remainingPointer = Array.from(this.activePointers.values())[0];
      this.startX = remainingPointer.clientX - this.translateX;
      this.startY = remainingPointer.clientY - this.translateY;
      this.isDragging = true;
    } else if (this.activePointers.size === 0) {
      this.isDragging = false;
    }
    const canvasViewport = this.shadowRoot?.querySelector(
      '.canvas-viewport'
    ) as HTMLElement;
    if (canvasViewport) {
      canvasViewport.releasePointerCapture(e.pointerId);
    }
  }

  private resetView() {
    this.scale = 1;
    const bounds = this.shadowRoot
      ?.querySelector('.canvas-viewport')
      ?.getBoundingClientRect();
    if (bounds) {
      this.translateX = bounds.width / 2;
      this.translateY = bounds.height / 2;
    } else {
      this.translateX = window.innerWidth / 2;
      this.translateY = window.innerHeight / 2;
    }
  }

  firstUpdated() {
    setTimeout(() => {
      this.resetView();
    }, 50);
  }

  // --- NODE DRAG LOGIC ---
  private handleNodePointerDown(e: PointerEvent, id: string) {
    e.stopPropagation(); // prevent canvas drag
    this.draggingNodeId = id;
    this.nodeStartX = e.clientX;
    this.nodeStartY = e.clientY;
    this.dragHasMoved = false;

    const nodeEl = e.currentTarget as HTMLElement;
    nodeEl.setPointerCapture(e.pointerId);
  }

  private handleNodePointerMove(e: PointerEvent, id: string) {
    if (this.draggingNodeId === id) {
      e.stopPropagation();
      const dx = (e.clientX - this.nodeStartX) / this.scale;
      const dy = (e.clientY - this.nodeStartY) / this.scale;

      if (
        Math.abs(e.clientX - this.nodeStartX) > 3 ||
        Math.abs(e.clientY - this.nodeStartY) > 3
      ) {
        this.dragHasMoved = true;
      }

      this.nodeStartX = e.clientX;
      this.nodeStartY = e.clientY;

      const pos = this.nodePositions[id] || { x: 0, y: 0 };
      this.nodePositions = {
        ...this.nodePositions,
        [id]: {
          x: pos.x + dx,
          y: pos.y + dy,
        },
      };
    }
  }

  private handleNodePointerUp(e: PointerEvent, id: string) {
    if (this.draggingNodeId === id) {
      e.stopPropagation();
      this.draggingNodeId = null;
      const nodeEl = e.currentTarget as HTMLElement;
      nodeEl.releasePointerCapture(e.pointerId);

      // If we didn't drag it, it's a click to route.
      if (!this.dragHasMoved) {
        Router.go(`/console/agents/${encodeURIComponent(id)}`);
      }
    }
  }

  // --- RENDERING ---
  private renderAgentCard(agent: ManagedAgentSummary) {
    const detailUrl = `/console/agents/${encodeURIComponent(agent.id)}`;
    const liveActivity = this.liveActivity[agent.id];
    const liveTotal =
      (liveActivity?.modelCalls || 0) + (liveActivity?.toolCalls || 0);

    const isGlowing =
      liveActivity?.lastActivityAt &&
      Date.now() - new Date(liveActivity.lastActivityAt).getTime() < 2000;

    return html`
      <sl-card
        class="agent-card ${liveTotal > 0 ? 'live' : ''} ${isGlowing
          ? 'glowing'
          : ''}"
      >
        <div class="card-stack">
          <div class="title-row">
            <div>
              <div class="agent-name">${agent.display_name}</div>
              <div class="agent-meta">
                ${this.getSourceLabel(agent.session_source_type)} ·
                ${agent.session_source_id}
              </div>
            </div>
            <div class="badges">
              <sl-badge variant="${this.getOnboardingVariant(agent)}"
                >${this.getOnboardingLabel(agent)}</sl-badge
              >
              <sl-badge variant="${this.getLifecycleVariant(agent)}"
                >${this.getLifecycleLabel(agent)}</sl-badge
              >
              <sl-badge variant="${this.getLiveValidationVariant(agent)}"
                >${this.getLiveValidationLabel(agent)}</sl-badge
              >
              ${liveTotal
                ? html`<sl-badge variant="primary">Live ${liveTotal}</sl-badge>`
                : null}
            </div>
          </div>

          ${liveActivity?.lastMessagePreview
            ? html`
                <div
                  style="background: var(--sl-color-neutral-100); padding: 8px 12px; border-radius: var(--sl-border-radius-medium); margin-bottom: 12px; font-size: 0.85rem;"
                >
                  <div
                    style="font-weight: 600; font-size: 0.75rem; text-transform: uppercase; color: var(--sl-color-neutral-500); margin-bottom: 4px;"
                  >
                    Latest from ${liveActivity.lastMessageSource || 'Agent'}
                  </div>
                  <div
                    style="color: var(--sl-color-neutral-800); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;"
                  >
                    ${liveActivity.lastMessagePreview}
                  </div>
                </div>
              `
            : ''}

          <div class="metric-row">
            <span class="label">Preloop MCP Proxy</span>
            <span class="value"
              >${agent.mcp_proxy_configured ? 'Configured' : 'Missing'}</span
            >
          </div>
          <div class="metric-row">
            <span class="label">Preloop Model Gateway</span>
            <span class="value"
              >${agent.model_gateway_configured
                ? 'Configured'
                : 'Missing'}</span
            >
          </div>
          <div class="metric-row">
            <span class="label">Requests</span>
            <span class="value">${agent.total_requests}</span>
          </div>
          <div class="metric-row">
            <span class="label">Estimated Cost</span>
            <span class="value">${this.formatMoney(agent.estimated_cost)}</span>
          </div>
          <div class="metric-row">
            <span class="label">Last Seen</span>
            <span class="value"
              >${this.formatDateTime(
                liveActivity?.lastActivityAt || agent.last_seen_at
              )}</span
            >
          </div>

          <div class="action-row">
            <span class="label">Inspect, rename, or remove</span>
            <div class="badges">
              <sl-button
                size="small"
                variant="danger"
                ?loading=${this.actionAgentId === agent.id}
                @click=${() => this.removeAgent(agent)}
              >
                Remove
              </sl-button>
              <sl-button
                size="small"
                variant="default"
                @click=${() => Router.go(detailUrl)}
                >View Agent</sl-button
              >
            </div>
          </div>
        </div>
      </sl-card>
    `;
  }

  private renderCanvas() {
    return html`
      <div class="canvas-container" style="margin: 0 24px 24px 24px;">
        ${this.loading && !this.agents
          ? html`
              <div
                style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 50; background: var(--sl-panel-background-color); backdrop-filter: blur(4px);"
              >
                <sl-spinner style="font-size: 2rem;"></sl-spinner>
                <div
                  style="margin-top: 16px; font-family: monospace; color: var(--sl-color-neutral-600);"
                >
                  Loading topology data...
                </div>
              </div>
            `
          : ''}

        <div class="controls-overlay">
          <sl-tooltip content="Zoom In" placement="left">
            <sl-button
              size="medium"
              circle
              @click=${() =>
                this.zoom(0.2, window.innerWidth / 2, window.innerHeight / 2)}
            >
              <sl-icon name="plus"></sl-icon>
            </sl-button>
          </sl-tooltip>
          <sl-tooltip content="Reset View" placement="left">
            <sl-button size="medium" circle @click=${this.resetView}>
              <sl-icon name="arrows-collapse"></sl-icon>
            </sl-button>
          </sl-tooltip>
          <sl-tooltip content="Zoom Out" placement="left">
            <sl-button
              size="medium"
              circle
              @click=${() =>
                this.zoom(-0.2, window.innerWidth / 2, window.innerHeight / 2)}
            >
              <sl-icon name="dash"></sl-icon>
            </sl-button>
          </sl-tooltip>
        </div>

        <div
          class="canvas-viewport"
          @wheel=${this.handleWheel}
          @pointerdown=${this.handlePointerDown}
          @pointermove=${this.handlePointerMove}
          @pointerup=${this.handlePointerUp}
          @pointercancel=${this.handlePointerUp}
          @pointerleave=${this.handlePointerUp}
        >
          <div
            style=${styleMap({
              transform: `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`,
            })}
            class="canvas-content"
          >
            <div class="gateway-node">
              <div
                class="gateway-icon ${Object.values(this.liveActivity).some(
                  (v) => v.modelCalls > 0 || v.toolCalls > 0
                )
                  ? 'pulsing'
                  : ''}"
              >
                <sl-icon name="hdd-network"></sl-icon>
              </div>
              <div class="gateway-label">PRELOOP GATEWAY</div>
            </div>

            ${this.agents?.items.map((agent: ManagedAgentSummary) => {
              const pos = this.nodePositions[agent.id] || { x: 0, y: 0 };
              const liveActivity = this.liveActivity[agent.id];
              const liveTotal = liveActivity
                ? liveActivity.modelCalls + liveActivity.toolCalls
                : 0;
              const isGlowing =
                liveTotal > 0 &&
                liveActivity &&
                Date.now() -
                  new Date(liveActivity.lastActivityAt || 0).getTime() <
                  2000;

              return html`
                <svg class="connection-line" xmlns="http://www.w3.org/2000/svg">
                  <line
                    x1="0"
                    y1="0"
                    x2="${pos.x}"
                    y2="${pos.y}"
                    stroke="${isGlowing
                      ? 'var(--sl-color-success-500)'
                      : 'var(--sl-color-neutral-400)'}"
                    stroke-width="${isGlowing ? '3' : '1.5'}"
                    stroke-dasharray="${isGlowing ? '0' : '4 4'}"
                  />
                </svg>

                <div
                  class="agent-node ${this.draggingNodeId === agent.id
                    ? 'dragging'
                    : ''}"
                  style=${styleMap({ left: `${pos.x}px`, top: `${pos.y}px` })}
                  @pointerdown=${(e: PointerEvent) =>
                    this.handleNodePointerDown(e, agent.id)}
                  @pointermove=${(e: PointerEvent) =>
                    this.handleNodePointerMove(e, agent.id)}
                  @pointerup=${(e: PointerEvent) =>
                    this.handleNodePointerUp(e, agent.id)}
                  @pointercancel=${(e: PointerEvent) =>
                    this.handleNodePointerUp(e, agent.id)}
                >
                  <div
                    class="agent-speech-bubble ${liveActivity?.lastMessagePreview &&
                    liveActivity?.lastActivityAt &&
                    Date.now() -
                      new Date(liveActivity.lastActivityAt).getTime() <
                      6000
                      ? 'visible'
                      : ''}"
                  >
                    <div class="speech-source">
                      ${liveActivity?.lastMessageSource || 'Agent'}
                    </div>
                    <div class="speech-text">
                      ${liveActivity?.lastMessagePreview}
                    </div>
                  </div>
                  <sl-card>
                    <div
                      slot="header"
                      style="display: flex; justify-content: space-between; align-items: center;"
                    >
                      <div
                        style="display: flex; align-items: center; gap: 8px; overflow: hidden;"
                      >
                        <sl-icon
                          name="robot"
                          style="flex-shrink: 0; color: var(--sl-color-neutral-500);"
                        ></sl-icon>
                        <strong
                          style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;"
                          >${agent.display_name}</strong
                        >
                      </div>
                      ${liveTotal > 0
                        ? html`<sl-badge variant="success" pulse
                            >Live</sl-badge
                          >`
                        : agent.activity_status === 'active_now'
                          ? html`<sl-badge variant="success">Active</sl-badge>`
                          : ''}
                    </div>
                    <div
                      style="font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-500); margin-bottom: 8px; word-break: break-all;"
                    >
                      ${agent.session_source_id}
                    </div>
                    <div
                      style="display: flex; justify-content: space-between; margin-top: 12px; font-size: 0.85rem; border-top: 1px solid var(--sl-color-neutral-200); padding-top: 8px;"
                    >
                      <div style="display: flex; flex-direction: column;">
                        <span
                          style="opacity: 0.7; font-size: 0.75rem; text-transform: uppercase;"
                          >Reqs</span
                        >
                        <strong>${agent.total_requests}</strong>
                      </div>
                      <div
                        style="display: flex; flex-direction: column; text-align: center;"
                      >
                        <span
                          style="opacity: 0.7; font-size: 0.75rem; text-transform: uppercase;"
                          >Spend</span
                        >
                        <strong
                          >${this.formatMoney(agent.estimated_cost)}</strong
                        >
                      </div>
                      <div
                        style="display: flex; flex-direction: column; text-align: right;"
                      >
                        <span
                          style="opacity: 0.7; font-size: 0.75rem; text-transform: uppercase;"
                          >Last Seen</span
                        >
                        <span style="font-weight: 600;"
                          >${new Date(
                            liveActivity?.lastActivityAt ||
                              agent.last_seen_at ||
                              0
                          ).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}</span
                        >
                      </div>
                    </div>
                  </sl-card>
                </div>
              `;
            })}
          </div>
        </div>
      </div>
    `;
  }

  render() {
    return html`
      <div
        class="page ${this.currentView === 'canvas'
          ? 'page-canvas-wrapper'
          : ''}"
      >
        <div
          class="header"
          style="align-items: flex-end; padding: 1.5rem 1.5rem 0 1.5rem; margin-bottom: 0.5rem; justify-content: start;"
        >
          <div>
            <h1>Agents</h1>
            <div
              style="color: var(--sl-color-neutral-500); font-size: 0.9rem; margin-top: 4px;"
            >
              Connections, telemetry, and live sessions managed by the Preloop
              gateway.
            </div>
          </div>
        </div>

        <div
          class="px-6 mb-4 flex-none"
          style="display: flex; flex-direction: column; gap: var(--sl-spacing-medium); padding: 0 1.5rem;"
        >
          <div style="display: flex; justify-content: flex-end; width: 100%;">
            <!-- View Switcher -->
            <sl-radio-group
              value=${this.currentView}
              @sl-change=${(e: any) => (this.currentView = e.target.value)}
              size="medium"
            >
              <sl-radio-button value="cards" title="Cards View">
                <sl-icon name="grid"></sl-icon>
              </sl-radio-button>
              <sl-radio-button value="canvas" title="Canvas View">
                <sl-icon name="share"></sl-icon>
              </sl-radio-button>
            </sl-radio-group>
          </div>

          <form
            class="filters"
            style="display: flex; gap: var(--sl-spacing-medium); flex-wrap: wrap; align-items: end; width: 100%;"
            @submit=${this.handleSearchSubmit}
          >
            <sl-input
              label="Search"
              placeholder="Search agent name or source id"
              clearable
              .value=${this.searchQuery}
              @sl-input=${this.handleSearchInput}
            >
              <sl-icon name="search" slot="prefix"></sl-icon>
            </sl-input>

            <sl-select
              label="Source"
              value=${this.sessionSourceType}
              @sl-change=${this.handleSourceTypeChange}
            >
              <sl-option value="all">All sources</sl-option>
              <sl-option value="apikey">API Key</sl-option>
              <sl-option value="oauth">OAuth</sl-option>
            </sl-select>

            <sl-select
              label="Status"
              value=${this.status}
              @sl-change=${this.handleStatusChange}
            >
              <sl-option value="all">All</sl-option>
              <sl-option value="active">Active</sl-option>
              <sl-option value="ended">Ended</sl-option>
            </sl-select>
            <sl-button type="submit" variant="default" style="margin-top: auto;"
              >Filter</sl-button
            >
          </form>
        </div>

        ${this.error
          ? html`<sl-alert open variant="danger" class="mx-6"
              >${this.error}</sl-alert
            >`
          : null}
        ${this.currentView === 'canvas'
          ? this.renderCanvas()
          : html`
              <div class="cards">
                ${(!this.agents || this.agents.items.length === 0) &&
                !this.loading
                  ? html`
                      <div class="empty-state">
                        No agents found matching your query.
                      </div>
                    `
                  : this.agents?.items.map((agent) =>
                      this.renderAgentCard(agent)
                    )}
              </div>
            `}
      </div>
    `;
  }
}
