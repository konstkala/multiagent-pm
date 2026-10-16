import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.db.models import LinkType, TicketCategory, TicketPriority, TicketStatus

# Labels are areas like "database" or "frontend": trimmed and lowercased so they group.
Label = Annotated[
    str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True, to_lower=True)
]
Labels = Annotated[list[Label], Field(max_length=10)]
StoryPoints = Literal[1, 2, 3, 5, 8, 13]
Title = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Description = Annotated[str, Field(max_length=20_000)]


class TicketCreate(BaseModel):
    title: Title
    description: Description = ""
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    labels: Labels = []
    story_points: StoryPoints | None = None
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    """Only the fields sent are changed. Sending null clears the optional ones."""

    title: Title | None = None
    description: Description | None = None
    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    labels: Labels | None = None
    story_points: StoryPoints | None = None
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    duplicate_of: uuid.UUID | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for name in ("title", "description", "status", "labels"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    number: int
    reporter_id: uuid.UUID | None
    title: str
    description: str
    status: TicketStatus
    category: TicketCategory | None
    priority: TicketPriority | None
    labels: list[str]
    story_points: int | None
    due_date: date | None
    assignee_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    duplicate_of: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TicketBrief(BaseModel):
    """Enough to show a ticket inside another one: PM-12 · title · status."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    title: str
    status: TicketStatus


class TicketPage(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int


class ReturnRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2_000)


class SimilarTicket(BaseModel):
    ticket: TicketRead
    similarity: float = Field(description="Cosine similarity, 1.0 means identical meaning")


class SimilarTickets(BaseModel):
    items: list[SimilarTicket]


class CommentWrite(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class CommentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID | None
    author_name: str | None  # None when the account was erased
    body: str
    created_at: datetime
    edited_at: datetime | None


class AttachmentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    uploader_id: uuid.UUID | None
    uploader_name: str | None
    created_at: datetime


class LinkCreate(BaseModel):
    target_id: uuid.UUID
    type: LinkType


class LinkRead(BaseModel):
    id: uuid.UUID
    type: LinkType
    # outgoing: this ticket blocks / relates to `ticket`; incoming: `ticket` blocks this one.
    direction: Literal["outgoing", "incoming"]
    ticket: TicketBrief
