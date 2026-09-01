/**
 * Investigation Intelligence Dashboard.
 *
 * Two rules hold for every widget on this page:
 *   1. The value comes from GET /dashboard - nothing is a constant.
 *   2. The widget is a doorway. Clicking it navigates to the detail page with
 *      the relevant filter already applied, so context survives the jump.
 */

import {
  html, useState, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock,
  fmt, entityColor, ENTITY_GLYPHS, BAND_COLORS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { GraphCanvas } from "../components/GraphCanvas.js";
import { ZoneMap } from "../components/MapCanvas.js";
import { EvidenceModal } from "../components/EvidenceModal.js";

const KPI_ICONS = {
  records: { glyph: "▥", bg: "#eef2ff", fg: "#21518F" },
  entities: { glyph: "◉", bg: "#e8f7f0", fg: "#12855c" },
  relationships: { glyph: "⚭", bg: "#fff5e9", fg: "#e07a1f" },
  cases: { glyph: "▤", bg: "#fdeef4", fg: "#c9376b" },
  leads: { glyph: "✦", bg: "#fff8e4", fg: "#c9930b" },
};

export function Dashboard({ data, loading, error, reload, navigate, user }) {
  const [evidenceId, setEvidenceId] = useState(null);
  const toast = useToast();

  const act = useCallback(async (action, payload) => {
    try {
      await action();
      toast.push(payload, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [reload, toast]);

  if (loading && !data) {
    return html`<div className="stack">
      <${LoadingBlock} rows=${2} />
      <div className="kpi-row">
        ${[0, 1, 2, 3, 4].map((i) => html`<div className="card card-pad" key=${i}><${LoadingBlock} rows=${2} /></div>`)}
      </div>
      <div className="card card-pad"><${LoadingBlock} rows=${5} /></div>
    </div>`;
  }
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;
  if (!data) return null;

  const scope = data.scope || {};
  const roleView = data.role_view || {};
  const ws = data.women_safety || {};
  const emphasiseWs = roleView.emphasis === "women_safety";

  const graphSection = html`<${Card}
    title="Network Graph"
    subtitle=${`${fmt.number(data.graph_preview?.counts?.nodes || 0)} entities · ${fmt.number(data.graph_preview?.counts?.edges || 0)} relationships in view · ${fmt.number(data.graph_totals?.nodes || 0)} in the full graph`}
    actions=${html`<${Button} size="sm" onClick=${() => navigate("/network", scope.case_id ? { case_id: scope.case_id } : {})}>
      Open full graph ⤢
    <//>`}
  >
    <${GraphCanvas}
      nodes=${data.graph_preview?.nodes || []}
      edges=${data.graph_preview?.edges || []}
      compact
      onNodeClick=${(uid) => navigate(`/entity/${uid}`)}
    />
    <div className="graph-legend">
      ${["person", "phone", "location", "organization", "vehicle", "transaction"].map(
        (type) => html`<span className="legend-item" key=${type}>
          <span className="legend-swatch" style=${{ background: entityColor(type) }}></span>
          ${fmt.title(type)}
        </span>`
      )}
      <span key="obs" className="legend-item">
        <span className="legend-line" style=${{ borderColor: "#9aa4bf" }}></span> Observed
      </span>
      <span key="inf" className="legend-item">
        <span className="legend-line dashed" style=${{ borderColor: "#21518F" }}></span> Inferred
      </span>
    </div>
  <//>`;

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Investigation Intelligence Dashboard</h1>
        <p>
          Explore relationships, patterns and investigative leads across connected datasets.
          ${scope.case_number
            ? html` Scoped to <strong>${scope.case_number}</strong> — ${scope.case_title}.`
            : " Showing all cases."}
        </p>
      </div>
      <div className="page-head-actions">
        ${scope.case_id
          ? html`<${Button} key="case" size="sm" onClick=${() => navigate(`/cases/${scope.case_id}`)}>Open case file<//>`
          : null}
        <${Button} key="refresh" size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <!-- KPI row: each tile opens its detail page pre-filtered -->
    <div className="kpi-row">
      ${(data.kpis || []).map((kpi) => {
        const icon = KPI_ICONS[kpi.key] || KPI_ICONS.records;
        return html`<button
          className="kpi-card" key=${kpi.key}
          onClick=${() => navigate(kpi.route, kpi.filters)}
          title=${`Open ${kpi.label}`}
        >
          <div className="kpi-top">
            <span className="kpi-icon" style=${{ background: icon.bg, color: icon.fg }}>${icon.glyph}</span>
            <span className="kpi-label">${kpi.label}</span>
          </div>
          <div className="kpi-value">${fmt.number(kpi.value)}</div>
          <div className="kpi-foot">
            ${kpi.delta_pct ? html`<span className="kpi-delta up">↑ ${kpi.delta_pct}%</span>` : null}
            <span>${kpi.caption}</span>
          </div>
          <span className="kpi-go">→</span>
        </button>`;
      })}
    </div>

    ${emphasiseWs ? html`<${WomenSafetyStrip} ws=${ws} navigate=${navigate} />` : null}

    <div className="dash-grid-main">
      ${graphSection}

      <div className="dash-side">
        <${Card}
          title="Top Investigation Priority"
          subtitle=${scope.case_number ? `Within ${scope.case_number}` : "Across all cases"}
          actions=${html`<button className="link-btn" onClick=${() => navigate("/priority", scope.case_id ? { case_id: scope.case_id } : {})}>View all</button>`}
        >
          ${(data.top_priority || []).length
            ? html`<div>
                ${data.top_priority.map((row, index) => html`<div
                  className="rank-row" key=${row.entity_uid}
                  onClick=${() => navigate(row.route, row.filters)}
                  title=${row.top_factor_detail || ""}
                >
                  <span className="rank-num">${index + 1}</span>
                  <div className="rank-body">
                    <div className="rank-name">${row.name}</div>
                    <div className="rank-meta">${row.top_factor || "—"}</div>
                    <div className="rank-bar">
                      <span style=${{
                        width: `${Math.min(100, row.score)}%`,
                        background: BAND_COLORS[row.band] || "#21518F",
                      }}></span>
                    </div>
                  </div>
                  <span className="rank-score" style=${{ color: BAND_COLORS[row.band] }}>
                    ${fmt.score(row.score)}
                  </span>
                </div>`)}
                <div className="tiny muted mt-1">
                  Analytical triage signal — not a measure of guilt or criminality.
                </div>
              </div>`
            : html`<${EmptyState} title="No scored entities" text="Run priority scoring to rank entities in this scope." />`}
        <//>

        <${Card}
          title="Live Alerts"
          subtitle=${`${(data.alerts || []).length} unresolved`}
          actions=${html`<button className="link-btn" onClick=${() => navigate("/safety/alerts")}>View all</button>`}
        >
          ${(data.alerts || []).length
            ? data.alerts.map((alert) => html`<div
                className="feed-row" key=${alert.alert_ref}
                onClick=${() => navigate(alert.route, alert.filters)}
              >
                <span className="feed-dot" style=${{ background: BAND_COLORS[alert.priority] || "#78819c" }}></span>
                <div className="feed-body">
                  <div className="feed-title">${alert.message}</div>
                  <div className="feed-meta">
                    <${Pill} kind=${alert.priority}>${alert.priority}<//>
                    <span>${alert.status.replace(/_/g, " ")}</span>
                    <span>· ${alert.time_label || fmt.relative(alert.raised_at)}</span>
                  </div>
                </div>
              </div>`)
            : html`<${EmptyState} icon="✓" title="No open alerts" text="All safety alerts have been resolved." />`}
        <//>
      </div>
    </div>

    ${!emphasiseWs ? html`<${WomenSafetyStrip} ws=${ws} navigate=${navigate} />` : null}

    <!-- Pending investigator actions, actionable inline -->
    ${(data.pending_actions || []).length
      ? html`<${Card}
          className="mb-2"
          title="Awaiting your review"
          subtitle="AI-surfaced findings that need an investigator decision before they enter the case record"
          actions=${html`<${Button} size="sm" onClick=${() => navigate("/link-analysis")}>Open review queue<//>`}
        >
          ${data.pending_actions.map((action) => html`<div className="action-row" key=${`${action.kind}-${action.id}`}>
            <span className="feed-dot" style=${{ background: action.kind === "resolution" ? "#0ea5a5" : "#21518F", marginTop: "6px" }}></span>
            <div className="action-body">
              <div className="row" style=${{ gap: "8px" }}>
                <span className="action-title">${action.title}</span>
                <${EvidenceBadge} status=${action.evidence_status} />
                <span className="tiny muted">confidence ${fmt.percent(action.confidence)}</span>
              </div>
              <div className="action-sub">${action.subtitle}</div>
              <div className="action-buttons">
                ${action.kind === "hidden_link"
                  ? html`
                      <${Button} key="ev" size="sm" onClick=${() => setEvidenceId(action.id)}>View evidence<//>
                      <${Button} key="ok" size="sm" variant="success"
                        onClick=${() => act(
                          () => api.post(`/graph/relationship/${action.id}/validate`, { decision: "VALIDATED" }),
                          "Relationship validated and recorded in the case."
                        )}>Validate<//>
                      <${Button} key="no" size="sm" variant="danger"
                        onClick=${() => act(
                          () => api.post(`/graph/relationship/${action.id}/validate`, { decision: "REJECTED" }),
                          "Relationship rejected and removed from analysis."
                        )}>Reject<//>`
                  : html`
                      <${Button} key="rev" size="sm" onClick=${() => navigate("/entity-resolution", { candidate: action.id })}>
                        Review match
                      <//>
                      <${Button} key="accept" size="sm" variant="success"
                        onClick=${() => act(
                          () => api.post(`/resolution/candidates/${action.id}/decide`, { decision: "ACCEPTED" }),
                          "Identities merged. An alias relationship has been recorded."
                        )}>Accept match<//>
                      <${Button} key="reject" size="sm" variant="danger"
                        onClick=${() => act(
                          () => api.post(`/resolution/candidates/${action.id}/decide`, { decision: "REJECTED" }),
                          "Match rejected. These records stay separate."
                        )}>Reject<//>`}
              </div>
            </div>
          </div>`)}
        <//>`
      : null}

    <div className="dash-grid-two">
      <${Card}
        title="Timeline of Key Events"
        subtitle=${scope.case_number ? `Case ${scope.case_number}` : "Most recent activity"}
        actions=${html`<button className="link-btn" onClick=${() => navigate("/timeline", scope.case_id ? { case_id: scope.case_id } : {})}>View full timeline</button>`}
      >
        ${(data.timeline || []).length
          ? html`<div className="timeline-strip">
              ${data.timeline.map((event) => html`<div
                className="ts-node" key=${event.uid}
                onClick=${() => navigate(event.route, event.filters)}
                title=${event.title}
              >
                <span className="ts-dot"></span>
                <div className="ts-body">
                  <div className="ts-date">${event.time_label || fmt.date(event.occurred_at)}</div>
                  <div className="ts-title">${event.title.length > 62 ? `${event.title.slice(0, 62)}…` : event.title}</div>
                </div>
              </div>`)}
            </div>`
          : html`<${EmptyState} title="No dated events" text="Events appear here once records with dates are ingested." />`}
      <//>

      <${Card}
        title="Geographic Safety Map"
        subtitle="Zone density computed from stored incident records"
        actions=${html`<button className="link-btn" onClick=${() => navigate("/safety/heatmap")}>View full map</button>`}
      >
        <${ZoneMap}
          zones=${data.zones || []} height=${232}
          onZoneClick=${(zone) => navigate("/safety/heatmap", { zone: zone.zone_ref })}
        />
        <div className="map-legend">
          ${["GREEN", "YELLOW", "ORANGE", "RED"].map((band) => html`<span className="legend-item" key=${band}>
            <span className="band-swatch" style=${{ background: BAND_COLORS[band] }}></span>${band}
          </span>`)}
          <span className="tiny muted">Bands are relative to the current selection.</span>
        </div>
      <//>
    </div>

    <${Card}
      title="Recent Records"
      subtitle="Most recently ingested source records"
      actions=${html`<button className="link-btn" onClick=${() => navigate("/data-management")}>Open data management</button>`}
    >
      ${(data.recent_records || []).length
        ? html`<div className="table-wrap">
            <table className="data">
              <thead><tr>
                <th>Source</th><th>Reference</th><th>Date</th><th>Summary</th><th>Classification</th>
              </tr></thead>
              <tbody>
                ${data.recent_records.map((record) => html`<tr
                  key=${record.id} className="clickable"
                  onClick=${() => navigate(record.route, record.filters)}
                >
                  <td><${Pill} kind="info">${record.source_type}<//></td>
                  <td className="mono">${record.source_ref || "—"}</td>
                  <td className="nowrap">${fmt.date(record.occurred_at)}</td>
                  <td>${record.summary}</td>
                  <td><span className="tiny muted">${record.classification}</span></td>
                </tr>`)}
              </tbody>
            </table>
          </div>`
        : html`<${EmptyState} title="No records yet" text="Upload a dataset to populate the platform." />`}
    <//>

    ${evidenceId
      ? html`<${EvidenceModal}
          relationshipId=${evidenceId}
          onClose=${() => setEvidenceId(null)}
          onDecision=${() => { setEvidenceId(null); reload(); }}
          canValidate=${roleView.can_validate}
        />`
      : null}
  </div>`;
}

// --------------------------------------------------------- women safety

function WomenSafetyStrip({ ws, navigate }) {
  if (!ws || !ws.incidents) return null;
  const sos = ws.sos || {};
  const incidents = ws.incidents || {};
  const patterns = ws.patterns || {};
  const topTypes = (incidents.by_type || []).slice(0, 3);

  return html`<${Card}
    className="mb-2"
    title=${html`<span><span style=${{ color: "var(--rose)" }}>◈</span> Women Safety Intelligence</span>`}
    subtitle="Live operational picture — click any tile to open the module"
    actions=${html`<${Button} size="sm" onClick=${() => navigate("/safety")}>Open module →<//>`}
  >
    <div className="ws-strip">
      <div className="ws-tile" onClick=${() => navigate("/safety/sos")}>
        <div className="ws-tile-label"><span>🚨</span> Open SOS Alerts</div>
        <div className="ws-tile-value" style=${{ color: sos.open ? "var(--red)" : "var(--green)" }}>
          ${fmt.number(sos.open || 0)}
        </div>
        <div className="ws-tile-sub">
          ${Object.entries(sos.by_status || {})
            .filter(([, v]) => v > 0)
            .map(([k, v]) => `${v} ${k.toLowerCase()}`)
            .join(" · ") || "No active alerts"}
        </div>
      </div>

      <div className="ws-tile" onClick=${() => navigate("/safety/incidents")}>
        <div className="ws-tile-label"><span>▤</span> Incidents Recorded</div>
        <div className="ws-tile-value">${fmt.number(incidents.total || 0)}</div>
        <div className="ws-tile-sub">
          ${topTypes.map((t) => `${t.label} ${t.count}`).join(" · ") || "None recorded"}
        </div>
      </div>

      <div className="ws-tile" onClick=${() => navigate("/safety/patterns")}>
        <div className="ws-tile-label"><span>👁</span> Patterns Awaiting Review</div>
        <div className="ws-tile-value" style=${{ color: patterns.pending ? "var(--orange)" : "var(--green)" }}>
          ${fmt.number(patterns.pending || 0)}
        </div>
        <div className="ws-tile-sub">${fmt.number(patterns.total || 0)} detected in total</div>
      </div>

      <div className="ws-tile" onClick=${() => navigate("/safety/route")}>
        <div className="ws-tile-label"><span>🛣</span> AI Safe Route</div>
        <div className="ws-tile-value" style=${{ fontSize: "15px", marginTop: "9px" }}>Plan a route</div>
        <div className="ws-tile-sub">Compare options by recorded safety indicators</div>
      </div>
    </div>
  <//>`;
}
