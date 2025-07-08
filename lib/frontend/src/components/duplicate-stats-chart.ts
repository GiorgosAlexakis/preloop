import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Chart, registerables } from 'chart.js';
import {
  getProjectDuplicateStats,
  ProjectStats,
  DuplicateStatsResponse,
} from '../api';

Chart.register(...registerables);

interface ProjectStats {
  project_id: string;
  project_name: string;
  total: number;
  duplicates: number;
}

interface DuplicateStatsResponse {
  projects: { [key: string]: ProjectStats };
}

@customElement('duplicate-stats-chart')
export class DuplicateStatsChart extends LitElement {
  @property({ type: Array }) projectIds: string[] = [];

  @property({ type: String }) selectedStatus: 'opened' | 'closed' | 'all' =
    'opened';

  @property({ type: Number }) similarityThreshold = 0.8;

  @property({ type: Boolean, reflect: true, attribute: 'no-padding' })
  noPadding = false;

  @property({ type: Boolean }) interactive = false;

  @state()
  private _loading = false;

  @state()
  private _error: string | null = null;

  @state()
  private _statsData: { [key: string]: ProjectStats } | null = null;

  private chart: Chart | null = null;

  static styles = css`
    :host {
      display: block;
      height: 140px;
      padding: var(--sl-spacing-small);
    }

    :host([no-padding]) {
      padding: 0;
    }

    canvas {
      width: 100% !important;
      height: 100% !important;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.fetchData();
  }

  updated(changedProperties: Map<string, any>) {
    if (
      changedProperties.has('projectIds') ||
      changedProperties.has('selectedStatus') ||
      changedProperties.has('similarityThreshold')
    ) {
      this.fetchData();
    }

    // Re-render the chart if the stats data is updated
    if (this._statsData && changedProperties.has('_statsData')) {
      this.renderChart(this._statsData);
    }
  }

  async fetchData() {
    this._loading = true;
    this._error = null;
    this._statsData = null; // Clear previous stats

    try {
      const data = await getProjectDuplicateStats({
        project_ids: this.projectIds,
        status: this.selectedStatus,
        similarity_threshold: this.similarityThreshold,
      });
      // Guard against a missing projects property to prevent crashes
      if (data && data.projects) {
        this._statsData = data.projects;
      } else {
        this._statsData = {}; // Set empty stats to trigger render
      }
    } catch (error) {
      this._error =
        error instanceof Error ? error.message : 'An unknown error occurred.';
      console.error('Failed to fetch duplicate stats:', error);
    } finally {
      this._loading = false;
    }
  }

  renderChart(stats: { [key: string]: ProjectStats }) {
    const sortedStats = Object.values(stats)
      .sort((a, b) => b.duplicates - a.duplicates)
      .slice(0, 5);

    const labels = sortedStats.map((s) => s.project_name);
    const duplicateData = sortedStats.map((s) => s.duplicates);
    const otherData = sortedStats.map((s) => s.total - s.duplicates);

    const canvas = this.shadowRoot?.querySelector('canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const alarmingColor = 'hsl(350, 70%, 60%)';
    const alarmingBgColor = 'hsl(350, 70%, 65%)';
    const duplicatePattern = this._createDiagonalPattern(
      ctx,
      alarmingColor,
      alarmingBgColor
    );

    if (this.chart) {
      this.chart.destroy();
    }

    this.chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Similar Issues',
            data: duplicateData,
            backgroundColor: duplicatePattern,
            hoverBackgroundColor: 'hsl(350, 70%, 50%)',
            borderRadius: {
              topLeft: 0,
              topRight: 0,
              bottomLeft: 4,
              bottomRight: 4,
            },
            borderSkipped: false,
          },
          {
            label: 'Unique Issues',
            data: otherData,
            backgroundColor: 'hsl(210, 60%, 55%)',
            hoverBackgroundColor: 'hsl(210, 60%, 65%)',
            borderRadius: {
              topLeft: 4,
              topRight: 4,
              bottomLeft: 0,
              bottomRight: 0,
            },
            borderSkipped: false,
          },
        ],
      },
      options: {
        interaction: {
          mode: 'index',
          intersect: false,
        },
        onClick: (event, elements) => {
          if (!this.interactive || elements.length === 0) {
            return;
          }
          const element = elements[0];
          const index = element.index;
          const clickedStat = sortedStats[index];
          if (clickedStat) {
            this.dispatchEvent(
              new CustomEvent('project-selected', {
                detail: { projectId: clickedStat.project_id },
                bubbles: true,
                composed: true,
              })
            );
          }
        },
        onHover: (event, chartElement) => {
          const target = event.native?.target as HTMLCanvasElement;
          if (target) {
            target.style.cursor =
              this.interactive && chartElement[0] ? 'pointer' : 'default';
          }
        },
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            stacked: true,
            display: true,
            grid: {
              display: false,
            },
            ticks: {
              color: 'white',
            },
            border: {
              display: false,
            },
          },
          y: {
            stacked: true,
            display: false,
            beginAtZero: true,
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: 'var(--sl-color-neutral-1000)',
            titleColor: 'var(--sl-color-neutral-0)',
            bodyColor: 'var(--sl-color-neutral-0)',
            displayColors: false,
            callbacks: {
              title: () => null, // Hide title
              label: () => '', // Use footer for all info
              footer: (tooltipItems) => {
                const similarItem = tooltipItems.find(
                  (item) => item.dataset.label === 'Similar Issues'
                );
                const uniqueItem = tooltipItems.find(
                  (item) => item.dataset.label === 'Unique Issues'
                );

                const similarCount = similarItem?.parsed.y || 0;
                const uniqueCount = uniqueItem?.parsed.y || 0;
                const total = similarCount + uniqueCount;

                return [
                  `Similar: ${similarCount}`,
                  `Unique: ${uniqueCount}`,
                  ``,
                  `Total: ${total}`,
                ];
              },
            },
          },
        },
      },
    });
  }

  private _createDiagonalPattern(
    chartCtx: CanvasRenderingContext2D,
    color = 'black',
    backgroundColor = 'transparent'
  ) {
    const patternCanvas = document.createElement('canvas');
    const patternCtx = patternCanvas.getContext('2d');
    if (!patternCtx) return color;

    const size = 10;
    patternCanvas.width = size;
    patternCanvas.height = size;

    patternCtx.fillStyle = backgroundColor;
    patternCtx.fillRect(0, 0, size, size);

    patternCtx.strokeStyle = color;
    patternCtx.lineWidth = 3;

    patternCtx.beginPath();
    patternCtx.moveTo(-2, size / 2 - 2);
    patternCtx.lineTo(size / 2 + 2, size + 2);
    patternCtx.stroke();

    patternCtx.beginPath();
    patternCtx.moveTo(size / 2 - 2, 0 - 2);
    patternCtx.lineTo(size + 2, size / 2 + 2);
    patternCtx.stroke();

    return chartCtx.createPattern(patternCanvas, 'repeat') || color;
  }

  render() {
    if (this._loading) {
      return html`<sl-spinner></sl-spinner>`;
    }
    if (this._error) {
      return html`<div>Error: ${this._error}</div>`;
    }
    return html`<canvas></canvas>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'duplicate-stats-chart': DuplicateStatsChart;
  }
}
