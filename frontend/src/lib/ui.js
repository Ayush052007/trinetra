/**
 * Shared UI primitives and formatting helpers.
 *
 * `html` is htm bound to React.createElement - it gives JSX-like templates
 * with no build step, using tagged template literals.
 */

const { createElement, useState, useEffect, useRef, useCallback, useMemo, useContext, createContext } = React;
export const html = htm.bind(createElement);
export { useState, useEffect, useRef, useCallback, useMemo, useContext, createContext, createElement };

// ------------------------------------------------------------- formatting

export const fmt = {
  number: (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("en-IN")),
  score: (n) => (n === null || n === undefined ? "—" : Number(n).toFixed(1)),
  percent: (n) => (n === null || n === undefined ? "—" : `${Math.round(Number(n) * 100)}%`),
  currency: (n) =>
    n === null || n === undefined ? "—" : `₹${Number(n).toLocaleString("en-IN")}`,

  date(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  },

  dateTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  },

  time(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  },

  relative(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const seconds = Math.round((Date.now() - d.getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)} d ago`;
    return fmt.date(value);
  },

  title: (s) => (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
  duration(seconds) {
    if (seconds === null || seconds === undefined) return "—";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  },
};

// The entity palette from the project material.
export const ENTITY_COLORS = {
  person: "#6d4fd1",
  phone: "#1f9d63",
  location: "#2f6fed",
  organization: "#e07a1f",
  vehicle: "#6b7280",
  transaction: "#c9a227",
  social: "#0ea5a5",
  event: "#c94f7c",
  case_record: "#4a5578",
};

export const ENTITY_GLYPHS = {
  person: "◉", phone: "☎", location: "⌖", organization: "▣",
  vehicle: "▭", transaction: "₹", social: "@", event: "◈", case_record: "§",
};

export const ENTITY_LABELS = {
  person: "Person", phone: "Phone", location: "Location",
  organization: "Organization", vehicle: "Vehicle", transaction: "Transaction",
  social: "Social Handle", event: "Event", case_record: "Prior Case",
};

export const BAND_COLORS = {
  GREEN: "#12855c", YELLOW: "#c9930b", ORANGE: "#e07a1f", RED: "#c62b39",
  LOW: "#12855c", MEDIUM: "#c9930b", HIGH: "#e07a1f", CRITICAL: "#c62b39",
};

export function entityColor(type) {
  return ENTITY_COLORS[type] || "#8892ab";
}

// ------------------------------------------------------------- components

export function Pill({ kind, children, dot }) {
  const cls = `pill pill-${String(kind || "neutral").toLowerCase()}`;
  return html`<span className=${cls}>
    ${dot ? html`<span className="pill-dot"></span>` : null}${children}
  </span>`;
}

/**
 * OBSERVED vs INFERRED is the platform's core integrity distinction, so it
 * gets one component used everywhere rather than ad-hoc styling per screen.
 */
export function EvidenceBadge({ status }) {
  const map = {
    OBSERVED: { label: "Observed", title: "Directly recorded in a source document." },
    VALIDATED: { label: "Validated", title: "Inferred, then confirmed by an authorised investigator." },
    INFERRED: { label: "Inferred", title: "Derived by analysis. Not an observed fact; requires validation." },
    UNDER_REVIEW: { label: "Under Review", title: "Flagged for further investigator review." },
    REJECTED: { label: "Rejected", title: "Reviewed and rejected by an investigator." },
  };
  const meta = map[status] || { label: fmt.title(status), title: "" };
  return html`<span className="pill pill-${String(status).toLowerCase()}" title=${meta.title}>
    ${meta.label}
  </span>`;
}

export function Card({ title, subtitle, actions, children, className = "", pad = true }) {
  return html`<div className=${`card ${pad ? "card-pad" : ""} ${className}`}>
    ${title
      ? html`<div className="card-head">
          <div>
            <div className="card-title">${title}</div>
            ${subtitle ? html`<div className="card-sub">${subtitle}</div>` : null}
          </div>
          ${actions ? html`<div className="card-actions">${actions}</div>` : null}
        </div>`
      : null}
    ${children}
  </div>`;
}

export function Button({ variant = "secondary", size, onClick, disabled, loading, children, type = "button", title, className = "" }) {
  const classes = [
    "btn", `btn-${variant}`, size ? `btn-${size}` : "", className,
  ].filter(Boolean).join(" ");
  return html`<button
    type=${type} className=${classes} onClick=${onClick}
    disabled=${disabled || loading} title=${title}
  >
    ${loading ? html`<span className=${`spinner ${variant === "secondary" ? "spinner-dark" : ""}`}></span>` : null}
    ${children}
  </button>`;
}

export function EmptyState({ icon = "◇", title, text, action }) {
  return html`<div className="empty-state">
    <div className="es-icon">${icon}</div>
    <div className="es-title">${title}</div>
    ${text ? html`<div className="es-text">${text}</div>` : null}
    ${action ? html`<div className="mt-2">${action}</div>` : null}
  </div>`;
}

export function Skeleton({ height = 16, width = "100%", className = "" }) {
  return html`<div className=${`skeleton ${className}`} style=${{ height: `${height}px`, width }}></div>`;
}

export function LoadingBlock({ rows = 3, label }) {
  return html`<div className="stack">
    ${label ? html`<div className="small muted">${label}</div>` : null}
    ${Array.from({ length: rows }).map((_, i) =>
      html`<${Skeleton} key=${i} height=${i === 0 ? 22 : 15} width=${i === 0 ? "45%" : "100%"} />`
    )}
  </div>`;
}

export function ErrorBlock({ error, onRetry }) {
  if (!error) return null;
  return html`<div className="alert alert-error">
    <span>⚠</span>
    <div style=${{ flex: 1 }}>
      <strong>${error.isForbidden ? "Access denied" : "Something went wrong"}</strong>
      ${error.message}
      ${error.requestId
        ? html`<div className="tiny mt-1" style=${{ opacity: .8 }}>Request ID: <span className="mono">${error.requestId}</span></div>`
        : null}
      ${onRetry && !error.isForbidden
        ? html`<div className="mt-1"><${Button} size="sm" onClick=${onRetry}>Try again<//></div>`
        : null}
    </div>
  </div>`;
}

export function Modal({ title, subtitle, onClose, children, footer, size = "" }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose && onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return html`<div className="modal-backdrop" onClick=${(e) => e.target === e.currentTarget && onClose && onClose()}>
    <div className=${`modal ${size}`} role="dialog" aria-modal="true">
      <div className="modal-head">
        <div>
          <h3>${title}</h3>
          ${subtitle ? html`<div className="card-sub mt-1">${subtitle}</div>` : null}
        </div>
        <button className="icon-btn" onClick=${onClose} aria-label="Close">✕</button>
      </div>
      <div className="modal-body">${children}</div>
      ${footer ? html`<div className="modal-foot">${footer}</div>` : null}
    </div>
  </div>`;
}

export function Drawer({ title, subtitle, onClose, children, footer }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose && onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return html`<div className="drawer-backdrop" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div className="drawer">
      <div className="modal-head">
        <div>
          <h3>${title}</h3>
          ${subtitle ? html`<div className="card-sub mt-1">${subtitle}</div>` : null}
        </div>
        <button className="icon-btn" onClick=${onClose} aria-label="Close">✕</button>
      </div>
      <div className="modal-body">${children}</div>
      ${footer ? html`<div className="modal-foot">${footer}</div>` : null}
    </div>
  </div>`;
}

export function Disclaimer({ children, subtle }) {
  return html`<div className=${`disclaimer-box ${subtle ? "subtle" : ""}`}>${children}</div>`;
}

export function BarChart({ items, colorFor, max }) {
  const peak = max || Math.max(1, ...items.map((i) => i.value));
  return html`<div className="bar-chart">
    ${items.map(
      (item) => html`<div className="bar-row" key=${item.label}>
        <div className="nowrap" style=${{ overflow: "hidden", textOverflow: "ellipsis" }} title=${item.label}>
          ${item.label}
        </div>
        <div className="bar-track">
          <div className="bar-fill" style=${{
            width: `${Math.max(2, (item.value / peak) * 100)}%`,
            background: colorFor ? colorFor(item) : "var(--indigo)",
          }}></div>
        </div>
        <div className="bar-value">${item.display || fmt.number(item.value)}</div>
      </div>`
    )}
  </div>`;
}

export function FactorList({ factors, maxContribution }) {
  if (!factors || !factors.length) return null;
  const peak = maxContribution || Math.max(...factors.map((f) => Math.abs(f.contribution || 0)), 1);
  return html`<div>
    ${factors.map(
      (factor) => html`<div className="factor-row" key=${factor.key || factor.label}>
        <div>
          <div className="factor-label">${factor.label}</div>
          <div className="factor-detail">${factor.detail}</div>
          ${factor.contribution !== undefined
            ? html`<div className="factor-bar">
                <span style=${{ width: `${Math.min(100, (Math.abs(factor.contribution) / peak) * 100)}%` }}></span>
              </div>`
            : null}
        </div>
        ${factor.contribution !== undefined
          ? html`<div className="factor-contrib">
              ${typeof factor.contribution === "number" ? factor.contribution.toFixed(1) : factor.contribution}
              ${factor.weight !== undefined ? html`<div className="tiny muted" style=${{ fontWeight: 400 }}>w ${factor.weight}</div>` : null}
            </div>`
          : null}
      </div>`
    )}
  </div>`;
}

// --------------------------------------------------------------- toasts

const ToastContext = createContext({ push: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, kind = "success", ttl = 4600) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((current) => [...current, { id, message, kind }]);
    setTimeout(() => setToasts((c) => c.filter((t) => t.id !== id)), ttl);
  }, []);
  const dismiss = useCallback((id) => setToasts((c) => c.filter((t) => t.id !== id)), []);

  return html`<${ToastContext.Provider} value=${{ push }}>
    ${children}
    <div className="toast-stack">
      ${toasts.map(
        (t) => html`<div className=${`toast ${t.kind}`} key=${t.id}>
          <div style=${{ flex: 1 }}>${t.message}</div>
          <button className="toast-close" onClick=${() => dismiss(t.id)}>✕</button>
        </div>`
      )}
    </div>
  <//>`;
}

// ----------------------------------------------------------------- hooks

/** Fetch-on-mount with loading/error state and a manual reload. */
export function useAsync(fn, deps = [], options = {}) {
  const { immediate = true } = options;
  const [state, setState] = useState({ data: null, loading: immediate, error: null });
  const mounted = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current();
      if (mounted.current) setState({ data, loading: false, error: null });
      return data;
    } catch (error) {
      if (mounted.current) setState({ data: null, loading: false, error });
      return null;
    }
  }, []);

  useEffect(() => {
    if (immediate) run();
  }, deps);

  return { ...state, reload: run, setData: (data) => setState((s) => ({ ...s, data })) };
}

export function useDebounced(value, delay = 280) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

/** Close a popover when clicking outside it. */
export function useOutsideClick(ref, onOutside) {
  useEffect(() => {
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onOutside();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ref, onOutside]);
}
