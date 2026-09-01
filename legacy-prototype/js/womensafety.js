/*
 * TriNetra — Women Safety Module view rendering.
 * Owns its own Cytoscape graph instance (WomenSafetyGraph) over the WS_*
 * dataset defined in data-womensafety.js, kept entirely separate from the
 * main case's graph so the two demo cases never visually mix.
 *
 * Shared utilities defined here (renderTimelineList, renderBarChart) are also
 * used by app.js's Timeline / Pattern Detection pages — this file loads
 * before app.js, so both are available globally by the time app.js runs.
 */

const WomenSafetyGraph = createGraphController(WS_ENTITIES, WS_RELATIONSHIPS);

// ---- Shared rendering utilities (also used by app.js) ---------------------

function renderTimelineList(container, events) {
  if (!events.length) {
    container.innerHTML = '<div class="detail-empty">No events match this filter.</div>';
    return;
  }
  container.innerHTML = `<div class="tl-list">${events
    .map(
      (ev) => `
    <div class="tl-item ${ev.tagClass || ""}">
      <span class="tl-dot"></span>
      <div class="tl-date">${ev.dateLabel}</div>
      <div class="tl-title">${ev.title}</div>
      <div class="tl-desc">${ev.description}</div>
    </div>`
    )
    .join("")}</div>`;
}

function renderBarChart(container, rows) {
  const maxVal = Math.max(...rows.map((r) => r.value), 1);
  container.innerHTML = rows
    .map((r) => {
      const pct = Math.max(4, Math.round((r.value / maxVal) * 100));
      return `<div class="bar-chart-row">
        <div class="bar-chart-label">${r.label}</div>
        <div class="bar-chart-track"><div class="bar-chart-fill ${r.cls || "a"}" style="width:${pct}%"></div></div>
        <div class="bar-chart-values">${r.value.toLocaleString()}</div>
      </div>`;
    })
    .join("");
}

// ---- Women Safety page ------------------------------------------------

(function () {
  let graphInitialized = false;
  let wsSelectedEntityId = null;

  function renderContextStats() {
    const grid = document.getElementById("ws-context-stats");
    grid.innerHTML = DELHI_CONTEXT_STATS.headline
      .map(
        (s) => `
      <div class="stat-context-card">
        <div class="stat-context-value">${s.value}</div>
        <div class="stat-context-label">${s.label}</div>
        <div class="stat-context-source">Source: ${s.source}</div>
      </div>`
      )
      .join("");

    const chartRows = [];
    DELHI_CONTEXT_STATS.yearOverYear.categories.forEach((c) => {
      chartRows.push({ label: `${c.label} — 2023`, value: c.y2023, cls: "a" });
      chartRows.push({ label: `${c.label} — 2024`, value: c.y2024, cls: "b" });
    });
    const chartEl = document.getElementById("ws-yoy-chart");
    chartEl.innerHTML = `<div class="bar-chart-legend"><span><span class="sw" style="background:var(--indigo);"></span>2023</span><span><span class="sw" style="background:var(--orange);"></span>2024</span></div><div id="ws-yoy-chart-rows"></div>`;
    renderBarChart(document.getElementById("ws-yoy-chart-rows"), chartRows);

    document.getElementById("ws-context-note").textContent =
      `${DELHI_CONTEXT_STATS.yearOverYear.title} (${DELHI_CONTEXT_STATS.yearOverYear.source}). ${DELHI_CONTEXT_STATS.note}`;
  }

  function renderNarrative() {
    const events = WS_NARRATIVE_EVENTS.map((ev) => ({
      dateLabel: ev.day,
      title: ev.title,
      description: ev.description,
      tagClass: "tag-" + ev.tag,
    }));
    renderTimelineList(document.getElementById("ws-timeline"), events);
  }

  function ensureGraphInitialized() {
    if (graphInitialized) return;
    WomenSafetyGraph.init("cy-ws", {
      onNodeSelect: renderWsEntityDetailPanel,
      onCandidateEdgeSelect: (id) => window.TriNetraApp.openEvidenceModal(id),
    });
    graphInitialized = true;

    const presentTypes = Array.from(new Set(WS_ENTITIES.map((e) => e.type)));
    const filterWrap = document.getElementById("ws-type-filters");
    filterWrap.innerHTML = presentTypes
      .map(
        (key) => `
      <label class="filter-chip">
        <input type="checkbox" value="${key}" checked />
        <span class="swatch" style="background:${ENTITY_TYPES[key].color}"></span>${ENTITY_TYPES[key].label}
      </label>`
      )
      .join("");
    filterWrap.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener("change", () => {
        const active = Array.from(filterWrap.querySelectorAll('input[type="checkbox"]:checked')).map((c) => c.value);
        WomenSafetyGraph.setTypeFilter(active);
      });
    });

    document.getElementById("ws-graph-search").addEventListener("input", (e) => {
      WomenSafetyGraph.searchHighlight(e.target.value);
    });
    document.getElementById("ws-graph-reset").addEventListener("click", () => {
      document.getElementById("ws-graph-search").value = "";
      filterWrap.querySelectorAll('input[type="checkbox"]').forEach((cb) => (cb.checked = true));
      WomenSafetyGraph.reset();
      document.getElementById("ws-entity-detail-panel").innerHTML = '<div class="detail-empty">Click a node to see entity details.</div>';
    });

    document.getElementById("ws-graph-legend").innerHTML = presentTypes
      .map((key) => `<span class="legend-item"><span class="legend-swatch" style="background:${ENTITY_TYPES[key].color}"></span>${ENTITY_TYPES[key].label}</span>`)
      .join("");

    setTimeout(() => WomenSafetyGraph.fit(), 60);
  }

  function renderWsEntityDetailPanel(id) {
    const e = wsGetEntity(id);
    if (!e) return;
    wsSelectedEntityId = id;
    const conns = wsEdgesForEntity(id);
    const candidates = conns.filter((c) => c.candidateHiddenLink);
    const isRiskEntity = id === WOMEN_SAFETY_CASE.riskScore.entityId;

    const relRows = conns
      .map((r) => {
        const otherId = r.source === id ? r.target : r.source;
        const other = wsGetEntity(otherId);
        const clickable = r.candidateHiddenLink ? ` data-edge="${r.id}" style="cursor:pointer;"` : "";
        return `<div class="rel-row"${clickable}>
          <div><span class="rel-tag">${REL_LABELS[r.type] || r.type}</span> <span class="rel-target">${other ? other.name : "?"}</span></div>
          <span class="verify-state ${r.verification}">${r.verification}</span>
        </div>`;
      })
      .join("");

    const candidateNotes = candidates
      .map(
        (c) => `
      <div class="candidate-note" data-edge="${c.id}" style="cursor:pointer;">
        <strong>AI Insight:</strong> Candidate link detected (${Math.round(c.confidence * 100)}% analytical confidence). Click to review evidence.
      </div>`
      )
      .join("");

    const riskBlock = isRiskEntity
      ? `<div class="profile-fields" style="grid-template-columns:1fr 1fr;">
          <div><div class="field-label">Risk Score</div><div class="field-value"><span class="pill high">${WOMEN_SAFETY_CASE.riskScore.label}</span></div></div>
          <div><div class="field-label">Analytical Confidence</div><div class="field-value">${Math.round(WOMEN_SAFETY_CASE.riskScore.confidence * 100)}%</div></div>
        </div>`
      : "";

    document.getElementById("ws-entity-detail-panel").innerHTML = `
      <div class="section-title">Entity Details</div>
      <div class="profile-head" style="margin-bottom:10px;">
        <div class="entity-badge" style="background:${ENTITY_TYPES[e.type].color}">${entityIconLabel(e.type)}</div>
        <div><h2 style="font-size:1.05rem;">${e.name}</h2><div class="sub">${ENTITY_TYPES[e.type].label}${e.meta && e.meta.role ? " · " + e.meta.role : ""}</div></div>
      </div>
      ${riskBlock}
      <div class="profile-fields" style="grid-template-columns:1fr;">
        <div><div class="field-label">Connections</div><div class="field-value">${conns.length}</div></div>
      </div>
      <div class="section-title" style="font-size:0.85rem; margin-top:14px;">Relationships</div>
      ${relRows || '<div class="detail-empty">No relationships recorded.</div>'}
      ${candidateNotes}
    `;

    document.querySelectorAll("#ws-entity-detail-panel [data-edge]").forEach((el) => {
      el.addEventListener("click", () => window.TriNetraApp.openEvidenceModal(el.dataset.edge));
    });
  }

  function renderAnalyticsCards() {
    const c = WOMEN_SAFETY_CASE;
    const riskEntity = wsGetEntity(c.riskScore.entityId);
    const fromEntity = wsGetEntity(c.hiddenLink.fromId);
    const toEntity = wsGetEntity(c.hiddenLink.toId);
    const clusterNames = c.suspiciousCluster.entityIds.map((id) => wsGetEntity(id).name).join(" + ");
    const hiddenEdgeId = wsFindEdgeId(c.hiddenLink.fromId, c.hiddenLink.toId, "alias_of");

    document.getElementById("ws-analytics-cards").innerHTML = `
      <div class="analytics-card">
        <div class="ac-icon">⚠</div>
        <div class="ac-title">Risk Score — ${riskEntity.name}</div>
        <div class="ac-desc">${c.riskScore.reason}</div>
        <div class="ac-count"><span class="pill high">${c.riskScore.label}</span> ${Math.round(c.riskScore.confidence * 100)}%</div>
      </div>
      <div class="analytics-card">
        <div class="ac-icon">🔗</div>
        <div class="ac-title">Hidden Link Discovered</div>
        <div class="ac-desc">${fromEntity.name} ↔ ${toEntity.name}. ${c.hiddenLink.reason}</div>
        <div class="ac-count">${Math.round(c.hiddenLink.confidence * 100)}% confidence</div>
        <button class="btn btn-primary btn-sm" style="margin-top:10px;" id="ws-review-hidden-link">Review Evidence</button>
      </div>
      <div class="analytics-card">
        <div class="ac-icon">🧩</div>
        <div class="ac-title">Suspicious Cluster</div>
        <div class="ac-desc">${clusterNames}. ${c.suspiciousCluster.reason}</div>
      </div>
      <div class="analytics-card">
        <div class="ac-icon">🛡</div>
        <div class="ac-title">Recommended Action</div>
        <div class="ac-desc">${c.recommendedAction.note}</div>
        <div class="ac-count" style="font-size:0.95rem;">${c.recommendedAction.action}</div>
      </div>
    `;

    const btn = document.getElementById("ws-review-hidden-link");
    if (btn && hiddenEdgeId) {
      btn.addEventListener("click", () => window.TriNetraApp.openEvidenceModal(hiddenEdgeId));
    }
  }

  function render() {
    renderContextStats();
    renderNarrative();
    ensureGraphInitialized();
    renderAnalyticsCards();
    setTimeout(() => WomenSafetyGraph.fit(), 60);
  }

  window.WomenSafety = {
    render,
    refreshSelectedPanel: function () {
      if (wsSelectedEntityId) renderWsEntityDetailPanel(wsSelectedEntityId);
    },
  };
})();
