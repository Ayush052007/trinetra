/** Investigation timeline. */

import {
  html, useState,
  Card, Button, Pill, EmptyState, LoadingBlock, ErrorBlock,
  useAsync, fmt,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { EvidenceModal } from "../components/EvidenceModal.js";

const TYPE_COLORS = {
  communication: "#1f9d63", meeting: "#6d4fd1", transaction: "#c9a227",
  location_activity: "#2f6fed", vehicle_sighting: "#6b7280", complaint: "#c9376b",
  witness_statement: "#0ea5a5", stalking_report: "#c62b39", entity_resolution: "#4338ca",
  risk_update: "#e07a1f", entity_link: "#4338ca", sim_purchase: "#c9a227",
  confrontation: "#c62b39",
};

export function TimelinePage({ navigate, user, caseId, params }) {
  const [types, setTypes] = useState([]);
  const [entityUid, setEntityUid] = useState(params.entity || "");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [evidenceId, setEvidenceId] = useState(null);
  const anchor = params.event;

  const { data, loading, error, reload } = useAsync(
    () => api.get("/timeline", {
      case_id: caseId || undefined,
      entity_uid: entityUid || undefined,
      types: types.length ? types.join(",") : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: 300,
    }),
    [caseId, entityUid, JSON.stringify(types), dateFrom, dateTo]
  );

  const canValidate = (user.permissions || []).includes("relationship:validate");

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Investigation Timeline</h1>
        <p>
          Chronological view of calls, meetings, transactions, sightings and case events,
          built from stored records. Selecting an event opens the underlying record.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <${Card} className="mb-2">
      <div className="row">
        <span className="small strong">Event type</span>
        ${(data?.available_types || []).map((type) => html`<button
          key=${type.key} className=${`chip ${types.includes(type.key) ? "active" : ""}`}
          onClick=${() => setTypes((c) => c.includes(type.key) ? c.filter((t) => t !== type.key) : [...c, type.key])}
        >
          <span className="chip-swatch" style=${{ background: TYPE_COLORS[type.key] || "#8892ab" }}></span>
          ${type.label} <span className="tiny muted">${type.count}</span>
        </button>`)}
        ${types.length ? html`<button className="link-btn" onClick=${() => setTypes([])}>All types</button>` : null}
      </div>
      <div className="row mt-2">
        <div className="field" style=${{ margin: 0 }}>
          <label className="tiny">From</label>
          <input className="input" type="date" value=${dateFrom} onInput=${(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="field" style=${{ margin: 0 }}>
          <label className="tiny">To</label>
          <input className="input" type="date" value=${dateTo} onInput=${(e) => setDateTo(e.target.value)} />
        </div>
        <div className="field" style=${{ margin: 0, flex: 1, minWidth: "180px" }}>
          <label className="tiny">Entity ID</label>
          <input className="input" placeholder="e.g. p1, S1, VEH1" value=${entityUid}
            onInput=${(e) => setEntityUid(e.target.value.trim())} />
        </div>
        ${(dateFrom || dateTo || entityUid)
          ? html`<${Button} size="sm" onClick=${() => { setDateFrom(""); setDateTo(""); setEntityUid(""); }}>
              Clear filters
            <//>`
          : null}
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <${Card}
      title=${`${data?.count || 0} event${data?.count === 1 ? "" : "s"}`}
      subtitle=${data?.range?.from
        ? `${fmt.date(data.range.from)} — ${fmt.date(data.range.to)}`
        : null}
    >
      ${loading && !data ? html`<${LoadingBlock} rows=${6} />` : null}
      ${data && data.items.length === 0
        ? html`<${EmptyState}
            icon="◷" title="No events match these filters"
            text="Widen the date range or clear the type filter."
          />`
        : null}
      ${data && data.items.length
        ? html`<div style=${{ position: "relative", paddingLeft: "22px" }}>
            <div style=${{
              position: "absolute", left: "7px", top: "10px", bottom: "10px",
              width: "2px", background: "var(--line)",
            }}></div>
            ${data.items.map((event) => {
              const color = TYPE_COLORS[event.type] || "#8892ab";
              const highlighted = anchor === event.uid;
              return html`<div
                key=${event.uid}
                style=${{
                  position: "relative", padding: "11px 13px", marginBottom: "8px",
                  borderRadius: "10px",
                  background: highlighted ? "var(--indigo-50)" : "transparent",
                  border: highlighted ? "1px solid #c9d2fb" : "1px solid transparent",
                }}
              >
                <span style=${{
                  position: "absolute", left: "-21px", top: "17px", width: "11px", height: "11px",
                  borderRadius: "50%", background: color, border: "2.5px solid var(--surface)",
                  boxShadow: `0 0 0 1.5px ${color}`,
                }}></span>
                <div className="row-between">
                  <div style=${{ flex: 1, minWidth: 0 }}>
                    <div className="row" style=${{ gap: "8px", marginBottom: "3px" }}>
                      <span className="strong" style=${{ fontSize: "11.5px", color }}>
                        ${event.time_label || fmt.dateTime(event.occurred_at)}
                      </span>
                      <${Pill} kind="neutral">${event.type_label}<//>
                    </div>
                    <div style=${{ fontSize: "13.4px", fontWeight: 560 }}>${event.title}</div>
                    <div className="row tiny muted mt-1">
                      ${event.entity
                        ? html`<button className="link-btn" onClick=${() => navigate(`/entity/${event.entity.uid}`)}>
                            ${event.entity.name}
                          </button>`
                        : null}
                      ${event.location
                        ? html`<span>· at ${event.location.name}</span>` : null}
                      ${event.case_id
                        ? html`<button className="link-btn" onClick=${() => navigate(`/cases/${event.case_id}`)}>
                            Open case
                          </button>`
                        : null}
                    </div>
                  </div>
                  ${event.relationship_id
                    ? html`<${Button} size="sm" onClick=${() => setEvidenceId(event.relationship_id)}>
                        Source record
                      <//>`
                    : null}
                </div>
              </div>`;
            })}
          </div>`
        : null}
    <//>

    ${evidenceId
      ? html`<${EvidenceModal}
          relationshipId=${evidenceId} onClose=${() => setEvidenceId(null)}
          onDecision=${() => { setEvidenceId(null); reload(); }} canValidate=${canValidate}
        />`
      : null}
  </div>`;
}
