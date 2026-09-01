"""Role-based access control.

Permissions are granular and mapped per role. The frontend also gates UI, but
this module is the enforcement point: every protected route depends on
require_permission(...), so hiding a button is never the security boundary.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    INVESTIGATOR = "INVESTIGATOR"
    SENIOR_INVESTIGATOR = "SENIOR_INVESTIGATOR"
    ANALYST = "ANALYST"
    WOMEN_SAFETY_OFFICER = "WOMEN_SAFETY_OFFICER"
    ADMIN = "ADMIN"


# Human-facing designation used throughout the UI. Sourced from the roles the
# project material lists on the sign-in screen.
ROLE_DESIGNATION: dict[str, str] = {
    Role.INVESTIGATOR: "Investigating Officer",
    Role.SENIOR_INVESTIGATOR: "Supervisory Officer",
    Role.ANALYST: "Intelligence Analyst",
    Role.WOMEN_SAFETY_OFFICER: "Women Safety Officer",
    Role.ADMIN: "NCRB Administrator",
}


class Perm(StrEnum):
    # Cases
    CASE_READ = "case:read"
    CASE_CREATE = "case:create"
    CASE_UPDATE = "case:update"
    CASE_ASSIGN = "case:assign"
    CASE_CLOSE = "case:close"
    # Entities / graph
    ENTITY_READ = "entity:read"
    ENTITY_UPDATE = "entity:update"
    GRAPH_READ = "graph:read"
    RELATIONSHIP_CREATE = "relationship:create"
    RELATIONSHIP_VALIDATE = "relationship:validate"
    RESOLUTION_DECIDE = "resolution:decide"
    # Analysis
    ANALYTICS_RUN = "analytics:run"
    NLP_RUN = "nlp:run"
    PRIORITY_RECOMPUTE = "priority:recompute"
    # Data
    DATA_UPLOAD = "data:upload"
    DATA_EXPORT = "data:export"
    # Women Safety
    SAFETY_READ = "safety:read"
    SAFETY_INCIDENT_CREATE = "safety:incident:create"
    SAFETY_DISPATCH = "safety:dispatch"
    SOS_RAISE = "sos:raise"
    # Reports / audit / admin
    REPORT_GENERATE = "report:generate"
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"
    SYSTEM_ADMIN = "system:admin"


_INVESTIGATOR_BASE = {
    Perm.CASE_READ, Perm.CASE_CREATE, Perm.CASE_UPDATE,
    Perm.ENTITY_READ, Perm.ENTITY_UPDATE, Perm.GRAPH_READ,
    Perm.RELATIONSHIP_CREATE, Perm.RELATIONSHIP_VALIDATE,
    Perm.RESOLUTION_DECIDE, Perm.ANALYTICS_RUN, Perm.NLP_RUN,
    Perm.DATA_UPLOAD, Perm.DATA_EXPORT, Perm.REPORT_GENERATE,
    Perm.SAFETY_READ, Perm.SOS_RAISE,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.INVESTIGATOR: set(_INVESTIGATOR_BASE),
    # Supervisory officer adds assignment, closure and priority recomputation.
    Role.SENIOR_INVESTIGATOR: _INVESTIGATOR_BASE | {
        Perm.CASE_ASSIGN, Perm.CASE_CLOSE, Perm.PRIORITY_RECOMPUTE,
        Perm.AUDIT_READ, Perm.SAFETY_DISPATCH, Perm.SAFETY_INCIDENT_CREATE,
    },
    # Analyst is read + analysis. Deliberately cannot validate relationships:
    # confirming an inferred link into the case record is an investigator act.
    Role.ANALYST: {
        Perm.CASE_READ, Perm.ENTITY_READ, Perm.GRAPH_READ,
        Perm.ANALYTICS_RUN, Perm.NLP_RUN, Perm.PRIORITY_RECOMPUTE,
        Perm.DATA_UPLOAD, Perm.DATA_EXPORT, Perm.REPORT_GENERATE,
        Perm.SAFETY_READ,
    },
    # Women Safety Officer owns the safety module end-to-end and reads the
    # network graph for context, but does not run core-case administration.
    Role.WOMEN_SAFETY_OFFICER: {
        Perm.CASE_READ, Perm.CASE_CREATE, Perm.CASE_UPDATE,
        Perm.ENTITY_READ, Perm.GRAPH_READ, Perm.ANALYTICS_RUN,
        Perm.RELATIONSHIP_VALIDATE, Perm.REPORT_GENERATE, Perm.DATA_EXPORT,
        Perm.SAFETY_READ, Perm.SAFETY_INCIDENT_CREATE, Perm.SAFETY_DISPATCH,
        Perm.SOS_RAISE,
    },
    Role.ADMIN: set(Perm),
}


def permissions_for(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
