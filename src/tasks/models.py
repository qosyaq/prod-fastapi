from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IdIntPkMixin, TimestampMixin
from .constants import TaskStatus


class TaskOrm(IdIntPkMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING)
