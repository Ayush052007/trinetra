/**
 * API client.
 *
 * Handles bearer-token attachment, silent refresh on 401, and a uniform error
 * shape so every screen can render a real message instead of a stack trace.
 */

const BASE = "/api/v1";

let accessToken = null;
let tokenExpiry = null;
let refreshPromise = null;
const listeners = new Set();

/** Raised for any non-2xx response. Carries the server's error envelope. */
export class ApiError extends Error {
  constructor(status, payload) {
    const detail = payload && payload.error ? payload.error : {};
    super(detail.message || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code || `http_${status}`;
    this.requestId = detail.requestId || detail.request_id || null;
    this.fields = detail.fields || null;
    this.detail = detail;
  }

  get isAuthError() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isLocked() {
    return this.status === 423;
  }
}

export function onAuthChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(event) {
  listeners.forEach((fn) => {
    try {
      fn(event);
    } catch (err) {
      console.error("auth listener failed", err);
    }
  });
}

export function setSession(session) {
  accessToken = session ? session.access_token : null;
  tokenExpiry = session && session.expires_at ? new Date(session.expires_at) : null;
  if (session) {
    try {
      sessionStorage.setItem("trinetra_has_session", "1");
    } catch (_) {
      /* private browsing: session simply will not survive a reload */
    }
  } else {
    try {
      sessionStorage.removeItem("trinetra_has_session");
    } catch (_) {}
  }
}

export function getToken() {
  return accessToken;
}

export function hadSession() {
  try {
    return sessionStorage.getItem("trinetra_has_session") === "1";
  } catch (_) {
    return false;
  }
}

export function secondsUntilExpiry() {
  if (!tokenExpiry) return null;
  return Math.max(0, Math.round((tokenExpiry - new Date()) / 1000));
}

/**
 * Exchange the refresh cookie for a new access token.
 * Concurrent callers share one in-flight request.
 */
export async function refresh() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
      });
      if (!response.ok) throw new ApiError(response.status, await safeJson(response));
      const session = await response.json();
      setSession(session);
      emit({ type: "refreshed", session });
      return session;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (_) {
    return null;
  }
}

async function execute(path, options = {}, retry = true) {
  const { raw = false, ...init } = options;
  const headers = new Headers(init.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(path.startsWith("/api") ? path : `${BASE}${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
    });
  } catch (networkError) {
    throw new ApiError(0, {
      error: {
        code: "network_error",
        message:
          "Could not reach the server. Check that the TRINETRA service is running.",
      },
    });
  }

  if (response.status === 401 && retry && accessToken) {
    // The access token expired mid-session: refresh once and replay.
    try {
      await refresh();
      return execute(path, options, false);
    } catch (_) {
      setSession(null);
      emit({ type: "expired" });
      throw new ApiError(401, {
        error: { code: "session_expired", message: "Your session has expired. Please sign in again." },
      });
    }
  }

  if (!response.ok) {
    const payload = await safeJson(response);
    const error = new ApiError(response.status, payload);
    if (error.isAuthError) {
      setSession(null);
      emit({ type: "expired" });
    }
    throw error;
  }

  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path, params) => {
    const query = params
      ? "?" +
        new URLSearchParams(
          Object.entries(params).filter(
            ([, v]) => v !== undefined && v !== null && v !== ""
          )
        ).toString()
      : "";
    return execute(`${path}${query}`);
  },
  post: (path, body) =>
    execute(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: (path, body) =>
    execute(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: (path) => execute(path, { method: "DELETE" }),
  upload: (path, formData) => execute(path, { method: "POST", body: formData }),
  raw: (path, params) => {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    return execute(`${path}${query}`, { raw: true });
  },
};

// ------------------------------------------------------------------ auth

export async function login(serviceId, password, remember) {
  const response = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ service_id: serviceId, password, remember }),
  });
  const payload = await safeJson(response);
  if (!response.ok) throw new ApiError(response.status, payload);
  setSession(payload);
  emit({ type: "login", session: payload });
  return payload;
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch (_) {
    /* signing out locally matters more than the server round trip */
  }
  setSession(null);
  emit({ type: "logout" });
}

/**
 * Download a file through the authenticated client.
 * A plain link cannot carry the Authorization header.
 */
export async function download(path, filename) {
  const response = await api.raw(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
