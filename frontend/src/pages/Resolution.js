/** Entity resolution review queue. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EmptyState, LoadingBlock, ErrorBlock,
  FactorList, Disclaimer, useAsync, fmt, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";

export function ResolutionPage({ navigate, user, params }) {
  const [status, setStatus] = useState("PENDING");
  const [expanded, setExpanded] = useState(
    params.candidate ? Number(params.candidate) : null
  );
  const [busy, setBusy] = useState(null);
  const toast = useToast();
  const canDecide = (user.permissions || []).includes("resolution:decide");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/resolution/candidates", { status, limit: 60 }), [status]
  );

  const decide = useCallback(async (candidateId, decision) => {
    setBusy(`${candidateId}-${decision}`);
    try {
      const result = await api.post(`/resolution/candidates/${candidateId}/decide`, { decision });
      toast.push(result.message, decision === "REJECTED" ? "warn" : "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setBusy(null);
    }
  }, [reload, toast]);

  const refreshCandidates = useCallback(async () => {
    try {
      const result = await api.post("/resolution/refresh");
      toast.push(`Found ${result.new_candidates} new match candidate(s).`, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [reload, toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Entity Resolution</h1>
        <p>
          Records that may describe the same person. Nothing is merged automatically —
          each match is proposed with its contributing factors and requires an
          investigator decision.
        </p>
      </div>
      <div className="page-head-actions">
        ${canDecide ? html`<${Button} size="sm" onClick=${refreshCandidates}>Re-scan for matches<//>` : null}
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <div className="graph-toolbar">
      ${["PENDING", "ACCEPTED", "REJECTED", "UNDER_REVIEW", "ALL"].map((value) => html`<button
        key=${value} className=${`chip ${status === value ? "active" : ""}`}
        onClick=${() => setStatus(value)}
      >
        ${fmt.title(value)}
        ${data?.status_counts?.[value] ? html`<span className="tiny muted">${data.status_counts[value]}</span>` : ""}
      </button>`)}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${5} /><//>` : null}

    ${data && data.items.length === 0
      ? html`<${EmptyState}
          icon="✓" title="No candidates in this view"
          text=${status === "PENDING"
            ? "Every proposed identity match has been decided."
            : "No records with this status."}
        />`
      : null}

    ${(data?.items || []).map((candidate) => {
      const open = expanded === candidate.id;
      const strong = candidate.confidence >= 0.8;
      return html`<${Card} key=${candidate.id} className="mb-2">
        <div className="row-between mb-2">
          <div className="row" style=${{ gap: "14px", flexWrap: "wrap" }}>
            <div>
              <button className="link-btn strong" style=${{ fontSize: "14.5px", padding: 0 }}
                onClick=${() => navigate(`/entity/${candidate.entity_a.uid}`)}>
                ${candidate.entity_a.name}
              </button>
              <div className="tiny muted">
                ${candidate.entity_a.uid}
                ${candidate.entity_a.aliases?.length ? ` · aka ${candidate.entity_a.aliases.join(", ")}` : ""}
              </div>
            </div>
            <span className="muted" style=${{ fontSize: "17px" }}>⟷</span>
            <div>
              <button className="link-btn strong" style=${{ fontSize: "14.5px", padding: 0 }}
                onClick=${() => navigate(`/entity/${candidate.entity_b.uid}`)}>
                ${candidate.entity_b.name}
              </button>
              <div className="tiny muted">
                ${candidate.entity_b.uid}
                ${candidate.entity_b.aliases?.length ? ` · aka ${candidate.entity_b.aliases.join(", ")}` : ""}
              </div>
            </div>
          </div>
          <div style=${{ textAlign: "right" }}>
            <div className="tiny muted">Match confidence</div>
            <div style=${{
              fontSize: "22px", fontWeight: 700,
              color: strong ? "var(--orange)" : "var(--indigo)",
            }}>${fmt.percent(candidate.confidence)}</div>
            <${Pill} kind=${candidate.status === "PENDING" ? "inferred"
              : candidate.status === "ACCEPTED" ? "validated" : "rejected"}>
              ${candidate.status === "PENDING" ? "Review required" : fmt.title(candidate.status)}
            <//>
          </div>
        </div>

        <${Button} size="sm" onClick=${() => setExpanded(open ? null : candidate.id)}>
          ${open ? "Hide matching factors" : "Show matching factors"}
        <//>

        ${open
          ? html`<div className="mt-2">
              <${FactorList} factors=${candidate.matching_factors.map((f) => ({
                key: f.key, label: f.label, detail: f.detail,
                contribution: f.contribution * 100, weight: f.weight,
              }))} />
              <div className="tiny muted mt-1">Algorithm ${candidate.algorithm_version}</div>
            </div>`
          : null}

        ${candidate.status === "PENDING" && canDecide
          ? html`<div className="row mt-2">
              <${Button} key="ok" size="sm" variant="success"
                loading=${busy === `${candidate.id}-ACCEPTED`}
                onClick=${() => decide(candidate.id, "ACCEPTED")}>
                Accept match
              <//>
              <${Button} key="no" size="sm" variant="danger"
                loading=${busy === `${candidate.id}-REJECTED`}
                onClick=${() => decide(candidate.id, "REJECTED")}>
                Reject
              <//>
              <${Button} key="rev" size="sm"
                loading=${busy === `${candidate.id}-UNDER_REVIEW`}
                onClick=${() => decide(candidate.id, "UNDER_REVIEW")}>
                Needs more evidence
              <//>
              <span className="tiny muted">
                Accepting records an alias relationship and deactivates the absorbed record. Reversible.
              </span>
            </div>`
          : candidate.decided_at
            ? html`<div className="tiny muted mt-2">Decided ${fmt.dateTime(candidate.decided_at)}</div>`
            : null}

        ${candidate.status === "PENDING"
          ? html`<div className="mt-2"><${Disclaimer} subtle>${candidate.disclaimer}<//></div>`
          : null}
      <//>`;
    })}
  </div>`;
}
