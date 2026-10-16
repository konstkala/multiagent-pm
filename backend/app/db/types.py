from enum import StrEnum

from sqlalchemy import Enum


def _values(cls: type[StrEnum]) -> list[str]:
    return [member.value for member in cls]


def text_enum(cls: type[StrEnum]) -> Enum:
    """Stored as text with a CHECK constraint: adding a value is a plain migration."""
    return Enum(cls, native_enum=False, create_constraint=True, length=20, values_callable=_values)
