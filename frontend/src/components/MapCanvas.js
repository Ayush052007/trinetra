/**
 * Self-contained SVG map renderer.
 *
 * Draws zones, incident points, routes and service pins from stored data with
 * no external tile service, so the map works with no internet connection. A
 * tile layer can be enabled through MAP_TILE_URL when a deployment has one;
 * the geometry below is unchanged by that.
 *
 * The base layer is a coordinate grid, not a street map: it shows relative
 * position honestly rather than implying cartographic detail we do not have.
 */

import { html, useState, useMemo, BAND_COLORS, fmt } from "../lib/ui.js";

const BAND_FILL = {
  GREEN: "rgba(18,133,92,.17)",
  YELLOW: "rgba(201,147,11,.20)",
  ORANGE: "rgba(224,122,31,.22)",
  RED: "rgba(198,43,57,.24)",
};

/** Fit a set of lat/lng points into an SVG viewport. */
function useProjection(points, width, height, padding = 34) {
  return useMemo(() => {
    const valid = points.filter(
      (p) => Number.isFinite(p.lat) && Number.isFinite(p.lng)
    );
    if (!valid.length) {
      return { project: () => [width / 2, height / 2], scale: 1, ok: false };
    }
    let minLat = Math.min(...valid.map((p) => p.lat));
    let maxLat = Math.max(...valid.map((p) => p.lat));
    let minLng = Math.min(...valid.map((p) => p.lng));
    let maxLng = Math.max(...valid.map((p) => p.lng));

    // Guard against a degenerate extent when everything shares one point.
    const spanLat = Math.max(maxLat - minLat, 0.012);
    const spanLng = Math.max(maxLng - minLng, 0.012);
    const midLat = (minLat + maxLat) / 2;
    const midLng = (minLng + maxLng) / 2;
    minLat = midLat - spanLat / 2; maxLat = midLat + spanLat / 2;
    minLng = midLng - spanLng / 2; maxLng = midLng + spanLng / 2;

    const usableW = width - padding * 2;
    const usableH = height - padding * 2;
    // Longitude degrees shrink with latitude; keep the aspect honest.
    const latCorrection = Math.cos((midLat * Math.PI) / 180);
    const scale = Math.min(usableW / (spanLng * latCorrection), usableH / spanLat);

    const project = (lat, lng) => [
      padding + usableW / 2 + (lng - midLng) * latCorrection * scale,
      padding + usableH / 2 - (lat - midLat) * scale,
    ];
    return { project, scale, ok: true, midLat, spanLat, spanLng };
  }, [JSON.stringify(points), width, height]);
}

export function ZoneMap({
  zones = [], points = [], services = [], route = null,
  height = 340, onZoneClick, onPointClick, highlightZone = null,
  showPoints = false,
}) {
  const width = 760;
  const [tooltip, setTooltip] = useState(null);

  // Only fit the viewport to what is actually drawn. Individual incident points
  // span the whole NCR, so including them when they are hidden compresses the
  // zones into an unreadable dot.
  const allPoints = [
    ...zones.map((z) => ({ lat: z.center?.lat ?? z.center_lat, lng: z.center?.lng ?? z.center_lng })),
    ...(showPoints ? points.map((p) => ({ lat: p.lat, lng: p.lng })) : []),
    ...services.map((s) => ({ lat: s.lat, lng: s.lng })),
    // (services are configured deployment points and sit near the zones)
    ...(route ? route.map((w) => ({ lat: w.lat, lng: w.lng })) : []),
  ];
  const { project, scale, ok } = useProjection(allPoints, width, height);

  if (!ok) {
    return html`<div className="empty-state" style=${{ height: `${height}px`, display: "grid", placeItems: "center" }}>
      <div>
        <div className="es-icon">⌖</div>
        <div className="es-title">No mapped data</div>
        <div className="es-text">Records in this view have no coordinates attached.</div>
      </div>
    </div>`;
  }

  // 1 km in projected pixels, for radius drawing and the scale bar.
  const kmInDegrees = 1 / 111.32;
  const pxPerKm = kmInDegrees * scale;

  return html`<div className="map-wrap">
    <svg
      className="map-canvas" viewBox=${`0 0 ${width} ${height}`}
      style=${{ height: `${height}px` }} role="img"
      aria-label="Zone density map"
    >
      <defs>
        <pattern id="grid" width="38" height="38" patternUnits="userSpaceOnUse">
          <path d="M 38 0 L 0 0 0 38" fill="none" stroke="#e2e6f0" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width=${width} height=${height} fill="url(#grid)" />

      <!-- zones -->
      ${zones.map((zone) => {
        const lat = zone.center?.lat ?? zone.center_lat;
        const lng = zone.center?.lng ?? zone.center_lng;
        const [cx, cy] = project(lat, lng);
        const r = Math.max(16, (zone.radius_km || 1) * pxPerKm);
        const band = zone.band || "GREEN";
        const isHighlight = highlightZone === zone.zone_ref;
        return html`<g
          key=${zone.zone_ref}
          style=${{ cursor: onZoneClick ? "pointer" : "default" }}
          onClick=${() => onZoneClick && onZoneClick(zone)}
          onMouseMove=${(e) => {
            const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect();
            setTooltip({
              x: ((e.clientX - rect.left) / rect.width) * 100,
              y: ((e.clientY - rect.top) / rect.height) * 100,
              content: html`<div>
                <div><b>${zone.name}</b></div>
                <div>${band} · ${zone.incident_count} incident${zone.incident_count === 1 ? "" : "s"}</div>
                <div>Weighted density ${zone.weighted_density}</div>
                ${zone.services_nearby !== undefined
                  ? html`<div>${zone.services_nearby} emergency service(s) nearby</div>` : null}
              </div>`,
            });
          }}
          onMouseLeave=${() => setTooltip(null)}
        >
          <circle
            cx=${cx} cy=${cy} r=${r}
            fill=${BAND_FILL[band] || BAND_FILL.GREEN}
            stroke=${BAND_COLORS[band] || "#12855c"}
            strokeWidth=${isHighlight ? 3 : 1.6}
            strokeDasharray=${isHighlight ? "6 3" : "none"}
          />
          <circle cx=${cx} cy=${cy} r="4.5" fill=${BAND_COLORS[band] || "#12855c"} />
          <text
            x=${cx} y=${cy - r - 7} textAnchor="middle"
            style=${{ fontSize: "10.5px", fontWeight: 650, fill: "#29335c" }}
          >${zone.name}</text>
          <text
            x=${cx} y=${cy + 17} textAnchor="middle"
            style=${{ fontSize: "10px", fontWeight: 700, fill: BAND_COLORS[band] }}
          >${zone.incident_count}</text>
        </g>`;
      })}

      <!-- individual incidents -->
      ${showPoints
        ? points.slice(0, 900).map((point, index) => {
            const [px, py] = project(point.lat, point.lng);
            return html`<circle
              key=${`${point.ref}-${index}`} cx=${px} cy=${py} r="2.4"
              fill=${BAND_COLORS[point.priority] || "#78819c"} opacity="0.62"
              style=${{ cursor: onPointClick ? "pointer" : "default" }}
              onClick=${() => onPointClick && onPointClick(point)}
              onMouseMove=${(e) => {
                const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect();
                setTooltip({
                  x: ((e.clientX - rect.left) / rect.width) * 100,
                  y: ((e.clientY - rect.top) / rect.height) * 100,
                  content: html`<div>
                    <div><b>${point.ref}</b></div>
                    <div>${fmt.title(point.type)} · ${point.priority}</div>
                    ${point.hour !== undefined && point.hour !== null
                      ? html`<div>Around ${String(point.hour).padStart(2, "0")}:00</div>` : null}
                  </div>`,
                });
              }}
              onMouseLeave=${() => setTooltip(null)}
            />`;
          })
        : null}

      <!-- route -->
      ${route && route.length > 1
        ? html`<g>
            <polyline
              points=${route.map((w) => project(w.lat, w.lng).join(",")).join(" ")}
              fill="none" stroke="#21518F" strokeWidth="3.4"
              strokeLinejoin="round" strokeLinecap="round" opacity="0.9"
            />
            ${route.map((waypoint, index) => {
              const [x, y] = project(waypoint.lat, waypoint.lng);
              const terminal = index === 0 || index === route.length - 1;
              return html`<g key=${waypoint.ref}>
                <circle
                  cx=${x} cy=${y} r=${terminal ? 7 : 4.5}
                  fill=${terminal ? "#21518F" : "#ffffff"}
                  stroke="#21518F" strokeWidth="2.4"
                />
                ${terminal
                  ? html`<text
                      x=${x} y=${y - 12} textAnchor="middle"
                      style=${{ fontSize: "10.5px", fontWeight: 700, fill: "#29277d" }}
                    >${index === 0 ? "FROM" : "TO"}</text>`
                  : null}
              </g>`;
            })}
          </g>`
        : null}

      <!-- emergency services -->
      ${services.map((service) => {
        const [x, y] = project(service.lat, service.lng);
        const glyph = service.type.includes("Police") ? "P"
          : service.type.includes("Hospital") ? "H"
          : service.type.includes("Response") ? "R" : "S";
        return html`<g
          key=${service.service_ref}
          onMouseMove=${(e) => {
            const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect();
            setTooltip({
              x: ((e.clientX - rect.left) / rect.width) * 100,
              y: ((e.clientY - rect.top) / rect.height) * 100,
              content: html`<div>
                <div><b>${service.name}</b></div>
                <div>${service.type} · ${service.status}</div>
                ${service.distance_km !== undefined ? html`<div>${service.distance_km} km away</div>` : null}
              </div>`,
            });
          }}
          onMouseLeave=${() => setTooltip(null)}
        >
          <rect x=${x - 8} y=${y - 8} width="16" height="16" rx="4" fill="#0d7f8a" opacity="0.92" />
          <text
            x=${x} y=${y + 4} textAnchor="middle"
            style=${{ fontSize: "9.5px", fontWeight: 700, fill: "#fff" }}
          >${glyph}</text>
        </g>`;
      })}

      <!-- scale bar: keeps the abstraction honest about distance -->
      <g transform=${`translate(${width - 118}, ${height - 22})`}>
        <line x1="0" y1="0" x2=${Math.min(90, pxPerKm)} y2="0" stroke="#5a6484" strokeWidth="2" />
        <line x1="0" y1="-4" x2="0" y2="4" stroke="#5a6484" strokeWidth="2" />
        <line x1=${Math.min(90, pxPerKm)} y1="-4" x2=${Math.min(90, pxPerKm)} y2="4" stroke="#5a6484" strokeWidth="2" />
        <text x=${Math.min(90, pxPerKm) / 2} y="-7" textAnchor="middle"
          style=${{ fontSize: "9.5px", fill: "#5a6484" }}>
          ${pxPerKm > 90 ? `${(90 / pxPerKm).toFixed(1)} km` : "1 km"}
        </text>
      </g>
    </svg>

    ${tooltip
      ? html`<div className="map-tooltip" style=${{
          left: `${Math.min(72, tooltip.x)}%`, top: `${Math.max(4, tooltip.y - 12)}%`,
        }}>${tooltip.content}</div>`
      : null}
  </div>`;
}
