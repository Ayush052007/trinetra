/**
 * Application shell: sidebar, top bar, global search, notifications, profile.
 *
 * The sidebar mirrors the information architecture in the project material
 * exactly (Dashboard · Women Safety · Analysis · Data · Reports) and hides
 * items the signed-in role cannot use. The backend enforces the same rules -
 * hiding is convenience, not security.
 */

import {
  html, useState, useEffect, useRef, useCallback,
  fmt, useDebounced, useOutsideClick, entityColor, ENTITY_GLYPHS,
} from "../lib/ui.js";
import { api, secondsUntilExpiry } from "../api/client.js";
import { TrinetraLogo } from "./Brand.js";

export const NAV = [
  { group: null, items: [
    { key: "dashboard", label: "Dashboard", icon: "▤", route: "/" },
    { key: "womensafety", label: "Women Safety", icon: "◈", route: "/safety", ws: true, perm: "safety:read" },
  ]},
  { group: "Analysis", items: [
    { key: "network", label: "Network Graph", icon: "◍", route: "/network", perm: "graph:read" },
    { key: "search", label: "Entity Search", icon: "⌕", route: "/search", perm: "entity:read" },
    { key: "timeline", label: "Timeline", icon: "◷", route: "/timeline", perm: "case:read" },
    { key: "patterns", label: "Pattern Detection", icon: "◫", route: "/patterns", perm: "analytics:run" },
    { key: "risk", label: "Investigation Priority", icon: "◮", route: "/priority", perm: "analytics:run" },
    { key: "links", label: "Link Analysis", icon: "⚭", route: "/link-analysis", perm: "graph:read" },
    { key: "resolution", label: "Entity Resolution", icon: "⧉", route: "/entity-resolution", perm: "entity:read" },
    { key: "nlp", label: "AI & NLP Analysis", icon: "✦", route: "/nlp", perm: "nlp:run" },
  ]},
  { group: "Data", items: [
    { key: "cases", label: "Cases", icon: "▤", route: "/cases", perm: "case:read" },
    { key: "sources", label: "Data Sources", icon: "▥", route: "/data-sources", perm: "case:read" },
    { key: "upload", label: "Upload Data", icon: "⇪", route: "/upload", perm: "data:upload" },
    { key: "manage", label: "Data Management", icon: "▦", route: "/data-management", perm: "entity:read" },
  ]},
  { group: "Reports", items: [
    { key: "reports", label: "Case Reports", icon: "▧", route: "/reports", perm: "report:generate" },
    { key: "audit", label: "Audit Logs", icon: "▨", route: "/audit", perm: "audit:read" },
    { key: "admin", label: "Administration", icon: "⚙", route: "/admin", perm: "user:manage" },
  ]},
];

function avatarTone(role) {
  return {
    WOMEN_SAFETY_OFFICER: "rose",
    ANALYST: "teal",
    SENIOR_INVESTIGATOR: "orange",
    ADMIN: "green",
  }[role] || "";
}

export function Shell({
  user, config, route, navigate, onLogout, dashboard, liveStatus, children,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [expiry, setExpiry] = useState(secondsUntilExpiry());

  const profileRef = useRef(null);
  const notifRef = useRef(null);
  useOutsideClick(profileRef, useCallback(() => setProfileOpen(false), []));
  useOutsideClick(notifRef, useCallback(() => setNotifOpen(false), []));

  useEffect(() => {
    const timer = setInterval(() => setExpiry(secondsUntilExpiry()), 15000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { setMobileOpen(false); }, [route.path]);

  const can = (perm) => !perm || (user.permissions || []).includes(perm);
  const notifications = (dashboard && dashboard.notifications) || [];
  const classification = (config && config.classification) || {};

  const pendingCount = dashboard ? (dashboard.pending_actions || []).length : 0;
  const wsOpen = dashboard
    ? (dashboard.women_safety?.sos?.open || 0) + (dashboard.women_safety?.patterns?.pending || 0)
    : 0;

  return html`<div className="app-shell">
    <aside className=${`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="sidebar-brand">
        <${TrinetraLogo} size=${36} />
        <div className="brand-text">
          <div className="brand-name">TRINETRA</div>
          <div className="brand-sub">Criminal Network Intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        ${NAV.map((section) => {
          const visible = section.items.filter((item) => can(item.perm));
          if (!visible.length) return null;
          return html`<div key=${section.group || "main"}>
            ${section.group ? html`<div className="side-group">${section.group}</div>` : null}
            ${visible.map((item) => {
              const active = route.path === item.route
                || (item.route !== "/" && route.path.startsWith(item.route));
              const badge = item.key === "womensafety" && wsOpen
                ? wsOpen
                : item.key === "links" && pendingCount
                  ? pendingCount
                  : null;
              return html`<button
                key=${item.key}
                className=${`side-link ${item.ws ? "ws-link" : ""} ${active ? "active" : ""}`}
                onClick=${() => navigate(item.route)}
                title=${collapsed ? item.label : undefined}
              >
                <span className="side-icon">${item.icon}</span>
                <span className="side-label">${item.label}</span>
                ${badge
                  ? html`<span className=${`side-badge ${item.key === "links" ? "muted" : ""}`}>${badge}</span>`
                  : null}
              </button>`;
            })}
          </div>`;
        })}
      </nav>

      <div className="sidebar-foot">
        <div className="status-line">
          <span className=${`status-dot ${liveStatus === "live" ? "" : liveStatus === "polling" ? "warn" : "down"}`}></span>
          <span>${liveStatus === "live" ? "Live updates connected"
            : liveStatus === "polling" ? "Live updates: polling" : "Live updates offline"}</span>
        </div>
        <div className="sidebar-foot-text">
          ${config?.app?.name || "TRINETRA"} v${config?.app?.version || "1.0.0"}
          · graph: ${dashboard?.graph_preview?.backend || "embedded"}
        </div>
      </div>
    </aside>

    <div className="content-col">
      <header className="topbar">
        <button className="icon-btn" onClick=${() => {
          if (window.innerWidth <= 780) setMobileOpen((v) => !v);
          else setCollapsed((v) => !v);
        }} title="Toggle navigation" aria-label="Toggle navigation">☰</button>

        <${GlobalSearch} navigate=${navigate} can=${can} />

        <div className="topbar-right">
          ${dashboard && dashboard.cases && dashboard.cases.length
            ? html`<${CasePicker} dashboard=${dashboard} route=${route} navigate=${navigate} />`
            : null}

          <div ref=${notifRef} style=${{ position: "relative" }}>
            <button className="icon-btn" onClick=${() => setNotifOpen((v) => !v)} title="Notifications" aria-label="Notifications">
              ⌾${notifications.length ? html`<span className="dot">${notifications.length}</span>` : null}
            </button>
            ${notifOpen
              ? html`<div className="dropdown">
                  <div className="dropdown-head">
                    <div className="strong">Notifications</div>
                    <div className="tiny muted">${notifications.length} unread</div>
                  </div>
                  <div className="dropdown-body">
                    ${notifications.length
                      ? notifications.map((n) => html`<button
                          key=${n.id} className="dropdown-row"
                          onClick=${() => { setNotifOpen(false); if (n.link) navigate(n.link); }}
                        >
                          <span className=${`pill pill-${String(n.severity).toLowerCase()}`} style=${{ flex: "none" }}>
                            ${n.severity}
                          </span>
                          <span style=${{ flex: 1, textAlign: "left" }}>
                            <div className="strong small">${n.title}</div>
                            <div className="tiny muted">${n.body}</div>
                          </span>
                        </button>`)
                      : html`<div className="dropdown-note">No unread notifications.</div>`}
                  </div>
                </div>`
              : null}
          </div>

          <div ref=${profileRef} style=${{ position: "relative" }}>
            <button className="profile-chip" onClick=${() => setProfileOpen((v) => !v)}>
              <span className=${`avatar ${avatarTone(user.role)}`}>${user.initials}</span>
              <span className="profile-meta">
                <span className="pm-name">${user.full_name}</span>
                <span className="pm-role">${user.service_id} · ${user.role_label}</span>
              </span>
              <span className="muted tiny">▾</span>
            </button>
            ${profileOpen
              ? html`<div className="dropdown">
                  <div className="dropdown-head">
                    <div className="row" style=${{ gap: "11px" }}>
                      <span className=${`avatar lg ${avatarTone(user.role)}`}>${user.initials}</span>
                      <div>
                        <div className="strong">${user.full_name}</div>
                        <div className="small muted">${user.role_label}</div>
                        <div className="tiny muted">${user.unit}</div>
                      </div>
                    </div>
                    <div className="mt-2 tiny muted">
                      <div><b>Service ID:</b> ${user.service_id}</div>
                      ${user.extension ? html`<div><b>Extension:</b> ${user.extension}</div>` : null}
                      <div><b>Last sign-in:</b> ${user.last_login_at ? fmt.dateTime(user.last_login_at) : "First session"}</div>
                      <div><b>Session expires in:</b> ${expiry !== null ? fmt.duration(expiry) : "—"}</div>
                      <div><b>Permissions:</b> ${(user.permissions || []).length} granted</div>
                    </div>
                  </div>
                  <div className="dropdown-body">
                    <button className="dropdown-row" onClick=${() => { setProfileOpen(false); navigate("/profile"); }}>
                      <span>◉</span> My profile & permissions
                    </button>
                    <button className="dropdown-row danger" onClick=${onLogout}>
                      <span>⏻</span> Sign out
                    </button>
                  </div>
                  <div className="dropdown-note">
                    All actions in this session are recorded in the audit log.
                  </div>
                </div>`
              : null}
          </div>
        </div>
      </header>

      ${classification.show_banner
        ? html`<div className="classification-banner">
            ⚠ ${classification.message || "SYNTHETIC DATA — for demonstration and testing only."}
          </div>`
        : null}

      <main className="page">${children}</main>

      <div className="footer-note">
        <div>
          <strong>TRINETRA</strong> is an investigative decision-support system.
          It does not determine guilt and does not replace authorised human judgement.
        </div>
        <div className="footer-badges">
          <span>Privacy</span><span>Access Control</span><span>Audit Logging</span>
          <span>Evidence Preservation</span><span>Human Verification</span>
        </div>
      </div>
    </div>
  </div>`;
}

// ------------------------------------------------------------ case picker

function CasePicker({ dashboard, route, navigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useOutsideClick(ref, useCallback(() => setOpen(false), []));

  const current = dashboard.scope || {};
  return html`<div ref=${ref} style=${{ position: "relative" }}>
    <button className="case-picker" onClick=${() => setOpen((v) => !v)} title="Scope the platform to a case">
      <span className="muted tiny">CASE</span>
      <span className="case-label">${current.case_number || "All cases"}</span>
      <span className="muted tiny">▾</span>
    </button>
    ${open
      ? html`<div className="dropdown">
          <div className="dropdown-head"><div className="strong small">Active case scope</div>
            <div className="tiny muted">Re-scopes the dashboard, timeline and analytics.</div>
          </div>
          <div className="dropdown-body">
            <button className="dropdown-row" onClick=${() => { setOpen(false); navigate(route.path, {}); }}>
              <span>◇</span> All cases
            </button>
            ${dashboard.cases.map((c) => html`<button
              key=${c.id} className="dropdown-row"
              onClick=${() => { setOpen(false); navigate(route.path, { case_id: c.id }); }}
            >
              <span className=${`pill pill-${String(c.priority).toLowerCase()}`} style=${{ flex: "none" }}>
                ${c.module === "WOMEN_SAFETY" ? "WS" : "NET"}
              </span>
              <span style=${{ flex: 1, textAlign: "left" }}>
                <div className="small strong">${c.case_number}</div>
                <div className="tiny muted">${c.title}</div>
              </span>
            </button>`)}
          </div>
        </div>`
      : null}
  </div>`;
}

// ---------------------------------------------------------- global search

function GlobalSearch({ navigate, can }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const debounced = useDebounced(query, 260);
  const ref = useRef(null);
  useOutsideClick(ref, useCallback(() => setResults(null), []));

  useEffect(() => {
    if (!can("entity:read") || debounced.trim().length < 2) {
      setResults(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    api.get("/entities/search", { q: debounced, limit: 8 })
      .then((data) => { if (!cancelled) { setResults(data.results); setHighlight(0); } })
      .catch(() => { if (!cancelled) setResults([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debounced]);

  const open = (uid) => {
    setQuery("");
    setResults(null);
    navigate(`/entity/${uid}`);
  };

  const onKeyDown = (event) => {
    if (!results || !results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => Math.min(results.length - 1, h + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      open(results[highlight].uid);
    } else if (event.key === "Escape") {
      setResults(null);
    }
  };

  return html`<div className="global-search" ref=${ref}>
    <span className="search-icon">⌕</span>
    <input
      className="input" type="search" value=${query} onKeyDown=${onKeyDown}
      placeholder="Search person, phone, location, vehicle, organisation, case…"
      onInput=${(e) => setQuery(e.target.value)}
      onFocus=${() => query.length >= 2 && results === null && setQuery(query)}
    />
    ${results !== null && query.trim().length >= 2
      ? html`<div className="search-dropdown">
          ${loading
            ? html`<div className="search-empty">Searching…</div>`
            : results.length
              ? results.map((item, index) => html`<div
                  key=${item.uid}
                  className=${`search-item ${index === highlight ? "highlighted" : ""}`}
                  onMouseEnter=${() => setHighlight(index)}
                  onClick=${() => open(item.uid)}
                >
                  <span style=${{
                    width: "26px", height: "26px", borderRadius: "7px", flex: "none",
                    display: "grid", placeItems: "center", fontSize: "12px", color: "#fff",
                    background: entityColor(item.type),
                  }}>${ENTITY_GLYPHS[item.type] || "?"}</span>
                  <span style=${{ flex: 1, minWidth: 0 }}>
                    <div className="si-name">${item.name}</div>
                    <div className="si-meta">
                      ${item.type_label} · ${item.connections} connection${item.connections === 1 ? "" : "s"}
                      ${item.aliases && item.aliases.length ? ` · aka ${item.aliases.join(", ")}` : ""}
                    </div>
                  </span>
                  ${item.priority_band
                    ? html`<span className=${`pill pill-${String(item.priority_band).toLowerCase()}`}>
                        ${item.priority_score}
                      </span>`
                    : null}
                </div>`)
              : html`<div className="search-empty">
                  No entities match “${query}”.<br />
                  <span className="tiny">Try a name, phone number, vehicle registration or case number.</span>
                </div>`}
        </div>`
      : null}
  </div>`;
}
