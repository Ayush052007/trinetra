/**
 * Interactive knowledge-graph canvas (Cytoscape).
 *
 * Observed relationships are drawn as solid edges, inferred ones as dashed
 * indigo. That distinction is load-bearing, not decorative: an investigator
 * must be able to tell a recorded fact from a derived suggestion at a glance.
 */

import { html, useRef, useEffect, useState, entityColor, ENTITY_GLYPHS } from "../lib/ui.js";

const LAYOUTS = {
  cose: {
    name: "cose", animate: false, padding: 26, nodeRepulsion: 9000,
    idealEdgeLength: 92, nodeOverlap: 18, gravity: 0.3, numIter: 900,
    componentSpacing: 110, randomize: false,
  },
  concentric: {
    name: "concentric", animate: false, padding: 26, minNodeSpacing: 42,
    concentric: (node) => node.degree(),
    levelWidth: () => 2,
  },
  grid: { name: "grid", animate: false, padding: 26, avoidOverlap: true },
  circle: { name: "circle", animate: false, padding: 26, avoidOverlap: true },
  breadthfirst: { name: "breadthfirst", animate: false, padding: 26, spacingFactor: 1.15 },
};

export function GraphCanvas({
  nodes = [], edges = [], compact = false, rootUid = null,
  onNodeClick, onEdgeClick, onNodeExpand, highlightPath = null,
  layout = "cose", filterTypes = null, showInferred = true, searchTerm = "",
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [selected, setSelected] = useState(null);

  // Build / rebuild the graph when the data changes.
  useEffect(() => {
    if (!containerRef.current || typeof cytoscape === "undefined") return undefined;

    const elements = [
      ...nodes.map((node) => ({
        data: {
          id: node.uid,
          label: node.name,
          type: node.type,
          isRoot: node.uid === rootUid || node.is_root,
          glyph: ENTITY_GLYPHS[node.type] || "?",
        },
      })),
      ...edges.map((edge) => ({
        data: {
          id: edge.uid,
          source: edge.source,
          target: edge.target,
          label: (edge.type || "").replace(/_/g, " "),
          observed: edge.is_observed !== false,
          status: edge.evidence_status,
          confidence: edge.confidence,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      wheelSensitivity: 0.22,
      minZoom: 0.15,
      maxZoom: 3.2,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (el) => entityColor(el.data("type")),
            label: "data(label)",
            "font-size": "9.5px",
            "font-family": "Segoe UI, system-ui, sans-serif",
            "font-weight": 600,
            color: "#111a3a",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-max-width": "94px",
            "text-wrap": "ellipsis",
            width: 26, height: 26,
            "border-width": 2,
            "border-color": "#ffffff",
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node[?isRoot]",
          style: {
            width: 42, height: 42,
            "border-width": 3.5,
            "border-color": "#21518F",
            "font-size": "11.5px",
            "font-weight": 700,
            "z-index": 20,
          },
        },
        {
          selector: "node:selected",
          style: { "border-color": "#111a3a", "border-width": 3.5, "z-index": 30 },
        },
        {
          selector: "node.dimmed",
          style: { opacity: 0.16, "text-opacity": 0.16 },
        },
        {
          selector: "node.match",
          style: { "border-color": "#e07a1f", "border-width": 4, "z-index": 25 },
        },
        {
          selector: "edge",
          style: {
            width: (el) => 1 + (el.data("confidence") || 0.5) * 1.9,
            "line-color": "#b6bfd4",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#b6bfd4",
            "arrow-scale": 0.72,
            opacity: 0.82,
            "overlay-opacity": 0,
          },
        },
        {
          // Inferred: dashed and indigo. Never rendered like an observed edge.
          selector: "edge[!observed]",
          style: {
            "line-color": "#21518F",
            "target-arrow-color": "#21518F",
            "line-style": "dashed",
            "line-dash-pattern": [6, 3],
            opacity: 0.95,
          },
        },
        {
          selector: "edge:selected",
          style: { "line-color": "#111a3a", "target-arrow-color": "#111a3a", width: 3.4, opacity: 1 },
        },
        { selector: "edge.dimmed", style: { opacity: 0.06 } },
        {
          selector: "edge.path",
          style: {
            "line-color": "#e07a1f", "target-arrow-color": "#e07a1f",
            width: 4, opacity: 1, "z-index": 40,
          },
        },
        {
          selector: "edge.labelled",
          style: {
            label: "data(label)",
            "font-size": "8.5px",
            color: "#5a6484",
            "text-rotation": "autorotate",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.88,
            "text-background-padding": "2px",
          },
        },
      ],
      layout: LAYOUTS[layout] || LAYOUTS.cose,
    });

    cy.on("tap", "node", (event) => {
      const uid = event.target.id();
      setSelected({ kind: "node", id: uid });
      if (onNodeClick) onNodeClick(uid);
    });
    cy.on("dbltap", "node", (event) => {
      if (onNodeExpand) onNodeExpand(event.target.id());
    });
    cy.on("tap", "edge", (event) => {
      const data = event.target.data();
      setSelected({ kind: "edge", id: data.id });
      if (onEdgeClick) onEdgeClick(data);
    });
    cy.on("tap", (event) => {
      if (event.target === cy) {
        setSelected(null);
        cy.elements().removeClass("dimmed");
      }
    });

    // Focus a node's neighbourhood on selection.
    cy.on("select", "node", (event) => {
      const node = event.target;
      const keep = node.closedNeighborhood();
      cy.elements().addClass("dimmed");
      keep.removeClass("dimmed");
    });
    cy.on("unselect", () => cy.elements().removeClass("dimmed"));

    // Label edges only when the graph is small enough to stay readable.
    if (edges.length <= 40) cy.edges().addClass("labelled");

    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [JSON.stringify(nodes.map((n) => n.uid)), JSON.stringify(edges.map((e) => e.uid)), layout]);

  // Type filter + inferred toggle.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const hidden = filterTypes && filterTypes.length && !filterTypes.includes(node.data("type"));
        node.style("display", hidden ? "none" : "element");
      });
      cy.edges().forEach((edge) => {
        const hiddenByInferred = !showInferred && !edge.data("observed");
        const endpointsHidden =
          edge.source().style("display") === "none" || edge.target().style("display") === "none";
        edge.style("display", hiddenByInferred || endpointsHidden ? "none" : "element");
      });
    });
  }, [JSON.stringify(filterTypes), showInferred]);

  // In-graph search highlight.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("match");
    const term = (searchTerm || "").trim().toLowerCase();
    if (!term) return;
    const matches = cy.nodes().filter((n) => n.data("label").toLowerCase().includes(term));
    matches.addClass("match");
    if (matches.length) cy.animate({ fit: { eles: matches, padding: 90 }, duration: 300 });
  }, [searchTerm]);

  // Highlight a specific path.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("path dimmed");
    if (!highlightPath || highlightPath.length < 2) return;
    cy.elements().addClass("dimmed");
    for (let i = 0; i < highlightPath.length - 1; i += 1) {
      const a = highlightPath[i];
      const b = highlightPath[i + 1];
      const edge = cy.edges().filter((e) => {
        const s = e.data("source");
        const t = e.data("target");
        return (s === a && t === b) || (s === b && t === a);
      });
      edge.removeClass("dimmed").addClass("path");
      cy.getElementById(a).removeClass("dimmed");
      cy.getElementById(b).removeClass("dimmed");
    }
  }, [JSON.stringify(highlightPath)]);

  const control = (fn) => () => { if (cyRef.current) fn(cyRef.current); };

  return html`<div className=${`graph-canvas ${compact ? "compact" : ""}`}>
    <div ref=${containerRef} style=${{ width: "100%", height: "100%" }}></div>
    <div className="graph-float">
      <button onClick=${control((cy) => cy.zoom(cy.zoom() * 1.3))} title="Zoom in">+</button>
      <button onClick=${control((cy) => cy.zoom(cy.zoom() / 1.3))} title="Zoom out">−</button>
      <button onClick=${control((cy) => cy.fit(undefined, 40))} title="Fit to view">⛶</button>
      <button onClick=${control((cy) => {
        cy.elements().removeClass("dimmed path match");
        cy.$(":selected").unselect();
        cy.fit(undefined, 40);
      })} title="Reset view">↺</button>
    </div>
    ${nodes.length === 0
      ? html`<div style=${{
          position: "absolute", inset: 0, display: "grid", placeItems: "center",
          color: "var(--gray)", fontSize: "13px",
        }}>No entities to display in this view.</div>`
      : html`<div className="graph-hint">
          Click a node to focus · double-click to expand · drag to reposition · scroll to zoom
        </div>`}
  </div>`;
}
