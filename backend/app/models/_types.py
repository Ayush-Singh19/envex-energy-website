"""Column helpers shared by the models."""

import enum
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import mapped_column

CreatedAt = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
]


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Native Postgres enum that stores member *values* ("new"), not names ("NEW")."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
