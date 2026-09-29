from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import EdgeKind


class EdgeCreate(BaseModel, extra="forbid"):
    other_contact_id: UUID
    kind: EdgeKind = EdgeKind.knows
    strength: int = Field(default=50, ge=0, le=100)
    note: str | None = Field(default=None, max_length=500)


class EdgeRead(BaseModel):
    id: UUID
    contact_id: UUID
    other_contact_id: UUID
    other_display_name: str
    other_honorific: str | None
    other_company: str | None
    other_gravity_score: int
    kind: EdgeKind
    strength: int
    note: str | None
    created_at: datetime


class GraphNode(BaseModel):
    id: str
    kind: Literal["me", "contact"]
    display_name: str
    initials: str
    title: str | None
    company: str | None
    industry: str | None
    relationship_type: str | None
    gravity_score: int
    band: str
    last_interaction_at: datetime | None
    deal_value_cents: int
    connection_count: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    strength: int
    kind: str


class Graph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Path(BaseModel):
    nodes: list[str]
    hops: int
    min_strength: int


class PathsResult(BaseModel):
    from_id: str
    to_ids: list[str]
    paths: list[Path]
