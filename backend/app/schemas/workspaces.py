import uuid
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.db.models import ProjectRole, WorkspaceRole

# Uppercase letters and digits, starting with a letter: PM, WEB2. Used in ticket keys like PM-42.
ProjectKey = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{1,9}$")]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    role: WorkspaceRole


class ProjectCreate(BaseModel):
    key: ProjectKey
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5_000)


class ProjectRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    key: str
    name: str
    description: str
    role: ProjectRole


class MemberAdd(BaseModel):
    email: EmailStr
    role: ProjectRole = ProjectRole.EMPLOYEE


class RoleUpdate(BaseModel):
    role: ProjectRole


class MemberRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    role: ProjectRole
