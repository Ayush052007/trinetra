/*
 * TriNetra app shell: view routing, search, entity profiles, evidence modal,
 * and all page renderers. No backend — everything here reads/writes the
 * in-memory synthetic datasets defined in data.js / data-womensafety.js.
 */

(function () {
  let currentView = "dashboard";
  let selectedEntityId = null;
  let graphInitialized = false;
  let dashGraphInitialized = false;
  let extractionAdded = false;
  let timelineFilter = "all";

  const DashboardGraph = createGraphController(ENTITIES, RELATIONSHIPS);

  // ---------------- View routing ----------------

  function switchView(name, opts) {
    opts = opts || {};
    currentView = name;
    document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
    const el = document.getElementById("view-" + name);
    if (el) el.classList.add("active");
    document.querySelectorAll(".side-link").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === name);
    });
    document.getElementById("sidebar").classList.remove("open");
    window.scrollTo(0, 0);

    if (name === "network") {
      ensureGraphInitialized();
      if (opts.centerOn) {
        setTimeout(() => {
          TriNetraGraph.centerOn(opts.centerOn);
          renderEntityDetailPanel(opts.centerOn);
        }, 50);
      } else {
        setTimeout(() => TriNetraGraph.fit(), 50);
      }
      if (opts.openCandidateEdge) {
        setTimeout(() => openEvidenceModal(opts.openCandidateEdge), 400);
      }
    }
    if (name === "womensafety") window.WomenSafety.render();
    if (name === "timeline") renderTimelinePage();
    if (name === "patterns") renderPatternsPage();
    if (name === "riskscoring") renderRiskScoringPage();
    if (name === "linkanalysis") renderLinkAnalysisPage();
    if (name === "datasources") renderDataSourcesPage();
    if (name === "datamanagement") renderDataManagementPage();
    if (name === "reports") renderReportsPage();
    if (name === "auditlogs") renderAuditLogsPage();
  }

  document.querySelectorAll(".side-link").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });

  document.querySelectorAll("[data-action]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const action = el.dataset.action;
      if (action === "open-network") switchView("network");
      else if (action === "open-womensafety") switchView("womensafety");
      else if (action === "open-riskscoring") switchView("riskscoring");
      else if (action === "open-linkanalysis") switchView("linkanalysis");
      else if (action === "open-timeline") switchView("timeline");
    });
  });

  document.getElementById("global-search").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const q = e.target.value;
    switchView("investigation");
    setTimeout(() => {
      const input = document.getElementById("investigation-search");
      input.value = q;
      input.dispatchEvent(new Event("input"));
    }, 30);
  });

  // ---------------- Dashboard ----------------

  function buildMainTimelineEvents() {
    const dated = RELATIONSHIPS.filter((r) => r.timestamp)
      .slice()
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    return dated.map((r) => {
      const src = getEntity(r.source);
      const tgt = getEntity(r.target);
      const category = /CALLED/.test(r.type)
        ? "calls"
        : /MET/.test(r.type)
        ? "meetings"
        : /TRANSFERRED/.test(r.type)
        ? "transactions"
        : /VISITED/.test(r.type)
        ? "locations"
        : "other";
      return {
        category,
        dateLabel: r.timestamp,
        title: `${REL_LABELS[r.type] || r.type}${r.callCount ? " ×" + r.callCount : ""}`,
        description: `${src ? src.name : "?"} ${(REL_LABELS[r.type] || r.type).toLowerCase()} ${tgt ? tgt.name : "?"}`,
        tagClass: category === "transactions" ? "tag-escalation" : "",
      };
    });
  }

  function ensureDashboardGraphInitialized() {
    if (dashGraphInitialized) return;
    DashboardGraph.init("cy-dashboard", {});
    dashGraphInitialized = true;
    setTimeout(() => DashboardGraph.fit(), 60);
  }
  document.getElementById("dash-graph-reset").addEventListener("click", () => DashboardGraph.reset());

  function renderRiskLeaderboard() {
    const people = ENTITIES.filter((e) => e.type === "person").map((e) => Object.assign({ id: e.id, name: e.name, source: "main" }, investigationPriority(e.id)));
    const wsTop = {
      id: "S1",
      name: wsGetEntity("S1").name,
      source: "ws",
      label: WOMEN_SAFETY_CASE.riskScore.label,
      confidence: WOMEN_SAFETY_CASE.riskScore.confidence,
    };
    const combined = [wsTop, ...people].sort((a, b) => b.confidence - a.confidence).slice(0, 5);
    document.getElementById("risk-leaderboard").innerHTML = combined
      .map(
        (p, idx) => `
      <div class="leaderboard-row" data-id="${p.id}" data-source="${p.source}">
        <div class="lb-top"><span class="lb-name">${idx + 1}. ${p.name}${p.source === "ws" ? ' <span class="cite-badge synthetic">Women Safety</span>' : ""}</span><span class="lb-score">${Math.round(p.confidence * 100)}%</span></div>
        <div class="lb-bar-track"><div class="lb-bar-fill ${p.label.toLowerCase()}" style="width:${Math.round(p.confidence * 100)}%"></div></div>
      </div>`
      )
      .join("");
    document.querySelectorAll("#risk-leaderboard .leaderboard-row").forEach((row) => {
      row.addEventListener("click", () => {
        if (row.dataset.source === "ws") switchView("womensafety");
        else switchView("network", { centerOn: row.dataset.id });
      });
    });
  }

  function renderInsightList() {
    const insights = [
      {
        dot: "orange",
        text: `<strong>${getEntity("p1").name}</strong> shows a high number of connections this week and is flagged Investigation Priority: HIGH.`,
        time: "Updated just now",
        action: () => switchView("network", { centerOn: "p1" }),
      },
      {
        dot: "indigo",
        text: `A candidate hidden link was surfaced between <strong>${getEntity("p1").name}</strong> and <strong>${getEntity("p3").name}</strong> — pending investigator review.`,
        time: "Awaiting review",
        action: () => switchView("network", { centerOn: "p1", openCandidateEdge: findEdgeId("p1", "p3", "CONNECTED_TO") }),
      },
      {
        dot: "red",
        text: `Women Safety Module: <strong>${wsGetEntity("S1").name}</strong> flagged HIGH risk with a confirmed alias link to a prior stalking FIR.`,
        time: "Investigator review requested",
        action: () => switchView("womensafety"),
      },
      {
        dot: "green",
        text: `A relationship cluster has formed around <strong>${getEntity("o1").name}</strong>.`,
        time: "Detected via community structure",
        action: () => switchView("network", { centerOn: "o1" }),
      },
    ];
    document.getElementById("insight-list").innerHTML = insights
      .map(
        (i, idx) => `
        <div class="insight-item" data-idx="${idx}">
          <span class="dot ${i.dot}"></span>
          <div><div>${i.text}</div><div class="insight-time">${i.time}</div></div>
        </div>`
      )
      .join("");
    document.querySelectorAll("#insight-list .insight-item").forEach((el, idx) => {
      el.addEventListener("click", () => insights[idx].action());
    });
  }

  function renderDashTimelineStrip() {
    renderTimelineList(document.getElementById("dash-timeline-strip"), buildMainTimelineEvents().slice(0, 5));
  }

  function renderHeatmap() {
    const positions = { l2: [40, 52], l3: [46, 40], l1: [64, 46], l4: [20, 66], l5: [72, 26] };
    const locs = ENTITIES.filter((e) => e.type === "location");
    const maxDeg = Math.max(...locs.map((l) => edgesForEntity(l.id).length), 1);
    document.getElementById("dash-heatmap").innerHTML = locs
      .map((l) => {
        const deg = edgesForEntity(l.id).length;
        const intensity = deg / maxDeg;
        const size = 28 + intensity * 56;
        const color = intensity > 0.66 ? "var(--red)" : intensity > 0.33 ? "var(--orange)" : "var(--green)";
        const pos = positions[l.id] || [50, 50];
        return `<div class="heat-spot" style="left:${pos[0]}%; top:${pos[1]}%; width:${size}px; height:${size}px; background:radial-gradient(circle, ${color} 0%, transparent 72%); opacity:0.75;">
          <span class="heat-spot-label">${l.name.split(",")[0]} (${deg})</span>
        </div>`;
      })
      .join("");
  }

  function renderSampleTable() {
    const rows = buildSampleDatasetRows(10);
    document.getElementById("dash-sample-table").innerHTML = `
      <thead><tr><th>ID</th><th>Source</th><th>FIR ID</th><th>Date</th><th>Person</th><th>Alias</th><th>Phone</th><th>Location</th><th>Organization</th><th>Vehicle</th><th>Txn Amt</th><th>Txn Type</th><th>Description</th><th>Risk</th></tr></thead>
      <tbody>${rows
        .map(
          (r) => `<tr><td>${r.recordId}</td><td>${r.sourceType}</td><td>${r.firId}</td><td>${r.date}</td><td>${r.personName}</td><td>${r.alias}</td><td>${r.phone}</td><td>${r.location}</td><td>${r.organization}</td><td>${r.vehicle}</td><td>${r.transactionAmount}</td><td>${r.transactionType}</td><td>${r.description}</td><td>${r.riskScore}</td></tr>`
        )
        .join("")}</tbody>`;
  }

  function renderDashboard() {
    document.getElementById("kpi-records").textContent = RELATIONSHIPS.length + ENTITIES.length;
    document.getElementById("kpi-entities").textContent = ENTITIES.length;
    document.getElementById("kpi-relationships").textContent = RELATIONSHIPS.length;
    document.getElementById("kpi-cases").textContent = CASES.length + 1;
    document.getElementById("kpi-leads").textContent =
      RELATIONSHIPS.filter((r) => r.candidateHiddenLink).length + WS_RELATIONSHIPS.filter((r) => r.candidateHiddenLink).length;

    document.getElementById("dashboard-legend").innerHTML = Object.entries(ENTITY_TYPES)
      .map(([, t]) => `<span class="legend-item"><span class="legend-swatch" style="background:${t.color}"></span>${t.label}</span>`)
      .join("");

    renderRiskLeaderboard();
    renderInsightList();
    renderDashTimelineStrip();
    renderHeatmap();
    renderSampleTable();
  }

  // ---------------- Investigation / search (Entity Search) ----------------

  const searchInput = document.getElementById("investigation-search");
  const resultsEl = document.getElementById("investigation-results");
  const profileEl = document.getElementById("entity-profile");

  function renderSearchResults(query) {
    const hits = searchEntities(query);
    if (!query) {
      resultsEl.innerHTML = "";
      return;
    }
    if (hits.length === 0) {
      resultsEl.innerHTML = `<div style="color:var(--gray); font-size:0.88rem;">No matching entities in the synthetic dataset. Try the Women Safety Module for case DEMO/WS-2026-0417.</div>`;
      return;
    }
    resultsEl.innerHTML = hits
      .map(
        (e) => `
        <div class="search-result-row" data-id="${e.id}">
          <div class="entity-badge" style="background:${ENTITY_TYPES[e.type].color}">${entityIconLabel(e.type)}</div>
          <div>
            <div class="result-name">${e.name}${e.aliases.length ? ` <span style="color:var(--gray); font-weight:400;">(alias: ${e.aliases.join(", ")})</span>` : ""}</div>
            <div class="result-type">${ENTITY_TYPES[e.type].label}</div>
          </div>
        </div>`
      )
      .join("");

    resultsEl.querySelectorAll(".search-result-row").forEach((row) => {
      row.addEventListener("click", () => renderEntityProfile(row.dataset.id));
    });
  }

  function renderEntityProfile(id) {
    const e = getEntity(id);
    if (!e) return;
    selectedEntityId = id;
    const conns = edgesForEntity(id);
    const priority = investigationPriority(id);
    const phones = neighborsOf(id).filter((n) => n.type === "phone").map((n) => n.name);
    const locations = neighborsOf(id).filter((n) => n.type === "location").map((n) => n.name);
    const orgs = neighborsOf(id).filter((n) => n.type === "organization").map((n) => n.name);
    const txns = neighborsOf(id).filter((n) => n.type === "transaction").map((n) => n.name);

    profileEl.innerHTML = `
      <div class="card profile-card">
        <div style="grid-column: 1 / -1;">
          <div class="profile-head">
            <div class="entity-badge" style="background:${ENTITY_TYPES[e.type].color}">${entityIconLabel(e.type)}</div>
            <div>
              <h2>${e.name}</h2>
              <div class="sub">${ENTITY_TYPES[e.type].label}${e.meta && e.meta.occupation ? " · " + e.meta.occupation : ""}</div>
            </div>
          </div>

          <div class="profile-fields">
            <div><div class="field-label">Known Aliases</div><div class="field-value">${e.aliases.length ? e.aliases.join(", ") : "—"}</div></div>
            <div><div class="field-label">Connections</div><div class="field-value">${conns.length}</div></div>
            <div><div class="field-label">Associated Phones</div><div class="field-value">${phones.length ? phones.join(", ") : "—"}</div></div>
            <div><div class="field-label">Locations</div><div class="field-value">${locations.length ? locations.join(", ") : "—"}</div></div>
            <div><div class="field-label">Organizations</div><div class="field-value">${orgs.length ? orgs.join(", ") : "—"}</div></div>
            <div><div class="field-label">Transactions</div><div class="field-value">${txns.length ? txns.join(", ") : "—"}</div></div>
            <div><div class="field-label">Investigation Priority</div><div class="field-value"><span class="pill ${priority.label.toLowerCase()}">${priority.label}</span></div></div>
            <div><div class="field-label">Analytical Confidence</div><div class="field-value">${Math.round(priority.confidence * 100)}%</div></div>
          </div>

          <button class="btn btn-primary" id="explore-network-btn">Explore Network</button>
        </div>
      </div>`;

    document.getElementById("explore-network-btn").addEventListener("click", () => {
      switchView("network", { centerOn: id });
    });
  }

  searchInput.addEventListener("input", (e) => renderSearchResults(e.target.value));
  document.getElementById("investigation-search-clear").addEventListener("click", () => {
    searchInput.value = "";
    resultsEl.innerHTML = "";
    profileEl.innerHTML = "";
  });

  // ---------------- Network graph view ----------------

  function ensureGraphInitialized() {
    if (graphInitialized) return;
    TriNetraGraph.init("cy", {
      onNodeSelect: renderEntityDetailPanel,
      onCandidateEdgeSelect: openEvidenceModal,
    });
    graphInitialized = true;

    const filterWrap = document.getElementById("type-filters");
    filterWrap.innerHTML = Object.entries(ENTITY_TYPES)
      .filter(([key]) => ENTITIES.some((e) => e.type === key))
      .map(
        ([key, t]) => `
        <label class="filter-chip">
          <input type="checkbox" value="${key}" checked />
          <span class="swatch" style="background:${t.color}"></span>${t.label}
        </label>`
      )
      .join("");

    filterWrap.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener("change", () => {
        const active = Array.from(filterWrap.querySelectorAll('input[type="checkbox"]:checked')).map((c) => c.value);
        TriNetraGraph.setTypeFilter(active);
      });
    });

    document.getElementById("graph-search").addEventListener("input", (e) => {
      TriNetraGraph.searchHighlight(e.target.value);
    });

    document.getElementById("graph-reset").addEventListener("click", () => {
      document.getElementById("graph-search").value = "";
      filterWrap.querySelectorAll('input[type="checkbox"]').forEach((cb) => (cb.checked = true));
      TriNetraGraph.reset();
      document.getElementById("entity-detail-panel").innerHTML = `<div class="detail-empty">Click a node to see entity details.</div>`;
    });

    document.getElementById("graph-legend").innerHTML = Object.entries(ENTITY_TYPES)
      .filter(([key]) => ENTITIES.some((e) => e.type === key))
      .map(([key, t]) => `<span class="legend-item"><span class="legend-swatch" style="background:${t.color}"></span>${t.label}</span>`)
      .join("");
  }

  function renderEntityDetailPanel(id) {
    const e = getEntity(id);
    if (!e) return;
    selectedEntityId = id;
    const conns = edgesForEntity(id);
    const priority = investigationPriority(id);
    const candidates = conns.filter((c) => c.candidateHiddenLink);

    const relRows = conns
      .map((r) => {
        const otherId = r.source === id ? r.target : r.source;
        const other = getEntity(otherId);
        const clickable = r.candidateHiddenLink ? ` data-edge="${r.id}" style="cursor:pointer;"` : "";
        return `<div class="rel-row"${clickable}>
          <div><span class="rel-tag">${REL_LABELS[r.type]}</span> <span class="rel-target">${other ? other.name : "?"}</span></div>
          <span class="verify-state ${r.verification}">${r.verification}</span>
        </div>`;
      })
      .join("");

    const candidateNotes = candidates
      .map(
        (c) => `
        <div class="candidate-note" data-edge="${c.id}" style="cursor:pointer;">
          <strong>AI Insight:</strong> Potentially significant connection detected (${Math.round(c.confidence * 100)}% analytical confidence). Click to review evidence.
        </div>`
      )
      .join("");

    document.getElementById("entity-detail-panel").innerHTML = `
      <div class="section-title">Entity Details</div>
      <div class="profile-head" style="margin-bottom:10px;">
        <div class="entity-badge" style="background:${ENTITY_TYPES[e.type].color}">${entityIconLabel(e.type)}</div>
        <div><h2 style="font-size:1.05rem;">${e.name}</h2><div class="sub">${ENTITY_TYPES[e.type].label}</div></div>
      </div>
      <div class="profile-fields" style="grid-template-columns:1fr 1fr;">
        <div><div class="field-label">Connections</div><div class="field-value">${conns.length}</div></div>
        <div><div class="field-label">Investigation Priority</div><div class="field-value"><span class="pill ${priority.label.toLowerCase()}">${priority.label}</span></div></div>
        <div><div class="field-label">Analytical Confidence</div><div class="field-value">${Math.round(priority.confidence * 100)}%</div></div>
      </div>
      <div class="section-title" style="font-size:0.85rem; margin-top:14px;">Relationships</div>
      ${relRows || '<div class="detail-empty">No relationships recorded.</div>'}
      ${candidateNotes}
    `;

    document.querySelectorAll("#entity-detail-panel [data-edge]").forEach((el) => {
      el.addEventListener("click", () => openEvidenceModal(el.dataset.edge));
    });
  }

  // ---------------- Evidence modal + human verification (shared across cases) ----------------

  function findRelById(id) {
    return RELATIONSHIPS.find((r) => r.id === id) || WS_RELATIONSHIPS.find((r) => r.id === id);
  }
  function findEntityAnywhere(id) {
    return getEntity(id) || wsGetEntity(id);
  }

  function openEvidenceModal(edgeId) {
    const rel = findRelById(edgeId);
    if (!rel) return;
    const pool = RELATIONSHIPS.some((r) => r.id === edgeId) ? RELATIONSHIPS : WS_RELATIONSHIPS;
    const srcEntity = findEntityAnywhere(rel.source);
    const tgtEntity = findEntityAnywhere(rel.target);

    let evidenceHtml;
    if (rel.candidateHiddenLink) {
      const refs = (rel.evidenceRefs || []).map((rid) => pool.find((r) => r.id === rid)).filter(Boolean);
      evidenceHtml = `
        <p style="font-size:0.85rem; color:var(--navy-soft);">${rel.explanation}</p>
        <div class="field-label" style="margin-top:10px;">Supporting records</div>
        <ul class="evidence-list">
          ${refs
            .map((r) => {
              const a = findEntityAnywhere(r.source),
                b = findEntityAnywhere(r.target);
              return `<li><strong>${REL_LABELS[r.type] || r.type}</strong> — ${a ? a.name : "?"} ↔ ${b ? b.name : "?"}<br/><span class="evidence-tag">Source: ${r.evidenceSource} · ${r.timestamp || "—"} · Confidence ${Math.round(r.confidence * 100)}%</span></li>`;
            })
            .join("")}
        </ul>`;
    } else {
      evidenceHtml = `
        <ul class="evidence-list">
          <li><strong>${REL_LABELS[rel.type] || rel.type}</strong> — ${srcEntity.name} ↔ ${tgtEntity.name}<br/>
          <span class="evidence-tag">Source: ${rel.evidenceSource} · ${rel.timestamp || "—"} · Confidence ${Math.round(rel.confidence * 100)}%</span></li>
        </ul>`;
    }

    const modalRoot = document.getElementById("modal-root");
    modalRoot.innerHTML = `
      <div class="modal-backdrop" id="modal-backdrop">
        <div class="modal">
          <button class="close-x" id="modal-close">✕</button>
          <h3>${rel.candidateHiddenLink ? "Candidate Hidden Link — Evidence Review" : "Relationship Evidence"}</h3>
          <div style="font-size:0.82rem; color:var(--gray); margin-bottom:8px;">
            ${srcEntity.name} <strong>${REL_LABELS[rel.type] || rel.type}</strong> ${tgtEntity.name}
            &nbsp;<span class="verify-state ${rel.verification}">${rel.verification}</span>
          </div>
          ${evidenceHtml}
          ${
            rel.candidateHiddenLink
              ? `<div style="margin-top:14px;">
                  <button class="btn btn-accept btn-sm" id="modal-accept">Accept as Investigative Lead</button>
                  <button class="btn btn-reject btn-sm" id="modal-reject">Reject</button>
                </div>`
              : ""
          }
        </div>
      </div>`;

    document.getElementById("modal-close").addEventListener("click", closeModal);
    document.getElementById("modal-backdrop").addEventListener("click", (e) => {
      if (e.target.id === "modal-backdrop") closeModal();
    });

    const acceptBtn = document.getElementById("modal-accept");
    const rejectBtn = document.getElementById("modal-reject");
    if (acceptBtn) acceptBtn.addEventListener("click", () => setVerification(rel.id, "reviewed"));
    if (rejectBtn) rejectBtn.addEventListener("click", () => setVerification(rel.id, "rejected"));
  }

  function setVerification(edgeId, state) {
    const rel = findRelById(edgeId);
    if (!rel) return;
    rel.verification = state;
    logAudit(
      state === "reviewed" ? "Accepted AI-suggested link" : "Rejected AI-suggested link",
      `${findEntityAnywhere(rel.source).name} — ${REL_LABELS[rel.type] || rel.type} — ${findEntityAnywhere(rel.target).name}`
    );
    closeModal();
    if (selectedEntityId) renderEntityDetailPanel(selectedEntityId);
    if (window.WomenSafety) window.WomenSafety.refreshSelectedPanel();
    if (graphInitialized) {
      const el = TriNetraGraph.getCy().getElementById(edgeId);
      if (!el.empty()) el.data("verification", state);
    }
    const wsCy = WomenSafetyGraph.getCy();
    if (wsCy) {
      const el2 = wsCy.getElementById(edgeId);
      if (!el2.empty()) el2.data("verification", state);
    }
    if (currentView === "linkanalysis") renderLinkAnalysisPage();
  }

  function closeModal() {
    document.getElementById("modal-root").innerHTML = "";
  }

  // ---------------- AI / NLP Extraction demo ----------------

  document.getElementById("fir-text").textContent = SAMPLE_FIR_TEXT;

  const stepOrder = ["raw", "nlp", "entities", "relations"];

  function resetExtractionUI() {
    document.querySelectorAll("#pipeline-steps .pipeline-step").forEach((el) => el.classList.remove("active", "done"));
    document.getElementById("extraction-results").classList.add("hidden");
    document.getElementById("extracted-entities").innerHTML = "";
    document.getElementById("detected-relationships").innerHTML = "";
    document.getElementById("added-confirmation").textContent = "";
    document.getElementById("add-to-graph").disabled = false;
    extractionAdded = false;
  }

  function runExtraction() {
    resetExtractionUI();
    let i = 0;
    function step() {
      if (i > 0) {
        const prevEl = document.querySelector(`#pipeline-steps .pipeline-step[data-step="${stepOrder[i - 1]}"]`);
        prevEl.classList.remove("active");
        prevEl.classList.add("done");
      }
      if (i >= stepOrder.length) {
        showExtractionResults();
        return;
      }
      const el = document.querySelector(`#pipeline-steps .pipeline-step[data-step="${stepOrder[i]}"]`);
      el.classList.add("active");
      i += 1;
      setTimeout(step, 550);
    }
    step();
  }

  function showExtractionResults() {
    const wrap = document.getElementById("extracted-entities");
    wrap.innerHTML = SAMPLE_EXTRACTION.entities
      .map(
        (ent, idx) => `
        <div class="extract-card fade-in-item" style="background:${ENTITY_TYPES[ent.type].color}; animation-delay:${idx * 60}ms;">
          <div class="et">${ENTITY_TYPES[ent.type].label}</div>
          <div class="ev">${ent.value}</div>
        </div>`
      )
      .join("");

    const relWrap = document.getElementById("detected-relationships");
    relWrap.innerHTML = SAMPLE_EXTRACTION.relationships
      .map(
        (r, idx) => `
        <div class="rel-detected-row fade-in-item" style="animation-delay:${idx * 80}ms;">
          <strong>${r.from}</strong> <span style="color:var(--indigo-dark); font-weight:700;">${r.rel}</span> <strong>${r.to}</strong>
        </div>`
      )
      .join("");

    document.getElementById("extraction-results").classList.remove("hidden");
  }

  document.getElementById("run-extraction").addEventListener("click", runExtraction);
  document.getElementById("reset-extraction").addEventListener("click", resetExtractionUI);

  document.getElementById("add-to-graph").addEventListener("click", () => {
    if (extractionAdded) return;
    extractionAdded = true;
    const entityIds = SAMPLE_EXTRACTION.entities.map((e) => e.entityId);
    const edgeIds = SAMPLE_EXTRACTION.relationships.map((r) => r.edgeId).filter(Boolean);
    document.getElementById("added-confirmation").textContent = "Added to knowledge graph — opening Network Graph…";
    document.getElementById("add-to-graph").disabled = true;
    logAudit("Entities added to knowledge graph", "Via AI/NLP extraction demo — sample FIR text");
    setTimeout(() => {
      switchView("network");
      setTimeout(() => TriNetraGraph.addHighlightedElements(entityIds, edgeIds), 60);
    }, 700);
  });

  // ---------------- Timeline page ----------------

  function renderTimelinePage() {
    const filters = ["all", "calls", "meetings", "transactions", "locations"];
    const filterWrap = document.getElementById("timeline-filters");
    filterWrap.innerHTML = filters
      .map((f) => `<button class="btn ${f === timelineFilter ? "btn-primary" : "btn-secondary"} btn-sm" data-filter="${f}">${f[0].toUpperCase() + f.slice(1)}</button>`)
      .join("");
    filterWrap.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        timelineFilter = btn.dataset.filter;
        renderTimelinePage();
      });
    });

    let events = buildMainTimelineEvents();
    if (timelineFilter !== "all") events = events.filter((e) => e.category === timelineFilter);
    renderTimelineList(document.getElementById("timeline-list"), events);
  }

  // ---------------- Pattern Detection / Graph Analytics page ----------------

  function renderPatternsPage() {
    document.getElementById("pattern-cards").innerHTML = `
      <div class="analytics-card"><div class="ac-icon">🕸</div><div class="ac-title">Centrality Analysis</div><div class="ac-desc">Identifies highly connected entities.</div></div>
      <div class="analytics-card"><div class="ac-icon">🧩</div><div class="ac-title">Community Detection</div><div class="ac-desc">Identifies clusters within the network.</div></div>
      <div class="analytics-card"><div class="ac-icon">📈</div><div class="ac-title">Anomaly Detection</div><div class="ac-desc">Highlights unusual activity patterns.</div></div>
      <div class="analytics-card"><div class="ac-icon">🔗</div><div class="ac-title">Link Analysis</div><div class="ac-desc">Finds potentially significant connections.</div></div>
    `;
    const top = ENTITIES.map((e) => ({ label: e.name, value: edgesForEntity(e.id).length }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
    renderBarChart(document.getElementById("top-connected-chart"), top);
    document.getElementById("pattern-review-evidence").onclick = () => openEvidenceModal(findEdgeId("p1", "p3", "CONNECTED_TO"));
  }

  // ---------------- Risk Scoring page ----------------

  function renderRiskScoringPage() {
    const people = ENTITIES.filter((e) => e.type === "person").map((e) =>
      Object.assign({ id: e.id, name: e.name, case: CASES[0].id, source: "main" }, investigationPriority(e.id))
    );
    const wsEntry = {
      id: "S1",
      name: wsGetEntity("S1").name,
      case: WOMEN_SAFETY_CASE.id,
      source: "ws",
      label: WOMEN_SAFETY_CASE.riskScore.label,
      confidence: WOMEN_SAFETY_CASE.riskScore.confidence,
    };
    const combined = [...people, wsEntry].sort((a, b) => b.confidence - a.confidence);
    document.getElementById("risk-scoring-list").innerHTML = combined
      .map(
        (p, idx) => `
      <div class="leaderboard-row" data-id="${p.id}" data-source="${p.source}">
        <div class="lb-top"><span class="lb-name">${idx + 1}. ${p.name} <span class="link-card-case" style="margin-left:6px;">${p.case}</span></span><span class="lb-score"><span class="pill ${p.label.toLowerCase()}">${p.label}</span> ${Math.round(p.confidence * 100)}%</span></div>
        <div class="lb-bar-track"><div class="lb-bar-fill ${p.label.toLowerCase()}" style="width:${Math.round(p.confidence * 100)}%"></div></div>
      </div>`
      )
      .join("");
    document.querySelectorAll("#risk-scoring-list .leaderboard-row").forEach((row) => {
      row.addEventListener("click", () => {
        if (row.dataset.source === "ws") switchView("womensafety");
        else switchView("network", { centerOn: row.dataset.id });
      });
    });
  }

  // ---------------- Link Analysis page ----------------

  function renderLinkAnalysisPage() {
    const mainCandidates = RELATIONSHIPS.filter((r) => r.candidateHiddenLink).map((r) => Object.assign({ caseLabel: CASES[0].id, getE: getEntity }, r));
    const wsCandidates = WS_RELATIONSHIPS.filter((r) => r.candidateHiddenLink).map((r) => Object.assign({ caseLabel: WOMEN_SAFETY_CASE.id, getE: wsGetEntity }, r));
    const all = [...mainCandidates, ...wsCandidates];
    const wrap = document.getElementById("link-analysis-list");
    if (!all.length) {
      wrap.innerHTML = '<div class="card card-pad detail-empty">No candidate links pending review.</div>';
      return;
    }
    wrap.innerHTML = all
      .map((r) => {
        const a = r.getE(r.source),
          b = r.getE(r.target);
        return `<div class="link-card">
        <div class="link-card-top">
          <div><div class="link-card-case">${r.caseLabel}</div><div class="link-card-title">${a.name} ↔ ${b.name} <span style="color:var(--gray); font-weight:600;">(${REL_LABELS[r.type] || r.type})</span></div></div>
          <span class="verify-state ${r.verification}">${r.verification}</span>
        </div>
        <div class="link-card-explanation">${r.explanation || "—"} <strong>${Math.round(r.confidence * 100)}% confidence.</strong></div>
        <button class="btn btn-primary btn-sm" data-edge="${r.id}">Review Evidence</button>
      </div>`;
      })
      .join("");
    wrap.querySelectorAll("[data-edge]").forEach((btn) => btn.addEventListener("click", () => openEvidenceModal(btn.dataset.edge)));
  }

  // ---------------- Data Sources page ----------------

  function renderDataSourcesPage() {
    const counts = computeDataSourceCounts(RELATIONSHIPS.concat(WS_RELATIONSHIPS));
    document.getElementById("data-sources-grid").innerHTML = counts
      .map(
        (c) => `
      <div class="analytics-card">
        <div class="ac-icon">🗄</div>
        <div class="ac-title">${c.label}</div>
        <div class="ac-desc">Formats: ${c.formats}</div>
        <div class="ac-count">${c.count} <span style="font-size:0.7rem; color:var(--green); font-weight:700;">● Connected</span></div>
      </div>`
      )
      .join("");
  }

  // ---------------- Data Ingestion / Upload page ----------------

  const ingestionStepOrder = ["uploaded", "preprocessing", "nlp", "matching", "relationships", "graph", "complete"];

  function resetIngestionUI() {
    document.querySelectorAll("#ingestion-pipeline-steps .pipeline-step").forEach((el) => el.classList.remove("active", "done"));
    document.getElementById("ingestion-results").classList.add("hidden");
  }

  document.getElementById("process-data-btn").addEventListener("click", () => {
    resetIngestionUI();
    logAudit("Data ingestion run started", "Simulated pipeline over uploaded files");
    let i = 0;
    function step() {
      if (i > 0) {
        const prevEl = document.querySelector(`#ingestion-pipeline-steps .pipeline-step[data-step="${ingestionStepOrder[i - 1]}"]`);
        prevEl.classList.remove("active");
        prevEl.classList.add("done");
      }
      if (i >= ingestionStepOrder.length) {
        document.getElementById("ingestion-results").classList.remove("hidden");
        logAudit("Data ingestion complete", "1,284 records processed · 327 entities extracted · 582 relationships discovered");
        return;
      }
      const el = document.querySelector(`#ingestion-pipeline-steps .pipeline-step[data-step="${ingestionStepOrder[i]}"]`);
      el.classList.add("active");
      i += 1;
      setTimeout(step, 420);
    }
    step();
  });

  // ---------------- Data Management page ----------------

  function renderDataManagementPage(filter) {
    const q = (filter || "").trim().toLowerCase();
    const mainRows = ENTITIES.map((e) => ({ name: e.name, type: e.type, case: CASES[0].id, degree: edgesForEntity(e.id).length, id: e.id, source: "main" }));
    const wsRows = WS_ENTITIES.map((e) => ({ name: e.name, type: e.type, case: WOMEN_SAFETY_CASE.id, degree: wsEdgesForEntity(e.id).length, id: e.id, source: "ws" }));
    let all = [...mainRows, ...wsRows];
    if (q) all = all.filter((r) => r.name.toLowerCase().includes(q));
    all.sort((a, b) => b.degree - a.degree);
    document.getElementById("datamanagement-table").innerHTML = `
      <thead><tr><th>Name</th><th>Type</th><th>Case</th><th>Connections</th></tr></thead>
      <tbody>${all.map((r) => `<tr data-id="${r.id}" data-source="${r.source}" style="cursor:pointer;"><td>${r.name}</td><td>${ENTITY_TYPES[r.type].label}</td><td>${r.case}</td><td>${r.degree}</td></tr>`).join("")}</tbody>`;
    document.querySelectorAll("#datamanagement-table tbody tr").forEach((tr) => {
      tr.addEventListener("click", () => {
        if (tr.dataset.source === "ws") switchView("womensafety");
        else switchView("network", { centerOn: tr.dataset.id });
      });
    });
  }
  document.getElementById("datamanagement-search").addEventListener("input", (e) => renderDataManagementPage(e.target.value));

  // ---------------- CSV / report export ----------------

  function toCsv(rows, headers) {
    const esc = (v) => `"${String(v === undefined || v === null ? "" : v).replace(/"/g, '""')}"`;
    return [headers.map(esc).join(","), ...rows.map((r) => headers.map((h) => esc(r[h])).join(","))].join("\r\n");
  }

  function downloadBlob(filename, content) {
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function exportCsv(which, kind) {
    let entities, relationships, prefix;
    if (which === "ws") {
      entities = WS_ENTITIES;
      relationships = WS_RELATIONSHIPS;
      prefix = "trinetra_womensafety";
    } else if (which === "all") {
      entities = ENTITIES.concat(WS_ENTITIES);
      relationships = RELATIONSHIPS.concat(WS_RELATIONSHIPS);
      prefix = "trinetra_all_cases";
    } else {
      entities = ENTITIES;
      relationships = RELATIONSHIPS;
      prefix = "trinetra_main_case";
    }

    if (kind === "entities") {
      const rows = entities.map((e) => ({ id: e.id, name: e.name, type: e.type, aliases: (e.aliases || []).join("; ") }));
      downloadBlob(`${prefix}_entities.csv`, toCsv(rows, ["id", "name", "type", "aliases"]));
    } else {
      const rows = relationships.map((r) => ({
        source: r.source,
        target: r.target,
        type: r.type,
        confidence: r.confidence,
        observed: r.isObserved,
        evidenceSource: r.evidenceSource,
        timestamp: r.timestamp || "",
      }));
      downloadBlob(`${prefix}_relationships.csv`, toCsv(rows, ["source", "target", "type", "confidence", "observed", "evidenceSource", "timestamp"]));
    }
    logAudit("Data exported (CSV)", `${prefix} · ${kind}`);
  }

  document.getElementById("export-entities-csv").addEventListener("click", () => {
    exportCsv(document.getElementById("export-dataset-select").value, "entities");
    document.getElementById("export-confirmation").textContent = "Entities CSV downloaded.";
  });
  document.getElementById("export-relationships-csv").addEventListener("click", () => {
    exportCsv(document.getElementById("export-dataset-select").value, "relationships");
    document.getElementById("export-confirmation").textContent = "Relationships CSV downloaded.";
  });

  // ---------------- Case Reports page ----------------

  function renderReportsPage() {
    const mainAnomalies = RELATIONSHIPS.filter((r) => r.candidateHiddenLink).length;
    const wsAnomalies = WS_RELATIONSHIPS.filter((r) => r.candidateHiddenLink).length;
    const mainPriority = investigationPriority("p1");

    document.getElementById("report-cards").innerHTML = `
      <div class="card card-pad">
        <div class="section-title">Case ${CASES[0].id} — ${CASES[0].title}</div>
        <div class="profile-fields">
          <div><div class="field-label">Key Entities</div><div class="field-value">${["p1", "p2", "p3", "o1"].map((id) => getEntity(id).name).join(", ")}</div></div>
          <div><div class="field-label">Key Relationships</div><div class="field-value">${edgesForEntity("p1").length}</div></div>
          <div><div class="field-label">Network Clusters</div><div class="field-value">3</div></div>
          <div><div class="field-label">Anomalies / Candidate Links</div><div class="field-value">${mainAnomalies}</div></div>
          <div><div class="field-label">Investigation Priority</div><div class="field-value"><span class="pill ${mainPriority.label.toLowerCase()}">${mainPriority.label}</span></div></div>
          <div><div class="field-label">Analytical Confidence</div><div class="field-value">${Math.round(mainPriority.confidence * 100)}%</div></div>
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" data-report="main" data-action-report="generate">Generate Report</button>
          <button class="btn btn-secondary btn-sm" data-report="main" data-action-report="pdf">Export PDF</button>
          <button class="btn btn-secondary btn-sm" data-report="main" data-action-report="csv">Export CSV</button>
        </div>
      </div>
      <div class="card card-pad">
        <div class="section-title">Case ${WOMEN_SAFETY_CASE.id} — ${WOMEN_SAFETY_CASE.title} <span class="cite-badge synthetic">Women Safety Module</span></div>
        <div class="profile-fields">
          <div><div class="field-label">Key Entities</div><div class="field-value">${["V1", "S1", "S2", "W1"].map((id) => wsGetEntity(id).name).join(", ")}</div></div>
          <div><div class="field-label">Key Relationships</div><div class="field-value">${WS_RELATIONSHIPS.length}</div></div>
          <div><div class="field-label">Hidden Links</div><div class="field-value">1 (${Math.round(WOMEN_SAFETY_CASE.hiddenLink.confidence * 100)}%)</div></div>
          <div><div class="field-label">Anomalies / Candidate Links</div><div class="field-value">${wsAnomalies}</div></div>
          <div><div class="field-label">Risk Score</div><div class="field-value"><span class="pill high">${WOMEN_SAFETY_CASE.riskScore.label}</span></div></div>
          <div><div class="field-label">Analytical Confidence</div><div class="field-value">${Math.round(WOMEN_SAFETY_CASE.riskScore.confidence * 100)}%</div></div>
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" data-report="ws" data-action-report="generate">Generate Report</button>
          <button class="btn btn-secondary btn-sm" data-report="ws" data-action-report="pdf">Export PDF</button>
          <button class="btn btn-secondary btn-sm" data-report="ws" data-action-report="csv">Export CSV</button>
        </div>
      </div>
      <div class="card card-pad" style="font-size:0.78rem; color:var(--gray); border-left:3px solid var(--indigo);">
        This report contains AI-generated analytical insights based on synthetic/demo data. All findings require verification by authorized investigators.
      </div>
    `;

    document.querySelectorAll("[data-action-report]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const which = btn.dataset.report === "ws" ? "ws" : "main";
        const kind = btn.dataset.actionReport;
        const caseId = which === "ws" ? WOMEN_SAFETY_CASE.id : CASES[0].id;
        if (kind === "csv") {
          exportCsv(which, "entities");
        } else if (kind === "pdf") {
          logAudit("Report exported (PDF)", caseId);
          window.print();
        } else {
          logAudit("Report generated", caseId);
          const original = btn.textContent;
          btn.textContent = "Generated ✓";
          setTimeout(() => (btn.textContent = original), 1500);
        }
      });
    });
  }

  // ---------------- Audit Logs page ----------------

  function renderAuditLogsPage() {
    document.getElementById("audit-log-table").innerHTML = `
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr></thead>
      <tbody>${AUDIT_LOG.map((a) => `<tr><td>${a.time.toLocaleTimeString()}</td><td>${a.actor}</td><td>${a.action}</td><td>${a.detail}</td></tr>`).join("")}</tbody>`;
  }

  // ---------------- Init / login bridge ----------------

  window.TriNetraApp = {
    openEvidenceModal,
    onLogin: function () {
      ensureDashboardGraphInitialized();
    },
  };

  renderDashboard();
  if (document.documentElement.classList.contains("authed")) {
    ensureDashboardGraphInitialized();
  }
})();
