import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.db.models import CvImportStatus, WorkspaceRole

SkillName = Annotated[str, StringConstraints(min_length=1, max_length=60, strip_whitespace=True)]


class SkillWrite(BaseModel):
    name: SkillName
    level: int = Field(ge=1, le=5)


class ProfileWrite(BaseModel):
    headline: str = Field(default="", max_length=150)
    summary: str = Field(default="", max_length=5_000)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    skills: list[SkillWrite] = Field(default=[], max_length=50)

    @model_validator(mode="after")
    def skill_names_unique(self) -> Self:
        names = [s.name.lower() for s in self.skills]
        if len(names) != len(set(names)):
            raise ValueError("each skill can appear only once")
        return self


class SkillRead(BaseModel):
    name: str
    level: int


class ProfileRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    headline: str
    summary: str
    years_experience: int | None
    skills: list[SkillRead]
    updated_at: datetime | None  # None: nobody has filled it in yet


class PersonRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    workspace_role: WorkspaceRole
    headline: str
    skill_count: int


class SkillDraftRead(BaseModel):
    name: str
    level: int
    evidence: str


class ProfileDraftRead(BaseModel):
    headline: str
    summary: str
    years_experience: int | None
    skills: list[SkillDraftRead]


class CvImportRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    status: CvImportStatus
    error_code: str | None
    draft: ProfileDraftRead | None
    # Cost and latency of the AI run, shown to managers.
    model: str | None
    cost_usd: float | None
    latency_ms: float | None
    created_at: datetime
    processed_at: datetime | None
