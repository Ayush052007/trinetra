/** Audit log, administration and the signed-in user's own profile. */

import {
  html, useState, useCallback,
  Card, Button, Pill, EmptyState, LoadingBlock, ErrorBlock,
  useAsync, fmt, useToast,
} from "../lib/ui.js";
import { api, download } from "../api/client.js";

const RESULT_KIND = { SUCCESS: "green", DENIED: "orange", FAILURE: "red" };

// ============================================================== audit log

export function AuditPage({ user }) {
  const [action, setAction] = useState(null);
  const [result, setResult] = useState(null);
  const [query, setQuery] = useState("");
  const [days, setDays] = useState(null);
  const [offset, setOffset] = useState(0);
  const limit = 100;
  const toast = useToast();
  const canExport = (user.permissions || []).includes("data:export");

  const { data, loading, error, reload } = useAsync(
    () => api.get("/audit/logs", {
      action: action || undefined, result: result || undefined,
      q: query || undefined, days: days || undefined, offset, limit,
    }),
    [action, result, query, days, offset]
  );

  const exportCsv = useCallback(async () => {
    try {
      await download("/audit/logs/export?days=30", "trinetra_audit.csv");
      toast.push("Audit log exported.", "success");
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Audit Logs</h1>
        <p>
          Append-only record of every consequential action: sign-ins, searches,
          evidence views, validations, uploads, exports and permission denials.
        </p>
      </div>
      <div className="page-head-actions">
        ${canExport ? html`<${Button} size="sm" onClick=${exportCsv}>Export CSV (30 days)<//>` : null}
        <${Button} size="sm" onClick=${reload} loading=${loading}>Refresh<//>
      </div>
    </div>

    <${Card} className="mb-2">
      <input className="input" placeholder="Search actor, action or detail…" value=${query}
        onInput=${(e) => { setQuery(e.target.value); setOffset(0); }} />
      <div className="row mt-2">
        <span className="small strong">Result</span>
        ${["SUCCESS", "DENIED", "FAILURE"].map((value) => html`<button
          key=${value} className=${`chip ${result === value ? "active" : ""}`}
          onClick=${() => { setResult(result === value ? null : value); setOffset(0); }}
        >${value}</button>`)}
        <span style=${{ width: "1px", height: "18px", background: "var(--line)" }}></span>
        <span className="small strong">Period</span>
        ${[[1, "24 h"], [7, "7 days"], [30, "30 days"]].map(([value, label]) => html`<button
          key=${value} className=${`chip ${days === value ? "active" : ""}`}
          onClick=${() => { setDays(days === value ? null : value); setOffset(0); }}
        >${label}</button>`)}
      </div>
      <div className="row mt-2">
        <span className="small strong">Action</span>
        ${(data?.actions || []).slice(0, 14).map((item) => html`<button
          key=${item.action} className=${`chip ${action === item.action ? "active" : ""}`}
          onClick=${() => { setAction(action === item.action ? null : item.action); setOffset(0); }}
        >${fmt.title(item.action)} <span className="tiny muted">${item.count}</span></button>`)}
      </div>
    <//>

    ${error ? html`<${ErrorBlock} error=${error} onRetry=${reload} />` : null}

    <${Card}>
      ${loading && !data ? html`<${LoadingBlock} rows=${8} />` : null}
      ${data && data.items.length === 0
        ? html`<${EmptyState} title="No matching audit events" text="Adjust the filters above." />`
        : null}
      ${data && data.items.length
        ? html`<div>
            <div className="table-wrap">
              <table className="data">
                <thead><tr>
                  <th>Time</th><th>Actor</th><th>Role</th><th>Action</th>
                  <th>Resource</th><th>Result</th><th>Detail</th><th>IP</th>
                </tr></thead>
                <tbody>
                  ${data.items.map((entry) => html`<tr key=${entry.id}>
                    <td className="tiny nowrap">${fmt.dateTime(entry.timestamp)}</td>
                    <td className="tiny">${entry.actor}</td>
                    <td className="tiny muted">${entry.actor_role || "—"}</td>
                    <td><span className="mono tiny">${entry.action}</span></td>
                    <td className="tiny muted">
                      ${entry.resource_type ? `${entry.resource_type}` : "—"}
                      ${entry.resource_id ? html`<div className="mono">${entry.resource_id}</div>` : null}
                    </td>
                    <td><${Pill} kind=${RESULT_KIND[entry.result] || "neutral"}>${entry.result}<//></td>
                    <td className="tiny">${entry.detail || "—"}</td>
                    <td className="tiny muted mono">${entry.ip_address || "—"}</td>
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
  </div>`;
}

// ========================================================== administration

export function AdminPage({ navigate }) {
  const toast = useToast();
  const users = useAsync(() => api.get("/audit/users"), []);
  const system = useAsync(() => api.get("/dashboard/system"), []);
  const roles = useAsync(() => api.get("/auth/roles"), []);

  const unlock = useCallback(async (serviceId) => {
    try {
      const result = await api.post(`/audit/users/${serviceId}/unlock`);
      toast.push(result.message, "success");
      users.reload();
    } catch (err) {
      toast.push(err.message, "error");
    }
  }, [users, toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>Administration</h1>
        <p>Department roster, account status and system health.</p>
      </div>
    </div>

    ${system.data
      ? html`<div className="grid-4 mb-2">
          ${[
            ["Environment", system.data.environment],
            ["Database", system.data.database],
            ["Graph backend", system.data.graph_backend],
            ["Classification", system.data.classification],
            ["Users active", `${system.data.users_active} / ${system.data.users_total}`],
            ["Audit events (24 h)", fmt.number(system.data.audit_events_24h)],
            ["Failed sign-ins (24 h)", fmt.number(system.data.failed_logins_24h)],
            ["Access denied (24 h)", fmt.number(system.data.access_denied_24h)],
          ].map(([label, value]) => html`<div className="card card-pad" key=${label}>
            <div className="kpi-label">${label}</div>
            <div style=${{ fontSize: "17px", fontWeight: 700 }}>${value}</div>
          </div>`)}
        </div>`
      : null}

    <${Card} title="Department roster" className="mb-2">
      ${users.loading ? html`<${LoadingBlock} rows=${5} /> ` : null}
      ${users.error ? html`<${ErrorBlock} error=${users.error} onRetry=${users.reload} />` : null}
      ${users.data
        ? html`<div className="table-wrap">
            <table className="data">
              <thead><tr>
                <th>Service ID</th><th>Name</th><th>Designation</th><th>Unit</th>
                <th className="num">Permissions</th><th>Last sign-in</th>
                <th className="num">Sessions</th><th>Status</th><th></th>
              </tr></thead>
              <tbody>
                ${users.data.items.map((member) => html`<tr key=${member.service_id}>
                  <td className="mono strong">${member.service_id}</td>
                  <td>${member.full_name}</td>
                  <td className="tiny">${member.designation}</td>
                  <td className="tiny muted">${member.unit}</td>
                  <td className="num">${member.permission_count}</td>
                  <td className="tiny nowrap">${member.last_login_at ? fmt.relative(member.last_login_at) : "never"}</td>
                  <td className="num">${member.active_sessions}</td>
                  <td>
                    ${member.is_locked
                      ? html`<${Pill} kind="red">Locked<//>`
                      : member.is_active
                        ? html`<${Pill} kind="green">Active<//>`
                        : html`<${Pill} kind="neutral">Disabled<//>`}
                  </td>
                  <td>
                    ${member.is_locked
                      ? html`<${Button} size="sm" onClick=${() => unlock(member.service_id)}>Unlock<//>`
                      : null}
                  </td>
                </tr>`)}
              </tbody>
            </table>
          </div>`
        : null}
    <//>

    <${Card} title="Roles and permissions" subtitle="Enforced by the backend on every endpoint">
      ${(roles.data?.roles || []).map((role) => html`<div key=${role.role} className="mb-2">
        <div className="row-between mb-1">
          <span className="strong">${role.designation}</span>
          <span className="mono tiny muted">${role.role} · ${role.permissions.length} permissions</span>
        </div>
        <div className="row" style=${{ gap: "5px" }}>
          ${role.permissions.map((perm) => html`<span key=${perm} className="pill pill-neutral"
            style=${{ textTransform: "none", letterSpacing: 0 }}>${perm}</span>`)}
        </div>
      </div>`)}
    <//>
  </div>`;
}

// ================================================================ profile

export function ProfilePage({ user, config }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const changePassword = useCallback(async () => {
    if (next !== confirm) {
      toast.push("The new passwords do not match.", "error");
      return;
    }
    setSaving(true);
    try {
      await api.post("/auth/change-password", {
        current_password: current, new_password: next,
      });
      toast.push("Password changed. All sessions were signed out — please sign in again.", "success");
      setTimeout(() => window.location.assign("/"), 1800);
    } catch (err) {
      const errors = err.detail?.errors;
      toast.push(errors ? errors.join(" ") : err.message, "error");
    } finally {
      setSaving(false);
    }
  }, [current, next, confirm, toast]);

  return html`<div>
    <div className="page-head">
      <div className="page-head-main">
        <h1>My Profile</h1>
        <p>Your account, role and the permissions it grants.</p>
      </div>
    </div>

    <div className="grid-2">
      <${Card} title="Account">
        <div className="kv-row"><span className="kv-key">Full name</span><span className="kv-val">${user.full_name}</span></div>
        <div className="kv-row"><span className="kv-key">Service ID</span><span className="kv-val mono">${user.service_id}</span></div>
        <div className="kv-row"><span className="kv-key">Designation</span><span className="kv-val">${user.designation}</span></div>
        <div className="kv-row"><span className="kv-key">Role</span><span className="kv-val mono">${user.role}</span></div>
        <div className="kv-row"><span className="kv-key">Unit</span><span className="kv-val">${user.unit}</span></div>
        ${user.email ? html`<div className="kv-row"><span className="kv-key">Email</span><span className="kv-val">${user.email}</span></div>` : null}
        ${user.extension ? html`<div className="kv-row"><span className="kv-key">Extension</span><span className="kv-val">${user.extension}</span></div>` : null}
        <div className="kv-row"><span className="kv-key">Last sign-in</span>
          <span className="kv-val">${user.last_login_at ? fmt.dateTime(user.last_login_at) : "First session"}</span></div>
      <//>

      <${Card} title="Change password">
        <div className="field">
          <label>Current password</label>
          <input className="input" type="password" value=${current} onInput=${(e) => setCurrent(e.target.value)} />
        </div>
        <div className="field">
          <label>New password</label>
          <input className="input" type="password" value=${next} onInput=${(e) => setNext(e.target.value)} />
          <div className="hint">
            At least 12 characters, with an uppercase letter, a lowercase letter, a digit and a symbol.
          </div>
        </div>
        <div className="field">
          <label>Confirm new password</label>
          <input className="input" type="password" value=${confirm} onInput=${(e) => setConfirm(e.target.value)} />
        </div>
        <${Button} variant="primary" loading=${saving}
          disabled=${!current || !next || !confirm} onClick=${changePassword}>
          Change password
        <//>
        <div className="tiny muted mt-2">
          Changing your password signs out every active session, including this one.
        </div>
      <//>
    </div>

    <${Card} title=${`Permissions granted (${(user.permissions || []).length})`} className="mt-2">
      <div className="row" style=${{ gap: "5px" }}>
        ${(user.permissions || []).map((perm) => html`<span key=${perm} className="pill pill-info"
          style=${{ textTransform: "none", letterSpacing: 0 }}>${perm}</span>`)}
      </div>
      <div className="tiny muted mt-2">
        These are enforced by the backend on every request. An action you lack permission
        for returns 403 from the server, not merely a hidden button.
      </div>
    <//>
  </div>`;
}
