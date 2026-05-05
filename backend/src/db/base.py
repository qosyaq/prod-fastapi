from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=settings.postgres.naming_convention)
