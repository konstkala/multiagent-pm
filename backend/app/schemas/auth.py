import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

# Length over complexity rules, per NIST 800-63B. 128 caps hashing cost.
Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]
Token = Annotated[str, StringConstraints(min_length=20, max_length=200)]


class SignUpRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: str = Field(min_length=1, max_length=100)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: Token


class ResetPasswordRequest(BaseModel):
    token: Token
    password: Password


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    email_verified_at: datetime | None


class MessageResponse(BaseModel):
    message: str
