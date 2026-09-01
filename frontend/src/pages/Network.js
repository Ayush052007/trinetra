/** Network graph exploration. */

import {
  html, useState, useEffect, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock,
  useAsync, fmt, entityColor, ENTITY_LABELS, ENTITY_GLYPHS, BAND_COLORS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { GraphCanvas } from "../components/GraphCanvas.js";
import { EvidenceModal } from "../components/EvidenceModal.js";

const ALL_TYPES = Object.keys(ENTITY_LABELS);

export function NetworkPage({ navigate, user, caseId, params }) {
  const [rootUid, setRootUid] = useState(params.root || null);
  const [depth, setDepth] = useState(Number(params.depth) || 2);
  const [showInferred, setShowInferred] = useState(true);
  const [types, setTypes] = useState([]);
  const [search, setSearch] = useState("");
  const [layout, setLayout] = useState("cose");
  const [selected, setSelected] = useState(null);
  const [evidenceId, setEvidenceId] = useState(null);
  const [pathTarget, setPathTarget] = useState("");
  const [pathResult, setPathResult] = useState(null);
  const toast = useToast();

  // Without an explicit root, fall back to the case graph, else a lead entity.
  const { data, loading, error, reload } = useAsync(async () => {
    if (rootUid) {
      return api.get(`/graph/neighbourhood/${encodeURIComponent(rootUid)}`, {
        depth, include_inferred: showInferred,
      });
    }
    if (caseId) return api.get(`/graph/case/${caseId}`);
    const found = await api.get("/entities/search", { q: "Rahul Sharma", limit: 1 });
    if (found.results && found.results.length) {
      setRootUid(found.results[0].uid);
      return api.get(`/graph/neighbourhood/${found.results[0].uid}`, { depth, include_inferred: true });
    }
    return { nodes: [], edges: [], counts: {} };
  }, [rootUid, depth, showInferred, caseId]);

  const openEntity = useCallback(async (uid) => {
    try {
      const profile = await api.get(`/entities/${encodeURIComponent(uid)}`);
      setSelected(profile);
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [toast]);

  const findPath = useCallback(async () => {
    if (!rootUid || !pathTarget.trim()) return;
    try {
      const results = await api.get("/entities/search", { q: pathTarget, limit: 1 });
      if (!results.results.length) {
        toast.push(`No entity matches "${pathTarget}".`, "warn");
        return;
      }
      const target = results.results[0];
      const path = await api.get("/graph/path", { source: rootUid, target: target.uid });
      if (!path.found) {
        toast.push(`No connecting path found to ${target.name}.`, "warn");
        setPathResult(null);
        return;
      }
      setPathResult(path);
      toast.push(
        `Path found: ${path.shortest.length} hop${path.shortest.length === 1 ? "" : "s"} to ${target.name}.`,
        "success"
      );
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [rootUid, pathTarget, toast]);

  const nodes = data?.nodes || [];
  const edges = data?.edges || [];
  const presentTypes = [...new Set(nodes.map((n) => n.type))];

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Network Graph</h1>
        <p>
          Interactive relationship mapping. Solid edges are directly observed in source
          records; dashed indigo edges are AI-inferred and await investigator validation.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <div className="graph-toolbar">
      <span className="small strong">Expand</span>
      ${[1, 2, 3].map((d) => html`<button
        key=${d} className=${`chip ${depth === d ? "active" : ""}`}
        onClick=${() => setDepth(d)} disabled=${!rootUid}
      >${d}-hop</button>`)}

      <span style=${{ width: "1px", height: "20px", background: "var(--line)" }}></span>

      <label className="chip" style=${{ cursor: "pointer" }}>
        <input
          type="checkbox" checked=${showInferred} style=${{ margin: 0 }}
          onChange=${(e) => setShowInferred(e.target.checked)}
        />
        Show inferred links
      </label>

      <select className="input" style=${{ width: "auto", padding: "5px 9px" }}
        value=${layout} onChange=${(e) => setLayout(e.target.value)}>
        <option value="cose">Force layout</option>
        <option value="concentric">Concentric</option>
        <option value="breadthfirst">Hierarchy</option>
        <option value="circle">Circle</option>
        <option value="grid">Grid</option>
      </select>

      <div className="spacer"></div>

      <input
        className="input" style=${{ width: "190px" }} placeholder="Highlight in graph…"
        value=${search} onInput=${(e) => setSearch(e.target.value)}
      />
    </div>

    <div className="graph-toolbar" style=${{ marginTop: "-6px" }}>
      <span className="small strong">Entity types</span>
      ${presentTypes.map((type) => html`<button
        key=${type}
        className=${`chip ${types.length === 0 || types.includes(type) ? "active" : ""}`}
        onClick=${() => setTypes((current) =>
          current.includes(type) ? current.filter((t) => t !== type)
            : current.length === 0 ? presentTypes.filter((t) => t !== type)
            : [...current, type]
        )}
      >
        <span className="chip-swatch" style=${{ background: entityColor(type) }}></span>
        ${ENTITY_LABELS[type] || type}
      </button>`)}
      ${types.length ? html`<button className="link-btn" onClick=${() => setTypes([])}>Show all</button>` : null}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <div className="graph-layout">
      <div>
        ${loading && !data
          ? html`<div className="card card-pad"><${LoadingBlock} rows=${6} /></div>`
          : html`<${GraphCanvas}
              nodes=${nodes} edges=${edges} rootUid=${rootUid} layout=${layout}
              filterTypes=${types.length ? types : null} showInferred=${showInferred}
              searchTerm=${search}
              highlightPath=${pathResult?.shortest ? pathResult.shortest.nodes.map((n) => n.uid) : null}
              onNodeClick=${openEntity}
              onNodeExpand=${(uid) => { setRootUid(uid); setPathResult(null); }}
              onEdgeClick=${(edge) => {
                const match = edges.find((e) => e.uid === edge.id);
                if (match) {
                  const relId = match.uid;
                  api.get("/graph/hidden-links").then((links) => {
                    const stored = (links.stored || []).find((s) => s.uid === relId);
                    if (stored) setEvidenceId(stored.relationship_id);
                    else toast.push("This is a directly observed relationship.", "success");
                  }).catch(() => {});
                }
              }}
            />`}

        <div className="graph-legend">
          ${ALL_TYPES.filter((t) => presentTypes.includes(t)).map((type) => html`<span className="legend-item" key=${type}>
            <span className="legend-swatch" style=${{ background: entityColor(type) }}></span>
            ${ENTITY_LABELS[type]}
          </span>`)}
          <span key="obs" className="legend-item"><span className="legend-line" style=${{ borderColor: "#9aa4bf" }}></span> Observed</span>
          <span key="inf" className="legend-item"><span className="legend-line dashed" style=${{ borderColor: "#21518F" }}></span> Inferred</span>
          <span key="path" className="legend-item"><span className="legend-line" style=${{ borderColor: "#e07a1f" }}></span> Highlighted path</span>
        </div>

        ${data?.counts
          ? html`<div className="row mt-1 small muted">
              <span>${fmt.number(data.counts.nodes)} entities</span>
              <span>· ${fmt.number(data.counts.edges)} relationships</span>
              <span>· ${fmt.number(data.counts.observed)} observed</span>
              <span>· ${fmt.number(data.counts.inferred)} inferred</span>
              ${data.backend ? html`<span>· ${data.backend} graph backend</span>` : null}
            </div>`
          : null}
      </div>

      <div className="detail-panel">
        <${Card} title="Find connection">
          <div className="field" style=${{ marginBottom: "9px" }}>
            <input
              className="input" placeholder="Search for a second entity…"
              value=${pathTarget} onInput=${(e) => setPathTarget(e.target.value)}
              onKeyDown=${(e) => e.key === "Enter" && findPath()}
            />
          </div>
          <${Button} size="sm" variant="primary" onClick=${findPath} disabled=${!rootUid}>
            Find shortest path
          <//>
          ${pathResult?.shortest
            ? html`<div className="mt-2">
                <div className="small strong mb-1">
                  ${pathResult.shortest.length} hop${pathResult.shortest.length === 1 ? "" : "s"}
                  ${pathResult.shortest.all_observed
                    ? html` · <span style=${{ color: "var(--green)" }}>all observed</span>`
                    : html` · <span style=${{ color: "var(--indigo)" }}>includes inferred links</span>`}
                </div>
                ${pathResult.shortest.hops.map((hop, i) => html`<div className="kv-row" key=${i}>
                  <span className="kv-key tiny">${hop.from} → ${hop.to}</span>
                  <span className="kv-val tiny">
                    ${fmt.title(hop.type)} <${EvidenceBadge} status=${hop.evidence_status} />
                  </span>
                </div>`)}
              </div>`
            : null}
        <//>

        ${selected
          ? html`<${Card}
              title=${selected.name}
              subtitle=${`${selected.type_label}${selected.aliases?.length ? ` · aka ${selected.aliases.join(", ")}` : ""}`}
              actions=${html`<${Button} size="sm" onClick=${() => navigate(`/entity/${selected.uid}`)}>Full profile<//>`}
            >
              <div className="row mb-1">
                <${Button} size="sm" onClick=${() => { setRootUid(selected.uid); setPathResult(null); }}>
                  Centre graph here
                <//>
              </div>
              ${Object.entries(selected.summary || {})
                .filter(([, v]) => v > 0)
                .map(([key, value]) => html`<div className="kv-row" key=${key}>
                  <span className="kv-key">${fmt.title(key)}</span>
                  <span className="kv-val">${fmt.number(value)}</span>
                </div>`)}
              ${selected.priority
                ? html`<div className="mt-2">
                    <div className="row-between">
                      <span className="small strong">Investigation priority</span>
                      <span className="pill pill-${String(selected.priority.band).toLowerCase()}">
                        ${fmt.score(selected.priority.score)} ${selected.priority.band}
                      </span>
                    </div>
                    <div className="tiny muted mt-1">${selected.priority.factors?.[0]?.detail || ""}</div>
                  </div>`
                : null}
            <//>`
          : html`<${Card}>
              <div className="detail-empty">
                Click a node to inspect it.<br />
                <span className="tiny">Double-click to re-centre the graph on that entity.</span>
              </div>
            <//>`}
      </div>
    </div>

    ${evidenceId
      ? html`<${EvidenceModal}
          relationshipId=${evidenceId} onClose=${() => setEvidenceId(null)}
          onDecision=${() => { setEvidenceId(null); reload(); }}
          canValidate=${(user.permissions || []).includes("relationship:validate")}
        />`
      : null}
  </div>`;
}
