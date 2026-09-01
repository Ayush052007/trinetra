"""Women Safety Intelligence schema.

These tables are first-class members of the same database as the criminal
network model - incidents reference the same `entities` table, which is what
lets a safety incident be pivoted straight into the network graph.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    DateTime,
    AlertStatus,
    Base,
    DataClassification,
    Priority,
    SosStatus,
    TimestampMixin,
)
from app.db.models import Case, Entity, User


class IncidentType:
    """Incident categories present in the project material."""

    HARASSMENT = "harassment"
    STALKING = "stalking"
    ASSAULT = "assault_or_confrontation"
    MISSING_PERSON = "missing_person"
    THREAT = "threat"
    SUSPICIOUS_CONTACT = "suspicious_contact"
    SUSPICIOUS_VEHICLE = "suspicious_vehicle"
    OTHER = "other"

    ALL = [
        HARASSMENT,
        STALKING,
        ASSAULT,
        MISSING_PERSON,
        THREAT,
        SUSPICIOUS_CONTACT,
        SUSPICIOUS_VEHICLE,
        OTHER,
    ]

    LABELS = {
        HARASSMENT: "Harassment",
        STALKING: "Stalking",
        ASSAULT: "Assault / Confrontation",
        MISSING_PERSON: "Missing Person",
        THREAT: "Threat",
        SUSPICIOUS_CONTACT: "Suspicious Contact",
        SUSPICIOUS_VEHICLE: "Suspicious Vehicle",
        OTHER: "Other",
    }


class Incident(Base, TimestampMixin):
    """A reported women-safety incident."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    priority: Mapped[str] = mapped_column(String(16), default=Priority.MEDIUM, index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    time_label: Mapped[str | None] = mapped_column(String(48), default=None)
    hour_of_day: Mapped[int | None] = mapped_column(Integer, default=None, index=True)

    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    subject_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    location_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("safety_zones.id"), default=None, index=True
    )
    reported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)

    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    location_text: Mapped[str | None] = mapped_column(String(200), default=None)

    # Descriptors used by suspicious-pattern detection (vehicle description,
    # device identifier, and any entity uids named in the report).
    descriptors: Mapped[dict] = mapped_column(JSON, default=dict)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    case: Mapped[Case | None] = relationship()
    subject_entity: Mapped[Entity | None] = relationship(foreign_keys=[subject_entity_id])
    location_entity: Mapped[Entity | None] = relationship(foreign_keys=[location_entity_id])

    __table_args__ = (Index("ix_incident_type_time", "type", "occurred_at"),)


class SafetyZone(Base, TimestampMixin):
    """A geographic area used for heatmap aggregation and route costing.

    `band` is recomputed from live incident density - it is never stored as a
    fixed colour, so filters genuinely change what the map shows.
    """

    __tablename__ = "safety_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(255), default=None)

    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float, default=1.0)

    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )


class EmergencyService(Base, TimestampMixin):
    """Police station, hospital, response unit or safe public location.

    Sourced from configured deployment data. Real emergency-service directory
    APIs are not connected - see docs/INTEGRATIONS.md.
    """

    __tablename__ = "emergency_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(160))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("safety_zones.id"), default=None)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="AVAILABLE")
    contact: Mapped[str | None] = mapped_column(String(64), default=None)
    open_24x7: Mapped[bool] = mapped_column(Boolean, default=True)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )


class Waypoint(Base):
    """A node in the routable network used by the AI Safe Route engine."""

    __tablename__ = "waypoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    waypoint_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("safety_zones.id"), default=None)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)
    is_endpoint: Mapped[bool] = mapped_column(Boolean, default=False)
    lit: Mapped[bool] = mapped_column(Boolean, default=True)


class WaypointEdge(Base):
    """A traversable segment between two waypoints."""

    __tablename__ = "waypoint_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int] = mapped_column(
        ForeignKey("waypoints.id", ondelete="CASCADE"), index=True
    )
    to_id: Mapped[int] = mapped_column(ForeignKey("waypoints.id", ondelete="CASCADE"), index=True)
    distance_km: Mapped[float] = mapped_column(Float)
    path_type: Mapped[str] = mapped_column(String(32), default="road")


class RouteQuery(Base):
    """A stored safe-route computation with its explainable score breakdown."""

    __tablename__ = "route_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    from_waypoint_id: Mapped[int] = mapped_column(ForeignKey("waypoints.id"))
    to_waypoint_id: Mapped[int] = mapped_column(ForeignKey("waypoints.id"))
    depart_hour: Mapped[int] = mapped_column(Integer, default=12)
    routes: Mapped[list] = mapped_column(JSON, default=list)
    algorithm_version: Mapped[str] = mapped_column(String(16), default="route-1.0")


class EmergencyContact(Base, TimestampMixin):
    """A contact notified when a subject raises an SOS."""

    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), default=None, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    relation: Mapped[str | None] = mapped_column(String(64), default=None)
    phone: Mapped[str] = mapped_column(String(32))
    priority_order: Mapped[int] = mapped_column(Integer, default=1)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )


class SosAlert(Base, TimestampMixin):
    """A one-tap emergency alert and its response workflow.

    Location is simulated unless ENABLE_DEVICE_GPS is configured; the
    location_source column records which, so the UI never implies a real fix.
    Raising an SOS here notifies the in-platform dispatcher console only - no
    emergency call is placed.
    """

    __tablename__ = "sos_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default=SosStatus.RECEIVED, index=True)
    priority: Mapped[str] = mapped_column(String(16), default=Priority.CRITICAL)

    raised_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    subject_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)
    subject_name: Mapped[str] = mapped_column(String(120), default="Unnamed subject")

    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    location_text: Mapped[str | None] = mapped_column(String(200), default=None)
    location_source: Mapped[str] = mapped_column(String(24), default="SIMULATED")

    zone_id: Mapped[int | None] = mapped_column(ForeignKey("safety_zones.id"), default=None)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None)
    assigned_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("emergency_services.id"), default=None
    )
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    contacts_notified: Mapped[list] = mapped_column(JSON, default=list)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    assigned_unit: Mapped[EmergencyService | None] = relationship()
    assigned_officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id])
    history: Mapped[list[SosStatusHistory]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", order_by="SosStatusHistory.changed_at"
    )


class SosStatusHistory(Base):
    """Every state transition of an SOS alert, with who made it."""

    __tablename__ = "sos_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("sos_alerts.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(24), default=None)
    to_status: Mapped[str] = mapped_column(String(24))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text, default=None)

    alert: Mapped[SosAlert] = relationship(back_populates="history")
    changed_by: Mapped[User | None] = relationship()


class SafetyAlert(Base, TimestampMixin):
    """A live safety alert surfaced to the operations feed."""

    __tablename__ = "safety_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(32), default="Women Safety", index=True)
    priority: Mapped[str] = mapped_column(String(16), default=Priority.MEDIUM, index=True)
    status: Mapped[str] = mapped_column(String(24), default=AlertStatus.NEW, index=True)
    message: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text, default=None)

    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    time_label: Mapped[str | None] = mapped_column(String(48), default=None)

    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), default=None)
    sos_alert_id: Mapped[int | None] = mapped_column(ForeignKey("sos_alerts.id"), default=None)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("safety_zones.id"), default=None)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)

    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Supporting record ids so an alert is always traceable, never a bare claim.
    supporting: Mapped[dict] = mapped_column(JSON, default=dict)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    assigned_to: Mapped[User | None] = relationship()


class PatternDetection(Base, TimestampMixin):
    """A stored analytical pattern: suspicious cluster or repeated encounter.

    Always advisory. `status` tracks investigator review; supporting_events and
    supporting_entities make every claim inspectable.
    """

    __tablename__ = "pattern_detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="PENDING_REVIEW", index=True)

    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    subject_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)
    counterpart_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None
    )

    supporting_incidents: Mapped[list] = mapped_column(JSON, default=list)
    supporting_events: Mapped[list] = mapped_column(JSON, default=list)
    supporting_entities: Mapped[list] = mapped_column(JSON, default=list)
    factors: Mapped[list] = mapped_column(JSON, default=list)

    algorithm_version: Mapped[str] = mapped_column(String(16), default="pattern-1.0")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
