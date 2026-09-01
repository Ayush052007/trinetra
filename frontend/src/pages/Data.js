/** Data sources, ingestion and data management. */

import {
  html, useState, useCallback, useRef,
  Card, Button, Pill, EmptyState, LoadingBlock, ErrorBlock,
  useAsync, fmt, entityColor, ENTITY_LABELS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";

// ============================================================ data sources

export function DataSourcesPage({ navigate, user }) {
  const { data, loading, error, reload } = useAsync(() => api.get("/data/sources"), []);
  const jobs = useAsync(() => api.get("/data/jobs", { limit: 10 }), []);
  const canUpload = (user.permissions || []).includes("data:upload");

  if (loading && !data) return html`<${Card}><${LoadingBlock} rows=${5} /><//>`;
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Data Sources</h1>
        <p>Ingestion channels connected to TRINETRA, with live record counts from the database.</p>
      </div>
      <div className="page-head-actions">
        ${canUpload ? html`<${Button} variant="primary" size="sm" onClick=${() => navigate("/upload")}>
          Upload data
        <//>` : null}
      </div>
    </div>

    <div className="grid-3 mb-2">
      ${(data?.sources || []).map((source) => html`<${Card} key=${source.key}>
        <div className="row-between mb-1">
          <span className="strong">${source.label}</span>
          <${Pill} kind=${source.record_count ? "green" : "neutral"}>
            ${fmt.number(source.record_count)}
          <//>
        </div>
        <div className="small muted">${source.description}</div>
        <div className="tiny muted mt-1">Formats: ${source.formats}</div>
      <//>`)}
    </div>

    <div className="grid-2">
      <${Card} title="Ingestion pipeline" subtitle="Every upload runs through these stages">
        <div className="stage-list">
          ${(data?.pipeline || []).map((stage) => html`<div className="stage-item pending" key=${stage.key}>
            <span className="stage-icon">·</span>${stage.label}
          </div>`)}
        </div>
      <//>

      <${Card} title="Automated feeds">
        <div className="alert alert-warn" style=${{ marginBottom: "12px" }}>
          <span>⚠</span>
          <div>${data?.connected_feeds?.notice}</div>
        </div>
        ${Object.entries(data?.connected_feeds || {})
          .filter(([key]) => key !== "notice")
          .map(([key, enabled]) => html`<div className="kv-row" key=${key}>
            <span className="kv-key">${fmt.title(key)}</span>
            <span className="kv-val">
              <${Pill} kind=${enabled ? "green" : "neutral"}>
                ${enabled ? "Connected" : "Requires authorisation"}
              <//>
            </span>
          </div>`)}
      <//>
    </div>

    <${Card} title="Recent ingestion jobs" className="mt-2">
      ${jobs.data?.items?.length
        ? html`<div className="table-wrap">
            <table className="data">
              <thead><tr>
                <th>File</th><th>Source</th><th>Status</th>
                <th className="num">Received</th><th className="num">Processed</th>
                <th className="num">Duplicates</th><th className="num">Entities</th>
                <th className="num">Relationships</th><th>By</th><th>When</th>
              </tr></thead>
              <tbody>
                ${jobs.data.items.map((job) => html`<tr key=${job.id}>
                  <td className="mono tiny">${job.filename}</td>
                  <td>${job.source_type}</td>
                  <td><${Pill} kind=${job.status === "COMPLETE" ? "green" : job.status === "FAILED" ? "red" : "yellow"}>
                    ${job.status}
                  <//></td>
                  <td className="num">${fmt.number(job.counters.records_received)}</td>
                  <td className="num">${fmt.number(job.counters.records_processed)}</td>
                  <td className="num">${fmt.number(job.counters.duplicates)}</td>
                  <td className="num">${fmt.number(job.counters.entities_extracted)}</td>
                  <td className="num">${fmt.number(job.counters.relationships_created)}</td>
                  <td className="tiny">${job.uploaded_by || "—"}</td>
                  <td className="tiny nowrap">${fmt.relative(job.started_at)}</td>
                </tr>`)}
              </tbody>
            </table>
          </div>`
        : html`<${EmptyState} title="No ingestion jobs" text="No files have been uploaded yet." />`}
    <//>
  </div>`;
}

// ================================================================= upload

export function UploadPage({ navigate, caseId }) {
  const [file, setFile] = useState(null);
  const [sourceType, setSourceType] = useState("FIR");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const toast = useToast();

  const sources = useAsync(() => api.get("/data/sources"), []);

  const upload = useCallback(async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("source_type", sourceType);
      if (caseId) form.append("case_id", String(caseId));
      const outcome = await api.upload("/data/upload", form);
      setResult(outcome);
      toast.push(outcome.message, "success");
    } catch (err) {
      setError(err);
      toast.push(err.message, "error");
    } finally {
      setUploading(false);
    }
  }, [file, sourceType, caseId, toast]);

  const pipeline = sources.data?.pipeline || [];
  const completed = new Set((result?.stages || []).filter((s) => s.status === "complete").map((s) => s.stage));

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Data Ingestion</h1>
        <p>
          Upload case records for parsing, entity extraction and knowledge-graph
          construction. Reported counts are computed from the file you upload.
        </p>
      </div>
    </div>

    <div className="grid-2">
      <${Card} title="Upload a file">
        <div className="field">
          <label>Source type</label>
          <select className="input" value=${sourceType} onChange=${(e) => setSourceType(e.target.value)}>
            ${(sources.data?.sources || []).map((source) => html`<option key=${source.key} value=${source.key}>
              ${source.label}
            </option>`)}
          </select>
        </div>

        <div
          onDragOver=${(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave=${() => setDragging(false)}
          onDrop=${(e) => {
            e.preventDefault(); setDragging(false);
            if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
          }}
          onClick=${() => inputRef.current?.click()}
          style=${{
            border: `2px dashed ${dragging ? "var(--indigo)" : "var(--line)"}`,
            borderRadius: "11px", padding: "30px 18px", textAlign: "center",
            cursor: "pointer", background: dragging ? "var(--indigo-50)" : "var(--surface-alt)",
          }}
        >
          <div style=${{ fontSize: "26px", opacity: .4, marginBottom: "7px" }}>⇪</div>
          ${file
            ? html`<div>
                <div className="strong">${file.name}</div>
                <div className="tiny muted mt-1">${(file.size / 1024).toFixed(1)} KB</div>
              </div>`
            : html`<div>
                <div className="strong small">Drop a file here, or click to browse</div>
                <div className="tiny muted mt-1">
                  ${(sources.data?.allowed_extensions || [".csv", ".txt", ".json"]).join(" · ")}
                  · max ${sources.data?.max_upload_mb || 25} MB
                </div>
              </div>`}
          <input ref=${inputRef} type="file" style=${{ display: "none" }}
            accept=".csv,.txt,.json,.tsv"
            onChange=${(e) => setFile(e.target.files?.[0] || null)} />
        </div>

        <div className="row mt-2">
          <${Button} variant="primary" onClick=${upload} loading=${uploading} disabled=${!file}>
            Process data
          <//>
          ${file ? html`<${Button} onClick=${() => { setFile(null); setResult(null); }}>Clear<//>` : null}
        </div>

        <div className="tiny muted mt-2">
          Tabular rows become observed relationships. Free-text paragraphs in a .txt file
          are run through NLP extraction and stored as inferred, pending validation.
        </div>
      <//>

      <${Card} title="Processing" subtitle=${result ? `Job #${result.job_id}` : "Stages run in order"}>
        <div className="stage-list">
          ${pipeline.map((stage) => {
            const done = completed.has(stage.key);
            const detail = (result?.stages || []).find((s) => s.stage === stage.key)?.detail;
            return html`<div key=${stage.key}
              className=${`stage-item ${done ? "complete" : uploading ? "active" : "pending"}`}>
              <span className="stage-icon">${done ? "✓" : uploading ? "•" : "·"}</span>
              <span>${stage.label}</span>
              ${detail ? html`<span className="stage-detail">${detail}</span>` : null}
            </div>`;
          })}
        </div>

        ${error ? html`<div className="mt-2"><${ErrorBlock} error=${error} /></div>` : null}

        ${result
          ? html`<div className="mt-2">
              <div className="alert alert-success">
                <span>✓</span><div>${result.message}</div>
              </div>
              <div className="grid-4">
                ${[
                  ["Records received", result.counters.records_received],
                  ["Records processed", result.counters.records_processed],
                  ["Duplicates", result.counters.duplicates],
                  ["Entities extracted", result.counters.entities_extracted],
                  ["Relationships created", result.counters.relationships_created],
                ].map(([label, value]) => html`<div key=${label}>
                  <div className="kpi-label">${label}</div>
                  <div style=${{ fontSize: "19px", fontWeight: 700 }}>${fmt.number(value)}</div>
                </div>`)}
              </div>
              <div className="row mt-2">
                <${Button} size="sm" onClick=${() => navigate("/data-management")}>View ingested data<//>
                <${Button} size="sm" onClick=${() => navigate("/network")}>Open network graph<//>
              </div>
            </div>`
          : null}
      <//>
    </div>
  </div>`;
}

// ======================================================= data management

export function DataManagementPage({ navigate, caseId, params }) {
  const [type, setType] = useState(null);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, loading, error, reload } = useAsync(
    () => api.get("/entities", {
      type: type || undefined, q: query || undefined,
      case_id: caseId || undefined, offset, limit,
    }),
    [type, query, caseId, offset]
  );

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Data Management</h1>
        <p>Every entity currently held in the knowledge graph.</p>
      </div>
    </div>

    <${Card} className="mb-2">
      <input className="input" placeholder="Filter by name…" value=${query}
        onInput=${(e) => { setQuery(e.target.value); setOffset(0); }} />
      <div className="row mt-2">
        <button className=${`chip ${!type ? "active" : ""}`} onClick=${() => { setType(null); setOffset(0); }}>
          All types ${data ? html`<span className="tiny muted">${fmt.number(data.total)}</span>` : ""}
        </button>
        ${(data?.types || []).map((item) => html`<button
          key=${item.key} className=${`chip ${type === item.key ? "active" : ""}`}
          onClick=${() => { setType(item.key); setOffset(0); }}
        >
          <span className="chip-swatch" style=${{ background: entityColor(item.key) }}></span>
          ${item.label} <span className="tiny muted">${fmt.number(item.count)}</span>
        </button>`)}
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <${Card}>
      ${loading && !data ? html`<${LoadingBlock} rows=${6} />` : null}
      ${data && data.items.length === 0
        ? html`<${EmptyState} title="No entities match" text="Adjust the filter or search term." />`
        : null}
      ${data && data.items.length
        ? html`<div>
            <div className="table-wrap">
              <table className="data">
                <thead><tr>
                  <th>Name</th><th>Type</th><th>ID</th><th>Aliases</th>
                  <th className="num">Connections</th><th>Source</th><th>Classification</th>
                </tr></thead>
                <tbody>
                  ${data.items.map((item) => html`<tr key=${item.uid} className="clickable"
                    onClick=${() => navigate(`/entity/${item.uid}`)}>
                    <td className="strong">${item.name}</td>
                    <td>
                      <span className="chip-swatch" style=${{
                        background: entityColor(item.type), display: "inline-block", marginRight: "6px",
                      }}></span>${item.type_label}
                    </td>
                    <td className="mono tiny">${item.uid}</td>
                    <td className="tiny muted">${item.aliases?.join(", ") || "—"}</td>
                    <td className="num">${fmt.number(item.connections)}</td>
                    <td className="tiny muted">${item.source || "—"}</td>
                    <td className="tiny muted">${item.classification}</td>
                  </tr>`)}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <span className="pager-info">
                Showing ${offset + 1}–${Math.min(offset + limit, data.total)} of ${fmt.number(data.total)}
              </span>
              <div className="row">
                <${Button} size="sm" disabled=${offset === 0}
                  onClick=${() => setOffset(Math.max(0, offset - limit))}>Previous<//>
                <${Button} size="sm" disabled=${offset + limit >= data.total}
                  onClick=${() => setOffset(offset + limit)}>Next<//>
              </div>
            </div>
          </div>`
        : null}
    <//>
  </div>`;
}
