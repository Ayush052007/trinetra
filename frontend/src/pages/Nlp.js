/** AI & NLP analysis: unstructured text to entities and relationships. */

import {
  html, useState, useCallback, useMemo,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock,
  Disclaimer, useAsync, fmt, entityColor, ENTITY_LABELS, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";

const PIPELINE_LABELS = {
  tokenise: "Sentence segmentation", ner: "Named entity recognition",
  gazetteer: "Knowledge-graph lookup", classify: "Entity classification",
  normalise: "Normalisation", relations: "Relationship extraction",
  confidence: "Confidence scoring",
};

export function NlpPage({ navigate, user, caseId }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState(null);
  const [rejected, setRejected] = useState(new Set());
  const toast = useToast();
  const canCommit = (user.permissions || []).includes("relationship:create");

  const samples = useAsync(() => api.get("/nlp/sample"), []);

  const analyse = useCallback(async () => {
    if (!text.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    setRejected(new Set());
    try {
      setResult(await api.post("/nlp/analyze", { text, case_id: caseId || undefined }));
    } catch (err) {
      setError(err);
    } finally {
      setRunning(false);
    }
  }, [text, caseId]);

  const commit = useCallback(async () => {
    if (!result) return;
    setCommitting(true);
    try {
      const accepted = result.entities
        .filter((e) => e.type !== "event" && !rejected.has(`e-${e.start}`))
        .map((e) => e.text);
      const relationships = result.relationships
        .map((r, i) => i)
        .filter((i) => !rejected.has(`r-${i}`));
      const outcome = await api.post("/nlp/commit", {
        text, case_id: caseId || undefined,
        accept_entities: accepted, accept_relationships: relationships,
      });
      toast.push(outcome.message, "success");
      setResult(null);
      setText("");
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setCommitting(false);
    }
  }, [result, text, caseId, rejected, toast]);

  // Render the source text with each extraction highlighted in place.
  const highlighted = useMemo(() => {
    if (!result || !result.entities.length) return null;
    const spans = [...result.entities].sort((a, b) => a.start - b.start);
    const output = [];
    let cursor = 0;
    spans.forEach((span, index) => {
      if (span.start < cursor) return;
      if (span.start > cursor) output.push(text.slice(cursor, span.start));
      output.push(html`<mark
        key=${index}
        title=${`${ENTITY_LABELS[span.type] || span.type} · ${span.method} · ${fmt.percent(span.confidence)}\n${span.detail}`}
        style=${{
          background: `${entityColor(span.type)}22`,
          borderBottom: `2px solid ${entityColor(span.type)}`,
          padding: "1px 2px", borderRadius: "3px", color: "inherit",
        }}
      >${text.slice(span.start, span.end)}</mark>`);
      cursor = span.end;
    });
    if (cursor < text.length) output.push(text.slice(cursor));
    return output;
  }, [result, text]);

  const toggle = (key) => setRejected((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>AI & NLP Analysis</h1>
        <p>
          Convert an unstructured report into structured entities and typed
          relationships. Every extraction is anchored to the exact characters that
          produced it, so you can see precisely what the text said.
        </p>
      </div>
    </div>

    <${Card} title="Source text" subtitle="Paste an FIR extract, statement or case narrative">
      <textarea
        className="input" rows="7" value=${text}
        placeholder="Paste investigative text here…"
        onInput=${(e) => setText(e.target.value)}
        style=${{ fontFamily: "var(--font)", lineHeight: 1.6, resize: "vertical" }}
      ></textarea>
      <div className="row mt-2">
        <${Button} variant="primary" onClick=${analyse} loading=${running} disabled=${!text.trim()}>
          Analyse text
        <//>
        <${Button} onClick=${() => { setText(""); setResult(null); setError(null); }}>Clear<//>
        <div className="spacer"></div>
        ${(samples.data?.samples || []).map((sample) => html`<${Button}
          key=${sample.key} size="sm"
          onClick=${() => { setText(sample.text); setResult(null); }}
        >${sample.label}<//>`)}
      </div>
      <div className="tiny muted mt-1">
        ${text.length} character${text.length === 1 ? "" : "s"}
        ${caseId ? " · extractions will be linked to the selected case" : ""}
      </div>
    <//>

    ${error ? html`<div className="mt-2"><${ErrorBlock} error=${error} onRetry=${analyse} /></div>` : null}

    ${running
      ? html`<${Card} className="mt-2" title="Processing">
          <${LoadingBlock} rows=${4} label="Running the extraction pipeline…" />
        <//>`
      : null}

    ${result ? html`<div className="mt-2 stack">
      <${Card} title="Pipeline" subtitle=${`Engine: ${result.engine} · overall confidence ${fmt.percent(result.confidence)}`}>
        <div className="stage-list">
          ${(result.pipeline || []).map((stage) => html`<div className="stage-item complete" key=${stage.stage}>
            <span className="stage-icon">✓</span>
            <span>${stage.label || PIPELINE_LABELS[stage.stage] || stage.stage}</span>
            ${stage.detail ? html`<span className="stage-detail">${stage.detail}</span>` : null}
          </div>`)}
        </div>
        <div className="tiny muted mt-2">${result.engine_note}</div>
      <//>

      <${Card} title="Source text with extractions highlighted">
        <div style=${{
          background: "var(--surface-alt)", padding: "14px 16px", borderRadius: "9px",
          lineHeight: 1.9, fontSize: "13.5px", border: "1px solid var(--line-soft)",
        }}>${highlighted}</div>
        <div className="graph-legend">
          ${[...new Set(result.entities.map((e) => e.type))].map((type) => html`<span className="legend-item" key=${type}>
            <span className="legend-swatch" style=${{ background: entityColor(type) }}></span>
            ${ENTITY_LABELS[type] || type}
          </span>`)}
        </div>
        <div className="tiny muted mt-1">Hover a highlight to see the recogniser and its confidence.</div>
      <//>

      <${Card}
        title=${`Extracted entities (${result.entities.length})`}
        subtitle="Entities already in the graph will be linked, not duplicated"
      >
        <div className="table-wrap">
          <table className="data">
            <thead><tr>
              <th>Text</th><th>Type</th><th>Method</th><th className="num">Confidence</th>
              <th>Action</th><th>Include</th>
            </tr></thead>
            <tbody>
              ${result.entities.map((entity) => {
                const key = `e-${entity.start}`;
                const excluded = rejected.has(key);
                return html`<tr key=${key} style=${{ opacity: excluded ? 0.44 : 1 }}>
                  <td>
                    <span style=${{
                      borderBottom: `2px solid ${entityColor(entity.type)}`, paddingBottom: "1px",
                    }}>${entity.text}</span>
                  </td>
                  <td>${ENTITY_LABELS[entity.type] || entity.type}</td>
                  <td>
                    <${Pill} kind=${entity.method === "gazetteer" ? "green" : entity.method === "pattern" ? "info" : "yellow"}>
                      ${entity.method}
                    <//>
                    <div className="tiny muted mt-1">${entity.detail}</div>
                  </td>
                  <td className="num">${fmt.percent(entity.confidence)}</td>
                  <td>
                    ${entity.exists
                      ? html`<${Pill} kind="green">Link to ${entity.entity_uid}<//>`
                      : entity.type === "event"
                        ? html`<span className="tiny muted">Timeline anchor</span>`
                        : html`<${Pill} kind="yellow">Create new<//>`}
                  </td>
                  <td>
                    ${entity.type !== "event"
                      ? html`<input type="checkbox" checked=${!excluded} onChange=${() => toggle(key)} />`
                      : html`<span className="tiny muted">—</span>`}
                  </td>
                </tr>`;
              })}
            </tbody>
          </table>
        </div>
      <//>

      <${Card}
        title=${`Relationships detected (${result.relationships.length})`}
        subtitle="Extracted from trigger phrases — stored as INFERRED and queued for validation"
      >
        ${result.relationships.length
          ? result.relationships.map((rel, index) => {
              const key = `r-${index}`;
              const excluded = rejected.has(key);
              return html`<div className="evidence-block" key=${key} style=${{ opacity: excluded ? 0.44 : 1 }}>
                <div className="row-between">
                  <div className="row" style=${{ gap: "8px" }}>
                    <span className="strong">${rel.source_text}</span>
                    <span className="pill pill-inferred">${rel.label}</span>
                    <span className="strong">${rel.target_text}</span>
                    <${EvidenceBadge} status="INFERRED" />
                  </div>
                  <div className="row">
                    <span className="tiny muted">${fmt.percent(rel.confidence)}</span>
                    <input type="checkbox" checked=${!excluded} onChange=${() => toggle(key)} />
                  </div>
                </div>
                <div className="evidence-meta">
                  <span>Trigger phrase: <b>“${rel.trigger}”</b></span>
                </div>
                <div className="tiny muted mt-1" style=${{ fontStyle: "italic" }}>“${rel.sentence}”</div>
              </div>`;
            })
          : html`<${EmptyState}
              title="No relationships detected"
              text="No trigger phrases connected two extracted entities within a single sentence."
            />`}
      <//>

      ${result.insights?.length
        ? html`<${Card} title="Analysis notes">
            ${result.insights.map((insight, i) => html`<div className="evidence-block" key=${i}>
              <div className="evidence-head">
                <${EvidenceBadge} status=${insight.status} />
                <span className="strong small">${fmt.title(insight.kind)}</span>
              </div>
              <div className="evidence-desc">${insight.text}</div>
              ${insight.supporting?.length
                ? html`<div className="tiny muted mt-1">${insight.supporting.join(" · ")}</div>` : null}
            </div>`)}
          <//>`
        : null}

      <${Card}>
        <${Disclaimer}>${result.disclaimer}<//>
        <div className="row mt-2">
          ${canCommit
            ? html`<${Button} variant="primary" onClick=${commit} loading=${committing}>
                Add to Knowledge Graph
              <//>`
            : html`<span className="small muted">
                Your role can run analysis but cannot write to the knowledge graph.
              </span>`}
          <${Button} onClick=${() => setResult(null)}>Discard<//>
          <span className="tiny muted">
            ${result.entities.filter((e) => e.type !== "event" && !rejected.has(`e-${e.start}`)).length} entities ·
            ${result.relationships.filter((_, i) => !rejected.has(`r-${i}`)).length} relationships selected
          </span>
        </div>
      <//>
    </div>` : null}
  </div>`;
}
