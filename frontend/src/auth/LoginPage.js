/**
 * Sign-in.
 *
 * Layout follows the convention enterprise identity platforms settled on: the
 * product mark anchored top-left, one centred card carrying the whole task,
 * and nothing else competing for attention.
 *
 * There is no role selector (a real system derives role from the account, never
 * from user choice) and no credential auto-fill. Failure states are the real
 * ones the API returns: remaining attempts, account lockout with a live
 * countdown, expired session, and forced password change.
 */

import { html, useState, useEffect, useRef, Button, fmt } from "../lib/ui.js";
import { login, ApiError } from "../api/client.js";
import { TrinetraLogo } from "../components/Brand.js";

export function LoginPage({ config, onSignedIn, sessionExpired }) {
  const [serviceId, setServiceId] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [attemptsLeft, setAttemptsLeft] = useState(null);
  const [lockedUntil, setLockedUntil] = useState(null);
  const [countdown, setCountdown] = useState(0);
  const idInput = useRef(null);

  const [initialising, setInitialising] = useState(false);

  useEffect(() => {
    if (idInput.current) idInput.current.focus();
  }, []);

  // A freshly deployed instance seeds itself on first boot. Until that
  // finishes there are no accounts, and a sign-in attempt would fail with a
  // misleading "invalid credentials". Poll health and say what is happening.
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const poll = async () => {
      try {
        const response = await fetch("/api/v1/health");
        const health = await response.json();
        if (cancelled) return;
        setInitialising(Boolean(health.initialising));
        if (health.initialising) timer = setTimeout(poll, 4000);
      } catch (_) {
        /* server not reachable yet; the sign-in error path covers it */
      }
    };
    poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, []);

  // Live lockout countdown, so the user sees exactly when they can retry.
  useEffect(() => {
    if (!lockedUntil) return undefined;
    const tick = () => {
      const remaining = Math.max(0, Math.round((new Date(lockedUntil) - Date.now()) / 1000));
      setCountdown(remaining);
      if (remaining === 0) {
        setLockedUntil(null);
        setError(null);
        setAttemptsLeft(null);
      }
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [lockedUntil]);

  const locked = Boolean(lockedUntil) && countdown > 0;

  async function submit(event) {
    event.preventDefault();
    if (submitting || locked) return;

    const id = serviceId.trim();
    if (!id) {
      setError({ message: "Enter your Service ID." });
      return;
    }
    if (!password) {
      setError({ message: "Enter your password." });
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const session = await login(id, password, remember);
      setPassword("");
      onSignedIn(session);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail || {};
        if (err.isLocked) {
          setLockedUntil(detail.locked_until || new Date(Date.now() + 15 * 60000).toISOString());
          setError({ message: detail.message || "Account temporarily locked." });
        } else {
          setAttemptsLeft(
            detail.attempts_remaining !== undefined ? detail.attempts_remaining : null
          );
          setError({ message: err.message });
        }
      } else {
        setError({ message: "Sign-in failed. Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const app = (config && config.app) || {};
  const deployment = (config && config.deployment) || {};
  const classification = (config && config.classification) || {};
  const session = (config && config.session) || {};

  return html`<div className="auth-shell">
    <header className="auth-topbar">
      <div className="auth-brand">
        <${TrinetraLogo} size=${46} />
        <span className="auth-brand-name">TRINETRA</span>
      </div>
      ${classification.show_banner
        ? html`<span className="auth-classification-chip">
            ${classification.label || "SYNTHETIC"} DATA
          </span>`
        : null}
    </header>

    <main className="auth-main">
      <div className="auth-card">
        <div className="auth-card-head">
          <h1>Sign in</h1>
          <p>Authorised personnel only. Every attempt is recorded.</p>
        </div>

        <form onSubmit=${submit} noValidate>
          ${initialising
            ? html`<div className="alert alert-info">
                <span className="spinner spinner-dark"></span>
                <div>
                  <strong>Setting up for the first time</strong>
                  This instance is preparing its database. Sign-in becomes
                  available in about a minute - this page will update itself.
                </div>
              </div>`
            : null}

          ${sessionExpired && !error
            ? html`<div className="alert alert-warn">
                <span>◷</span>
                <div><strong>Session expired</strong>Please sign in again to continue.</div>
              </div>`
            : null}

          ${locked
            ? html`<div className="alert alert-error">
                <span>⛔</span>
                <div>
                  <strong>Account temporarily locked</strong>
                  Too many failed attempts. Try again in
                  <strong style=${{ display: "inline" }}> ${fmt.duration(countdown)}</strong>.
                </div>
              </div>`
            : error
              ? html`<div className="alert alert-error">
                  <span>⚠</span>
                  <div>
                    <strong>Could not sign in</strong>
                    ${error.message}
                    ${attemptsLeft !== null && attemptsLeft > 0
                      ? html`<div className="tiny mt-1">
                          ${attemptsLeft} attempt${attemptsLeft === 1 ? "" : "s"} remaining
                          before the account is locked.
                        </div>`
                      : null}
                  </div>
                </div>`
              : null}

          <div className="field">
            <label htmlFor="service-id">Service ID</label>
            <input
              id="service-id" ref=${idInput}
              className=${`input ${error && !locked ? "error" : ""}`}
              type="text" value=${serviceId} autoComplete="username" spellCheck="false"
              placeholder="e.g. IO-114" disabled=${submitting || locked}
              onInput=${(e) => setServiceId(e.target.value.toUpperCase())}
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password" className=${`input ${error && !locked ? "error" : ""}`}
                type=${showPassword ? "text" : "password"} value=${password}
                autoComplete="current-password" placeholder="••••••••••••"
                disabled=${submitting || locked}
                onInput=${(e) => setPassword(e.target.value)}
              />
              <button
                type="button" className="password-toggle" tabIndex=${-1}
                onClick=${() => setShowPassword((v) => !v)}
                aria-label=${showPassword ? "Hide password" : "Show password"}
              >${showPassword ? "Hide" : "Show"}</button>
            </div>
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox" checked=${remember} disabled=${submitting || locked}
              onChange=${(e) => setRemember(e.target.checked)}
            />
            Keep me signed in on this device
          </label>

          <${Button}
            type="submit" variant="primary" size="lg" className="btn-block auth-submit"
            loading=${submitting} disabled=${locked || initialising}
          >
            ${submitting ? "Signing in…"
              : initialising ? "Preparing…"
              : locked ? `Locked — ${fmt.duration(countdown)}`
              : "Sign in"}
          <//>
        </form>

        <div className="auth-card-foot">
          Forgot your password? Contact your System Administrator.
          <br />
          ${session.max_failed_logins || 5} failed attempts locks an account for
          ${" "}${session.lockout_minutes || 15} minutes.
        </div>
      </div>
    </main>

    <footer className="auth-foot">
      ${deployment.organisation
        ? html`<span>${deployment.organisation}${deployment.division ? ` · ${deployment.division}` : ""}</span>`
        : null}
      <span className="auth-foot-sep">·</span>
      <span>${app.name || "TRINETRA"} v${app.version || "1.0.0"}</span>
      ${classification.show_banner
        ? html`<${"span"}>
            <span className="auth-foot-sep">·</span>
            <span className="auth-foot-warn">Synthetic data — not for operational use</span>
          <//>`
        : null}
    </footer>
  </div>`;
}
