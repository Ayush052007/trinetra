/*
 * TriNetra network graph rendering (Cytoscape.js wrapper).
 * createGraphController(entities, relationships) builds an independent graph
 * controller bound to its own dataset, so separate cases (e.g. the main
 * investigation vs. the Women Safety module) never share one Cytoscape
 * instance. `TriNetraGraph` below is the default instance for the main
 * dataset, kept for backwards compatibility with existing call sites.
 */

function createGraphController(entities, relationships) {
  let cy = null;
  let activeTypes = new Set(Object.keys(ENTITY_TYPES));
  let onNodeSelect = null;
  let onCandidateEdgeSelect = null;

  function localEdgesForEntity(id) {
    return relationships.filter((r) => r.source === id || r.target === id);
  }

  function buildElements() {
    const nodes = entities.map((e) => ({
      data: {
        id: e.id,
        label: e.name,
        type: e.type,
        degree: localEdgesForEntity(e.id).length,
      },
    }));

    const edges = relationships.map((r) => ({
      data: {
        id: r.id,
        source: r.source,
        target: r.target,
        label: REL_LABELS[r.type] || r.type,
        type: r.type,
        candidate: r.candidateHiddenLink,
        verification: r.verification,
      },
    }));

    return [...nodes, ...edges];
  }

  function style() {
    return [
      {
        selector: "node",
        style: {
          "background-color": (n) => ENTITY_TYPES[n.data("type")].color,
          label: "data(label)",
          "font-size": 10,
          "font-weight": 600,
          color: "#0f1a3c",
          "text-valign": "bottom",
          "text-margin-y": 6,
          width: (n) => 26 + Math.min(24, n.data("degree") * 2.5),
          height: (n) => 26 + Math.min(24, n.data("degree") * 2.5),
          "border-width": 2,
          "border-color": "#ffffff",
          "text-outline-width": 2,
          "text-outline-color": "#f5f6fb",
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.6,
          "line-color": "#c7cbe0",
          "target-arrow-color": "#c7cbe0",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          opacity: 0.85,
        },
      },
      {
        selector: 'edge[?candidate]',
        style: {
          "line-color": "#e07a1f",
          "target-arrow-color": "#e07a1f",
          "line-style": "dashed",
          width: 2.2,
        },
      },
      {
        selector: ".faded",
        style: { opacity: 0.08 },
      },
      {
        selector: ".highlighted",
        style: {
          "border-color": "#5b3fd1",
          "border-width": 4,
        },
      },
      {
        selector: "edge.highlighted",
        style: {
          "line-color": "#5b3fd1",
          "target-arrow-color": "#5b3fd1",
          width: 3,
          opacity: 1,
        },
      },
      {
        selector: "node.search-hit",
        style: {
          "border-color": "#1f9d63",
          "border-width": 4,
        },
      },
    ];
  }

  function init(containerId, handlers) {
    onNodeSelect = (handlers && handlers.onNodeSelect) || function () {};
    onCandidateEdgeSelect = (handlers && handlers.onCandidateEdgeSelect) || function () {};

    cy = cytoscape({
      container: document.getElementById(containerId),
      elements: buildElements(),
      style: style(),
      layout: { name: "cose", animate: false, idealEdgeLength: 90, nodeRepulsion: 9000 },
      wheelSensitivity: 0.25,
      minZoom: 0.2,
      maxZoom: 3,
    });

    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      selectNode(id);
      onNodeSelect(id);
    });

    cy.on("tap", "edge", (evt) => {
      const data = evt.target.data();
      if (data.candidate) {
        onCandidateEdgeSelect(data.id);
      }
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        clearHighlight();
      }
    });

    return cy;
  }

  function clearHighlight() {
    if (!cy) return;
    cy.elements().removeClass("highlighted faded search-hit");
  }

  function selectNode(id) {
    if (!cy) return;
    clearHighlight();
    const node = cy.getElementById(id);
    if (node.empty()) return;
    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass("faded");
    neighborhood.removeClass("faded");
    node.addClass("highlighted");
    neighborhood.edges().addClass("highlighted");
  }

  function centerOn(id) {
    if (!cy) return;
    const node = cy.getElementById(id);
    if (node.empty()) return;
    selectNode(id);
    cy.animate({ center: { eles: node }, zoom: 1.1 }, { duration: 400 });
  }

  function setTypeFilter(types) {
    activeTypes = new Set(types);
    if (!cy) return;
    cy.nodes().forEach((n) => {
      const visible = activeTypes.has(n.data("type"));
      n.style("display", visible ? "element" : "none");
    });
    cy.edges().forEach((e) => {
      const visible = e.source().style("display") !== "none" && e.target().style("display") !== "none";
      e.style("display", visible ? "element" : "none");
    });
  }

  function searchHighlight(query) {
    if (!cy) return [];
    const q = (query || "").trim().toLowerCase();
    cy.nodes().removeClass("search-hit");
    if (!q) return [];
    const hits = cy.nodes().filter((n) => n.data("label").toLowerCase().includes(q));
    hits.addClass("search-hit");
    return hits.map((n) => n.id());
  }

  function reset() {
    if (!cy) return;
    clearHighlight();
    setTypeFilter(Object.keys(ENTITY_TYPES));
    cy.fit(undefined, 40);
  }

  function addHighlightedElements(entityIds, edgeIds) {
    if (!cy) return;
    cy.batch(() => {
      entityIds.forEach((id) => {
        const n = cy.getElementById(id);
        if (!n.empty()) n.addClass("highlighted");
      });
      edgeIds.forEach((id) => {
        const e = cy.getElementById(id);
        if (!e.empty()) e.addClass("highlighted");
      });
    });
  }

  function fit() {
    if (cy) cy.fit(undefined, 40);
  }

  return {
    init,
    centerOn,
    selectNode,
    setTypeFilter,
    searchHighlight,
    reset,
    addHighlightedElements,
    fit,
    getCy: () => cy,
  };
}

const TriNetraGraph = createGraphController(ENTITIES, RELATIONSHIPS);
