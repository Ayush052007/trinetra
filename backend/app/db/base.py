"""Declarative base, shared mixins and enumerations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime as SADateTime
from sqlalchemy import TypeDecorator, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class DateTime(TypeDecorator):
    """Timezone-aware datetime that survives a round trip through SQLite.

    SQLite has no native timestamp type and returns naive datetimes, which
    then raise on any comparison with an aware value. Normalising on the way
    in and re-attaching UTC on the way out means application code can assume
    every datetime is aware, on any backend.
    """

    impl = SADateTime
    cache_ok = True

    def __init__(self, timezone: bool = True) -> None:
        super().__init__()
        self._timezone = timezone

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(SADateTime(timezone=self._timezone))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow,
        server_default=func.now(), nullable=False,
    )


class DataClassification(StrEnum):
    """Row-level provenance label.

    SYNTHETIC  - generated or fictional demonstration data.
    REFERENCE  - real, publicly published, cited statistics (context only).
    OPERATIONAL- authorised real case data. Never present in this build.
    """
    SYNTHETIC = "SYNTHETIC"
    REFERENCE = "REFERENCE"
    OPERATIONAL = "OPERATIONAL"


class EvidenceStatus(StrEnum):
    """Lifecycle of an assertion in the knowledge graph.

    The OBSERVED / INFERRED distinction lives here, in the schema, so no view
    can accidentally present a derived link as a recorded fact.
    """
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    REVIEW = "REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SosStatus(StrEnum):
    RECEIVED = "RECEIVED"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"


class AlertStatus(StrEnum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"


class EntityType(StrEnum):
    PERSON = "person"
    PHONE = "phone"
    LOCATION = "location"
    ORGANIZATION = "organization"
    VEHICLE = "vehicle"
    TRANSACTION = "transaction"
    SOCIAL = "social"
    EVENT = "event"
    CASE_RECORD = "case_record"
