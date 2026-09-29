"""SQLAlchemy models mirroring supabase/migrations. tests/integration/test_schema_parity.py keeps them honest."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, ENUM, INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import enums as e


def pg_enum(enum_cls: type[StrEnum], name: str) -> ENUM:
    return ENUM(enum_cls, name=name, create_type=False, values_callable=lambda c: [m.value for m in c])


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[str]: ARRAY(Text),
    }


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    full_name: Mapped[str] = mapped_column(Text, default="")
    role_title: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, default="UTC")
    avatar_path: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    onboarding_step: Mapped[int] = mapped_column(SmallInteger, default=0)
    onboarding_completed_at: Mapped[datetime | None]
    default_workspace_id: Mapped[UUID | None] = mapped_column(ForeignKey("workspaces.id", use_alter=True))
    deleted_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class UserInterest(Base):
    __tablename__ = "user_interests"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(CITEXT)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    kind: Mapped[e.WorkspaceKind] = mapped_column(pg_enum(e.WorkspaceKind, "workspace_kind"))
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    plan: Mapped[str] = mapped_column(Text, default="free")
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    role: Mapped[e.WorkspaceRole] = mapped_column(pg_enum(e.WorkspaceRole, "workspace_role"), default=e.WorkspaceRole.member)
    status: Mapped[e.MembershipStatus] = mapped_column(pg_enum(e.MembershipStatus, "membership_status"), default=e.MembershipStatus.active)
    joined_at: Mapped[datetime] = mapped_column(server_default="now()")
    departed_at: Mapped[datetime | None]
    grace_until: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    email: Mapped[str] = mapped_column(CITEXT)
    role: Mapped[e.WorkspaceRole] = mapped_column(pg_enum(e.WorkspaceRole, "workspace_role"), default=e.WorkspaceRole.member)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    expires_at: Mapped[datetime] = mapped_column(server_default="now() + interval '7 days'")
    accepted_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    name: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(CITEXT)
    industry: Mapped[str | None] = mapped_column(Text)
    type: Mapped[e.CompanyType] = mapped_column(pg_enum(e.CompanyType, "company_type"), default=e.CompanyType.other)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")
    deleted_at: Mapped[datetime | None]


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    first_name: Mapped[str] = mapped_column(Text, default="")
    last_name: Mapped[str] = mapped_column(Text, default="")
    display_name: Mapped[str] = mapped_column(Text, Computed("btrim(first_name || ' ' || last_name)", persisted=True), nullable=True)
    honorific: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    emails: Mapped[list[str]] = mapped_column(ARRAY(CITEXT), default=list)
    phones: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    location: Mapped[str | None] = mapped_column(Text)
    relationship_type: Mapped[e.RelationshipType] = mapped_column(
        pg_enum(e.RelationshipType, "relationship_type"), default=e.RelationshipType.other
    )
    visibility: Mapped[e.ContactVisibility] = mapped_column(
        pg_enum(e.ContactVisibility, "contact_visibility"), default=e.ContactVisibility.team
    )
    status: Mapped[e.ContactStatus] = mapped_column(pg_enum(e.ContactStatus, "contact_status"), default=e.ContactStatus.active)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    cadence_days: Mapped[int] = mapped_column(SmallInteger, default=30)
    gravity_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    gravity_updated_at: Mapped[datetime | None]
    last_interaction_at: Mapped[datetime | None]
    next_due_at: Mapped[datetime | None]
    origin_contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    source: Mapped[str] = mapped_column(Text, default="manual")
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")
    deleted_at: Mapped[datetime | None]
    # display_name and search_vector are generated columns; never assign them.
    __mapper_args__ = {"eager_defaults": True}


class ContactFact(Base):
    __tablename__ = "contact_facts"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"))
    category: Mapped[e.FactCategory] = mapped_column(pg_enum(e.FactCategory, "fact_category"))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[e.FactSource] = mapped_column(pg_enum(e.FactSource, "fact_source"), default=e.FactSource.manual)
    source_interaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("interactions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by: Mapped[UUID | None] = mapped_column(ForeignKey("contact_facts.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class ContactProfile(Base):
    __tablename__ = "contact_profiles"
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    summary: Mapped[str] = mapped_column(Text, default="")
    communication_style: Mapped[str | None] = mapped_column(Text)
    remember: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    risks: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    talking_points: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    common_ground: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None]
    stale: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Interaction(Base):
    __tablename__ = "interactions"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    kind: Mapped[e.InteractionKind] = mapped_column(pg_enum(e.InteractionKind, "interaction_kind"), default=e.InteractionKind.note)
    direction: Mapped[e.InteractionDirection] = mapped_column(
        pg_enum(e.InteractionDirection, "interaction_direction"), default=e.InteractionDirection.mutual
    )
    occurred_at: Mapped[datetime] = mapped_column(server_default="now()")
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[e.SentimentLabel | None] = mapped_column(pg_enum(e.SentimentLabel, "sentiment_label"))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    source: Mapped[e.InteractionSource] = mapped_column(
        pg_enum(e.InteractionSource, "interaction_source"), default=e.InteractionSource.manual
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    ai_status: Mapped[e.AiStatus] = mapped_column(pg_enum(e.AiStatus, "ai_status"), default=e.AiStatus.none)
    ai_extraction: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")
    deleted_at: Mapped[datetime | None]
    # search_vector (generated) and embedding (Phase 2, pgvector) are intentionally unmapped.
    __mapper_args__ = {"eager_defaults": True}


class Capture(Base):
    __tablename__ = "captures"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    kind: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    transcript: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[e.CaptureStatus] = mapped_column(pg_enum(e.CaptureStatus, "capture_status"), default=e.CaptureStatus.uploaded)
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    interaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("interactions.id"))
    error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    assignee_user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None]
    status: Mapped[e.TaskStatus] = mapped_column(pg_enum(e.TaskStatus, "task_status"), default=e.TaskStatus.open)
    priority: Mapped[int] = mapped_column(SmallInteger, default=2)
    source: Mapped[e.TaskSource] = mapped_column(pg_enum(e.TaskSource, "task_source"), default=e.TaskSource.manual)
    source_interaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("interactions.id"))
    completed_at: Mapped[datetime | None]
    snoozed_until: Mapped[datetime | None]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    name: Mapped[str] = mapped_column(Text)
    value_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    stage: Mapped[str] = mapped_column(Text, default="qualifying")
    probability: Mapped[int | None] = mapped_column(SmallInteger)
    expected_close: Mapped[date | None] = mapped_column(Date)
    status: Mapped[e.OpportunityStatus] = mapped_column(
        pg_enum(e.OpportunityStatus, "opportunity_status"), default=e.OpportunityStatus.open
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")
    deleted_at: Mapped[datetime | None]


class OpportunityContact(Base):
    __tablename__ = "opportunity_contacts"
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), primary_key=True)
    role: Mapped[e.OpportunityRole] = mapped_column(pg_enum(e.OpportunityRole, "opportunity_role"), default=e.OpportunityRole.other)


class ContactEdge(Base):
    __tablename__ = "contact_edges"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    contact_a_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"))
    contact_b_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"))
    kind: Mapped[e.EdgeKind] = mapped_column(pg_enum(e.EdgeKind, "edge_kind"), default=e.EdgeKind.knows)
    strength: Mapped[int] = mapped_column(SmallInteger, default=50)
    source: Mapped[str] = mapped_column(Text, default="manual")
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class RelationshipScore(Base):
    __tablename__ = "relationship_scores"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"))
    scored_on: Mapped[date] = mapped_column(Date)
    score: Mapped[int] = mapped_column(SmallInteger)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    band: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[e.InsightKind] = mapped_column(pg_enum(e.InsightKind, "insight_kind"))
    severity: Mapped[e.InsightSeverity] = mapped_column(pg_enum(e.InsightSeverity, "insight_severity"), default=e.InsightSeverity.info)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    suggested_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(Text)
    status: Mapped[e.InsightStatus] = mapped_column(pg_enum(e.InsightStatus, "insight_status"), default=e.InsightStatus.new)
    expires_at: Mapped[datetime | None]
    generated_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class ContextItem(Base):
    __tablename__ = "context_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("contacts.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    source: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None]
    relevance: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    provider: Mapped[e.IntegrationProvider] = mapped_column(pg_enum(e.IntegrationProvider, "integration_provider"))
    status: Mapped[e.IntegrationStatus] = mapped_column(
        pg_enum(e.IntegrationStatus, "integration_status"), default=e.IntegrationStatus.connected
    )
    external_account_id: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # credentials_enc is deliberately unmapped: `authenticated` has no select privilege on it.
    sync_cursor: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_synced_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class AiCredential(Base):
    __tablename__ = "ai_credentials"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    provider: Mapped[str] = mapped_column(Text)
    # key_enc is deliberately unmapped: `authenticated` has no select privilege on it.
    key_hint: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    workspace_id: Mapped[UUID | None] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    status: Mapped[e.JobStatus] = mapped_column(pg_enum(e.JobStatus, "job_status"), default=e.JobStatus.queued)
    run_after: Mapped[datetime] = mapped_column(server_default="now()")
    priority: Mapped[int] = mapped_column(SmallInteger, default=5)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=5)
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[UUID | None]
    actor_user_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[UUID | None]
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class Export(Base):
    __tablename__ = "exports"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    scope: Mapped[str] = mapped_column(Text)
    status: Mapped[e.JobStatus] = mapped_column(pg_enum(e.JobStatus, "job_status"), default=e.JobStatus.queued)
    storage_path: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None]
