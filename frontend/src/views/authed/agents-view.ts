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
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
import '@shoelace-style/shoelace/dist/components/tab-panel/tab-panel.js';
import '@shoelace-style/shoelace/dist/components/copy-button/copy-button.js';
import '../../components/view-header.ts';
import {
  getAccountAgents,
  removeAccountAgent,
  getAccountGatewayUsageSummary,
  getFlows,
  getFlowExecutions,
  getAIModels,
  type ManagedAgentListParams,
} from '../../api';
import type {
  AccountManagedAgentListResponse,
  ManagedAgentSummary,
  AccountGatewayUsageSummaryResponse,
  AIModel,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import { renderAgentIcon } from '../../utils/agent-icons';

@customElement('agents-view')
export class AgentsView extends LitElement {
  @state() private agents: AccountManagedAgentListResponse | null = null;
  @state() private loading = true;
  @state() private error: string | null = null;
  @state() private searchQuery = '';
  @state() private agentKinds: string[] = ['all'];
  @state() private lastSeenAfter = 'all';
  @state() private flows: any[] = [];
  @state() private aiModels: AIModel[] = [];

  @state() private actionAgentId: string | null = null;
  @state() private liveActivity: Record<
    string,
    {
      modelCalls: number;
      toolCalls: number;
      lastActivityAt: string | null;
      lastMessagePreview?: string;
      lastMessageSource?: string;
      currentBubble?: { text: string; source: string; timestamp: number };
      messageQueue?: { text: string; source: string; timestamp: number }[];
      processTimeoutId?: any;
    }
  > = {};

  @state() private gatewaySummary: AccountGatewayUsageSummaryResponse | null =
    null;

  @state() private showOnboardingDialog = false;
  // Used to track agents count from the last fetch to detect new registrations
  private previousAgentCount = -1;

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
  private resizeObserver = new ResizeObserver(() => this.resetView());

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
        padding: 1rem 1rem 0 2rem;
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
      @media (prefers-color-scheme: dark) {
        .flow-icon {
          filter: invert(0.8) hue-rotate(180deg);
        }
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
      .agent-speech-bubble.tool-bubble {
        background: var(--sl-color-neutral-100);
        color: var(--sl-color-neutral-800);
        border: 1px solid var(--sl-color-neutral-300);
        box-shadow: 0 4px 12px rgba(var(--sl-color-warning-500-rgb), 0.15);
      }
      .agent-speech-bubble.tool-bubble::after {
        border-color: var(--sl-color-neutral-300) transparent transparent
          transparent;
      }
      .agent-speech-bubble.tool-bubble .speech-source {
        color: var(--sl-color-warning-600);
      }

      /* Canvas specific styles */
      .content-bounds {
        width: 100%;
        max-width: 80rem;
        margin: 0 auto;
        padding: 1rem 1rem 0 2rem;
        box-sizing: border-box;
      }
      .page-canvas-wrapper .content-bounds {
        /* Any overrides for canvas wrapper */
      }
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
        position: absolute;
        top: calc(100% + 12px);
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
        width: max-content;
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

    // Restore saved view preference
    const savedView = localStorage.getItem('preloop.agents.view_mode');
    if (savedView === 'cards' || savedView === 'canvas') {
      this.currentView = savedView;
    }

    // Restore saved node positions
    try {
      const savedPositions = localStorage.getItem(
        'preloop.agents.canvas_positions'
      );
      if (savedPositions) {
        this.nodePositions = JSON.parse(savedPositions);
      }
    } catch (e) {
      console.warn('Failed to parse saved canvas positions', e);
    }

    void this.loadAgents();
    this.connectRealtime();
    requestAnimationFrame(() => {
      this.resizeObserver.observe(this);
    });
  }

  updated(changedProperties: Map<string, unknown>) {
    super.updated?.(changedProperties);
    if (changedProperties.has('currentView')) {
      this.dispatchEvent(
        new CustomEvent('request-full-bleed', {
          detail: this.currentView === 'canvas',
          bubbles: true,
          composed: true,
        })
      );
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribeRealtime?.();
    this.resizeObserver.disconnect();
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  onBeforeLeave() {
    this.dispatchEvent(
      new CustomEvent('request-full-bleed', {
        detail: false,
        bubbles: true,
        composed: true,
      })
    );
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
      limit: 50,
    };

    // If 'all' is selected, clear agentKind param for backend. If specific kinds are selected, send comma separated.
    const selectedAgentKinds = this.agentKinds.includes('all')
      ? []
      : this.agentKinds.filter((k) => k !== 'flows');
    if (selectedAgentKinds.length > 0) {
      params.agentKind = selectedAgentKinds.join(',');
    } else if (!this.agentKinds.includes('all')) {
      params.agentKind = '__none__'; // Send a dummy value so no agents match this request
    }
    // We handle the 'flows' display separately in frontend if not 'all'
    const includeFlows =
      this.agentKinds.includes('all') || this.agentKinds.includes('flows');

    if (this.lastSeenAfter !== 'all') {
      const now = Date.now();
      let ms = 0;
      switch (this.lastSeenAfter) {
        case 'last_10_minutes':
          ms = 10 * 60 * 1000;
          break;
        case 'last_1_hour':
          ms = 60 * 60 * 1000;
          break;
        case 'last_24_hours':
          ms = 24 * 60 * 60 * 1000;
          break;
        case 'last_7_days':
          ms = 7 * 24 * 60 * 60 * 1000;
          break;
      }
      if (ms > 0) {
        params.lastSeenAfter = new Date(now - ms).toISOString();
      }
    }

    let queryPart = this.searchQuery.trim();
    if (queryPart) {
      const tags: Record<string, string> = {};
      let ownerUsername: string | undefined;

      const tagRegex = /tags?:([\w-]+(?:=[\w-]+)?)/g;
      const ownerRegex = /owner:([\w.-]+)/g;

      let match;
      while ((match = tagRegex.exec(queryPart)) !== null) {
        const parts = match[1].split('=');
        tags[parts[0]] = parts[1] || 'true';
      }
      queryPart = queryPart.replace(tagRegex, '').trim();

      while ((match = ownerRegex.exec(queryPart)) !== null) {
        ownerUsername = match[1];
      }
      queryPart = queryPart.replace(ownerRegex, '').trim();

      if (queryPart) params.query = queryPart;
      if (Object.keys(tags).length > 0) params.tags = JSON.stringify(tags);
      if (ownerUsername) params.ownerUsername = ownerUsername;
    }

    try {
      // Parallel fetch
      const [agentsData, gatewayData, flowsData, modelsData] =
        await Promise.all([
          getAccountAgents(params),
          getAccountGatewayUsageSummary(),
          getFlows(),
          getAIModels().catch(() => [] as AIModel[]),
        ]);

      // Handle custom local empty case for dummy filter
      if (params.agentKind === '__none__') {
        agentsData.items = [];
        agentsData.total = 0;
      }

      // Check if a new agent was registered while the dialog is open
      if (
        this.showOnboardingDialog &&
        this.previousAgentCount !== -1 &&
        agentsData.items.length > this.previousAgentCount
      ) {
        this.showOnboardingDialog = false;

        // Show success toast
        const alertEl = Object.assign(document.createElement('sl-alert'), {
          variant: 'success',
          duration: 4000,
          closable: true,
          innerHTML: `<sl-icon slot="icon" name="check2-circle"></sl-icon> <strong>Success</strong><br>A new agent was successfully registered!`,
        });
        document.body.append(alertEl);
        alertEl.toast();
      }

      const shouldForceReset =
        this.previousAgentCount !== -1 &&
        agentsData.items.length !== this.previousAgentCount;

      this.agents = agentsData;
      this.previousAgentCount = agentsData.items.length;
      this.gatewaySummary = gatewayData;

      // Filter flows locally if lastSeenAfter is set (since backend getFlows doesn't support it)
      let activeFlows = includeFlows
        ? Array.isArray(flowsData)
          ? flowsData
          : (flowsData as any).items || []
        : [];
      if (this.lastSeenAfter !== 'all') {
        const now = Date.now();
        let ms = 0;
        switch (this.lastSeenAfter) {
          case 'last_10_minutes':
            ms = 10 * 60 * 1000;
            break;
          case 'last_1_hour':
            ms = 60 * 60 * 1000;
            break;
          case 'last_24_hours':
            ms = 24 * 60 * 60 * 1000;
            break;
          case 'last_7_days':
            ms = 7 * 24 * 60 * 60 * 1000;
            break;
        }
        this.flows = activeFlows.filter((f: any) => {
          const t = new Date(
            f.execution_stats?.last_seen_at || f.created_at
          ).getTime();
          return now - t <= ms;
        });
      } else {
        this.flows = activeFlows;
      }

      this.initializeNodePositions(shouldForceReset);
    } catch (error) {
      console.error('Failed to load managed agents or gateway summary:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load managed agents or gateway summary';
    } finally {
      this.loading = false;
    }
  }

  private initializeNodePositions(forceReset = false) {
    if (!this.agents) return;
    const items = [...(this.agents?.items || []), ...this.flows];
    let didChange = false;
    let newPositions = forceReset ? {} : { ...this.nodePositions };

    const unpositionedAgents = items.filter((a) => !newPositions[a.id]);

    // If nothing to position and not forcing reset, do nothing
    if (!forceReset && unpositionedAgents.length === 0) {
      return;
    }

    didChange = true;
    const isFirstTime = Object.keys(newPositions).length === 0;

    if ((forceReset || isFirstTime) && items.length > 3) {
      // Polygon layout around the center (0,0)
      newPositions = {};

      const viewport = this.shadowRoot?.querySelector('.canvas-viewport');
      const bounds = viewport
        ? viewport.getBoundingClientRect()
        : { width: window.innerWidth, height: window.innerHeight };

      // Calculate a radius that pushes items to the edges of the screen comfortably
      const maxRadiusX = Math.max(100, bounds.width / 2 - 200);
      const maxRadiusY = Math.max(100, bounds.height / 2 - 160);
      const adaptiveRadius = Math.min(maxRadiusX, maxRadiusY);

      const radius = Math.max(adaptiveRadius, items.length * 60);
      const angleStep = (2 * Math.PI) / items.length;

      items.forEach((agent, i) => {
        // Start from top (-90 degrees) and distribute evenly
        const angle = -Math.PI / 2 + i * angleStep;
        newPositions[agent.id] = {
          x: Math.round(Math.cos(angle) * radius),
          y: Math.round(Math.sin(angle) * radius),
        };
      });
    } else {
      // Legacy corner/layer-based layout for <= 3 agents,
      // or for appending a new agent without resetting existing layout
      const directions = [
        { x: -1, y: -1 }, // Top Left
        { x: 1, y: -1 }, // Top Right
        { x: -1, y: 1 }, // Bottom Left
        { x: 1, y: 1 }, // Bottom Right
      ];

      // Build a set of taken coordinate strings to avoid exact overlaps
      const takenCoords = new Set(
        Object.values(newPositions).map((p) => `${p.x},${p.y}`)
      );

      let nextSlotIndex = 0;
      items.forEach((agent) => {
        if (!newPositions[agent.id]) {
          let found = false;
          while (!found) {
            const layer = Math.floor(nextSlotIndex / 4);
            const posPos = nextSlotIndex % 4;
            const dir = directions[posPos];

            // base distance 250, increase by 200 per layer
            const distance = 250 + layer * 200;
            const x = dir.x * distance;
            const y = dir.y * distance;
            const coord = `${x},${y}`;

            if (!takenCoords.has(coord)) {
              newPositions[agent.id] = { x, y };
              takenCoords.add(coord);
              found = true;
            }
            nextSlotIndex++;
          }
        }
      });
    }

    if (didChange) {
      localStorage.setItem(
        'preloop.agents.canvas_positions',
        JSON.stringify(newPositions)
      );
      this.animateNodePositions(newPositions);
    }
  }

  private animatePositionFrameId: number | null = null;

  private animateNodePositions(
    targetPositions: Record<string, { x: number; y: number }>
  ) {
    if (this.animatePositionFrameId) {
      cancelAnimationFrame(this.animatePositionFrameId);
    }

    const startPositions = { ...this.nodePositions };
    const startTime = performance.now();
    const duration = 600;

    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

    const animate = (time: number) => {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = easeOutCubic(progress);

      const currentPositions: Record<string, { x: number; y: number }> = {};
      let allDone = progress >= 1;

      for (const id in targetPositions) {
        const start = startPositions[id] || { x: 0, y: 0 };
        const target = targetPositions[id];
        currentPositions[id] = {
          x: start.x + (target.x - start.x) * ease,
          y: start.y + (target.y - start.y) * ease,
        };
      }

      this.nodePositions = currentPositions;

      if (!allDone) {
        this.animatePositionFrameId = requestAnimationFrame(animate);
      } else {
        this.animatePositionFrameId = null;
        this.nodePositions = targetPositions; // ensure exact final values
      }
    };

    this.animatePositionFrameId = requestAnimationFrame(animate);
  }

  private handleSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery = target.value;

    // Add debounce for search query filtering
    if ((this as any)._searchTimeout)
      clearTimeout((this as any)._searchTimeout);
    (this as any)._searchTimeout = setTimeout(() => {
      void this.loadAgents();
    }, 400);
  }

  private handleSearchSubmit(event: Event): void {
    event.preventDefault();
    void this.loadAgents();
  }

  private handleAgentKindChange(kind: string, checked: boolean): void {
    if (kind === 'all') {
      this.agentKinds = checked ? ['all'] : [];
    } else {
      let updated = [...this.agentKinds].filter((k) => k !== 'all');
      if (checked) {
        if (!updated.includes(kind)) updated.push(kind);
      } else {
        updated = updated.filter((k) => k !== kind);
      }
      this.agentKinds = updated.length === 0 ? ['all'] : updated;
    }

    void this.loadAgents();
  }

  private handleLastSeenAfterChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.lastSeenAfter = target.value || 'all';
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
      case 'gemini_cli':
        return 'Gemini CLI';
      case 'opencode':
        return 'OpenCode';
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
    if (agent.onboarding_state === 'mcp_proxy_only') return 'MCP only';
    if (agent.onboarding_state === 'gateway_only') return 'Gateway only';
    return 'Incomplete';
  }

  private getOnboardingDescription(agent: ManagedAgentSummary): string {
    if (agent.total_requests > 0) return '';
    if (agent.onboarding_state === 'fully_onboarded') {
      return 'Tool calls and model traffic both flow through Preloop.';
    }
    if (agent.onboarding_state === 'mcp_proxy_only') {
      return 'Tool calls flow through Preloop, but model traffic is still direct.';
    }
    if (agent.onboarding_state === 'gateway_only') {
      return 'Model traffic flows through Preloop, but MCP tool traffic is still direct.';
    }
    return 'This agent is not fully managed by Preloop yet.';
  }

  private isMcpConfigured(agent: ManagedAgentSummary): boolean {
    return !!agent.mcp_proxy_configured;
  }

  private isModelConfigured(agent: ManagedAgentSummary): boolean {
    return !!agent.model_gateway_configured;
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

  private extractPreviewFromRequest(
    request: any
  ): { text: string; source: string } | null {
    console.log(
      '[Canvas] extractPreviewFromRequest parsing API JSON Payload',
      request
    );
    let text = '';

    const messages = request.messages || request.input || [];
    if (Array.isArray(messages) && messages.length > 0) {
      const lastItem: any = messages[messages.length - 1];
      if (lastItem.role === 'assistant' && Array.isArray(lastItem.content)) {
        const toolUsePart = lastItem.content.find(
          (part: any) => part.type === 'tool_use' || part.type === 'tool_call'
        );
        if (toolUsePart) {
          console.log(
            '[Canvas] extractPreviewFromRequest found tool use:',
            toolUsePart.name
          );
          return { text: `Running: ${toolUsePart.name}`, source: 'Tool' };
        }
      }

      // Find the last non-assistant message or just the last message
      const userMsg = [...messages]
        .reverse()
        .find((m: any) => m.role === 'user');
      const lastMsg: any = userMsg || lastItem;
      if (lastMsg.content) {
        if (Array.isArray(lastMsg.content)) {
          const textPart = lastMsg.content.find(
            (part: any) => part.type === 'text' || part.type === 'input_text'
          );
          text = textPart ? textPart.text : JSON.stringify(lastMsg.content);
        } else if (typeof lastMsg.content === 'string') {
          text = lastMsg.content;
        } else {
          text = JSON.stringify(lastMsg.content);
        }
      }
    } else if (request.prompt) {
      text =
        typeof request.prompt === 'string'
          ? request.prompt
          : JSON.stringify(request.prompt);
    }

    if (text) {
      console.log(
        '[Canvas] extractPreviewFromRequest resolving bubble display:',
        text.substring(0, 50) + '...'
      );
      return { text: text.substring(0, 300), source: 'User' };
    }
    return null;
  }

  private enqueueBubble(agentId: string, text: string, source: string) {
    if (!text || !text.trim()) return;

    const state = this.liveActivity[agentId] || {
      modelCalls: 0,
      toolCalls: 0,
      lastActivityAt: null,
    };

    const isVisible =
      state.currentBubble && Date.now() - state.currentBubble.timestamp < 6000;
    const isDuplicate =
      (isVisible && state.currentBubble?.text === text) ||
      state.messageQueue?.some((b: any) => b.text === text);
    if (isDuplicate) return;

    const bubble = { text, source, timestamp: Date.now() };

    const nextState = {
      ...state,
      messageQueue: [...(state.messageQueue || []), bubble],
    };
    this.liveActivity = { ...this.liveActivity, [agentId]: nextState };

    this.processBubbleQueue(agentId);
  }

  private processBubbleQueue(agentId: string) {
    const state = this.liveActivity[agentId];
    if (!state) return;

    if (
      state.currentBubble &&
      Date.now() - state.currentBubble.timestamp < 2400
    ) {
      if ((state.messageQueue || []).length > 0 && !state.processTimeoutId) {
        const timeoutId = setTimeout(() => {
          this.liveActivity[agentId].processTimeoutId = null;
          this.processBubbleQueue(agentId);
        }, 2500);
        this.liveActivity = {
          ...this.liveActivity,
          [agentId]: { ...state, processTimeoutId: timeoutId as any },
        };
      }
      return;
    }

    const queue = state.messageQueue || [];
    if (queue.length > 0) {
      const nextBubble = { ...queue[0], timestamp: Date.now() };
      const nextState = {
        ...state,
        currentBubble: nextBubble,
        messageQueue: queue.slice(1),
        processTimeoutId: null,
      };

      // Set the next state
      this.liveActivity = { ...this.liveActivity, [agentId]: nextState };

      // Schedule clearing/next item
      const timeoutId = setTimeout(() => {
        this.liveActivity[agentId].processTimeoutId = null;
        this.processBubbleQueue(agentId);
      }, 2500);
      this.liveActivity[agentId].processTimeoutId = timeoutId as any;

      setTimeout(() => this.requestUpdate(), 6000);
    }
  }

  private handleGatewayActivity(message: any): void {
    const payload = message?.payload ?? {};
    const type = message?.type;

    console.log(`[Canvas/Dashboard] Raw Event received: ${type}`, message);

    let agentId = payload.managed_agent_id || payload.flow_id;
    const sessionId =
      payload.session_id ||
      payload.runtime_session_id ||
      message.runtime_session_id;

    if (!agentId && payload.execution_id) {
      const flowExec = this.flows.find(
        (f: any) => f.id === payload.flow_id || f.id === payload.execution_id
      );
      if (flowExec) agentId = flowExec.id;
    }
    if (!agentId && sessionId) {
      const agentWithSession = (this.agents?.items || []).find(
        (a: any) => a.runtime_session_id === sessionId
      );
      if (agentWithSession) agentId = agentWithSession.id;
    }

    if (!agentId) {
      console.log(
        '[Canvas] Cannot resolve agentId for event. managed: ',
        payload.managed_agent_id,
        ' session: ',
        sessionId
      );
      return;
    }

    let preview: { text: string; source: string } | undefined = undefined;

    if (type === 'model_gateway_request_started' && payload.request) {
      preview = this.extractPreviewFromRequest(payload.request) || undefined;
    } else if (type === 'model_gateway_call_started' && payload.request) {
      preview = this.extractPreviewFromRequest(payload.request) || undefined;
    } else if (type === 'flow_execution_started') {
      preview = {
        text: payload.resolved_input_prompt || 'User triggered flow...',
        source: 'User',
      };
    } else if (
      (type === 'model_gateway_call' ||
        type === 'model_gateway_call_completed') &&
      payload.conversation_preview?.messages?.length > 0
    ) {
      const messages = payload.conversation_preview.messages;
      const last = messages[messages.length - 1];
      preview = {
        text: last.text || '(No text)',
        source: last.source === 'request' ? 'Agent' : 'AI Model',
      };
    } else if (
      (payload.messages &&
        Array.isArray(payload.messages) &&
        payload.messages.length > 0) ||
      (payload.input &&
        Array.isArray(payload.input) &&
        payload.input.length > 0)
    ) {
      preview = this.extractPreviewFromRequest(payload) || undefined;
    } else if (
      type === 'mcp_call' ||
      type === 'mcp_call_started' ||
      type === 'tool_execution_started' ||
      type === 'mcp_tool_call' ||
      type === 'mcp_gateway_call_started' ||
      type === 'mcp_gateway_call' ||
      (type && (type.includes('tool') || type.includes('mcp')))
    ) {
      const toolName =
        payload.tool_name || payload.name || payload.action || 'Tool';
      const serverName = payload.server_name ? payload.server_name + '/' : '';
      const status = payload.status === 'failed' ? 'Failed: ' : 'Running: ';
      preview = {
        text: `${status}${serverName}${toolName}`,
        source: 'Tool',
      };
    }

    if (preview) {
      this.enqueueBubble(agentId, preview.text, preview.source);
    }

    const previous = this.liveActivity[agentId] ?? {
      modelCalls: 0,
      toolCalls: 0,
      lastActivityAt: null,
    };

    const current = this.liveActivity[agentId] ?? previous;
    const t = type || '';
    const isModelCall =
      t.includes('model_gateway_call') || preview?.source === 'AI Model';
    const isToolCall =
      t.includes('mcp') || t.includes('tool') || preview?.source === 'Tool';

    const next = {
      ...current,
      modelCalls: previous.modelCalls + (isModelCall ? 1 : 0),
      toolCalls: previous.toolCalls + (isToolCall ? 1 : 0),
      lastActivityAt:
        payload.timestamp ??
        payload.last_activity_at ??
        previous.lastActivityAt ??
        new Date().toISOString(),
      lastMessagePreview: preview?.text ?? previous.lastMessagePreview,
      lastMessageSource: preview?.source ?? previous.lastMessageSource,
    };

    this.liveActivity = { ...this.liveActivity, [agentId]: next };
    this.agents = {
      ...(this.agents as any),
      items: this.agents!.items.map((agent) =>
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
    const items = [...(this.agents?.items || []), ...this.flows];
    const bounds = this.shadowRoot
      ?.querySelector('.canvas-viewport')
      ?.getBoundingClientRect();

    if (!bounds || bounds.width === 0) {
      this.scale = 1;
      this.translateX = bounds ? bounds.width / 2 : window.innerWidth / 2;
      this.translateY = bounds ? bounds.height / 2 : window.innerHeight / 2;
      return;
    }

    if (items.length === 0) {
      this.scale = 1;
      this.translateX = bounds.width / 2;
      this.translateY = bounds.height / 2;
      return;
    }

    // Force recalculation of node positions based on the algorithm
    this.initializeNodePositions(true);

    // Find bounding box of all nodes
    let minX = 0,
      maxX = 0,
      minY = 0,
      maxY = 0;
    items.forEach((agent) => {
      const pos = this.nodePositions[agent.id];
      if (pos) {
        minX = Math.min(minX, pos.x);
        maxX = Math.max(maxX, pos.x);
        minY = Math.min(minY, pos.y);
        maxY = Math.max(maxY, pos.y);
      }
    });

    // Add padding for node dimensions (width ~250px, height ~150px) and visual padding
    minX -= 180;
    maxX += 180;
    minY -= 150;
    maxY += 150;

    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;

    // Determine scale to fit
    const scaleX = bounds.width / contentWidth;
    const scaleY = bounds.height / contentHeight;
    let targetScale = Math.min(scaleX, scaleY, 1); // Cap maximum zoom at 1x

    // Ensure minimum reasonable zoom
    targetScale = Math.max(targetScale, 0.2);

    this.scale = targetScale;

    // Center the bounding box in the viewport
    const contentCenterX = (minX + maxX) / 2;
    const contentCenterY = (minY + maxY) / 2;

    this.translateX = bounds.width / 2 - contentCenterX * targetScale;
    this.translateY = bounds.height / 2 - contentCenterY * targetScale;
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
        const isFlow = this.flows.some((f: any) => f.id === id);
        if (isFlow) {
          Router.go(`/console/flows/${encodeURIComponent(id)}`);
        } else {
          Router.go(`/console/agents/${encodeURIComponent(id)}`);
        }
      } else {
        localStorage.setItem(
          'preloop.agents.canvas_positions',
          JSON.stringify(this.nodePositions)
        );
      }
    }
  }

  private setCurrentView(view: 'cards' | 'canvas') {
    this.currentView = view;
    localStorage.setItem('preloop.agents.view_mode', view);
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
            <div style="display: flex; gap: 12px; align-items: flex-start;">
              ${renderAgentIcon(
                agent.agent_kind || agent.session_source_type,
                'font-size: 24px; color: var(--sl-color-neutral-500); margin-top: 2px;'
              )}
              <div>
                <div class="agent-name">${agent.display_name}</div>
                <div class="agent-meta">
                  ${this.getSourceLabel(
                    agent.agent_kind || agent.session_source_type
                  )}
                  · ${agent.session_source_id}
                </div>
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

          ${(agent as any)?.ai_model_id ||
          (agent as any)?.configured_model_alias ||
          (agent as any)?.latest_model_alias
            ? html`
                <div
                  style="font-size: 0.85rem; color: var(--sl-color-neutral-700); margin-bottom: 8px; display: flex; align-items: center; gap: 6px;"
                >
                  <sl-icon
                    name="cpu"
                    style="color: var(--sl-color-primary-500);"
                  ></sl-icon>
                  <strong>Model:</strong>
                  <a
                    href="/console/settings/ai-models/${encodeURIComponent(
                      (agent as any).ai_model_id ||
                        (agent as any).configured_model_id ||
                        'unknown'
                    )}"
                    style="color: inherit; text-decoration: underline; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px;"
                    @pointerdown="${(e: Event) => e.stopPropagation()}"
                  >
                    ${(() => {
                      const mId = (agent as any).ai_model_id;
                      if (mId) {
                        const model = this.aiModels.find((m) => m.id === mId);
                        if (model && model.name) return model.name;
                      }
                      return (
                        (agent as any).ai_model_name ||
                        (agent as any).configured_model_alias ||
                        (agent as any).latest_model_alias ||
                        mId
                      );
                    })()}
                  </a>
                </div>
              `
            : ''}
          ${agent.owner_username
            ? html`
                <div
                  style="font-size: 0.85rem; color: var(--sl-color-neutral-700); margin-bottom: 8px; display: flex; align-items: center; gap: 6px;"
                >
                  <sl-icon
                    name="person-circle"
                    style="color: var(--sl-color-primary-500);"
                  ></sl-icon>
                  <strong>Owner:</strong> ${agent.owner_username}
                </div>
              `
            : ''}
          ${agent.tags && Object.keys(agent.tags).length > 0
            ? html`
                <div
                  style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;"
                >
                  ${Object.entries(agent.tags).map(
                    ([k, v]) => html`
                      <sl-badge
                        variant="neutral"
                        pill
                        style="font-weight: normal; max-width: 100%; overflow: hidden; text-overflow: ellipsis;"
                      >
                        <span style="opacity: 0.7">${k}</span>${v &&
                        v !== 'true'
                          ? html`<span style="opacity: 0.4; margin: 0 4px;"
                                >=</span
                              >${v}`
                          : ''}
                      </sl-badge>
                    `
                  )}
                </div>
              `
            : ''}

          <div
            style="font-size: 0.85rem; color: var(--sl-color-neutral-600); margin-bottom: 12px;"
          >
            ${this.getOnboardingDescription(agent)}
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
      <div class="canvas-container">
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
          style="position: absolute; left: 20px; bottom: 20px; z-index: 20; background: color-mix(in srgb, var(--sl-panel-background-color) 92%, transparent); border: 1px solid var(--sl-color-neutral-200); border-radius: var(--sl-border-radius-medium); padding: 10px 12px; font-size: 0.8rem; color: var(--sl-color-neutral-700); display: flex; gap: 16px;"
        >
          <div style="display: flex; align-items: center; gap: 8px;">
            <span
              style="display: inline-block; width: 20px; height: 0; border-top: 2px solid var(--sl-color-primary-500);"
            ></span>
            <span>Model traffic</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span
              style="display: inline-block; width: 20px; height: 0; border-top: 2px dashed var(--sl-color-warning-500);"
            ></span>
            <span>Tool traffic</span>
          </div>
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
                  (v) =>
                    v.lastActivityAt &&
                    Date.now() - new Date(v.lastActivityAt).getTime() < 2000
                )
                  ? 'pulsing'
                  : ''}"
              >
                <sl-icon
                  src="/assets/preloop-badge.svg"
                  style="margin-left: -5px;margin-bottom: -4px;"
                ></sl-icon>
              </div>
              <div class="gateway-label" style="text-align: center;">
                <div>PRELOOP GATEWAY</div>
                ${this.gatewaySummary
                  ? html`
                      <div
                        style="font-size: 0.75rem; color: var(--sl-color-primary-500); margin-top: 4px; font-weight: 500; font-family: monospace;"
                      >
                        ${this.gatewaySummary.token_usage.total_tokens.toLocaleString()}
                        Tokens ·
                        ${this.gatewaySummary.requests_by_day?.length > 0
                          ? (
                              this.gatewaySummary.token_usage.total_tokens /
                              this.gatewaySummary.requests_by_day.length
                            ).toFixed(0)
                          : '0'}
                        / day
                      </div>
                    `
                  : ''}
              </div>
            </div>

            ${[...(this.agents?.items || []), ...this.flows].map(
              (item: any) => {
                const isFlow =
                  'flow_status' in item ||
                  ('name' in item && !('display_name' in item));
                const agent = isFlow ? null : (item as ManagedAgentSummary);
                const flowName = isFlow ? item.name : '';
                const flowNode = isFlow ? (item as any) : null;
                const liveExecs = isFlow
                  ? item.execution_stats?.running_execs || 0
                  : 0;
                const totalExecs = isFlow
                  ? item.execution_stats?.total_execs || 0
                  : 0;
                const totalSpend = isFlow ? 0 : 0; // Not available easily anymore, omit for now.
                const lastSeenFlow = isFlow
                  ? item.execution_stats?.last_seen_at
                  : null;

                const pos = this.nodePositions[item.id] || { x: 250, y: 250 };
                const liveActivity = this.liveActivity[item.id];
                const liveTotal = liveActivity
                  ? liveActivity.modelCalls + liveActivity.toolCalls
                  : 0;
                const mcpEnabled = isFlow
                  ? true
                  : this.isMcpConfigured(agent as any);
                const modelEnabled = isFlow
                  ? true
                  : this.isModelConfigured(agent as any);
                const modelActive = !!(
                  liveActivity?.modelCalls &&
                  liveActivity?.lastActivityAt &&
                  Date.now() - new Date(liveActivity.lastActivityAt).getTime() <
                    2000
                );
                const toolActive = !!(
                  liveActivity?.toolCalls &&
                  liveActivity?.lastActivityAt &&
                  Date.now() - new Date(liveActivity.lastActivityAt).getTime() <
                    2000
                );
                const isGlowing =
                  liveTotal > 0 &&
                  liveActivity &&
                  Date.now() -
                    new Date(liveActivity.lastActivityAt || 0).getTime() <
                    2000;
                const distance = Math.max(
                  Math.sqrt(pos.x * pos.x + pos.y * pos.y),
                  1
                );
                const offsetX = (-pos.y / distance) * 8;
                const offsetY = (pos.x / distance) * 8;

                return html`
                  <svg
                    class="connection-line ${this.draggingNodeId === item.id
                      ? 'dragging'
                      : ''}"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <line
                      x1="${offsetX}"
                      y1="${offsetY}"
                      x2="${pos.x + offsetX}"
                      y2="${pos.y + offsetY}"
                      stroke="${isFlow
                        ? 'var(--sl-color-primary-500)'
                        : modelEnabled
                          ? modelActive
                            ? 'var(--sl-color-success-500)'
                            : 'var(--sl-color-primary-500)'
                          : 'var(--sl-color-neutral-300)'}"
                      stroke-width="${isFlow
                        ? '2'
                        : modelActive
                          ? '3'
                          : modelEnabled
                            ? '2'
                            : '1.25'}"
                      stroke-dasharray="${modelEnabled ? '0' : '6 6'}"
                      opacity="${modelEnabled ? '1' : '0.55'}"
                    />
                    <line
                      x1="${-offsetX}"
                      y1="${-offsetY}"
                      x2="${pos.x - offsetX}"
                      y2="${pos.y - offsetY}"
                      stroke="${mcpEnabled
                        ? toolActive
                          ? 'var(--sl-color-warning-300)'
                          : 'var(--sl-color-warning-500)'
                        : 'var(--sl-color-neutral-300)'}"
                      stroke-width="${toolActive
                        ? '3'
                        : mcpEnabled
                          ? '2'
                          : '1.25'}"
                      stroke-dasharray="${mcpEnabled ? '5 4' : '6 6'}"
                      opacity="${mcpEnabled ? '1' : '0.55'}"
                    />
                  </svg>

                  <div
                    class="agent-node ${this.draggingNodeId === item.id
                      ? 'dragging'
                      : ''}"
                    style=${styleMap({ left: `${pos.x}px`, top: `${pos.y}px` })}
                    @pointerdown=${(e: PointerEvent) =>
                      this.handleNodePointerDown(e, item.id)}
                    @pointermove=${(e: PointerEvent) =>
                      this.handleNodePointerMove(e, item.id)}
                    @pointerup=${(e: PointerEvent) =>
                      this.handleNodePointerUp(e, item.id)}
                    @pointercancel=${(e: PointerEvent) =>
                      this.handleNodePointerUp(e, item.id)}
                  >
                    ${html`
                      <div
                        class="agent-speech-bubble ${liveActivity?.currentBubble &&
                        Date.now() - liveActivity.currentBubble.timestamp < 6000
                          ? 'visible'
                          : ''} ${liveActivity?.currentBubble?.source === 'Tool'
                          ? 'tool-bubble'
                          : ''}"
                      >
                        <div class="speech-source">
                          ${liveActivity?.currentBubble?.source || 'Agent'}
                        </div>
                        <div class="speech-text">
                          ${liveActivity?.currentBubble?.text || ''}
                        </div>
                      </div>
                      <sl-card>
                        <div
                          slot="header"
                          style="display: flex; justify-content: space-between; align-items: center;"
                        >
                          <div
                            style="display: flex; gap: 8px; overflow: hidden;"
                          >
                            ${isFlow
                              ? html`<img
                                  src="/images/flow.svg"
                                  class="flow-icon"
                                  style="width: 20px; height: 20px; flex-shrink: 0;"
                                  alt="Flow"
                                />`
                              : renderAgentIcon(
                                  agent?.agent_kind ||
                                    agent?.session_source_type,
                                  'flex-shrink: 0; color: var(--sl-color-neutral-500); width: 20px; height: 20px;'
                                )}
                            <strong
                              style="font-size: 1rem; word-break: break-word; line-height: 1.2;"
                              >${isFlow
                                ? flowName
                                : agent?.display_name}</strong
                            >
                          </div>
                          ${liveTotal > 0
                            ? html`<sl-badge variant="success" pulse
                                >Live</sl-badge
                              >`
                            : agent?.activity_status === 'active_now' || isFlow
                              ? html`<sl-badge variant="success"
                                  >Active</sl-badge
                                >`
                              : ''}
                        </div>
                        <div
                          style="font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-500); margin-bottom: 8px; word-break: break-all;"
                        >
                          ${isFlow
                            ? html`<span title="Description"
                                >${flowNode?.description || ''}</span
                              >`
                            : agent?.session_source_id}
                        </div>
                        ${!isFlow && agent?.owner_username
                          ? html` <div
                              style="font-size: 0.75rem; color: var(--sl-color-neutral-600); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;"
                            >
                              <sl-icon
                                name="person-circle"
                                style="color: var(--sl-color-primary-500);"
                              ></sl-icon>
                              ${agent.owner_username}
                            </div>`
                          : ''}
                        ${isFlow && flowNode?.agent_type
                          ? html` <div
                              style="font-size: 0.75rem; color: var(--sl-color-neutral-600); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;"
                            >
                              ${renderAgentIcon(
                                flowNode.agent_type,
                                'color: var(--sl-color-primary-500); width: 14px; height: 14px;'
                              )}
                              ${flowNode.agent_type}
                            </div>`
                          : ''}
                        ${!isFlow && (agent as any)?.ai_model_id
                          ? html` <div
                              style="font-size: 0.75rem; color: var(--sl-color-neutral-600); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;"
                            >
                              <sl-icon
                                name="cpu"
                                style="color: var(--sl-color-primary-500);"
                              ></sl-icon>
                              <a
                                href="/console/settings/ai-models/${encodeURIComponent(
                                  (agent as any).ai_model_id
                                )}"
                                style="max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: inherit; text-decoration: underline;"
                                @click=${(e: Event) => e.stopPropagation()}
                                >${(agent as any).ai_model_id}</a
                              >
                            </div>`
                          : ''}
                        ${isFlow && flowNode?.ai_model_id
                          ? html` <div
                              style="font-size: 0.75rem; color: var(--sl-color-neutral-600); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;"
                            >
                              <sl-icon
                                name="cpu"
                                style="color: var(--sl-color-primary-500);"
                              ></sl-icon>
                              <a
                                href="/console/settings/ai-models/${encodeURIComponent(
                                  flowNode.ai_model_id
                                )}"
                                style="max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: inherit; text-decoration: underline;"
                                @click=${(e: Event) => e.stopPropagation()}
                                >${flowNode.ai_model_id}</a
                              >
                            </div>`
                          : ''}
                        ${!isFlow &&
                        agent?.tags &&
                        Object.keys(agent.tags).length > 0
                          ? html` <div
                              style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;"
                            >
                              ${Object.entries(agent.tags)
                                .slice(0, 3)
                                .map(
                                  ([k, v]) => html`
                                    <div
                                      style="font-size: 0.65rem; background: var(--sl-color-neutral-100); padding: 2px 6px; border-radius: 10px; color: var(--sl-color-neutral-700); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                                    >
                                      <span style="opacity: 0.7">${k}</span
                                      >${v && v !== 'true'
                                        ? html`<span
                                              style="opacity: 0.4; margin: 0 2px;"
                                              >=</span
                                            >${v}`
                                        : ''}
                                    </div>
                                  `
                                )}
                              ${Object.keys(agent.tags).length > 3
                                ? html`<div
                                    style="font-size: 0.65rem; padding: 2px;"
                                  >
                                    +${Object.keys(agent.tags).length - 3}
                                  </div>`
                                : ''}
                            </div>`
                          : ''}
                        ${!isFlow && agent
                          ? html` <div
                              style="font-size: 0.78rem; color: var(--sl-color-neutral-600); margin-bottom: 8px;"
                            >
                              ${this.getOnboardingDescription(agent)}
                            </div>`
                          : ''}
                        <div
                          style="display: flex; justify-content: space-between; margin-top: 12px; font-size: 0.85rem; border-top: 1px solid var(--sl-color-neutral-200); padding-top: 8px;"
                        >
                          <div style="display: flex; flex-direction: column;">
                            <span
                              style="opacity: 0.7; font-size: 0.75rem; text-transform: uppercase;"
                              >${isFlow ? 'Execs' : 'Reqs'}</span
                            >
                            <strong
                              >${isFlow
                                ? totalExecs
                                : agent?.total_requests}</strong
                            >
                          </div>
                          <div
                            style="display: flex; flex-direction: column; text-align: center;"
                          >
                            <span
                              style="opacity: 0.7; font-size: 0.75rem; text-transform: uppercase;"
                              >Spend</span
                            >
                            <strong
                              >${this.formatMoney(
                                isFlow ? totalSpend : agent?.estimated_cost || 0
                              )}</strong
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
                                  (isFlow
                                    ? lastSeenFlow
                                    : agent?.last_seen_at) ||
                                  0
                              ).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}</span
                            >
                          </div>
                        </div>
                      </sl-card>
                    `}
                  </div>
                `;
              }
            )}
          </div>
        </div>
      </div>
    `;
  }

  private renderOnboardingDialog() {
    return html`
      <sl-dialog
        label="Onboard Agents"
        ?open=${this.showOnboardingDialog}
        @sl-after-hide=${() => (this.showOnboardingDialog = false)}
        style="--width: 650px;"
      >
        <sl-tab-group>
          <sl-tab slot="nav" panel="cli">CLI SETUP</sl-tab>
          <sl-tab slot="nav" panel="openclaw">OpenClaw Plugin</sl-tab>
          <sl-tab slot="nav" panel="manual">Manual</sl-tab>

          <sl-tab-panel name="cli">
            <div style="padding: var(--sl-spacing-large) 0 0 0;">
              <div style="margin-bottom: var(--sl-spacing-medium);">
                The Preloop CLI is the fastest way to register local agents.
              </div>
              <ol style="line-height: 2; margin: 0; padding-left: 20px;">
                <li>
                  <strong>Install CLI:</strong> Follow documentation to install
                  the Preloop CLI.
                </li>
                <li>
                  <strong>Authenticate:</strong> Run
                  <code
                    style="background: var(--sl-color-neutral-100); padding: 2px 6px; border-radius: 4px;"
                    >preloop login</code
                  >
                  <sl-copy-button value="preloop login"></sl-copy-button>
                </li>
                <li>
                  <strong>Discover Agents:</strong> Run
                  <code
                    style="background: var(--sl-color-neutral-100); padding: 2px 6px; border-radius: 4px;"
                    >preloop agents discover</code
                  >
                  <sl-copy-button
                    value="preloop agents discover"
                  ></sl-copy-button>
                </li>
              </ol>
            </div>
          </sl-tab-panel>

          <sl-tab-panel name="openclaw">
            <div style="padding: var(--sl-spacing-large) 0 0 0;">
              <div style="margin-bottom: var(--sl-spacing-medium);">
                For users of OpenClaw, use the native plugin for smooth
                integration.
              </div>
              <ol style="line-height: 2; margin: 0; padding-left: 20px;">
                <li>
                  <strong>Install Preloop Plugin:</strong> Find and install the
                  Preloop Plugin for OpenClaw.
                </li>
                <li>
                  <strong>Authenticate:</strong> Use the plugin interface to log
                  in to Preloop.
                </li>
                <li>
                  <strong>Complete Onboarding:</strong> Follow the on-screen
                  flow to finish setup.
                </li>
              </ol>
            </div>
          </sl-tab-panel>

          <sl-tab-panel name="manual">
            <div style="padding: var(--sl-spacing-large) 0 0 0;">
              <ol style="line-height: 1.8; margin: 0; padding-left: 20px;">
                <li style="margin-bottom: 8px;">
                  Provide instructions on how to edit the configuration based on
                  your specific agent framework.
                </li>
                <li style="margin-bottom: 8px;">
                  Add your configured AI models and desired MCP servers to
                  Preloop.
                </li>
                <li style="margin-bottom: 8px;">
                  Create an Agent-Specific Preloop API key.
                </li>
                <li>
                  Reconfigure your agent to use the AI model through the Preloop
                  gateway, and tools through the Preloop MCP proxy (or Preloop
                  CLI).
                </li>
              </ol>
            </div>
          </sl-tab-panel>
        </sl-tab-group>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${() => (this.showOnboardingDialog = false)}
        >
          Close
        </sl-button>
      </sl-dialog>
    `;
  }

  render() {
    return html`
      <div
        class="page ${this.currentView === 'canvas'
          ? 'page-canvas-wrapper'
          : ''}"
      >
        ${this.renderOnboardingDialog()}
        <div class="content-bounds">
          <div
            class="header"
            style="display: flex; flex-wrap: wrap; gap: var(--sl-spacing-medium); align-items: flex-start; justify-content: space-between; margin-bottom: var(--sl-spacing-large);"
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
            <sl-button
              variant="primary"
              @click=${() => (this.showOnboardingDialog = true)}
            >
              <sl-icon slot="prefix" name="plus"></sl-icon>
              Onboard agents
            </sl-button>
          </div>

          <div
            style="display: flex; flex-direction: column; gap: var(--sl-spacing-medium);"
          >
            <div style="display: flex; justify-content: flex-end; width: 100%;">
              <!-- View Switcher -->
              <sl-radio-group
                value=${this.currentView}
                @sl-change=${(e: any) => this.setCurrentView(e.target.value)}
                size="small"
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
                placeholder="Search name, tags:env=prod, owner:username"
                clearable
                .value=${this.searchQuery}
                @sl-input=${this.handleSearchInput}
              >
                <sl-icon name="search" slot="prefix"></sl-icon>
              </sl-input>

              <sl-dropdown stay-open-on-select>
                <sl-button slot="trigger" caret variant="default">
                  Agent Kinds
                  (${this.agentKinds.length === 1 &&
                  this.agentKinds[0] === 'all'
                    ? 'All'
                    : this.agentKinds.length})
                </sl-button>
                <div
                  style="padding: var(--sl-spacing-medium); background: var(--sl-panel-background-color); border: solid 1px var(--sl-panel-border-color); border-radius: var(--sl-border-radius-medium); box-shadow: var(--sl-shadow-large); display: flex; flex-direction: column; gap: var(--sl-spacing-small); min-width: 200px;"
                >
                  ${[
                    { value: 'all', label: 'All Agents' },
                    { value: 'flows', label: 'Flows' },
                    { value: 'openclaw', label: 'OpenClaw' },
                    { value: 'opencode', label: 'OpenCode' },
                    { value: 'claude_code', label: 'Claude Code' },
                    { value: 'codex', label: 'Codex CLI' },
                    { value: 'gemini_cli', label: 'Gemini CLI' },
                    { value: 'cursor', label: 'Cursor' },
                    { value: 'windsurf', label: 'Windsurf' },
                  ].map(
                    (kind) => html`
                      <sl-checkbox
                        .checked=${this.agentKinds.includes(kind.value)}
                        @sl-change=${(e: any) =>
                          this.handleAgentKindChange(
                            kind.value,
                            e.target.checked
                          )}
                      >
                        ${kind.label}
                      </sl-checkbox>
                    `
                  )}
                </div>
              </sl-dropdown>

              <sl-select
                value=${this.lastSeenAfter}
                @sl-change=${this.handleLastSeenAfterChange}
              >
                <sl-option value="all">All Time</sl-option>
                <sl-option value="last_10_minutes">Last 10 minutes</sl-option>
                <sl-option value="last_1_hour">Last 1 hour</sl-option>
                <sl-option value="last_24_hours">Last 24 hours</sl-option>
                <sl-option value="last_7_days">Last 7 days</sl-option>
              </sl-select>
            </form>
          </div>

          ${this.error
            ? html`<sl-alert open variant="danger" class="mx-6 mb-4"
                >${this.error}</sl-alert
              >`
            : null}
        </div>
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
