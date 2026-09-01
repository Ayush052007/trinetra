/** Entity profile: everything the platform holds about one record. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock,
  FactorList, Disclaimer, useAsync, fmt, entityColor, ENTITY_GLYPHS,
  ENTITY_LABELS, BAND_COLORS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { GraphCanvas } from "../components/GraphCanvas.js";
import { EvidenceModal } from "../components/EvidenceModal.js";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "relationships", label: "Relationships" },
  { key: "network", label: "Network" },
  { key: "timeline", label: "Timeline" },
  { key: "evidence", label: "Evidence" },
  { key: "priority", label: "Priority" },
];

export function EntityProfile({ uid, navigate, user, params }) {
  const [tab, setTab] = useState(params.panel === "priority" ? "priority" : "overview");
  const [evidenceId, setEvidenceId] = useState(null);
  const [depth, setDepth] = useState(1);
  const toast = useToast();

  const { data, loading, error, reload } = useAsync(
    () => api.get(`/entities/${encodeURIComponent(uid)}`), [uid]
  );

  const graph = useAsync(
    () => (tab === "network"
      ? api.get(`/graph/neighbourhood/${encodeURIComponent(uid)}`, { depth, include_inferred: true })
      : Promise.resolve(null)),
    [uid, tab, depth],
    { immediate: false }
  );

  const loadGraph = useCallback(() => { if (tab === "network") graph.reload(); }, [tab, depth, uid]);
  React.useEffect(loadGraph, [tab, depth, uid]);

  if (loading && !data) return html`<${LoadingBlock} rows=${6} />`;
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;
  if (!data) return null;

  const canValidate = (user.permissions || []).includes("relationship:validate");
  const summary = data.summary || {};

  return html`<div>
    <div className="breadcrumb">
      <button onClick=${() => navigate("/")}>Dashboard</button>
      <span>›</span>
      <button onClick=${() => navigate("/search")}>Entity Search</button>
      <span>›</span>
      <span>${data.name}</span>
    </div>

    <div className="page-head">
      <div className="page-head-main">
        <div className="row" style=${{ gap: "13px" }}>
          <span style=${{
            width: "44px", height: "44px", borderRadius: "12px", flex: "none",
            display: "grid", placeItems: "center", fontSize: "19px", color: "#fff",
            background: entityColor(data.type),
          }}>${ENTITY_GLYPHS[data.type] || "?"}</span>
          <div>
            <h1>${data.name}</h1>
            <div className="row small muted" style=${{ gap: "9px" }}>
              <span>${data.type_label}</span>
              <span className="mono">${data.uid}</span>
              ${data.aliases?.length ? html`<span>· aka ${data.aliases.join(", ")}</span>` : null}
              <${Pill} kind="neutral">${data.classification}<//>
              ${!data.is_active
                ? html`<${Pill} kind="rejected">Merged into ${data.merged_into}<//>`
                : null}
            </div>
          </div>
        </div>
      </div>
      <div className="page-head-actions">
        ${data.priority
          ? html`<div className="card card-pad" style=${{ padding: "9px 14px", textAlign: "center" }}>
              <div className="tiny muted">Investigation Priority</div>
              <div style=${{
                fontSize: "21px", fontWeight: 700,
                color: BAND_COLORS[data.priority.band],
              }}>${fmt.score(data.priority.score)}</div>
              <${Pill} kind=${data.priority.band}>${data.priority.band}<//>
            </div>`
          : null}
        <${Button} key="explore" variant="primary" size="sm" onClick=${() => navigate("/network", { root: data.uid })}>
          Explore network →
        <//>
      </div>
    </div>

    <div className="grid-4 mb-2">
      ${[
        ["Connections", summary.connections],
        ["Relationships", summary.relationships],
        ["Observed", summary.observed],
        ["Inferred", summary.inferred],
        ["Cases", summary.cases],
        ["Events", summary.events],
        ["Evidence", summary.evidence],
        ["Incidents", summary.incidents],
      ].filter(([, v]) => v !== undefined).map(([label, value]) => html`<div className="card card-pad" key=${label}>
        <div className="kpi-label">${label}</div>
        <div style=${{ fontSize: "21px", fontWeight: 700 }}>${fmt.number(value)}</div>
      </div>`)}
    </div>

    <div className="graph-toolbar">
      ${TABS.map((t) => html`<button
        key=${t.key} className=${`chip ${tab === t.key ? "active" : ""}`}
        onClick=${() => setTab(t.key)}
      >${t.label}</button>`)}
    </div>

    ${tab === "overview" ? html`<div className="grid-2">
      <${Card} title="Attributes">
        ${Object.keys(data.attributes || {}).length
          ? Object.entries(data.attributes).map(([key, value]) => html`<div className="kv-row" key=${key}>
              <span className="kv-key">${fmt.title(key)}</span>
              <span className="kv-val">${String(value)}</span>
            </div>`)
          : html`<div className="muted small">No additional attributes recorded.</div>`}
        ${data.source ? html`<div className="kv-row">
          <span className="kv-key">Source</span><span className="kv-val">${data.source}</span>
        </div>` : null}
        ${data.coordinates ? html`<div className="kv-row">
          <span className="kv-key">Coordinates</span>
          <span className="kv-val mono">${data.coordinates.lat?.toFixed(4)}, ${data.coordinates.lng?.toFixed(4)}</span>
        </div>` : null}
      <//>

      <${Card} title="Cases">
        ${data.cases?.length
          ? data.cases.map((c) => html`<div
              className="feed-row" key=${c.id} onClick=${() => navigate(`/cases/${c.id}`)}
            >
              <span className="feed-dot" style=${{ background: c.module === "WOMEN_SAFETY" ? "var(--rose)" : "var(--indigo)" }}></span>
              <div className="feed-body">
                <div className="feed-title">${c.case_number}</div>
                <div className="feed-meta">${c.title} · ${fmt.title(c.status)}</div>
              </div>
            </div>`)
          : html`<div className="muted small">Not linked to any case.</div>`}
      <//>

      ${data.incidents?.length
        ? html`<${Card} title="Women Safety incidents" className="grid-2-full">
            ${data.incidents.map((incident) => html`<div className="feed-row" key=${incident.incident_ref}>
              <span className="feed-dot" style=${{ background: BAND_COLORS[incident.priority] }}></span>
              <div className="feed-body">
                <div className="feed-title">${incident.description}</div>
                <div className="feed-meta">
                  <${Pill} kind=${incident.priority}>${incident.priority}<//>
                  <span className="mono">${incident.incident_ref}</span>
                  <span>${fmt.title(incident.type)}</span>
                  <span>· ${fmt.date(incident.occurred_at)}</span>
                </div>
              </div>
            </div>`)}
          <//>`
        : null}
    </div>` : null}

    ${tab === "relationships" ? html`<${Card}
      title=${`Relationships (${data.relationships?.length || 0})`}
      subtitle="Grouped by the type of the connected entity"
    >
      ${data.relationships?.length
        ? Object.entries(data.relationships_by_type || {}).map(([type, items]) => html`<div key=${type} className="mb-2">
            <div className="row mb-1">
              <span className="chip-swatch" style=${{ background: entityColor(type), width: "11px", height: "11px", borderRadius: "3px" }}></span>
              <span className="strong small">${ENTITY_LABELS[type] || type}</span>
              <span className="tiny muted">${items.length}</span>
            </div>
            <div className="table-wrap">
              <table className="data">
                <thead><tr>
                  <th>Connected entity</th><th>Relationship</th><th>Status</th>
                  <th>Confidence</th><th>Source</th><th>Date</th><th></th>
                </tr></thead>
                <tbody>
                  ${items.map((rel) => html`<tr key=${rel.relationship_id}>
                    <td>
                      <button className="link-btn" onClick=${() => navigate(`/entity/${rel.other.uid}`)}>
                        ${rel.other.name}
                      </button>
                    </td>
                    <td>
                      ${fmt.title(rel.type)}
                      <span className="tiny muted"> ${rel.direction === "outgoing" ? "→" : "←"}</span>
                    </td>
                    <td><${EvidenceBadge} status=${rel.evidence_status} /></td>
                    <td className="num">${fmt.percent(rel.confidence)}</td>
                    <td className="tiny">${rel.source_ref || "—"}</td>
                    <td className="nowrap tiny">${rel.time_label || fmt.date(rel.occurred_at)}</td>
                    <td>
                      <${Button} size="sm" onClick=${() => setEvidenceId(rel.relationship_id)}>Evidence<//>
                    </td>
                  </tr>`)}
                </tbody>
              </table>
            </div>
          </div>`)
        : html`<${EmptyState} title="No relationships" text="This entity has no recorded connections." />`}
    <//>` : null}

    ${tab === "network" ? html`<div>
      <div className="graph-toolbar">
        <span className="small strong">Depth</span>
        ${[1, 2, 3].map((d) => html`<button
          key=${d} className=${`chip ${depth === d ? "active" : ""}`} onClick=${() => setDepth(d)}
        >${d}-hop</button>`)}
        <div className="spacer"></div>
        <${Button} size="sm" onClick=${() => navigate("/network", { root: data.uid })}>
          Open in full graph explorer →
        <//>
      </div>
      ${graph.loading
        ? html`<div className="card card-pad"><${LoadingBlock} rows=${5} /></div>`
        : html`<${GraphCanvas}
            nodes=${graph.data?.nodes || []} edges=${graph.data?.edges || []}
            rootUid=${data.uid} onNodeClick=${(u) => navigate(`/entity/${u}`)}
          />`}
    </div>` : null}

    ${tab === "timeline" ? html`<${Card} title=${`Timeline (${data.timeline?.length || 0} events)`}>
      ${data.timeline?.length
        ? data.timeline.map((event) => html`<div className="feed-row" key=${event.uid}>
            <span className="feed-dot" style=${{ background: "var(--indigo)" }}></span>
            <div className="feed-body">
              <div className="feed-title">${event.title}</div>
              <div className="feed-meta">
                <${Pill} kind="info">${fmt.title(event.type)}<//>
                <span>${event.time_label || fmt.dateTime(event.occurred_at)}</span>
                ${event.relationship_id
                  ? html`<button className="link-btn" onClick=${() => setEvidenceId(event.relationship_id)}>
                      View source record
                    </button>`
                  : null}
              </div>
            </div>
          </div>`)
        : html`<${EmptyState} title="No dated events" text="No timeline events reference this entity." />`}
    <//>` : null}

    ${tab === "evidence" ? html`<${Card} title=${`Evidence (${data.evidence?.length || 0})`}>
      ${data.evidence?.length
        ? data.evidence.map((item) => html`<div className="evidence-block" key=${item.evidence_ref}>
            <div className="evidence-head">
              <span className="evidence-ref">${item.evidence_ref}</span>
              <${Pill} kind="info">${item.source_type}<//>
              <${EvidenceBadge} status=${item.status} />
            </div>
            <div className="evidence-desc">${item.description}</div>
            <div className="evidence-meta">
              <span>Source: ${item.source}</span>
              <span>Confidence: ${fmt.percent(item.confidence)}</span>
              ${item.occurred_at ? html`<span>${fmt.date(item.occurred_at)}</span>` : null}
            </div>
          </div>`)
        : html`<${EmptyState} title="No evidence records" text="No evidence items reference this entity." />`}
    <//>` : null}

    ${tab === "priority" ? (data.priority
      ? html`<${Card}
          title="Investigation Priority Score"
          subtitle=${`${data.priority.algorithm_version} · computed ${fmt.dateTime(data.priority.computed_at)}`}
        >
          <div className="row-between mb-2">
            <div>
              <div style=${{ fontSize: "38px", fontWeight: 700, lineHeight: 1, color: BAND_COLORS[data.priority.band] }}>
                ${fmt.score(data.priority.score)}
                <span style=${{ fontSize: "15px", color: "var(--gray)", fontWeight: 500 }}> / 100</span>
              </div>
              <div className="mt-1"><${Pill} kind=${data.priority.band}>${data.priority.band}<//></div>
            </div>
            <div className="small muted" style=${{ textAlign: "right" }}>
              Evidence confidence<br />
              <span className="strong" style=${{ fontSize: "17px", color: "var(--navy)" }}>
                ${fmt.percent(data.priority.confidence)}
              </span>
            </div>
          </div>
          <${FactorList} factors=${data.priority.factors} />
          <div className="mt-2">
            <${Disclaimer}>${data.priority.disclaimer}<//>
          </div>
        <//>`
      : html`<${EmptyState} title="No priority score" text="This entity has not been scored." />`) : null}

    ${evidenceId
      ? html`<${EvidenceModal}
          relationshipId=${evidenceId} onClose=${() => setEvidenceId(null)}
          onDecision=${() => { setEvidenceId(null); reload(); }} canValidate=${canValidate}
        />`
      : null}
  </div>`;
}
