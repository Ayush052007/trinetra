/** Graph analytics, investigation priority and hidden-link review. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock,
  FactorList, BarChart, Disclaimer, useAsync, fmt, entityColor,
  ENTITY_LABELS, BAND_COLORS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { EvidenceModal } from "../components/EvidenceModal.js";

// ==================================================== Investigation Priority

export function PriorityPage({ navigate, user, caseId }) {
  const [entityType, setEntityType] = useState("person");
  const [band, setBand] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const toast = useToast();
  const canRecompute = (user.permissions || []).includes("priority:recompute");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/analytics/priority", {
      case_id: caseId || undefined, entity_type: entityType,
      band: band || undefined, limit: 60,
    }),
    [caseId, entityType, band]
  );

  const recompute = useCallback(async () => {
    try {
      const result = await api.post(
        `/analytics/priority/recompute${caseId ? `?case_id=${caseId}` : ""}`
      );
      toast.push(`Recomputed ${fmt.number(result.recomputed)} priority scores.`, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [caseId, reload, toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Investigation Priority</h1>
        <p>
          A ranked, explainable triage signal showing which records feature most
          prominently in the available data. Every score decomposes into weighted
          factors computed from stored records.
        </p>
      </div>
      <div className="page-head-actions">
        ${canRecompute ? html`<${Button} size="sm" onClick=${recompute}>Recompute scores<//>` : null}
      </div>
    </div>

    <div className="alert alert-info mb-2">
      <span>ⓘ</span>
      <div>
        <strong>This is not a guilt or criminality score.</strong>
        A high score means the record sits at a busy junction of the available data —
        a statement about the data, not about the person. It is a triage aid for
        deciding where to look first, and carries no evidentiary weight.
      </div>
    </div>

    <${Card} className="mb-2">
      <div className="row">
        <span className="small strong">Entity type</span>
        ${["person", "organization", "phone", "vehicle", "location"].map((type) => html`<button
          key=${type} className=${`chip ${entityType === type ? "active" : ""}`}
          onClick=${() => setEntityType(type)}
        >
          <span className="chip-swatch" style=${{ background: entityColor(type) }}></span>
          ${ENTITY_LABELS[type]}
        </button>`)}
        <div className="spacer"></div>
        <span className="small strong">Band</span>
        ${["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => html`<button
          key=${b} className=${`chip ${band === b ? "active" : ""}`}
          onClick=${() => setBand(band === b ? null : b)}
        >
          <span className="chip-swatch" style=${{ background: BAND_COLORS[b] }}></span>
          ${b} ${data?.band_counts?.[b] ? html`<span className="tiny muted">${data.band_counts[b]}</span>` : ""}
        </button>`)}
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${6} /><//>` : null}

    ${data && data.items.length === 0
      ? html`<${EmptyState} title="No scored entities" text="No entities match this filter." />`
      : null}

    ${data && data.items.length
      ? html`<${Card}
          title=${`${data.items.length} ranked ${ENTITY_LABELS[entityType] || entityType} records`}
          subtitle=${`Algorithm ${data.algorithm_version} · weights are published below`}
        >
          ${data.items.map((item, index) => html`<div key=${item.entity_uid} style=${{
            borderBottom: "1px solid var(--line-soft)", padding: "11px 0",
          }}>
            <div className="row-between">
              <div className="row" style=${{ gap: "12px", flex: 1, minWidth: 0 }}>
                <span className="rank-num">${index + 1}</span>
                <div style=${{ flex: 1, minWidth: 0 }}>
                  <button className="link-btn" style=${{ fontSize: "13.5px", padding: 0 }}
                    onClick=${() => navigate(`/entity/${item.entity_uid}`)}>
                    ${item.entity_name}
                  </button>
                  <div className="rank-bar" style=${{ maxWidth: "320px" }}>
                    <span style=${{
                      width: `${Math.min(100, item.score)}%`,
                      background: BAND_COLORS[item.band],
                    }}></span>
                  </div>
                  <div className="tiny muted mt-1">
                    ${item.factors[0]?.label}: ${item.factors[0]?.detail}
                  </div>
                </div>
              </div>
              <div className="row" style=${{ gap: "10px" }}>
                <div style=${{ textAlign: "right" }}>
                  <div style=${{ fontSize: "18px", fontWeight: 700, color: BAND_COLORS[item.band] }}>
                    ${fmt.score(item.score)}
                  </div>
                  <${Pill} kind=${item.band}>${item.band}<//>
                </div>
                <${Button} size="sm"
                  onClick=${() => setExpanded(expanded === item.entity_uid ? null : item.entity_uid)}>
                  ${expanded === item.entity_uid ? "Hide" : "Factors"}
                <//>
              </div>
            </div>
            ${expanded === item.entity_uid
              ? html`<div className="mt-2" style=${{ paddingLeft: "33px" }}>
                  <${FactorList} factors=${item.factors} />
                  <div className="tiny muted mt-1">
                    Evidence confidence ${fmt.percent(item.confidence)} ·
                    computed ${fmt.dateTime(item.computed_at)}
                  </div>
                </div>`
              : null}
          </div>`)}

          <div className="mt-2">
            <div className="card-title mb-1">Factor weights</div>
            <${BarChart} items=${Object.entries(data.weights || {}).map(([key, weight]) => ({
              label: fmt.title(key), value: weight, display: weight.toFixed(2),
            }))} />
          </div>
          <div className="mt-2"><${Disclaimer}>${data.disclaimer}<//></div>
        <//>`
      : null}
  </div>`;
}

// ========================================================== Graph Analytics

export function PatternsPage({ navigate, caseId }) {
  const [entityType, setEntityType] = useState("person");
  const { data, loading, error, reload } = useAsync(
    () => api.get("/analytics/overview", {
      case_id: caseId || undefined,
      entity_type: entityType === "all" ? undefined : entityType,
    }),
    [caseId, entityType]
  );

  if (loading && !data) return html`<${Card}><${LoadingBlock} rows=${7} /><//>`;
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;
  if (!data || data.empty) {
    return html`<${EmptyState} title="Graph is empty" text=${data?.message || "No entities to analyse."} />`;
  }

  const measures = [
    ["degree", "Degree centrality"],
    ["betweenness", "Betweenness centrality"],
    ["closeness", "Closeness centrality"],
  ];

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Graph Analytics</h1>
        <p>
          Structural analysis of the knowledge graph. Every figure is computed live
          from the stored graph — nothing on this page is a fixed value.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Recompute<//>
      </div>
    </div>

    <div className="grid-4 mb-2">
      ${[
        ["Nodes", fmt.number(data.graph.nodes)],
        ["Edges", fmt.number(data.graph.edges)],
        ["Density", data.graph.density.toFixed(5)],
        ["Communities", fmt.number(data.communities.count)],
        ["Modularity", data.communities.modularity.toFixed(3)],
        ["Components", fmt.number(data.components.count)],
        ["Observed edges", fmt.number(data.evidence_split.observed)],
        ["Inferred edges", fmt.number(data.evidence_split.inferred)],
      ].map(([label, value]) => html`<div className="card card-pad" key=${label}>
        <div className="kpi-label">${label}</div>
        <div style=${{ fontSize: "20px", fontWeight: 700 }}>${value}</div>
      </div>`)}
    </div>

    <${Card} className="mb-2">
      <div className="row">
        <span className="small strong">Rank by entity type</span>
        ${["person", "organization", "phone", "vehicle", "location", "all"].map((type) => html`<button
          key=${type} className=${`chip ${entityType === type ? "active" : ""}`}
          onClick=${() => setEntityType(type)}
        >${type === "all" ? "All types" : ENTITY_LABELS[type]}</button>`)}
      </div>
      <div className="tiny muted mt-1">
        Locations connect to almost everything, so they dominate raw centrality.
        Filtering to people is usually the investigatively useful view.
      </div>
    <//>

    <div className="grid-2 mb-2">
      ${measures.map(([key, label]) => {
        const block = data.centrality[key];
        return html`<${Card} key=${key} title=${label} subtitle=${block.description}>
          ${block.top.length
            ? html`<${BarChart}
                items=${block.top.map((row) => ({
                  label: row.name, value: row.value,
                  display: key === "degree" ? `${row.connections}` : row.value.toFixed(4),
                }))}
                colorFor=${() => key === "betweenness" ? "var(--orange)" : "var(--indigo)"}
              />`
            : html`<div className="muted small">No entities of this type.</div>`}
        <//>`;
      })}

      <${Card}
        title=${data.communities.label}
        subtitle=${data.communities.description}
      >
        <div className="row-between mb-2">
          <span className="small">
            <strong>${data.communities.count}</strong> communities ·
            modularity <strong>${data.communities.modularity.toFixed(3)}</strong>
          </span>
          <${Pill} kind=${data.communities.modularity > 0.3 ? "green" : "yellow"}>
            ${data.communities.modularity > 0.3 ? "Well separated" : "Weak structure"}
          <//>
        </div>
        <div className="tiny muted mb-2">${data.communities.modularity_note}</div>
        ${data.communities.largest.slice(0, 5).map((community) => html`<div
          key=${community.community} className="mb-1"
          style=${{ padding: "9px 11px", background: "var(--surface-alt)", borderRadius: "8px" }}
        >
          <div className="row-between">
            <span className="small strong">Community ${community.community + 1}</span>
            <span className="tiny muted">${community.size} members</span>
          </div>
          <div className="row mt-1" style=${{ gap: "5px" }}>
            ${community.members.slice(0, 5).map((member) => html`<button
              key=${member.uid} className="chip" style=${{ padding: "2px 8px", fontSize: "11px" }}
              onClick=${() => navigate(`/entity/${member.uid}`)}
            >
              <span className="chip-swatch" style=${{ background: entityColor(member.type) }}></span>
              ${member.name}
            </button>`)}
          </div>
        </div>`)}
      <//>

      <${Card} title="Network composition">
        <div className="card-sub mb-1">Entity types</div>
        <${BarChart}
          items=${data.composition.entity_types.map((t) => ({ label: t.label, value: t.count }))}
          colorFor=${(item) => entityColor(
            Object.keys(ENTITY_LABELS).find((k) => ENTITY_LABELS[k] === item.label) || "person"
          )}
        />
        <div className="card-sub mb-1 mt-2">Relationship types</div>
        <${BarChart} items=${data.composition.relationship_types.map((t) => ({ label: t.label, value: t.count }))} />
      <//>
    </div>

    <${Card} title="Connected components">
      <div className="row">
        <div><span className="muted small">Components</span>
          <div style=${{ fontSize: "19px", fontWeight: 700 }}>${fmt.number(data.components.count)}</div></div>
        <div style=${{ marginLeft: "26px" }}><span className="muted small">Largest</span>
          <div style=${{ fontSize: "19px", fontWeight: 700 }}>${fmt.number(data.components.largest_size)}</div></div>
        <div style=${{ marginLeft: "26px" }}><span className="muted small">Isolated entities</span>
          <div style=${{ fontSize: "19px", fontWeight: 700 }}>${fmt.number(data.components.isolated)}</div></div>
      </div>
      <div className="tiny muted mt-2">
        A component is a group of entities reachable from one another. Isolated
        entities have no recorded relationships at all.
      </div>
    <//>
  </div>`;
}

// =========================================================== Link Analysis

export function LinkAnalysisPage({ navigate, user, caseId, params }) {
  const [evidenceId, setEvidenceId] = useState(
    params.relationship ? Number(params.relationship) : null
  );
  const [tab, setTab] = useState("pending");
  const toast = useToast();
  const canValidate = (user.permissions || []).includes("relationship:validate");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/graph/hidden-links", { case_id: caseId || undefined, limit: 40 }),
    [caseId]
  );

  const decide = useCallback(async (relationshipId, decision) => {
    try {
      const result = await api.post(`/graph/relationship/${relationshipId}/validate`, { decision });
      toast.push(result.message, decision === "REJECTED" ? "warn" : "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [reload, toast]);

  const stored = data?.stored || [];
  const pending = stored.filter((s) => s.requires_validation);
  const reviewed = stored.filter((s) => !s.requires_validation);
  const discovered = data?.discovered || [];

  const list = tab === "pending" ? pending : tab === "reviewed" ? reviewed : discovered;

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Link Analysis</h1>
        <p>
          Connections surfaced by analysis rather than recorded directly. Each one shows
          why it was proposed and which stored records support it. Nothing here enters
          the case record until an investigator validates it.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${tab === "pending" ? "active" : ""}`} onClick=${() => setTab("pending")}>
        Awaiting validation <span className="tiny">${pending.length}</span>
      </button>
      <button className=${`chip ${tab === "reviewed" ? "active" : ""}`} onClick=${() => setTab("reviewed")}>
        Reviewed <span className="tiny">${reviewed.length}</span>
      </button>
      <button className=${`chip ${tab === "discovered" ? "active" : ""}`} onClick=${() => setTab("discovered")}>
        Newly discovered <span className="tiny">${discovered.length}</span>
      </button>
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${5} /><//>` : null}

    ${tab === "discovered" && discovered.length
      ? html`<div className="alert alert-info mb-2">
          <span>ⓘ</span>
          <div>
            These pairs have <strong>no direct relationship on record</strong> but share
            intermediaries. They are computed on demand and are not stored until an
            investigator acts on them.
          </div>
        </div>`
      : null}

    ${!loading && list.length === 0
      ? html`<${EmptyState}
          icon="✓"
          title=${tab === "pending" ? "Nothing awaiting validation" : "Nothing to show"}
          text=${tab === "pending"
            ? "Every inferred connection in this scope has been reviewed."
            : "No entries in this view."}
        />`
      : null}

    ${list.map((item) => {
      const isStored = tab !== "discovered";
      const sourceName = isStored ? item.source.name : item.source_name;
      const targetName = isStored ? item.target.name : item.target_name;
      const sourceUid = isStored ? item.source.uid : item.source_uid;
      const targetUid = isStored ? item.target.uid : item.target_uid;
      const key = isStored ? item.relationship_id : `${item.source_uid}-${item.target_uid}`;

      return html`<${Card} key=${key} className="mb-2">
        <div className="row-between mb-1">
          <div className="row" style=${{ gap: "9px" }}>
            <button className="link-btn strong" style=${{ fontSize: "14px" }}
              onClick=${() => navigate(`/entity/${sourceUid}`)}>${sourceName}</button>
            <span className="muted">⟷</span>
            <button className="link-btn strong" style=${{ fontSize: "14px" }}
              onClick=${() => navigate(`/entity/${targetUid}`)}>${targetName}</button>
            ${isStored ? html`<${EvidenceBadge} status=${item.evidence_status} />` : html`<${Pill} kind="inferred">Inferred<//>`}
          </div>
          <div className="row">
            <span className="small muted">Confidence</span>
            <span className="strong" style=${{ fontSize: "15px", color: "var(--indigo)" }}>
              ${fmt.percent(item.confidence)}
            </span>
          </div>
        </div>

        <div className="reason-box">
          <div className="reason-label">Why this was surfaced</div>
          ${item.reason || "No stated reason."}
          ${item.method ? html`<div className="tiny mt-1" style=${{ opacity: .8 }}>Method: ${item.method}</div>` : null}
        </div>

        ${item.shared_entities?.length
          ? html`<div className="mb-1">
              <span className="small strong">Shared intermediaries: </span>
              ${item.shared_entities.map((entity) => html`<button
                key=${entity.uid} className="chip" style=${{ padding: "2px 8px", fontSize: "11px", marginRight: "5px" }}
                onClick=${() => navigate(`/entity/${entity.uid}`)}
              >
                <span className="chip-swatch" style=${{ background: entityColor(entity.type) }}></span>
                ${entity.name}
              </button>`)}
            </div>`
          : null}

        ${item.supporting?.length
          ? html`<div className="mb-1">
              <div className="small strong mb-1">Supporting records (${item.supporting.length})</div>
              ${item.supporting.slice(0, 4).map((support) => html`<div className="kv-row" key=${support.relationship_id}>
                <span className="kv-key tiny">${support.description}</span>
                <span className="kv-val tiny">
                  <${EvidenceBadge} status=${support.evidence_status} /> ${support.source_ref || ""}
                </span>
              </div>`)}
            </div>`
          : null}

        <div className="row mt-1">
          ${isStored
            ? html`<${Button} size="sm" onClick=${() => setEvidenceId(item.relationship_id)}>
                View full evidence
              <//>`
            : null}
          ${isStored && item.requires_validation && canValidate
            ? html`
                <${Button} key="ok" size="sm" variant="success" onClick=${() => decide(item.relationship_id, "VALIDATED")}>
                  Validate
                <//>
                <${Button} key="no" size="sm" variant="danger" onClick=${() => decide(item.relationship_id, "REJECTED")}>
                  Reject
                <//>
                <${Button} key="rev" size="sm" onClick=${() => decide(item.relationship_id, "UNDER_REVIEW")}>
                  Mark for review
                <//>`
            : null}
          <${Button} size="sm" onClick=${() => navigate("/network", { root: sourceUid })}>
            Investigate in graph →
          <//>
          ${isStored && item.validated_at
            ? html`<span className="tiny muted">Decided ${fmt.dateTime(item.validated_at)}</span>`
            : null}
        </div>

        ${item.disclaimer
          ? html`<div className="tiny muted mt-1">${item.disclaimer}</div>` : null}
      <//>`;
    })}

    ${evidenceId
      ? html`<${EvidenceModal}
          relationshipId=${evidenceId} onClose=${() => setEvidenceId(null)}
          onDecision=${() => { setEvidenceId(null); reload(); }} canValidate=${canValidate}
        />`
      : null}
  </div>`;
}
