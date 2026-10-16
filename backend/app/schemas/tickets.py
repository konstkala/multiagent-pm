import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.db.models import TicketPriority, TicketStatus, TicketType

Label = Annotated[str, StringConstraints(min_length=1, max_length=50)]
Labels = Annotated[list[Label], Field(max_length=20)]


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20_000)


class TicketUpdate(BaseModel):
    """Only the fields sent are changed. Sending null clears the optional ones."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)
    status: TicketStatus | None = None
    labels: Labels | None = None
    type: TicketType | None = None
    priority: TicketPriority | None = None
    component: str | None = Field(default=None, max_length=100)
    assignee: str | None = Field(default=None, max_length=100)
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
    labels: list[str]
    type: TicketType | None
    priority: TicketPriority | None
    component: str | None
    assignee: str | None
    duplicate_of: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SimilarTicket(BaseModel):
    ticket: TicketRead
    similarity: float = Field(description="Cosine similarity, 1.0 means identical meaning")


class SimilarTickets(BaseModel):
    items: list[SimilarTicket]


class TicketPage(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int
