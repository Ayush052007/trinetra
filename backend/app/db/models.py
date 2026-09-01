"""TRINETRA relational schema.

Grouped: identity -> cases -> knowledge graph -> ingestion -> analysis ->
reporting. Women Safety tables live in models_safety.py.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    DateTime,
    Base,
    CaseStatus,
    DataClassification,
    EvidenceStatus,
    Priority,
    TimestampMixin,
)

# ============================ IDENTITY =====================================


class User(Base, TimestampMixin):
    """A member of the deploying department."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), index=True)
    designation: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160), unique=True, default=None)
    extension: Mapped[str | None] = mapped_column(String(16), default=None)

    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    @property
    def initials(self) -> str:
        parts = [p for p in self.full_name.replace(".", " ").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class SessionToken(Base):
    """Issued refresh tokens. The revoked flag is the revocation list."""

    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)

    user: Mapped[User] = relationship()


class AuditLog(Base):
    """Append-only trail. Written for every consequential action."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    actor: Mapped[str] = mapped_column(String(120))
    actor_role: Mapped[str | None] = mapped_column(String(32), default=None)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(48), default=None)
    resource_id: Mapped[str | None] = mapped_column(String(64), default=None)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    result: Mapped[str] = mapped_column(String(16), default="SUCCESS")
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    ip_address: Mapped[str | None] = mapped_column(String(64), default=None)

    __table_args__ = (Index("ix_audit_ts_action", "timestamp", "action"),)


# ============================== CASES ======================================


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_number: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.OPEN, index=True)
    priority: Mapped[str] = mapped_column(String(16), default=Priority.MEDIUM)
    module: Mapped[str] = mapped_column(String(32), default="NETWORK")
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    lead_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])
    notes: Mapped[list[CaseNote]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseMember(Base):
    __tablename__ = "case_members"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_on_case: Mapped[str] = mapped_column(String(48), default="Contributor")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class CaseNote(Base, TimestampMixin):
    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    body: Mapped[str] = mapped_column(Text)

    case: Mapped[Case] = relationship(back_populates="notes")
    author: Mapped[User | None] = relationship()


class CaseEntity(Base):
    """Association of an entity with a case."""

    __tablename__ = "case_entities"
    __table_args__ = (UniqueConstraint("case_id", "entity_id", name="uq_case_entity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    role_in_case: Mapped[str | None] = mapped_column(String(48), default=None)
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ========================= KNOWLEDGE GRAPH =================================


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str | None] = mapped_column(String(200), default=None)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    # Entity resolution: when merged, points at the surviving record.
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)

    aliases: Mapped[list[EntityAlias]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_entity_type_name", "type", "normalized_name"),)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(200), index=True)
    normalized_alias: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str | None] = mapped_column(String(200), default=None)

    entity: Mapped[Entity] = relationship(back_populates="aliases")


class Relationship(Base, TimestampMixin):
    """A typed, directed assertion between two entities.

    evidence_status carries the OBSERVED/INFERRED distinction; derivation holds
    the supporting relationship ids for an inferred link, which is what makes
    every AI-surfaced connection traceable back to source records.
    """

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(48), index=True)

    evidence_status: Mapped[str] = mapped_column(
        String(16), default=EvidenceStatus.OBSERVED, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str | None] = mapped_column(String(200), default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    time_label: Mapped[str | None] = mapped_column(String(48), default=None)

    derivation: Mapped[dict] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )

    validated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    source_entity: Mapped[Entity] = relationship(foreign_keys=[source_id])
    target_entity: Mapped[Entity] = relationship(foreign_keys=[target_id])

    __table_args__ = (Index("ix_rel_pair_type", "source_id", "target_id", "type"),)

    @property
    def is_inferred(self) -> bool:
        return self.evidence_status in (
            EvidenceStatus.INFERRED,
            EvidenceStatus.UNDER_REVIEW,
            EvidenceStatus.REJECTED,
        )


class Evidence(Base, TimestampMixin):
    """A traceable pointer from an assertion back to its underlying record."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(48))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    relationship_id: Mapped[int | None] = mapped_column(
        ForeignKey("relationships.id"), default=None, index=True
    )
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey("records.id"), default=None)

    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(16), default=EvidenceStatus.OBSERVED, index=True)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )


class Validation(Base):
    """Immutable record of an investigator decision on an analytical output."""

    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    decision: Mapped[str] = mapped_column(String(16))
    previous_status: Mapped[str | None] = mapped_column(String(16), default=None)
    rationale: Mapped[str | None] = mapped_column(Text, default=None)

    user: Mapped[User] = relationship()


class ResolutionCandidate(Base, TimestampMixin):
    """A possible duplicate/alias pair awaiting an investigator decision.

    Nothing is ever merged automatically: status stays PENDING until a user
    holding resolution:decide accepts or rejects it.
    """

    __tablename__ = "resolution_candidates"
    __table_args__ = (UniqueConstraint("entity_a_id", "entity_b_id", name="uq_resolution_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_a_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    entity_b_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    factors: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    algorithm_version: Mapped[str] = mapped_column(String(16), default="er-1.0")

    entity_a: Mapped[Entity] = relationship(foreign_keys=[entity_a_id])
    entity_b: Mapped[Entity] = relationship(foreign_keys=[entity_b_id])


# ============================ INGESTION ====================================


class Record(Base):
    """A single raw ingested row/document, retained for traceability."""

    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_jobs.id"), default=None, index=True
    )
    source_type: Mapped[str] = mapped_column(String(48), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(120), default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(48))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[str] = mapped_column(String(24), default="RUNNING")
    stage: Mapped[str | None] = mapped_column(String(32), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)

    # Counters computed from the actual file, never hardcoded.
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    entities_extracted: Mapped[int] = mapped_column(Integer, default=0)
    relationships_created: Mapped[int] = mapped_column(Integer, default=0)
    stage_log: Mapped[list] = mapped_column(JSON, default=list)

    uploaded_by: Mapped[User | None] = relationship()


# ============================= ANALYSIS ====================================


class Event(Base):
    """A dated occurrence on the investigation timeline."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    time_label: Mapped[str | None] = mapped_column(String(48), default=None)
    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id"), default=None, index=True
    )
    location_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), default=None)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    relationship_id: Mapped[int | None] = mapped_column(
        ForeignKey("relationships.id"), default=None
    )
    record_id: Mapped[int | None] = mapped_column(ForeignKey("records.id"), default=None)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), default=None)
    data_classification: Mapped[str] = mapped_column(
        String(16), default=DataClassification.SYNTHETIC
    )


class PriorityScore(Base):
    """Investigation Priority Score - an analytical triage signal.

    Explicitly NOT a probability of guilt or criminality. Every score stores
    its factor breakdown, supporting evidence, and when it was computed.
    """

    __tablename__ = "priority_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None, index=True)
    score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    factors: Mapped[list] = mapped_column(JSON, default=list)
    algorithm_version: Mapped[str] = mapped_column(String(16), default="ips-1.0")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    entity: Mapped[Entity] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None, index=True)
    role_target: Mapped[str | None] = mapped_column(String(32), default=None)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    severity: Mapped[str] = mapped_column(String(16), default=Priority.MEDIUM)
    link: Mapped[str | None] = mapped_column(String(200), default=None)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str | None] = mapped_column(String(400), default=None)

    case: Mapped[Case] = relationship()
    generated_by: Mapped[User | None] = relationship()
