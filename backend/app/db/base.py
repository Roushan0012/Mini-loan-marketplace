from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Sensible naming convention for database constraints and indexes.
# Explicit naming prevents unnamed PostgreSQL constraints and enables deterministic migrations.
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.x declarative models in Mini Loan Marketplace."""

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
