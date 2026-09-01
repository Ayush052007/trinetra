/**
 * Evidence inspector.
 *
 * This is where "explainable AI" has to actually hold up: it shows the reason,
 * the method, the confidence, the direct evidence records, and the specific
 * supporting relationships an inferred link was derived from - then offers the
 * investigator decision that changes the stored record.
 */

import {
  html, useState, useCallback,
  Modal, Button, EvidenceBadge, Pill, LoadingBlock, ErrorBlock, Disclaimer,
  useAsync, fmt, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";

export function EvidenceModal({ relationshipId, onClose, onDecision, canValidate }) {
  const [deciding, setDeciding] = useState(null);
  const [rationale, setRationale] = useState("");
  const toast = useToast();

  const { data, loading, error, reload } = useAsync(
    () => api.get(`/graph/relationship/${relationshipId}/evidence`),
    [relationshipId]
  );

  const decide = useCallback(async (decision) => {
    setDeciding(decision);
    try {
      const result = await api.post(`/graph/relationship/${relationshipId}/validate`, {
        decision,
        rationale: rationale.trim() || null,
      });
      toast.push(result.message, decision === "REJECTED" ? "warn" : "success");
      if (onDecision) onDecision(result);
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setDeciding(null);
    }
  }, [relationshipId, rationale, onDecision, toast]);

  const isInferred = data && ["INFERRED", "UNDER_REVIEW"].includes(data.evidence_status);

  const footer = data && isInferred && canValidate
    ? html`<div style=${{ width: "100%" }}>
        <div className="field" style=${{ marginBottom: "11px" }}>
          <label htmlFor="rationale">Rationale (recorded in the audit log)</label>
          <textarea
            id="rationale" className="input" rows="2" value=${rationale}
            placeholder="Why are you accepting or rejecting this connection?"
            onInput=${(e) => setRationale(e.target.value)}
          ></textarea>
        </div>
        <div className="row" style=${{ justifyContent: "flex-end" }}>
          <${Button} onClick=${onClose}>Cancel<//>
          <${Button} variant="secondary" loading=${deciding === "UNDER_REVIEW"}
            onClick=${() => decide("UNDER_REVIEW")}>Mark for review<//>
          <${Button} variant="danger" loading=${deciding === "REJECTED"}
            onClick=${() => decide("REJECTED")}>Reject<//>
          <${Button} variant="success" loading=${deciding === "VALIDATED"}
            onClick=${() => decide("VALIDATED")}>Validate<//>
        </div>
      </div>`
    : html`<${Button} onClick=${onClose}>Close<//>`;

  return html`<${Modal}
    size="wide" onClose=${onClose} footer=${footer}
    title="Evidence"
    subtitle=${data
      ? `${data.source?.name || "?"} — ${fmt.title(data.type)} — ${data.target?.name || "?"}`
      : "Loading…"}
  >
    ${loading ? html`<${LoadingBlock} rows=${5} />` : null}
    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    ${data
      ? html`<div className="stack">
          <div className="row" style=${{ gap: "10px" }}>
            <${EvidenceBadge} status=${data.evidence_status} />
            <${Pill} kind="neutral">Confidence ${fmt.percent(data.confidence)}<//>
            ${data.source_ref ? html`<span className="small muted">Source: ${data.source_ref}</span>` : null}
            ${data.time_label || data.occurred_at
              ? html`<span className="small muted">· ${data.time_label || fmt.date(data.occurred_at)}</span>`
              : null}
          </div>

          ${data.is_observed
            ? html`<div className="alert alert-success" style=${{ marginBottom: 0 }}>
                <span>✓</span>
                <div>
                  <strong>Directly observed</strong>
                  This relationship is recorded in a source document. It is not an
                  analytical inference and does not require validation.
                </div>
              </div>`
            : html`<div className="reason-box">
                <div className="reason-label">Why this was surfaced</div>
                ${data.reason || "No stated reason recorded."}
                ${data.method
                  ? html`<div className="tiny mt-1" style=${{ opacity: .8 }}>Method: ${data.method}</div>`
                  : null}
              </div>`}

          ${data.factors && data.factors.length
            ? html`<div>
                <div className="card-title mb-1">Contributing factors</div>
                ${data.factors.map((factor, i) => html`<div className="kv-row" key=${i}>
                  <span className="kv-key">${factor.label}</span>
                  <span className="kv-val">${factor.detail}</span>
                </div>`)}
              </div>`
            : null}

          ${data.direct_evidence && data.direct_evidence.length
            ? html`<div>
                <div className="card-title mb-1">
                  Direct evidence <span className="card-sub">(${data.direct_evidence.length})</span>
                </div>
                ${data.direct_evidence.map((item) => html`<div className="evidence-block" key=${item.evidence_ref}>
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
                </div>`)}
              </div>`
            : null}

          ${data.supporting_relationships && data.supporting_relationships.length
            ? html`<div>
                <div className="card-title mb-1">
                  Supporting relationships
                  <span className="card-sub">
                    (${data.supporting_relationships.length}) — the recorded links this inference was built from
                  </span>
                </div>
                ${data.supporting_relationships.map((item) => html`<div className="evidence-block" key=${item.relationship_id}>
                  <div className="evidence-head">
                    <span className="strong small">
                      ${item.source?.name || "?"} → ${fmt.title(item.type)} → ${item.target?.name || "?"}
                    </span>
                    <${EvidenceBadge} status=${item.evidence_status} />
                    <span className="tiny muted">${fmt.percent(item.confidence)}</span>
                  </div>
                  <div className="evidence-meta">
                    <span>Source: ${item.source_ref || "unspecified"}</span>
                    ${item.occurred_at ? html`<span>${fmt.date(item.occurred_at)}</span>` : null}
                  </div>
                  ${item.evidence && item.evidence.length
                    ? html`<div className="tiny muted mt-1">
                        Backed by: ${item.evidence.map((e) => e.evidence_ref).join(", ")}
                      </div>`
                    : null}
                </div>`)}
              </div>`
            : null}

          ${data.validation_history && data.validation_history.length
            ? html`<div>
                <div className="card-title mb-1">Validation history</div>
                ${data.validation_history.map((entry, i) => html`<div className="kv-row" key=${i}>
                  <span className="kv-key">
                    ${fmt.dateTime(entry.timestamp)} — ${entry.by || "unknown"}
                  </span>
                  <span className="kv-val">
                    <${EvidenceBadge} status=${entry.decision} />
                    ${entry.rationale ? html`<div className="tiny muted mt-1">${entry.rationale}</div>` : null}
                  </span>
                </div>`)}
              </div>`
            : null}

          ${!data.is_observed
            ? html`<${Disclaimer}>
                This is an inferred connection produced by analysis. It is not an
                observed fact and is not evidence of wrongdoing. Validating it records
                your decision against your account in the audit log and updates the
                knowledge graph; rejecting it removes the link from all analysis.
              <//>`
            : null}

          ${!canValidate && !data.is_observed
            ? html`<div className="alert alert-info" style=${{ marginBottom: 0 }}>
                <span>ⓘ</span>
                <div>Your role can view this evidence but cannot validate relationships.
                Confirming an inferred link into the case record is an investigator action.</div>
              </div>`
            : null}
        </div>`
      : null}
  <//>`;
}
