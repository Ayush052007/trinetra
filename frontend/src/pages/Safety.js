/** Women Safety Intelligence module. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EvidenceBadge, EmptyState, LoadingBlock, ErrorBlock, Modal,
  BarChart, Disclaimer, useAsync, fmt, BAND_COLORS, entityColor, useToast,
} from "../lib/ui.js";
import { api } from "../api/client.js";
import { ZoneMap } from "../components/MapCanvas.js";

const SOS_FLOW = ["RECEIVED", "ASSIGNED", "RESPONDING", "RESOLVED"];

// ============================================================== overview

export function SafetyOverview({ navigate, user }) {
  const { data, loading, error, reload } = useAsync(() => api.get("/safety/overview"), []);

  if (loading && !data) return html`<${Card}><${LoadingBlock} rows=${6} /><//>`;
  if (error) return html`<${ErrorBlock} error=${error} onRetry=${reload} />`;
  if (!data) return null;

  const counters = data.counters || {};
  const context = data.context_statistics || {};

  const tiles = [
    ["Open SOS alerts", counters.sos_open, "/safety/sos", "🚨", counters.sos_open ? "var(--red)" : "var(--green)"],
    ["Incidents recorded", counters.incidents_total, "/safety/incidents", "▤", "var(--navy)"],
    ["Critical incidents", counters.incidents_critical, "/safety/incidents", "⚠", "var(--red)"],
    ["Open alerts", counters.alerts_open, "/safety/alerts", "🔔", "var(--orange)"],
    ["Patterns to review", counters.patterns_pending, "/safety/patterns", "👁", "var(--orange)"],
    ["Safety zones", counters.zones, "/safety/heatmap", "🗺", "var(--indigo)"],
    ["Emergency services", counters.services, "/safety/heatmap", "📍", "var(--teal)"],
  ];

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1><span style=${{ color: "var(--rose)" }}>◈</span> Women Safety Intelligence</h1>
        <p>
          Operational picture for harassment, stalking and repeat-pattern investigation,
          integrated with the criminal-network knowledge graph.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} key="sos" size="sm" variant="primary" onClick=${() => navigate("/safety/sos")}>SOS console<//>
        <${Button} key="route" size="sm" onClick=${() => navigate("/safety/route")}>Plan safe route<//>
      </div>
    </div>

    ${data.integration_notice
      ? html`<div className="alert alert-warn mb-2">
          <span>⚠</span>
          <div><strong>Integration status</strong>${data.integration_notice.message}</div>
        </div>`
      : null}

    <div className="grid-4 mb-2">
      ${tiles.map(([label, value, route, icon, color]) => html`<button
        className="kpi-card" key=${label} onClick=${() => navigate(route)}
      >
        <div className="kpi-top">
          <span className="kpi-icon" style=${{ background: "var(--surface-alt)" }}>${icon}</span>
          <span className="kpi-label">${label}</span>
        </div>
        <div className="kpi-value" style=${{ color }}>${fmt.number(value || 0)}</div>
        <span className="kpi-go">→</span>
      </button>`)}
    </div>

    <div className="grid-2 mb-2">
      <${Card} title="Incidents by type" subtitle="Computed from stored incident records">
        <${BarChart}
          items=${(data.incidents_by_type || []).map((item) => ({ label: item.label, value: item.count }))}
          colorFor=${() => "var(--rose)"}
        />
      <//>

      <${Card} title="Incidents by hour of day" subtitle="When incidents are recorded">
        <${BarChart}
          items=${(data.incidents_by_hour || []).map((item) => ({
            label: `${String(item.hour).padStart(2, "0")}:00`, value: item.count,
          }))}
          colorFor=${(item) => {
            const hour = parseInt(item.label, 10);
            return hour >= 20 || hour <= 5 ? "var(--red)" : hour >= 17 ? "var(--orange)" : "var(--indigo)";
          }}
        />
      <//>
    </div>

    ${data.recent_sos?.length
      ? html`<${Card} title="Recent SOS alerts" className="mb-2"
          actions=${html`<button className="link-btn" onClick=${() => navigate("/safety/sos")}>Open console</button>`}>
          ${data.recent_sos.slice(0, 4).map((alert) => html`<div className="feed-row" key=${alert.alert_ref}
            onClick=${() => navigate("/safety/sos")}>
            <span className="feed-dot" style=${{
              background: alert.status === "RESOLVED" ? "var(--green)" : "var(--red)",
            }}></span>
            <div className="feed-body">
              <div className="feed-title">${alert.subject_name} — ${alert.location?.text}</div>
              <div className="feed-meta">
                <${Pill} kind=${alert.status === "RESOLVED" ? "green" : "red"}>${alert.status}<//>
                <span className="mono">${alert.alert_ref}</span>
                <span>· ${fmt.relative(alert.raised_at)}</span>
              </div>
            </div>
          </div>`)}
        <//>`
      : null}

    ${context.headline
      ? html`<${Card}
          title="Why this matters — Delhi context"
          subtitle="Publicly reported statistics, included for problem context only"
        >
          <div className="alert alert-info">
            <span>ⓘ</span>
            <div>${context.disclaimer}</div>
          </div>
          <div className="grid-3 mb-2">
            ${context.headline.map((stat, i) => html`<div key=${i} className="card card-pad"
              style=${{ background: "var(--surface-alt)" }}>
              <div style=${{ fontSize: "24px", fontWeight: 700, color: "var(--rose)" }}>${stat.value}</div>
              <div className="small" style=${{ lineHeight: 1.5, marginTop: "5px" }}>${stat.label}</div>
              <div className="tiny muted mt-1">Source: ${stat.source}</div>
            </div>`)}
          </div>
          ${context.year_over_year
            ? html`<div>
                <div className="card-title mb-1">${context.year_over_year.title}</div>
                <${BarChart} items=${context.year_over_year.categories.flatMap((cat) => [
                  { label: `${cat.label} 2023`, value: cat.y2023 },
                  { label: `${cat.label} 2024`, value: cat.y2024 },
                ])} />
                <div className="tiny muted mt-1">Source: ${context.year_over_year.source}</div>
              </div>`
            : null}
          <div className="tiny muted mt-2">${context.note}</div>
        <//>`
      : null}
  </div>`;
}

// =================================================================== SOS

export function SosPage({ navigate, user }) {
  const [raising, setRaising] = useState(false);
  const [statusFilter, setStatusFilter] = useState(null);
  const toast = useToast();
  const canDispatch = (user.permissions || []).includes("safety:dispatch");
  const canRaise = (user.permissions || []).includes("sos:raise");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/safety/sos", { status: statusFilter || undefined }), [statusFilter]
  );

  const advance = useCallback(async (alertRef, status, unitRef) => {
    try {
      await api.patch(`/safety/sos/${alertRef}/status`, {
        status, unit_ref: unitRef || null,
        note: `Advanced to ${status} by ${user.service_id}`,
      });
      toast.push(`Alert ${alertRef} moved to ${status}.`, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [reload, toast, user.service_id]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>🚨 SOS Response Console</h1>
        <p>
          One-tap emergency alerts and their response workflow:
          ${SOS_FLOW.join(" → ")}.
        </p>
      </div>
      <div className="page-head-actions">
        ${canRaise ? html`<${Button} key="raise" variant="danger" onClick=${() => setRaising(true)}>Raise SOS<//>` : null}
        <${Button} key="refresh" size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <div className="alert alert-warn mb-2">
      <span>⚠</span>
      <div>
        <strong>No external dispatch is connected.</strong>
        Raising an SOS here notifies this operations console only. No emergency call is
        placed and no external service is contacted. Device GPS is not connected, so
        alert positions are simulated and labelled as such.
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${!statusFilter ? "active" : ""}`} onClick=${() => setStatusFilter(null)}>
        All ${data ? html`<span className="tiny muted">${data.items.length}</span>` : ""}
      </button>
      ${SOS_FLOW.map((status) => html`<button
        key=${status} className=${`chip ${statusFilter === status ? "active" : ""}`}
        onClick=${() => setStatusFilter(status)}
      >${status} ${data?.counts?.[status] ? html`<span className="tiny muted">${data.counts[status]}</span>` : ""}</button>`)}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${5} /><//>` : null}

    ${data && data.items.length === 0
      ? html`<${EmptyState} icon="✓" title="No SOS alerts" text="No alerts match this filter." />`
      : null}

    ${(data?.items || []).map((alert) => html`<${Card} key=${alert.alert_ref} className="mb-2">
      <div className="row-between mb-2">
        <div>
          <div className="row" style=${{ gap: "9px" }}>
            <span className="strong" style=${{ fontSize: "15px" }}>${alert.subject_name}</span>
            <${Pill} kind=${alert.status === "RESOLVED" ? "green" : alert.status === "RECEIVED" ? "red" : "orange"} dot>
              ${alert.status}
            <//>
            <${Pill} kind=${alert.priority}>${alert.priority}<//>
          </div>
          <div className="tiny muted mt-1">
            <span className="mono">${alert.alert_ref}</span> · raised ${fmt.dateTime(alert.raised_at)}
          </div>
        </div>
        ${alert.subject_entity_uid
          ? html`<${Button} size="sm" onClick=${() => navigate(`/entity/${alert.subject_entity_uid}`)}>
              Open subject profile
            <//>`
          : null}
      </div>

      <!-- workflow progress -->
      <div className="row mb-2" style=${{ gap: 0 }}>
        ${SOS_FLOW.map((step, index) => {
          const currentIndex = SOS_FLOW.indexOf(alert.status);
          const done = index <= currentIndex;
          const entry = alert.history?.find((h) => h.to === step);
          return html`<div key=${step} style=${{ flex: 1, textAlign: "center", position: "relative" }}>
            ${index > 0
              ? html`<div style=${{
                  position: "absolute", left: "-50%", right: "50%", top: "11px", height: "2px",
                  background: done ? "var(--green)" : "var(--line)",
                }}></div>`
              : null}
            <div style=${{
              width: "23px", height: "23px", borderRadius: "50%", margin: "0 auto",
              display: "grid", placeItems: "center", fontSize: "11px", position: "relative",
              background: done ? "var(--green)" : "var(--line-soft)",
              color: done ? "#fff" : "var(--gray)", fontWeight: 700,
            }}>${done ? "✓" : index + 1}</div>
            <div className="tiny mt-1" style=${{ fontWeight: done ? 650 : 400, color: done ? "var(--navy)" : "var(--gray)" }}>
              ${step}
            </div>
            ${entry ? html`<div className="tiny muted">${fmt.time(entry.at)}</div>` : null}
          </div>`;
        })}
      </div>

      <div className="grid-2">
        <div>
          <div className="kv-row">
            <span className="kv-key">Location</span>
            <span className="kv-val">
              ${alert.location?.text}
              <div className="tiny muted mono">
                ${alert.location?.lat?.toFixed(4)}, ${alert.location?.lng?.toFixed(4)}
              </div>
              <${Pill} kind=${alert.location?.source === "DEVICE" ? "green" : "yellow"}>
                ${alert.location?.source}
              <//>
            </span>
          </div>
          ${alert.assigned_unit
            ? html`<div className="kv-row">
                <span className="kv-key">Response unit</span>
                <span className="kv-val">${alert.assigned_unit.name}
                  <div className="tiny muted">${alert.assigned_unit.type} · ${alert.assigned_unit.contact || ""}</div>
                </span>
              </div>`
            : null}
          ${alert.assigned_officer
            ? html`<div className="kv-row"><span className="kv-key">Assigned officer</span>
                <span className="kv-val">${alert.assigned_officer}</span></div>`
            : null}
        </div>
        <div>
          ${alert.contacts?.length
            ? html`<div className="kv-row">
                <span className="kv-key">Emergency contacts</span>
                <span className="kv-val">
                  ${alert.contacts.map((contact) => html`<div key=${contact.name} className="tiny">
                    ${contact.name} — ${contact.relation} · ${contact.phone}
                  </div>`)}
                </span>
              </div>`
            : null}
          ${alert.notes ? html`<div className="kv-row"><span className="kv-key">Notes</span>
            <span className="kv-val tiny">${alert.notes}</span></div>` : null}
        </div>
      </div>

      ${alert.location?.source === "SIMULATED"
        ? html`<div className="tiny muted mt-1">${alert.location_notice}</div>` : null}

      ${canDispatch && alert.allowed_transitions?.length
        ? html`<div className="row mt-2">
            <span className="small strong">Advance to</span>
            ${alert.allowed_transitions.map((status) => html`<${Button}
              key=${status} size="sm"
              variant=${status === "RESOLVED" ? "success" : "primary"}
              onClick=${() => advance(alert.alert_ref, status)}
            >${status}<//>`)}
          </div>`
        : alert.status !== "RESOLVED" && !canDispatch
          ? html`<div className="tiny muted mt-2">
              Your role can view alerts but cannot dispatch. Status changes require a
              Women Safety Officer or Supervisory Officer.
            </div>`
          : null}

      ${alert.history?.length
        ? html`<details className="mt-2">
            <summary className="small" style=${{ cursor: "pointer", color: "var(--indigo)" }}>
              Status history (${alert.history.length})
            </summary>
            <div className="mt-1">
              ${alert.history.map((entry, i) => html`<div className="kv-row" key=${i}>
                <span className="kv-key tiny">
                  ${entry.from ? `${entry.from} → ` : ""}${entry.to}
                </span>
                <span className="kv-val tiny">
                  ${fmt.dateTime(entry.at)} · ${entry.by}
                  ${entry.note ? html`<div className="muted">${entry.note}</div>` : null}
                </span>
              </div>`)}
            </div>
          </details>`
        : null}
    <//>`)}

    ${raising
      ? html`<${RaiseSosModal} onClose=${() => setRaising(false)}
          onRaised=${() => { setRaising(false); reload(); }} />`
      : null}
  </div>`;
}

function RaiseSosModal({ onClose, onRaised }) {
  const [subject, setSubject] = useState("");
  const [location, setLocation] = useState("Simulated current position");
  const [lat, setLat] = useState(28.695);
  const [lng, setLng] = useState(77.14);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const raise = async () => {
    setSaving(true);
    try {
      const result = await api.post("/safety/sos", {
        subject_name: subject.trim() || "Unnamed subject",
        latitude: Number(lat), longitude: Number(lng),
        location_text: location.trim(), note: note.trim() || null,
      });
      toast.push(`SOS ${result.alert_ref} raised and sent to the operations console.`, "success");
      onRaised(result);
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return html`<${Modal}
    title="Raise SOS alert" size="narrow" onClose=${onClose}
    footer=${html`<div className="row">
      <${Button} onClick=${onClose}>Cancel<//>
      <${Button} variant="danger" loading=${saving} onClick=${raise}>Raise SOS<//>
    </div>`}
  >
    <div className="alert alert-warn">
      <span>⚠</span>
      <div>
        This notifies the in-platform operations console only. It does not place an
        emergency call or contact any external service.
      </div>
    </div>
    <div className="field">
      <label>Subject name</label>
      <input className="input" value=${subject} autoFocus placeholder="Name of the person at risk"
        onInput=${(e) => setSubject(e.target.value)} />
    </div>
    <div className="field">
      <label>Location description</label>
      <input className="input" value=${location} onInput=${(e) => setLocation(e.target.value)} />
    </div>
    <div className="row">
      <div className="field" style=${{ flex: 1 }}>
        <label>Latitude</label>
        <input className="input" type="number" step="0.0001" value=${lat}
          onInput=${(e) => setLat(e.target.value)} />
      </div>
      <div className="field" style=${{ flex: 1 }}>
        <label>Longitude</label>
        <input className="input" type="number" step="0.0001" value=${lng}
          onInput=${(e) => setLng(e.target.value)} />
      </div>
    </div>
    <div className="hint mb-1">
      Device GPS is not connected, so the position is entered manually and recorded as SIMULATED.
    </div>
    <div className="field">
      <label>Note</label>
      <textarea className="input" rows="2" value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
    </div>
  <//>`;
}

// =============================================================== heatmap

export function HeatmapPage({ navigate, params }) {
  const [types, setTypes] = useState([]);
  const [severities, setSeverities] = useState([]);
  const [hourRange, setHourRange] = useState(null);
  const [days, setDays] = useState(null);
  const [showPoints, setShowPoints] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => api.get("/safety/heatmap", {
      types: types.length ? types.join(",") : undefined,
      severities: severities.length ? severities.join(",") : undefined,
      hour_from: hourRange ? hourRange[0] : undefined,
      hour_to: hourRange ? hourRange[1] : undefined,
      days: days || undefined,
    }),
    [JSON.stringify(types), JSON.stringify(severities), JSON.stringify(hourRange), days]
  );

  const services = useAsync(() => api.get("/safety/services/nearby", {
    lat: 28.705, lng: 77.12, radius_km: 25,
  }), []);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>🗺 Safety Heatmap</h1>
        <p>
          Severity-weighted incident density per zone, computed live from stored
          records. Changing a filter recomputes the map.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <${Card} className="mb-2">
      <div className="row">
        <span className="small strong">Incident type</span>
        ${(data?.available_types || []).map((type) => html`<button
          key=${type.key} className=${`chip ${types.includes(type.key) ? "active" : ""}`}
          onClick=${() => setTypes((c) => c.includes(type.key) ? c.filter((t) => t !== type.key) : [...c, type.key])}
        >${type.label}</button>`)}
        ${types.length ? html`<button className="link-btn" onClick=${() => setTypes([])}>All types</button>` : null}
      </div>
      <div className="row mt-2">
        <span className="small strong">Severity</span>
        ${["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((severity) => html`<button
          key=${severity} className=${`chip ${severities.includes(severity) ? "active" : ""}`}
          onClick=${() => setSeverities((c) => c.includes(severity) ? c.filter((s) => s !== severity) : [...c, severity])}
        >
          <span className="chip-swatch" style=${{ background: BAND_COLORS[severity] }}></span>${severity}
        </button>`)}
        <span style=${{ width: "1px", height: "18px", background: "var(--line)" }}></span>
        <span className="small strong">Time of day</span>
        ${[[[20, 4], "Night 20:00–04:00"], [[17, 20], "Evening"], [[6, 17], "Daytime"]].map(([range, label]) => html`<button
          key=${label} className=${`chip ${hourRange && hourRange[0] === range[0] ? "active" : ""}`}
          onClick=${() => setHourRange(hourRange && hourRange[0] === range[0] ? null : range)}
        >${label}</button>`)}
        <span style=${{ width: "1px", height: "18px", background: "var(--line)" }}></span>
        ${[[30, "30 d"], [90, "90 d"], [365, "1 yr"]].map(([value, label]) => html`<button
          key=${value} className=${`chip ${days === value ? "active" : ""}`}
          onClick=${() => setDays(days === value ? null : value)}
        >${label}</button>`)}
        <div className="spacer"></div>
        <label className="chip" style=${{ cursor: "pointer" }}>
          <input type="checkbox" checked=${showPoints} style=${{ margin: 0 }}
            onChange=${(e) => setShowPoints(e.target.checked)} />
          Show individual incidents
        </label>
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <div className="grid-2">
      <${Card}
        title=${`${fmt.number(data?.total_incidents || 0)} incidents in view`}
        subtitle=${data?.method}
        className="grid-2-wide"
      >
        ${loading && !data
          ? html`<${LoadingBlock} rows=${6} />`
          : html`<${ZoneMap}
              zones=${data?.zones || []} points=${data?.points || []}
              services=${services.data?.items || []} showPoints=${showPoints}
              highlightZone=${params.zone} height=${390}
              onZoneClick=${() => {}}
            />`}
        <div className="map-legend">
          ${(data?.bands || []).map((band) => html`<span className="legend-item" key=${band.band}>
            <span className="band-swatch" style=${{ background: BAND_COLORS[band.band] }}></span>
            <span>${band.band}</span>
          </span>`)}
        </div>
        ${data?.band_note ? html`<div className="tiny muted mt-1">${data.band_note}</div>` : null}
      <//>

      <${Card} title="Zones by density">
        ${(data?.zones || []).map((zone) => html`<div key=${zone.zone_ref}
          className="rank-row" style=${{ alignItems: "flex-start" }}>
          <span className="band-swatch" style=${{
            background: BAND_COLORS[zone.band], marginTop: "4px", width: "12px", height: "12px",
          }}></span>
          <div className="rank-body">
            <div className="row-between">
              <span className="rank-name">${zone.name}</span>
              <${Pill} kind=${zone.band}>${zone.band}<//>
            </div>
            <div className="rank-meta">
              ${zone.incident_count} incident${zone.incident_count === 1 ? "" : "s"} ·
              density ${zone.weighted_density} ·
              ${zone.services_nearby} service${zone.services_nearby === 1 ? "" : "s"} nearby
            </div>
            <div className="rank-bar">
              <span style=${{
                width: `${Math.max(2, (zone.relative_share || 0) * 100)}%`,
                background: BAND_COLORS[zone.band],
              }}></span>
            </div>
            ${Object.keys(zone.by_type || {}).length
              ? html`<div className="tiny muted mt-1">
                  ${Object.entries(zone.by_type).slice(0, 3)
                    .map(([type, count]) => `${fmt.title(type)} ${count}`).join(" · ")}
                </div>`
              : null}
          </div>
        </div>`)}
        <${Disclaimer} subtle>
          A band describes reporting density in the current selection. It is not a
          statement about a location or the people in it, and reflects where incidents
          were reported rather than where they occurred.
        <//>
      <//>
    </div>
  </div>`;
}

// ============================================================= safe route

export function RoutePage({ navigate }) {
  const [from, setFrom] = useState("WP-LOC1");
  const [to, setTo] = useState("WP-LOC2");
  const [hour, setHour] = useState(21);
  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRoute, setSelectedRoute] = useState(0);
  const toast = useToast();

  const waypoints = useAsync(() => api.get("/safety/waypoints"), []);

  const compute = useCallback(async () => {
    if (from === to) {
      toast.push("Start and destination must differ.", "error");
      return;
    }
    setComputing(true);
    setError(null);
    try {
      const outcome = await api.post(
        `/safety/routes?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&depart_hour=${hour}`
      );
      setResult(outcome);
      setSelectedRoute(0);
    } catch (err) {
      setError(err);
    } finally {
      setComputing(false);
    }
  }, [from, to, hour, toast]);

  const endpoints = (waypoints.data?.items || []).filter((w) => w.is_endpoint);
  const active = result?.routes?.[selectedRoute];

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>🛣 AI Safe Route</h1>
        <p>
          Compare route options using recorded incident density, recent alerts, time of
          day, street lighting and emergency-service proximity.
        </p>
      </div>
    </div>

    <${Card} className="mb-2">
      <div className="row">
        <div className="field" style=${{ flex: 1, minWidth: "190px", margin: 0 }}>
          <label>From</label>
          <select className="input" value=${from} onChange=${(e) => setFrom(e.target.value)}>
            ${endpoints.map((w) => html`<option key=${w.ref} value=${w.ref}>${w.name}</option>`)}
          </select>
        </div>
        <div className="field" style=${{ flex: 1, minWidth: "190px", margin: 0 }}>
          <label>To</label>
          <select className="input" value=${to} onChange=${(e) => setTo(e.target.value)}>
            ${endpoints.map((w) => html`<option key=${w.ref} value=${w.ref}>${w.name}</option>`)}
          </select>
        </div>
        <div className="field" style=${{ width: "150px", margin: 0 }}>
          <label>Departure hour</label>
          <select className="input" value=${hour} onChange=${(e) => setHour(Number(e.target.value))}>
            ${Array.from({ length: 24 }).map((_, h) => html`<option key=${h} value=${h}>
              ${String(h).padStart(2, "0")}:00
            </option>`)}
          </select>
        </div>
        <${Button} variant="primary" onClick=${compute} loading=${computing}
          style=${{ alignSelf: "flex-end" }}>Compare routes<//>
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${compute} />` : null}

    ${result ? html`<div>
      <div className="alert alert-info mb-2">
        <span>ⓘ</span>
        <div>
          <strong>${result.recommendation.label} — ${result.recommendation.safety_score}/100.
          ${result.recommendation.wording}</strong>
          ${result.recommendation.why}
        </div>
      </div>

      <div className="grid-2">
        <${Card} key="map" title="Route map" subtitle=${`${result.from.name} → ${result.to.name}`}>
          <${ZoneMap}
            route=${active?.waypoints || []} height=${330}
            zones=${[]} services=${[]}
          />
          <div className="row mt-2">
            ${result.routes.map((route, index) => html`<button
              key=${route.label} className=${`chip ${selectedRoute === index ? "active" : ""}`}
              onClick=${() => setSelectedRoute(index)}
            >
              ${route.label} · ${route.safety_score}
              ${route.recommended ? html`<span className="tiny"> ★</span>` : null}
            </button>`)}
          </div>
        <//>

        <${Card} key="comparison" title="Comparison">
          ${result.routes.map((route, index) => html`<div key=${route.label}
            style=${{
              padding: "11px", borderRadius: "9px", marginBottom: "9px", cursor: "pointer",
              border: `1px solid ${selectedRoute === index ? "var(--indigo)" : "var(--line-soft)"}`,
              background: selectedRoute === index ? "var(--indigo-50)" : "var(--surface-alt)",
            }}
            onClick=${() => setSelectedRoute(index)}
          >
            <div className="row-between">
              <div className="row" style=${{ gap: "8px" }}>
                <span className="strong">${route.label}</span>
                ${route.recommended ? html`<${Pill} kind="green">Recommended<//>` : null}
              </div>
              <div className="row">
                <span style=${{
                  fontSize: "19px", fontWeight: 700,
                  color: route.safety_score >= 75 ? "var(--green)"
                    : route.safety_score >= 55 ? "var(--amber)" : "var(--orange)",
                }}>${route.safety_score}</span>
                <span className="tiny muted">/100</span>
              </div>
            </div>
            <div className="tiny muted">
              ${route.distance_km} km · ${route.waypoints.length} waypoints
            </div>
            ${selectedRoute === index
              ? html`<div className="mt-2">
                  ${route.factors.map((factor) => html`<div className="kv-row" key=${factor.key}>
                    <span className="kv-key tiny">${factor.label}</span>
                    <span className="kv-val tiny">${factor.detail}</span>
                  </div>`)}
                </div>`
              : null}
          </div>`)}
        <//>
      </div>

      ${active
        ? html`<${Card} title=${`${active.label} — segments`} className="mt-2">
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>From</th><th>To</th><th className="num">Distance</th>
                  <th className="num">Incidents nearby</th><th>Lighting</th></tr></thead>
                <tbody>
                  ${active.segments.map((segment, i) => html`<tr key=${i}>
                    <td>${segment.from_name}</td>
                    <td>${segment.to_name}</td>
                    <td className="num">${segment.distance_km} km</td>
                    <td className="num">${segment.incidents_near}</td>
                    <td>${segment.lit
                      ? html`<${Pill} kind="green">Lit<//>`
                      : html`<${Pill} kind="orange">Unlit<//>`}</td>
                  </tr>`)}
                </tbody>
              </table>
            </div>
          <//>`
        : null}

      <div className="mt-2"><${Disclaimer}>${result.disclaimer}<//></div>
    </div> ` : null}
  </div>`;
}

// ============================================================= incidents

export function IncidentsPage({ navigate, user, caseId }) {
  const [typeFilter, setTypeFilter] = useState(null);
  const [priorityFilter, setPriorityFilter] = useState(null);
  const [reporting, setReporting] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const canReport = (user.permissions || []).includes("safety:incident:create");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/safety/incidents", {
      case_id: caseId || undefined, type: typeFilter || undefined,
      priority: priorityFilter || undefined, offset, limit,
    }),
    [caseId, typeFilter, priorityFilter, offset]
  );

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Women Safety Incidents</h1>
        <p>All recorded incidents, with the descriptors that drive pattern detection.</p>
      </div>
      <div className="page-head-actions">
        ${canReport ? html`<${Button} variant="primary" size="sm" onClick=${() => setReporting(true)}>
          Record incident
        <//>` : null}
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${!typeFilter ? "active" : ""}`} onClick=${() => { setTypeFilter(null); setOffset(0); }}>
        All types
      </button>
      ${(data?.types || []).map((type) => html`<button
        key=${type.key} className=${`chip ${typeFilter === type.key ? "active" : ""}`}
        onClick=${() => { setTypeFilter(type.key); setOffset(0); }}
      >${type.label}</button>`)}
      <div className="spacer"></div>
      ${["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((priority) => html`<button
        key=${priority} className=${`chip ${priorityFilter === priority ? "active" : ""}`}
        onClick=${() => { setPriorityFilter(priorityFilter === priority ? null : priority); setOffset(0); }}
      >
        <span className="chip-swatch" style=${{ background: BAND_COLORS[priority] }}></span>${priority}
      </button>`)}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <${Card} title=${`${fmt.number(data?.total || 0)} incidents`}>
      ${loading && !data ? html`<${LoadingBlock} rows=${6} />` : null}
      ${data && data.items.length
        ? html`<div>
            <div className="table-wrap">
              <table className="data">
                <thead><tr>
                  <th>Reference</th><th>Type</th><th>Priority</th><th>Status</th>
                  <th>When</th><th>Location</th><th>Description</th><th>Descriptors</th>
                </tr></thead>
                <tbody>
                  ${data.items.map((incident) => html`<tr key=${incident.incident_ref}>
                    <td className="mono tiny">${incident.incident_ref}</td>
                    <td>${incident.type_label}</td>
                    <td><${Pill} kind=${incident.priority}>${incident.priority}<//></td>
                    <td className="tiny">${fmt.title(incident.status)}</td>
                    <td className="tiny nowrap">${incident.time_label || fmt.date(incident.occurred_at)}</td>
                    <td className="tiny">${incident.location_text || "—"}</td>
                    <td className="tiny">${incident.description}</td>
                    <td className="tiny muted">
                      ${Object.entries(incident.descriptors || {})
                        .map(([k, v]) => `${k}: ${v}`).join(", ") || "—"}
                    </td>
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

    ${reporting
      ? html`<${IncidentModal} types=${data?.types || []} caseId=${caseId}
          onClose=${() => setReporting(false)}
          onCreated=${() => { setReporting(false); reload(); }} />`
      : null}
  </div>`;
}

function IncidentModal({ types, caseId, onClose, onCreated }) {
  const [type, setType] = useState("harassment");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("MEDIUM");
  const [lat, setLat] = useState(28.71);
  const [lng, setLng] = useState(77.11);
  const [locationText, setLocationText] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [device, setDevice] = useState("");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const submit = async () => {
    if (description.trim().length < 3) {
      toast.push("A description is required.", "error");
      return;
    }
    setSaving(true);
    try {
      const created = await api.post("/safety/incidents", {
        type, description: description.trim(), priority,
        latitude: Number(lat), longitude: Number(lng),
        location_text: locationText.trim() || null,
        case_id: caseId || null,
        vehicle_descriptor: vehicle.trim() || null,
        device_descriptor: device.trim() || null,
      });
      toast.push(created.message, "success");
      onCreated(created);
    } catch (err) {
      toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return html`<${Modal}
    title="Record incident" onClose=${onClose}
    footer=${html`<div className="row">
      <${Button} onClick=${onClose}>Cancel<//>
      <${Button} variant="primary" loading=${saving} onClick=${submit}>Record incident<//>
    </div>`}
  >
    <div className="row">
      <div className="field" style=${{ flex: 1 }}>
        <label>Incident type</label>
        <select className="input" value=${type} onChange=${(e) => setType(e.target.value)}>
          ${types.map((t) => html`<option key=${t.key} value=${t.key}>${t.label}</option>`)}
        </select>
      </div>
      <div className="field" style=${{ width: "150px" }}>
        <label>Priority</label>
        <select className="input" value=${priority} onChange=${(e) => setPriority(e.target.value)}>
          ${["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((p) => html`<option key=${p} value=${p}>${p}</option>`)}
        </select>
      </div>
    </div>
    <div className="field">
      <label>Description</label>
      <textarea className="input" rows="3" value=${description} autoFocus
        onInput=${(e) => setDescription(e.target.value)}></textarea>
    </div>
    <div className="field">
      <label>Location description</label>
      <input className="input" value=${locationText} onInput=${(e) => setLocationText(e.target.value)} />
    </div>
    <div className="row">
      <div className="field" style=${{ flex: 1 }}>
        <label>Latitude</label>
        <input className="input" type="number" step="0.0001" value=${lat} onInput=${(e) => setLat(e.target.value)} />
      </div>
      <div className="field" style=${{ flex: 1 }}>
        <label>Longitude</label>
        <input className="input" type="number" step="0.0001" value=${lng} onInput=${(e) => setLng(e.target.value)} />
      </div>
    </div>
    <div className="row">
      <div className="field" style=${{ flex: 1 }}>
        <label>Vehicle descriptor</label>
        <input className="input" value=${vehicle} placeholder="e.g. DL-0X-XX-4471"
          onInput=${(e) => setVehicle(e.target.value)} />
      </div>
      <div className="field" style=${{ flex: 1 }}>
        <label>Device / phone descriptor</label>
        <input className="input" value=${device} placeholder="e.g. +91-70xxxx4482"
          onInput=${(e) => setDevice(e.target.value)} />
      </div>
    </div>
    <div className="hint">
      Descriptors let pattern detection link this incident to others reporting the
      same vehicle or device.
    </div>
  <//>`;
}

// ============================================================== patterns

export function SafetyPatternsPage({ navigate, user, caseId }) {
  const [tab, setTab] = useState("suspicious");
  const { data, loading, error, reload } = useAsync(
    () => api.get("/safety/patterns", { case_id: caseId || undefined }), [caseId]
  );

  const suspicious = data?.suspicious_patterns || [];
  const encounters = data?.repeated_encounters || [];

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>👁 Pattern Detection</h1>
        <p>
          Cross-incident clustering and repeated-encounter analysis, connected to the
          criminal-network graph.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Re-run detection<//>
      </div>
    </div>

    <div className="alert alert-warn mb-2">
      <span>⚠</span>
      <div>
        <strong>These are analytical patterns, not conclusions.</strong>
        They do not identify anyone as an offender, do not establish intent, and do not
        assert that an offence occurred. Every finding requires authorised investigator review.
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${tab === "suspicious" ? "active" : ""}`} onClick=${() => setTab("suspicious")}>
        Suspicious patterns <span className="tiny">${suspicious.length}</span>
      </button>
      <button className=${`chip ${tab === "encounters" ? "active" : ""}`} onClick=${() => setTab("encounters")}>
        Repeated encounters <span className="tiny">${encounters.length}</span>
      </button>
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${5} /><//>` : null}

    ${tab === "suspicious"
      ? (suspicious.length
        ? suspicious.map((pattern, index) => html`<${Card} key=${index} className="mb-2">
            <div className="row-between mb-1">
              <div className="row" style=${{ gap: "9px" }}>
                <${Pill} kind="rose">${fmt.title(pattern.kind)}<//>
                <span className="strong">${pattern.title}</span>
              </div>
              <span className="strong" style=${{ color: "var(--orange)" }}>
                ${fmt.percent(pattern.confidence)}
              </span>
            </div>
            <div className="reason-box">
              <div className="reason-label">Reason</div>${pattern.reason}
            </div>
            ${pattern.factors?.length
              ? pattern.factors.map((factor, i) => html`<div className="kv-row" key=${i}>
                  <span className="kv-key">${factor.label}</span>
                  <span className="kv-val">${factor.detail}</span>
                </div>`)
              : null}
            <div className="mt-2">
              <div className="small strong mb-1">Supporting incidents (${pattern.supporting_incidents.length})</div>
              ${pattern.supporting_incidents.map((incident) => html`<div className="kv-row" key=${incident.ref}>
                <span className="kv-key tiny mono">${incident.ref}</span>
                <span className="kv-val tiny">
                  ${incident.description}
                  <div className="muted">${incident.time_label || fmt.date(incident.occurred_at)} · ${incident.location || ""}</div>
                </span>
              </div>`)}
            </div>
            ${pattern.supporting_entities?.length
              ? html`<div className="row mt-2">
                  <span className="small strong">Entities:</span>
                  ${[...new Map(pattern.supporting_entities.map((e) => [e.uid, e])).values()]
                    .map((entity) => html`<button
                    key=${entity.uid} className="chip" style=${{ padding: "2px 8px", fontSize: "11px" }}
                    onClick=${() => navigate(`/entity/${entity.uid}`)}
                  >
                    <span className="chip-swatch" style=${{ background: entityColor(entity.type) }}></span>
                    ${entity.name}
                  </button>`)}
                </div>`
              : null}
            <div className="row mt-2">
              ${pattern.supporting_entities?.length
                ? html`<${Button} size="sm" variant="primary"
                    onClick=${() => navigate("/network", { root: pattern.supporting_entities[0].uid })}>
                    Investigate connection →
                  <//>`
                : null}
              <span className="tiny muted">${pattern.notice}</span>
            </div>
          <//>`)
        : html`<${EmptyState} title="No suspicious patterns" text="No cross-incident clusters detected in this scope." />`)
      : null}

    ${tab === "encounters"
      ? (encounters.length
        ? encounters.map((pattern, index) => html`<${Card} key=${index} className="mb-2">
            <div className="row-between mb-1">
              <span className="strong">${pattern.title}</span>
              <span className="strong" style=${{ color: "var(--orange)" }}>
                ${fmt.percent(pattern.confidence)}
              </span>
            </div>
            <div className="reason-box">
              <div className="reason-label">Reason</div>${pattern.reason}
            </div>
            <div className="row mb-2">
              <button className="chip" onClick=${() => navigate(`/entity/${pattern.subject.uid}`)}>
                <span className="chip-swatch" style=${{ background: entityColor(pattern.subject.type) }}></span>
                ${pattern.subject.name}
              </button>
              <span className="muted">⟷</span>
              <button className="chip" onClick=${() => navigate(`/entity/${pattern.counterpart.uid}`)}>
                <span className="chip-swatch" style=${{ background: entityColor(pattern.counterpart.type) }}></span>
                ${pattern.counterpart.name}
              </button>
            </div>
            ${pattern.factors.map((factor, i) => html`<div className="kv-row" key=${i}>
              <span className="kv-key">${factor.label}</span>
              <span className="kv-val">
                ${typeof factor.value === "boolean" ? (factor.value ? "Yes" : "No") : factor.value}
                <div className="tiny muted">${factor.detail}</div>
              </span>
            </div>`)}
            <div className="mt-2">
              <div className="small strong mb-1">Supporting events (${pattern.supporting_events.length})</div>
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>When</th><th>Location</th><th>Source</th><th>Status</th></tr></thead>
                  <tbody>
                    ${pattern.supporting_events.map((event, i) => html`<tr key=${i}>
                      <td className="tiny nowrap">${event.time_label || fmt.date(event.occurred_at)}</td>
                      <td className="tiny">${event.location}</td>
                      <td className="tiny muted">
                        ${event.kind === "incident"
                          ? `Incident ${event.incident_ref} (${fmt.title(event.incident_type || "")})`
                          : `${fmt.title(event.relationship_type || "")} · ${event.source_ref || ""}`}
                      </td>
                      <td><${EvidenceBadge} status=${event.evidence_status} /></td>
                    </tr>`)}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="row mt-2">
              <${Button} size="sm" variant="primary"
                onClick=${() => navigate("/network", { root: pattern.counterpart.uid })}>
                Investigate in graph →
              <//>
              <${Button} size="sm" onClick=${() => navigate(`/entity/${pattern.subject.uid}`)}>
                Open subject profile
              <//>
            </div>
            <div className="mt-2"><${Disclaimer}>${pattern.disclaimer}<//></div>
          <//>`)
        : html`<${EmptyState}
            title="No repeated-encounter patterns"
            text="No co-occurrence patterns crossed the confidence threshold in this scope."
          />`)
      : null}
  </div>`;
}

// ================================================================ alerts

export function AlertsPage({ navigate, user, params }) {
  const [statusFilter, setStatusFilter] = useState(null);
  const toast = useToast();
  const canDispatch = (user.permissions || []).includes("safety:dispatch");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/safety/alerts", { status: statusFilter || undefined }), [statusFilter]
  );

  const advance = useCallback(async (alertId, status) => {
    try {
      await api.patch(`/safety/alerts/${alertId}/status`, { status });
      toast.push(`Alert moved to ${status}.`, "success");
      reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [reload, toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>🔔 Live Safety Alerts</h1>
        <p>
          Operational alert feed ordered by priority. Status changes are pushed to
          every connected client.
        </p>
      </div>
      <div className="page-head-actions">
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <div className="graph-toolbar">
      <button className=${`chip ${!statusFilter ? "active" : ""}`} onClick=${() => setStatusFilter(null)}>All</button>
      ${(data?.workflow || []).map((status) => html`<button
        key=${status} className=${`chip ${statusFilter === status ? "active" : ""}`}
        onClick=${() => setStatusFilter(status)}
      >${status} ${data?.counts?.[status] ? html`<span className="tiny muted">${data.counts[status]}</span>` : ""}</button>`)}
    </div>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}
    ${loading && !data ? html`<${Card}><${LoadingBlock} rows=${4} /><//>` : null}

    ${data && data.items.length === 0
      ? html`<${EmptyState} icon="✓" title="No alerts" text="No alerts match this filter." />`
      : null}

    ${(data?.items || []).map((alert) => html`<${Card} key=${alert.id}
      className="mb-2"
      style=${{ borderLeft: `4px solid ${BAND_COLORS[alert.priority]}` }}
    >
      <div className="row-between">
        <div style=${{ flex: 1, minWidth: 0 }}>
          <div className="row" style=${{ gap: "9px", marginBottom: "4px" }}>
            <${Pill} kind=${alert.priority} dot>${alert.priority}<//>
            <${Pill} kind="neutral">${alert.status}<//>
            <span className="tiny muted mono">${alert.alert_ref}</span>
            <span className="tiny muted">${alert.module}</span>
          </div>
          <div className="strong">${alert.message}</div>
          ${alert.detail ? html`<div className="small muted mt-1">${alert.detail}</div>` : null}
          <div className="tiny muted mt-1">
            ${alert.time_label || fmt.dateTime(alert.raised_at)}
            ${alert.assigned_to ? ` · assigned to ${alert.assigned_to}` : ""}
          </div>
        </div>
      </div>
      <div className="row mt-2">
        ${canDispatch && alert.allowed_transitions?.length
          ? alert.allowed_transitions.map((status) => html`<${Button}
              key=${status} size="sm"
              variant=${status === "RESOLVED" ? "success" : "secondary"}
              onClick=${() => advance(alert.id, status)}
            >${fmt.title(status)}<//>`)
          : null}
        ${alert.sos_alert_id
          ? html`<${Button} size="sm" onClick=${() => navigate("/safety/sos")}>Open SOS console<//>` : null}
        ${alert.case_id
          ? html`<${Button} size="sm" onClick=${() => navigate(`/cases/${alert.case_id}`)}>Open case<//>` : null}
      </div>
    <//>`)}
  </div>`;
}
