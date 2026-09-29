"""Structured output schemas for the capture pipeline (Section 8.2 and 11.2). The LLM fills these; users edit them."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import FactCategory, InteractionDirection, InteractionKind, SentimentLabel


class ContactMatch(BaseModel):
    contact_id: str
    display_name: str
    confidence: float = Field(ge=0, le=1)


class ExtractedInteraction(BaseModel):
    kind: InteractionKind = InteractionKind.note
    occurred_at: datetime | None = None
    subject: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20000)
    sentiment: SentimentLabel = SentimentLabel.neutral
    sentiment_score: float = Field(default=0.0, ge=-1, le=1)
    direction: InteractionDirection = InteractionDirection.mutual


class ExtractedFact(BaseModel):
    category: FactCategory
    content: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.8, ge=0, le=1)
    supersedes: str | None = Field(default=None, description="Existing fact this one contradicts, verbatim")


class ExtractedTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime | None = None
    priority: int = Field(default=2, ge=1, le=3)
    contact_ref: str | None = Field(
        default=None, description="Name of the person the task concerns, if not the main contact"
    )


class MentionedPerson(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=120)
    relationship_hint: str | None = Field(default=None, max_length=200)


class ExtractedEdge(BaseModel):
    person_a: str = Field(min_length=1, max_length=120)
    person_b: str = Field(min_length=1, max_length=120)
    kind: Literal["knows", "reports_to", "works_with", "introduced_by", "former_colleague", "other"] = "knows"


class CaptureExtraction(BaseModel):
    contact_match: ContactMatch | None = None
    interaction: ExtractedInteraction
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)
    tasks: list[ExtractedTask] = Field(default_factory=list, max_length=20)
    mentioned_people: list[MentionedPerson] = Field(default_factory=list, max_length=20)
    mentioned_companies: list[str] = Field(default_factory=list, max_length=20)
    edges: list[ExtractedEdge] = Field(default_factory=list, max_length=20)
    needs_review: list[str] = Field(default_factory=list, max_length=10)


class ContactProfileDraft(BaseModel):
    summary: str = Field(max_length=900)
    communication_style: str = Field(default="", max_length=120)
    remember: list[str] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=4)
    talking_points: list[str] = Field(default_factory=list, max_length=5)
    common_ground: list[str] = Field(default_factory=list, max_length=3)


class BriefStructured(BaseModel):
    due_outs: list[str] = Field(default_factory=list, max_length=10)
    suggested_questions: list[str] = Field(default_factory=list, max_length=6)


class BriefDraft(BaseModel):
    text: str = Field(max_length=2400)
    structured: BriefStructured
