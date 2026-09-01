"""Women Safety Intelligence analytics.

Three engines, all computed from stored records:

  heatmap  - kernel-weighted incident density per zone, recoloured on every
             filter change rather than served from a stored colour.
  routing  - Dijkstra/Yen over a waypoint graph whose edge cost blends
             distance with safety signals, producing ranked alternatives with
             an explainable breakdown.
  patterns - suspicious-cluster and repeated-encounter detection over shared
             entities, descriptors and spatio-temporal co-occurrence.

Language rules enforced here and preserved by every caller: a route is
"recommended based on available safety indicators", never safe; a repeated
encounter is a "potential pattern requiring authorised investigator review",
never a stalker identification.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT / "graph") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "graph"))

from trinetra_graph.algorithms import build_adjacency, haversine_km, k_shortest_paths  # noqa: E402

from app.db.base import AlertStatus, EvidenceStatus, Priority  # noqa: E402
from app.db.models import Entity, Event, Relationship  # noqa: E402
from app.db.models_safety import (  # noqa: E402
    EmergencyService,
    Incident,
    IncidentType,
    PatternDetection,
    SafetyAlert,
    SafetyZone,
    Waypoint,
    WaypointEdge,
)

HEATMAP_VERSION = "heatmap-1.0"
ROUTE_VERSION = "route-1.0"
PATTERN_VERSION = "pattern-1.0"

SEVERITY_WEIGHT = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.5, "CRITICAL": 5.0}

# Band thresholds are density per square kilometre, weighted by severity.
BAND_THRESHOLDS = [(12.0, "RED"), (6.0, "ORANGE"), (2.0, "YELLOW"), (0.0, "GREEN")]

BAND_MEANING = {
    "GREEN": "Lower recorded incident density for the current selection",
    "YELLOW": "Moderate recorded incident density for the current selection",
    "ORANGE": "High recorded incident density for the current selection",
    "RED": "Highest recorded incident density in the current selection",
}

BAND_NOTE = (
    "Bands are relative to the zones in the current selection, so changing a "
    "filter re-ranks the map. The absolute weighted density is shown alongside "
    "each zone. A band is a description of reporting density, not a statement "
    "about any location or the people in it."
)


def _band_for(density: float) -> str:
    for threshold, band in BAND_THRESHOLDS:
        if density >= threshold:
            return band
    return "GREEN"


# ================================================================ heatmap


def build_heatmap(
    db: Session,
    incident_types: list[str] | None = None,
    severities: list[str] | None = None,
    hour_from: int | None = None,
    hour_to: int | None = None,
    days: int | None = None,
) -> dict[str, Any]:
    """Zone density from live incident data under the supplied filters."""
    query = select(Incident)
    if incident_types:
        query = query.where(Incident.type.in_(incident_types))
    if severities:
        query = query.where(Incident.priority.in_(severities))
    if days:
        query = query.where(Incident.occurred_at >= datetime.now(UTC) - timedelta(days=days))
    incidents = list(db.scalars(query).all())

    if hour_from is not None and hour_to is not None:
        if hour_from <= hour_to:
            incidents = [
                i for i in incidents
                if i.hour_of_day is not None and hour_from <= i.hour_of_day <= hour_to
            ]
        else:  # window wraps past midnight, e.g. 20:00-04:00
            incidents = [
                i for i in incidents
                if i.hour_of_day is not None
                and (i.hour_of_day >= hour_from or i.hour_of_day <= hour_to)
            ]

    zones = list(db.scalars(select(SafetyZone)).all())
    services = list(db.scalars(select(EmergencyService)).all())

    zone_payload: list[dict[str, Any]] = []
    for zone in zones:
        area = max(0.35, 3.14159 * zone.radius_km**2)
        weighted = 0.0
        contributing: list[Incident] = []
        by_type: dict[str, int] = defaultdict(int)

        for incident in incidents:
            if incident.latitude is None or incident.longitude is None:
                # Fall back to explicit zone assignment when there is no fix.
                if incident.zone_id == zone.id:
                    weighted += SEVERITY_WEIGHT.get(incident.priority, 1.0)
                    contributing.append(incident)
                    by_type[incident.type] += 1
                continue
            distance = haversine_km(
                zone.center_lat, zone.center_lng, incident.latitude, incident.longitude
            )
            if distance > zone.radius_km * 1.5:
                continue
            # Gaussian kernel: an incident at the centre counts fully, one at
            # the boundary counts little. Avoids hard cell edges.
            kernel = 2.71828 ** (-((distance / max(zone.radius_km, 0.2)) ** 2))
            weighted += SEVERITY_WEIGHT.get(incident.priority, 1.0) * kernel
            if kernel > 0.25:
                contributing.append(incident)
                by_type[incident.type] += 1

        density = weighted / area
        zone_payload.append({
            "zone_ref": zone.zone_ref,
            "name": zone.name,
            "description": zone.description,
            "center": {"lat": zone.center_lat, "lng": zone.center_lng},
            "radius_km": zone.radius_km,
            "incident_count": len(contributing),
            "weighted_density": round(density, 3),
            "band": _band_for(density),
            "band_meaning": BAND_MEANING[_band_for(density)],
            "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
            "services_nearby": sum(
                1 for s in services
                if haversine_km(zone.center_lat, zone.center_lng, s.latitude, s.longitude)
                <= zone.radius_km * 1.5
            ),
            "sample_incident_refs": [i.incident_ref for i in contributing[:6]],
        })

    # Band relative to the current selection, not against fixed absolute
    # thresholds. Filtering to one incident type shrinks every density, and
    # absolute thresholds would wash the whole map GREEN and make the filter
    # look broken. Relative banding keeps the comparison meaningful; the raw
    # weighted_density is always returned alongside so the absolute figure is
    # never hidden.
    densities = sorted((z["weighted_density"] for z in zone_payload), reverse=True)
    non_zero = [d for d in densities if d > 0]
    if non_zero:
        peak = non_zero[0]
        for zone_entry in zone_payload:
            density = zone_entry["weighted_density"]
            if density <= 0:
                band = "GREEN"
            else:
                share = density / peak
                band = (
                    "RED" if share >= 0.75
                    else "ORANGE" if share >= 0.45
                    else "YELLOW" if share >= 0.20
                    else "GREEN"
                )
            zone_entry["band"] = band
            zone_entry["band_meaning"] = BAND_MEANING[band]
            zone_entry["relative_share"] = round(density / peak, 3) if peak else 0.0

    zone_payload.sort(key=lambda z: -z["weighted_density"])
    return {
        "zones": zone_payload,
        "points": [
            {
                "lat": i.latitude, "lng": i.longitude, "type": i.type,
                "priority": i.priority, "ref": i.incident_ref,
                "hour": i.hour_of_day,
            }
            for i in incidents
            if i.latitude is not None and i.longitude is not None
        ],
        "total_incidents": len(incidents),
        "filters": {
            "types": incident_types or [],
            "severities": severities or [],
            "hour_from": hour_from,
            "hour_to": hour_to,
            "days": days,
        },
        "available_types": [
            {"key": t, "label": IncidentType.LABELS[t]} for t in IncidentType.ALL
        ],
        "bands": [
            {"band": b, "meaning": BAND_MEANING[b]}
            for b in ("RED", "ORANGE", "YELLOW", "GREEN")
        ],
        "band_note": BAND_NOTE,
        "algorithm_version": HEATMAP_VERSION,
        "method": (
            "Severity-weighted Gaussian kernel density per zone, computed from "
            "incident records matching the active filters, then banded relative "
            "to the highest-density zone in that selection."
        ),
    }


# ================================================================ routing


def _incident_pressure(
    db: Session, lat: float, lng: float, radius_km: float = 0.6
) -> tuple[float, int]:
    """Weighted incident load near a point, and the raw count."""
    incidents = db.scalars(select(Incident)).all()
    total = 0.0
    count = 0
    for incident in incidents:
        if incident.latitude is None or incident.longitude is None:
            continue
        distance = haversine_km(lat, lng, incident.latitude, incident.longitude)
        if distance <= radius_km:
            total += SEVERITY_WEIGHT.get(incident.priority, 1.0) * (1 - distance / radius_km)
            count += 1
    return total, count


def compute_routes(
    db: Session, from_ref: str, to_ref: str, depart_hour: int = 12, alternatives: int = 3
) -> dict[str, Any]:
    """Rank route options by an explainable safety score.

    Cost is distance inflated by incident pressure, night-hour risk and
    distance from the nearest emergency service. The returned score is a
    0-100 presentation of that cost, decomposed so the ranking is inspectable.
    """
    waypoints = {w.waypoint_ref: w for w in db.scalars(select(Waypoint)).all()}
    if from_ref not in waypoints or to_ref not in waypoints:
        return {"error": "unknown_waypoint", "routes": []}
    if from_ref == to_ref:
        return {"error": "same_waypoint", "routes": []}

    by_id = {w.id: w for w in waypoints.values()}
    edges = db.scalars(select(WaypointEdge)).all()
    services = list(db.scalars(select(EmergencyService)).all())

    adjacency = build_adjacency(
        [w.waypoint_ref for w in waypoints.values()],
        [
            (by_id[e.from_id].waypoint_ref, by_id[e.to_id].waypoint_ref, e)
            for e in edges
            if e.from_id in by_id and e.to_id in by_id
        ],
    )

    # Night hours carry a higher multiplier; this is a documented modelling
    # assumption reflecting reporting patterns, not a claim about any location.
    is_night = depart_hour >= 20 or depart_hour <= 5
    is_evening = 17 <= depart_hour < 20
    time_multiplier = 1.45 if is_night else (1.18 if is_evening else 1.0)

    recent_cutoff = datetime.now(UTC) - timedelta(days=30)
    recent_alerts = db.scalars(
        select(SafetyAlert).where(
            SafetyAlert.raised_at >= recent_cutoff,
            SafetyAlert.status != AlertStatus.RESOLVED,
        )
    ).all()
    alert_zone_ids = {a.zone_id for a in recent_alerts if a.zone_id}

    segment_cache: dict[tuple[str, str], dict[str, float]] = {}

    def segment_metrics(a: str, b: str, refs) -> dict[str, float]:
        key = (a, b) if a < b else (b, a)
        if key in segment_cache:
            return segment_cache[key]
        wa, wb = waypoints[a], waypoints[b]
        distance = min((r.distance_km for r in refs), default=None) or haversine_km(
            wa.latitude, wa.longitude, wb.latitude, wb.longitude
        )
        mid_lat = (wa.latitude + wb.latitude) / 2
        mid_lng = (wa.longitude + wb.longitude) / 2
        pressure, incident_count = _incident_pressure(db, mid_lat, mid_lng)
        nearest_service = min(
            (haversine_km(mid_lat, mid_lng, s.latitude, s.longitude) for s in services),
            default=5.0,
        )
        unlit = 0 if (wa.lit and wb.lit) else 1
        has_alert = 1 if (wa.zone_id in alert_zone_ids or wb.zone_id in alert_zone_ids) else 0
        metrics = {
            "distance_km": distance,
            "pressure": pressure,
            "incident_count": float(incident_count),
            "nearest_service_km": nearest_service,
            "unlit": float(unlit),
            "recent_alert": float(has_alert),
        }
        segment_cache[key] = metrics
        return metrics

    def cost(a, b, refs) -> float:
        m = segment_metrics(a, b, refs)
        return (
            m["distance_km"]
            * time_multiplier
            * (1 + 0.22 * m["pressure"])
            * (1 + 0.30 * m["unlit"])
            * (1 + 0.25 * m["recent_alert"])
            + 0.12 * m["nearest_service_km"]
        )

    paths = k_shortest_paths(adjacency, from_ref, to_ref, cost, k=alternatives)
    if not paths:
        return {"error": "no_route", "routes": []}

    routes: list[dict[str, Any]] = []
    for index, (path, total_cost) in enumerate(paths):
        distance = 0.0
        pressure = 0.0
        incidents_near = 0
        service_distances: list[float] = []
        unlit_segments = 0
        alert_segments = 0
        segments = []
        for a, b in zip(path, path[1:]):
            m = segment_metrics(a, b, adjacency.get(a, {}).get(b, []))
            distance += m["distance_km"]
            pressure += m["pressure"]
            incidents_near += int(m["incident_count"])
            service_distances.append(m["nearest_service_km"])
            unlit_segments += int(m["unlit"])
            alert_segments += int(m["recent_alert"])
            segments.append({
                "from": a, "to": b,
                "from_name": waypoints[a].name, "to_name": waypoints[b].name,
                "distance_km": round(m["distance_km"], 3),
                "incidents_near": int(m["incident_count"]),
                "lit": not bool(m["unlit"]),
            })

        # Present cost as a 0-100 score. Anchored on cost-per-km so a longer
        # route is not penalised merely for being longer.
        efficiency = total_cost / max(distance, 0.05)
        raw = max(0.0, 100.0 - (efficiency - 1.0) * 26.0)
        score = round(max(5.0, min(97.0, raw)), 1)

        routes.append({
            "rank": index + 1,
            "label": f"Route {chr(65 + index)}",
            "waypoints": [
                {"ref": p, "name": waypoints[p].name,
                 "lat": waypoints[p].latitude, "lng": waypoints[p].longitude}
                for p in path
            ],
            "segments": segments,
            "distance_km": round(distance, 2),
            "safety_score": score,
            "cost": round(total_cost, 3),
            "factors": [
                {
                    "key": "incident_density",
                    "label": "Incident density along route",
                    "value": round(pressure, 2),
                    "detail": f"{incidents_near} incident record(s) within 600m of the route",
                    "direction": "lower_is_better",
                },
                {
                    "key": "recent_alerts",
                    "label": "Recent unresolved alerts",
                    "value": alert_segments,
                    "detail": (
                        f"{alert_segments} segment(s) pass through a zone with an "
                        f"unresolved alert in the last 30 days"
                    ),
                    "direction": "lower_is_better",
                },
                {
                    "key": "time_of_day",
                    "label": "Time-of-day factor",
                    "value": time_multiplier,
                    "detail": (
                        f"Departure at {depart_hour:02d}:00 - "
                        + ("night hours" if is_night else "evening hours" if is_evening else "daytime")
                        + f", risk multiplier {time_multiplier:.2f}"
                    ),
                    "direction": "lower_is_better",
                },
                {
                    "key": "emergency_proximity",
                    "label": "Emergency service proximity",
                    "value": round(sum(service_distances) / len(service_distances), 2),
                    "detail": (
                        f"Average {sum(service_distances) / len(service_distances):.2f} km "
                        f"to the nearest police station, hospital or response unit"
                    ),
                    "direction": "lower_is_better",
                },
                {
                    "key": "lighting",
                    "label": "Street lighting",
                    "value": unlit_segments,
                    "detail": f"{unlit_segments} of {len(segments)} segment(s) recorded as unlit",
                    "direction": "lower_is_better",
                },
                {
                    "key": "distance",
                    "label": "Route distance",
                    "value": round(distance, 2),
                    "detail": f"{distance:.2f} km total",
                    "direction": "neutral",
                },
            ],
        })

    routes.sort(key=lambda r: -r["safety_score"])
    for index, route in enumerate(routes):
        route["rank"] = index + 1
        route["recommended"] = index == 0

    best = routes[0]
    return {
        "from": {"ref": from_ref, "name": waypoints[from_ref].name},
        "to": {"ref": to_ref, "name": waypoints[to_ref].name},
        "depart_hour": depart_hour,
        "routes": routes,
        "recommendation": {
            "label": best["label"],
            "safety_score": best["safety_score"],
            "wording": "Recommended based on available safety indicators.",
            "why": (
                f"{best['label']} scores {best['safety_score']}/100 - lowest incident "
                f"density among the compared options, "
                f"{best['factors'][3]['value']} km average distance to emergency services, "
                f"and {best['factors'][1]['value']} segment(s) affected by recent alerts."
            ),
        },
        "algorithm_version": ROUTE_VERSION,
        "disclaimer": (
            "Route scoring reflects recorded incident data and configured service "
            "locations only. It is not a guarantee of safety and does not account "
            "for live conditions. No route is ever described as safe."
        ),
    }


def nearby_services(
    db: Session, lat: float, lng: float, radius_km: float = 5.0, limit: int = 20
) -> list[dict[str, Any]]:
    services = db.scalars(select(EmergencyService)).all()
    out = []
    for service in services:
        distance = haversine_km(lat, lng, service.latitude, service.longitude)
        if distance > radius_km:
            continue
        out.append({
            "service_ref": service.service_ref,
            "type": service.type,
            "name": service.name,
            "status": service.status,
            "contact": service.contact,
            "open_24x7": service.open_24x7,
            "distance_km": round(distance, 3),
            "lat": service.latitude,
            "lng": service.longitude,
            "classification": service.data_classification,
        })
    out.sort(key=lambda s: s["distance_km"])
    return out[:limit]
