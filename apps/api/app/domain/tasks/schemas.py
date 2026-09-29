from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import TaskSource, TaskStatus


class TaskCreate(BaseModel, extra="forbid"):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    priority: int = Field(default=2, ge=1, le=3)
    contact_id: UUID | None = None
    assignee_user_id: UUID | None = None


class TaskUpdate(BaseModel, extra="forbid"):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    contact_id: UUID | None = None
    assignee_user_id: UUID | None = None
    status: Literal["open", "cancelled"] | None = None


class SnoozeRequest(BaseModel, extra="forbid"):
    until: datetime


class TaskRead(BaseModel):
    id: UUID
    workspace_id: UUID
    assignee_user_id: UUID
    assignee_name: str | None
    contact_id: UUID | None
    contact_name: str | None
    title: str
    description: str | None
    due_at: datetime | None
    status: TaskStatus
    priority: int
    source: TaskSource
    source_interaction_id: UUID | None
    completed_at: datetime | None
    snoozed_until: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
