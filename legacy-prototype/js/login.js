/*
 * TriNetra — investigator sign-in gate.
 * No backend: this validates against a single documented demo credential and
 * persists the session in sessionStorage (cleared when the browser tab/session
 * ends). It is a UI/workflow demonstration of the "Secure investigator login"
 * step described in the platform's own workflow docs — not real authentication
 * or encryption, and it makes no such claim.
 */

(function () {
  const DEMO_ID = "IO-114";
  const DEMO_PASSWORD = "TriNetra@2026";

  const ROLE_AVATARS = {
    "Investigating Officer": "IO",
    "Intelligence Analyst": "IA",
    "Cyber & Financial Investigator": "CF",
    "Supervisory Officer": "SO",
    "NCRB Administrator": "NA",
  };

  const form = document.getElementById("login-form");
  const idInput = document.getElementById("login-id");
  const pwInput = document.getElementById("login-password");
  const roleSelect = document.getElementById("login-role");
  const rememberInput = document.getElementById("login-remember");
  const errorBox = document.getElementById("login-error");
  const submitBtn = document.getElementById("login-submit");

  document.getElementById("pw-toggle").addEventListener("click", () => {
    pwInput.type = pwInput.type === "password" ? "text" : "password";
  });

  document.getElementById("fill-demo-creds").addEventListener("click", () => {
    idInput.value = DEMO_ID;
    pwInput.value = DEMO_PASSWORD;
    errorBox.classList.add("hidden");
  });

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }

  function completeLogin(role) {
    const avatar = ROLE_AVATARS[role] || "IO";
    if (rememberInput.checked) {
      sessionStorage.setItem("trinetra_auth", "1");
      sessionStorage.setItem("trinetra_role", role);
      sessionStorage.setItem("trinetra_avatar", avatar);
    }
    document.documentElement.classList.add("authed");
    const roleEl = document.getElementById("profile-role");
    const avatarEl = document.getElementById("profile-avatar");
    const menuRoleEl = document.getElementById("profile-menu-role");
    if (roleEl) roleEl.textContent = role;
    if (avatarEl) avatarEl.textContent = avatar;
    if (menuRoleEl) menuRoleEl.textContent = role;
    if (typeof logAudit === "function") {
      logAudit("Investigator login", `ID: ${DEMO_ID} · Role: ${role}`);
    }
    if (window.TriNetraApp && typeof window.TriNetraApp.onLogin === "function") {
      window.TriNetraApp.onLogin();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");

    const id = idInput.value.trim();
    const pw = pwInput.value;
    const role = roleSelect.value;

    if (!id || !pw) {
      showError("Enter your Investigator ID and password to continue.");
      return;
    }
    if (id.toLowerCase() !== DEMO_ID.toLowerCase() || pw !== DEMO_PASSWORD) {
      showError("Invalid credentials. Use the demo credentials shown below, or contact your System Administrator.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Authenticating…";
    setTimeout(() => {
      completeLogin(role);
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign In →";
    }, 700);
  });

  // Already-authenticated session (sessionStorage persisted across a reload) —
  // the inline anti-flash script in index.html already added the .authed
  // class synchronously, so just restore the profile chip text and run the
  // deferred dashboard-graph init once the rest of app.js has loaded.
  if (sessionStorage.getItem("trinetra_auth")) {
    const role = sessionStorage.getItem("trinetra_role") || "Investigating Officer";
    const avatar = sessionStorage.getItem("trinetra_avatar") || "IO";
    document.getElementById("profile-role").textContent = role;
    document.getElementById("profile-avatar").textContent = avatar;
    document.getElementById("profile-menu-role").textContent = role;
    window.addEventListener("DOMContentLoaded", () => {
      if (window.TriNetraApp && typeof window.TriNetraApp.onLogin === "function") {
        window.TriNetraApp.onLogin();
      }
    });
  }

  // Profile menu + logout
  const profileChip = document.getElementById("profile-chip");
  const profileMenu = document.getElementById("profile-menu");
  profileChip.addEventListener("click", (e) => {
    e.stopPropagation();
    profileMenu.classList.toggle("hidden");
  });
  document.addEventListener("click", () => profileMenu.classList.add("hidden"));

  document.getElementById("logout-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    if (typeof logAudit === "function") logAudit("Investigator logout", "Session ended");
    sessionStorage.removeItem("trinetra_auth");
    sessionStorage.removeItem("trinetra_role");
    sessionStorage.removeItem("trinetra_avatar");
    document.documentElement.classList.remove("authed");
    profileMenu.classList.add("hidden");
    form.reset();
    errorBox.classList.add("hidden");
  });

  // Sidebar collapse toggle (mobile)
  document.getElementById("sidebar-toggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
})();
