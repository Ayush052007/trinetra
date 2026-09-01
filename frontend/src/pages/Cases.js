/** Case management. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock, Modal,
  useAsync, fmt, entityColor, BAND_COLORS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { GraphCanvas } from "../components/GraphCanvas.js";

export function CasesPage({ navigate, user, params }) {
  const [statusFilter, setStatusFilter] = useState(params.status || null);
  const [creating, setCreating] = useState(false);
  const canCreate = (user.permissions || []).includes("case:create");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/cases", { status: statusFilter || undefined }), [statusFilter]
  );

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Cases</h1>
        <p>Investigation case files, their linked entities and outstanding review items.</p>
      </div>
      <div className="page-head-actions">
        ${canCreate ? html`<${Button} variant="primary" size="sm" onClick=${() => setCreating(true)}>
          New case
        <//>` : null}
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${!statusFilter ? "active" : ""}`} onClick=${() => setStatusFilter(null)}>All</button>
      <button className=${`chip ${statusFilter === "active" ? "active" : ""}`} onClick=${() => setStatusFilter("active")}>Active</button>
      ${(data?.statuses || []).map((s) => html`<button
        key=${s} className=${`chip ${statusFilter === s ? "active" : ""}`}
        onClick=${() => setStatusFilter(s)}
      >${fmt.title(s)}</button>`)}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${4} /><//>` : null}

    ${data && data.items.length === 0
      ? html`<${EmptyState} title="No cases" text="No case files match this filter." />`
      : null}

    <div className="grid-2">
      ${(data?.items || []).map((item) => html`<${Card} key=${item.id} className="clickable">
        <div className="row-between mb-1">
          <div>
            <div className="row" style=${{ gap: "8px" }}>
              <button className="link-btn strong" style=${{ fontSize: "15px", padding: 0 }}
                onClick=${() => navigate(`/cases/${item.id}`)}>${item.case_number}</button>
              <${Pill} kind=${item.module === "WOMEN_SAFETY" ? "rose" : "info"}>
                ${item.module === "WOMEN_SAFETY" ? "Women Safety" : "Network"}
              <//>
            </div>
            <div className="small strong mt-1">${item.title}</div>
          </div>
          <div style=${{ textAlign: "right" }}>
            <${Pill} kind=${item.priority}>${item.priority}<//>
            <div className="tiny muted mt-1">${fmt.title(item.status)}</div>
          </div>
        </div>
        <div className="small muted" style=${{ lineHeight: 1.55 }}>
          ${(item.description || "").slice(0, 170)}${(item.description || "").length > 170 ? "…" : ""}
        </div>
        <div className="row mt-2 tiny muted">
          <span>${fmt.number(item.entity_count)} entities</span>
          <span>· ${fmt.number(item.relationship_count)} relationships</span>
          ${item.pending_validation
            ? html`<${Pill} kind="inferred">${item.pending_validation} awaiting validation<//>`
            : null}
        </div>
        <div className="row mt-1 tiny muted">
          <span>Owner: ${item.owner || "unassigned"}</span>
          <span>· Opened ${fmt.date(item.opened_at)}</span>
        </div>
        <div className="row mt-2">
          <${Button} key="open" size="sm" onClick=${() => navigate(`/cases/${item.id}`)}>Open case file<//>
          <${Button} key="scope" size="sm" onClick=${() => navigate("/", { case_id: item.id })}>Scope dashboard<//>
        </div>
      <//>`)}
    </div>

    ${creating
      ? html`<${NewCaseModal} onClose=${() => setCreating(false)}
          onCreated=${(created) => { setCreating(false); reload(); navigate(`/cases/${created.id}`); }} />`
      : null}
  </div>`;
}

function NewCaseModal({ onClose, onCreated }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [module, setModule] = useState("NETWORK");
  const [priority, setPriority] = useState("MEDIUM");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const submit = async () => {
    if (title.trim().length < 3) {
      toast.push("A case title of at least 3 characters is required.", "error");
      return;
    }
    setSaving(true);
    try {
      const created = await api.post("/cases", {
        title: title.trim(), description: description.trim() || null, module, priority,
      });
      toast.push(`Case ${created.case_number} created.`, "success");
      onCreated(created);
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return html`<${Modal}
    title="Create case" onClose=${onClose}
    footer=${html`<div className="row">
      <${Button} onClick=${onClose}>Cancel<//>
      <${Button} variant="primary" loading=${saving} onClick=${submit}>Create case<//>
    </div>`}
  >
    <div className="field">
      <label>Case title</label>
      <input className="input" value=${title} autoFocus onInput=${(e) => setTitle(e.target.value)}
        placeholder="e.g. Financial Network Investigation" />
    </div>
    <div className="field">
      <label>Description</label>
      <textarea className="input" rows="3" value=${description}
        onInput=${(e) => setDescription(e.target.value)}
        placeholder="Scope, source records, background…"></textarea>
    </div>
    <div className="row">
      <div className="field" style=${{ flex: 1 }}>
        <label>Module</label>
        <select className="input" value=${module} onChange=${(e) => setModule(e.target.value)}>
          <option value="NETWORK">Criminal Network</option>
          <option value="WOMEN_SAFETY">Women Safety</option>
        </select>
      </div>
      <div className="field" style=${{ flex: 1 }}>
        <label>Priority</label>
        <select className="input" value=${priority} onChange=${(e) => setPriority(e.target.value)}>
          ${["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((p) => html`<option key=${p} value=${p}>${p}</option>`)}
        </select>
      </div>
    </div>
    <div className="tiny muted">The case number is allocated automatically.</div>
  <//>`;
}

// ============================================================ case detail

export function CaseDetailPage({ caseIdParam, navigate, user }) {
  const [tab, setTab] = useState("overview");
  const [note, setNote] = useState("");
  const toast = useToast();
  const perms = user.permissions || [];

  const { data, loading, error, reload } = useAsync(
    () => api.get(`/cases/${caseIdParam}`), [caseIdParam]
  );
  const graph = useAsync(
    () => (tab === "network" ? api.get(`/graph/case/${caseIdParam}`) : Promise.resolve(null)),
    [caseIdParam, tab], { immediate: false }
  );
  React.useEffect(() => { if (tab === "network") graph.reload(); }, [tab, caseIdParam]);

  const changeStatus = useCallback(async (status) => {
    try {
      await api.patch(`/cases/${caseIdParam}`, { status });
      toast.push(`Case moved to ${fmt.title(status)}.`, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [caseIdParam, reload, toast]);

  const addNote = useCallback(async () => {
    if (!note.trim()) return;
    try {
      await api.post(`/cases/${caseIdParam}/notes`, { body: note.trim() });
      setNote("");
      toast.push("Note added to the case file.", "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [caseIdParam, note, reload, toast]);

  if (loading && !data) return html`<${LoadingBlock} rows=${6} />`;
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;
  if (!data) return null;

  const counts = data.counts || {};

  return html`<div>
    <div className="breadcrumb">
      <button onClick=${() => navigate("/")}>Dashboard</button><span>›</span>
      <button onClick=${() => navigate("/cases")}>Cases</button><span>›</span>
      <span>${data.case_number}</span>
    </div>

    <div className="page-head">
      <div className="page-head-main">
        <div className="row" style=${{ gap: "10px" }}>
          <h1>${data.case_number}</h1>
          <${Pill} kind=${data.priority}>${data.priority}<//>
          <${Pill} kind=${data.module === "WOMEN_SAFETY" ? "rose" : "info"}>
            ${data.module === "WOMEN_SAFETY" ? "Women Safety" : "Network"}
          <//>
          <${Pill} kind="neutral">${fmt.title(data.status)}<//>
        </div>
        <p className="mt-1">${data.title} — ${data.description}</p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${() => navigate("/", { case_id: data.id })}>Scope dashboard<//>
        ${perms.includes("report:generate")
          ? html`<${Button} size="sm" variant="primary" onClick=${() => navigate("/reports", { case_id: data.id })}>
              Generate report
            <//>` : null}
      </div>
    </div>

    ${data.allowed_transitions?.length && perms.includes("case:update")
      ? html`<${Card} className="mb-2">
          <div className="row">
            <span className="small strong">Move case to</span>
            ${data.allowed_transitions.map((status) => html`<${Button}
              key=${status} size="sm"
              variant=${status === "CLOSED" ? "danger" : "secondary"}
              onClick=${() => changeStatus(status)}
            >${fmt.title(status)}<//>`)}
            ${data.allowed_transitions.includes("CLOSED") && !perms.includes("case:close")
              ? html`<span className="tiny muted">Closing requires Supervisory Officer authority.</span>`
              : null}
          </div>
        <//>`
      : null}

    <div className="grid-4 mb-2">
      ${[
        ["Entities", counts.entities], ["Relationships", counts.relationships],
        ["Observed", counts.observed], ["Inferred", counts.inferred],
        ["Validated", counts.validated], ["Events", counts.events],
        ["Evidence", counts.evidence], ["Incidents", counts.incidents],
      ].map(([label, value]) => html`<div className="card card-pad" key=${label}>
        <div className="kpi-label">${label}</div>
        <div style=${{ fontSize: "20px", fontWeight: 700 }}>${fmt.number(value || 0)}</div>
      </div>`)}
    </div>

    <div className="graph-toolbar">
      ${[["overview", "Overview"], ["entities", "Entities"], ["network", "Network"], ["notes", "Notes"]]
        .map(([key, label]) => html`<button
          key=${key} className=${`chip ${tab === key ? "active" : ""}`} onClick=${() => setTab(key)}
        >${label}</button>`)}
    </div>

    ${tab === "overview" ? html`<div className="grid-2">
      <${Card} title="Case team">
        ${data.team.map((member) => html`<div className="kv-row" key=${member.service_id}>
          <span className="kv-key">${member.name} <span className="tiny">(${member.service_id})</span></span>
          <span className="kv-val">
            ${member.role_on_case}
            <div className="tiny muted">${member.role_label}</div>
          </span>
        </div>`)}
      <//>
      <${Card} title="Case details">
        <div className="kv-row"><span className="kv-key">Owner</span><span className="kv-val">${data.owner || "—"}</span></div>
        <div className="kv-row"><span className="kv-key">Opened</span><span className="kv-val">${fmt.date(data.opened_at)}</span></div>
        ${data.closed_at ? html`<div className="kv-row"><span className="kv-key">Closed</span><span className="kv-val">${fmt.date(data.closed_at)}</span></div>` : null}
        <div className="kv-row"><span className="kv-key">Classification</span><span className="kv-val">${data.classification}</span></div>
        <div className="kv-row"><span className="kv-key">Status</span><span className="kv-val">${fmt.title(data.status)}</span></div>
      <//>
    </div>` : null}

    ${tab === "entities" ? html`<${Card} title=${`Linked entities (${data.entities.length})`}>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Entity</th><th>Type</th><th>Role in case</th><th>Priority</th></tr></thead>
          <tbody>
            ${data.entities.map((entity) => html`<tr key=${entity.uid} className="clickable"
              onClick=${() => navigate(`/entity/${entity.uid}`)}>
              <td className="strong">${entity.name}</td>
              <td>
                <span className="chip-swatch" style=${{
                  background: entityColor(entity.type), display: "inline-block", marginRight: "6px",
                }}></span>${fmt.title(entity.type)}
              </td>
              <td>${entity.role_in_case || "—"}</td>
              <td>${entity.priority_band
                ? html`<${Pill} kind=${entity.priority_band}>${fmt.score(entity.priority_score)}<//>`
                : html`<span className="muted tiny">—</span>`}</td>
            </tr>`)}
          </tbody>
        </table>
      </div>
    <//>` : null}

    ${tab === "network" ? html`<div>
      ${graph.loading
        ? html`<div className="card card-pad"><${LoadingBlock} rows=${5} /></div>`
        : html`<${GraphCanvas}
            nodes=${graph.data?.nodes || []} edges=${graph.data?.edges || []}
            onNodeClick=${(uid) => navigate(`/entity/${uid}`)}
          />`}
    </div>` : null}

    ${tab === "notes" ? html`<${Card} title=${`Case notes (${data.notes.length})`}>
      ${perms.includes("case:update")
        ? html`<div className="mb-2">
            <textarea className="input" rows="3" value=${note} placeholder="Add a note to the case file…"
              onInput=${(e) => setNote(e.target.value)}></textarea>
            <div className="row mt-1">
              <${Button} size="sm" variant="primary" onClick=${addNote} disabled=${!note.trim()}>Add note<//>
            </div>
          </div>`
        : null}
      ${data.notes.length
        ? data.notes.map((item) => html`<div className="evidence-block" key=${item.id}>
            <div className="evidence-head">
              <span className="strong small">${item.author || "Unknown"}</span>
              <span className="tiny muted">${fmt.dateTime(item.created_at)}</span>
            </div>
            <div className="evidence-desc">${item.body}</div>
          </div>`)
        : html`<${EmptyState} title="No notes" text="No notes have been added to this case." />`}
    <//>` : null}
  </div>`;
}
