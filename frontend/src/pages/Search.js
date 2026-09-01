/** Entity search. */

import {
  html, useState, useEffect,
  Card, Button, Pill, EmptyState, LoadingBlock, ErrorBlock,
  useDebounced, fmt, entityColor, ENTITY_GLYPHS, ENTITY_LABELS, BAND_COLORS,
} from "../lib/ui.js";
import { api } from "../api/client.js";

const TYPES = Object.keys(ENTITY_LABELS);

export function SearchPage({ navigate, caseId, params }) {
  const [query, setQuery] = useState(params.q || "");
  const [types, setTypes] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const debounced = useDebounced(query, 280);

  useEffect(() => {
    if (debounced.trim().length < 2) { setResults(null); return undefined; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.get("/entities/search", {
      q: debounced, limit: 50,
      types: types.length ? types.join(",") : undefined,
      case_id: caseId || undefined,
    })
      .then((data) => { if (!cancelled) setResults(data); })
      .catch((err) => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debounced, JSON.stringify(types), caseId]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Entity Search</h1>
        <p>
          Search people, phones, locations, vehicles, organisations, transactions and
          case records across the live database. Aliases and normalised forms are
          matched too — a phone number is found whether or not it carries a country code.
        </p>
      </div>
    </div>

    <${Card}>
      <input
        className="input" autoFocus value=${query}
        placeholder="Search by name, phone number, vehicle registration, organisation or case number…"
        onInput=${(e) => setQuery(e.target.value)}
      />
      <div className="row mt-2">
        <span className="small strong">Filter by type</span>
        ${TYPES.map((type) => html`<button
          key=${type} className=${`chip ${types.includes(type) ? "active" : ""}`}
          onClick=${() => setTypes((c) => c.includes(type) ? c.filter((t) => t !== type) : [...c, type])}
        >
          <span className="chip-swatch" style=${{ background: entityColor(type) }}></span>
          ${ENTITY_LABELS[type]}
        </button>`)}
        ${types.length ? html`<button className="link-btn" onClick=${() => setTypes([])}>Clear</button>` : null}
      </div>
    <//>

    <div className="mt-2">
      ${error ? html`<${ErrorBlock} error=${error} />` : null}
      ${loading ? html`<${Card}><${LoadingBlock} rows=${4} /><//>` : null}

      ${!loading && query.trim().length < 2
        ? html`<${EmptyState}
            icon="⌕" title="Start typing to search"
            text="Enter at least two characters. Try “Rahul Sharma”, “9876543210”, “DL 8C AA 1234” or “Shivam”."
          />`
        : null}

      ${!loading && results && results.results.length === 0
        ? html`<${EmptyState}
            icon="◇" title=${`No results for “${results.query}”`}
            text="No entity name or alias matches this search. Check the spelling, or widen the type filter."
          />`
        : null}

      ${!loading && results && results.results.length
        ? html`<${Card}
            title=${`${results.count} result${results.count === 1 ? "" : "s"}`}
            subtitle=${`for “${results.query}”`}
          >
            <div className="table-wrap">
              <table className="data">
                <thead><tr>
                  <th>Entity</th><th>Type</th><th>Aliases</th>
                  <th className="num">Connections</th><th>Priority</th><th>Classification</th>
                </tr></thead>
                <tbody>
                  ${results.results.map((item) => html`<tr
                    key=${item.uid} className="clickable"
                    onClick=${() => navigate(`/entity/${item.uid}`)}
                  >
                    <td>
                      <div className="row" style=${{ gap: "9px" }}>
                        <span style=${{
                          width: "24px", height: "24px", borderRadius: "7px", flex: "none",
                          display: "grid", placeItems: "center", fontSize: "11px", color: "#fff",
                          background: entityColor(item.type),
                        }}>${ENTITY_GLYPHS[item.type] || "?"}</span>
                        <span className="strong">${item.name}</span>
                      </div>
                    </td>
                    <td>${item.type_label}</td>
                    <td className="tiny muted">${item.aliases?.join(", ") || "—"}</td>
                    <td className="num">${fmt.number(item.connections)}</td>
                    <td>
                      ${item.priority_band
                        ? html`<${Pill} kind=${item.priority_band}>
                            ${fmt.score(item.priority_score)} ${item.priority_band}
                          <//>`
                        : html`<span className="muted tiny">—</span>`}
                    </td>
                    <td><span className="tiny muted">${item.classification}</span></td>
                  </tr>`)}
                </tbody>
              </table>
            </div>
          <//>`
        : null}
    </div>
  </div>`;
}
