from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ExportRequest(BaseModel, extra="forbid"):
    scope: Literal["personal", "my_contributions"] = "personal"


class ExportRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    scope: str
    status: str
    download_url: str | None
    expires_at: datetime | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ExportAccepted(BaseModel):
    export_id: UUID
    job_id: UUID | None
