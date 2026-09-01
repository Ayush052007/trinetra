/**
 * Application root: bootstrap, authentication state, routing, live updates.
 */

import {
  html, useState, useEffect, useCallback, useRef,
  ToastProvider, LoadingBlock, ErrorBlock, EmptyState, Button, useAsync,
} from "./lib/ui.js";
import { api, login, logout, refresh, onAuthChange, hadSession, getToken } from "./api/client.js";
import { LoginPage } from "./auth/LoginPage.js";
import { Shell } from "./components/Shell.js";
import { Dashboard } from "./pages/Dashboard.js";
import { NetworkPage } from "./pages/Network.js";
import { EntityProfile } from "./pages/EntityProfile.js";
import { SearchPage } from "./pages/Search.js";
import { TimelinePage } from "./pages/Timeline.js";
import { PriorityPage, PatternsPage, LinkAnalysisPage } from "./pages/Analysis.js";
import { ResolutionPage } from "./pages/Resolution.js";
import { NlpPage } from "./pages/Nlp.js";
import { CasesPage, CaseDetailPage } from "./pages/Cases.js";
import { DataSourcesPage, UploadPage, DataManagementPage } from "./pages/Data.js";
import { ReportsPage } from "./pages/Reports.js";
import { AuditPage, AdminPage, ProfilePage } from "./pages/Admin.js";
import {
  SafetyOverview, SosPage, HeatmapPage, RoutePage,
  IncidentsPage, SafetyPatternsPage, AlertsPage,
} from "./pages/Safety.js";

// ------------------------------------------------------------- routing

function parseLocation() {
  const path = window.location.pathname || "/";
  const params = Object.fromEntries(new URLSearchParams(window.location.search));
  return { path, params };
}

function useRouter() {
  const [route, setRoute] = useState(parseLocation);

  useEffect(() => {
    const onPop = () => setRoute(parseLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((path, params = {}, options = {}) => {
    const search = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    const url = `${path}${search ? `?${search}` : ""}`;
    if (options.replace) window.history.replaceState({}, "", url);
    else window.history.pushState({}, "", url);
    setRoute(parseLocation());
    window.scrollTo({ top: 0 });
  }, []);

  return { route, navigate };
}

// ---------------------------------------------------------- live updates

function useLiveUpdates(enabled, onEvent) {
  const [status, setStatus] = useState("offline");
  const socketRef = useRef(null);
  const pollRef = useRef(null);
  const seqRef = useRef(0);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return undefined;
    let closed = false;

    const startPolling = () => {
      if (pollRef.current) return;
      setStatus("polling");
      pollRef.current = setInterval(async () => {
        try {
          const data = await api.get("/events/poll", { since: seqRef.current });
          seqRef.current = data.seq;
          (data.events || []).forEach((e) => handlerRef.current && handlerRef.current(e));
        } catch (_) {
          /* keep polling; a transient failure is not fatal */
        }
      }, 8000);
    };

    const connect = () => {
      const token = getToken();
      if (!token) return;
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(
        `${protocol}://${window.location.host}/ws/events?token=${encodeURIComponent(token)}`
      );
      socketRef.current = socket;

      socket.onopen = () => {
        if (closed) return;
        setStatus("live");
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.seq) seqRef.current = message.seq;
          if (message.event !== "ping" && handlerRef.current) handlerRef.current(message);
        } catch (_) {}
      };
      socket.onerror = () => { if (!closed) startPolling(); };
      socket.onclose = () => {
        socketRef.current = null;
        if (closed) return;
        setStatus("offline");
        // Fall back to polling, then retry the socket.
        startPolling();
        setTimeout(() => { if (!closed) connect(); }, 12000);
      };
    };

    connect();
    return () => {
      closed = true;
      if (socketRef.current) socketRef.current.close();
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [enabled]);

  return status;
}

// ------------------------------------------------------------------ app

function App() {
  const { route, navigate } = useRouter();
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const [booting, setBooting] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Bootstrap: load public config, then try to restore a session.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const publicConfig = await api.get("/config");
        if (!cancelled) setConfig(publicConfig);
      } catch (_) {
        if (!cancelled) setConfig({});
      }
      if (hadSession()) {
        try {
          const session = await refresh();
          if (!cancelled) setUser(session.user);
        } catch (_) {
          /* refresh cookie gone or expired: fall through to the login screen */
        }
      }
      if (!cancelled) setBooting(false);
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => onAuthChange((event) => {
    if (event.type === "expired") {
      setUser(null);
      setSessionExpired(true);
    }
  }), []);

  const caseId = route.params.case_id ? Number(route.params.case_id) : null;

  const dashboardState = useAsync(
    () => (user ? api.get("/dashboard", caseId ? { case_id: caseId } : {}) : Promise.resolve(null)),
    [user ? user.service_id : null, caseId],
    { immediate: Boolean(user) }
  );

  const liveStatus = useLiveUpdates(Boolean(user), useCallback((event) => {
    // Refresh the shell counters when something operational changes.
    if (["sos", "alerts", "incidents"].includes(event.channel)) {
      dashboardState.reload();
    }
  }, [dashboardState.reload]));

  const onSignedIn = useCallback((session) => {
    setUser(session.user);
    setSessionExpired(false);
    navigate("/", {}, { replace: true });
  }, [navigate]);

  const onLogout = useCallback(async () => {
    await logout();
    setUser(null);
    setSessionExpired(false);
    navigate("/", {}, { replace: true });
  }, [navigate]);

  if (booting) {
    return html`<div className="boot-screen">
      <div className="boot-mark">TN</div>
      <div className="boot-title">TRINETRA</div>
      <div className="boot-sub">Restoring your session…</div>
      <div className="boot-bar"><span></span></div>
    </div>`;
  }

  if (!user) {
    return html`<${LoginPage}
      config=${config} onSignedIn=${onSignedIn} sessionExpired=${sessionExpired}
    />`;
  }

  const page = renderPage({ route, navigate, user, config, dashboardState, caseId });

  return html`<${Shell}
    user=${user} config=${config} route=${route} navigate=${navigate}
    onLogout=${onLogout} dashboard=${dashboardState.data} liveStatus=${liveStatus}
  >${page}<//>`;
}

function renderPage({ route, navigate, user, config, dashboardState, caseId }) {
  const { path, params } = route;
  const common = { navigate, user, config, caseId, params };

  // Entity profile: /entity/<uid>
  if (path.startsWith("/entity/")) {
    return html`<${EntityProfile} ...${common} uid=${decodeURIComponent(path.slice("/entity/".length))} />`;
  }
  // Case detail: /cases/<id>
  if (path.startsWith("/cases/") && path.length > "/cases/".length) {
    return html`<${CaseDetailPage} ...${common} caseIdParam=${Number(path.slice("/cases/".length))} />`;
  }

  switch (path) {
    case "/":
      return html`<${Dashboard}
        data=${dashboardState.data} loading=${dashboardState.loading}
        error=${dashboardState.error} reload=${dashboardState.reload}
        navigate=${navigate} user=${user}
      />`;
    case "/network":       return html`<${NetworkPage} ...${common} />`;
    case "/search":        return html`<${SearchPage} ...${common} />`;
    case "/timeline":      return html`<${TimelinePage} ...${common} />`;
    case "/patterns":      return html`<${PatternsPage} ...${common} />`;
    case "/priority":      return html`<${PriorityPage} ...${common} />`;
    case "/link-analysis": return html`<${LinkAnalysisPage} ...${common} />`;
    case "/entity-resolution": return html`<${ResolutionPage} ...${common} />`;
    case "/nlp":           return html`<${NlpPage} ...${common} />`;
    case "/cases":         return html`<${CasesPage} ...${common} />`;
    case "/data-sources":  return html`<${DataSourcesPage} ...${common} />`;
    case "/upload":        return html`<${UploadPage} ...${common} />`;
    case "/data-management": return html`<${DataManagementPage} ...${common} />`;
    case "/reports":       return html`<${ReportsPage} ...${common} />`;
    case "/audit":         return html`<${AuditPage} ...${common} />`;
    case "/admin":         return html`<${AdminPage} ...${common} />`;
    case "/profile":       return html`<${ProfilePage} ...${common} />`;
    case "/safety":            return html`<${SafetyOverview} ...${common} />`;
    case "/safety/sos":        return html`<${SosPage} ...${common} />`;
    case "/safety/heatmap":    return html`<${HeatmapPage} ...${common} />`;
    case "/safety/route":      return html`<${RoutePage} ...${common} />`;
    case "/safety/incidents":  return html`<${IncidentsPage} ...${common} />`;
    case "/safety/patterns":   return html`<${SafetyPatternsPage} ...${common} />`;
    case "/safety/alerts":     return html`<${AlertsPage} ...${common} />`;
    default:
      return html`<${EmptyState}
        icon="◇" title="Page not found"
        text=${`No screen is registered for ${path}.`}
        action=${html`<${Button} variant="primary" onClick=${() => navigate("/")}>Back to dashboard<//>`}
      />`;
  }
}

// ------------------------------------------------------------- mounting

/** Keeps one bad screen from taking down the whole application. */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error("Render error:", error, info); }
  render() {
    if (this.state.error) {
      return html`<div style=${{ padding: "44px", maxWidth: "640px", margin: "0 auto" }}>
        <h1 style=${{ marginBottom: "10px" }}>Something went wrong</h1>
        <p className="muted">
          An unexpected error occurred while rendering this screen. The details have
          been written to the browser console.
        </p>
        <pre style=${{
          background: "#fdecee", border: "1px solid #f5c2c8", padding: "13px",
          borderRadius: "8px", fontSize: "12px", overflow: "auto", color: "#8e1c27",
        }}>${String(this.state.error && this.state.error.message)}</pre>
        <button className="btn btn-primary mt-2" onClick=${() => window.location.assign("/")}>
          Reload TRINETRA
        </button>
      </div>`;
    }
    return this.props.children;
  }
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(html`<${ErrorBoundary}><${ToastProvider}><${App} /><//><//>`);
