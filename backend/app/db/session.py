from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Construct the database URL safely using SQLAlchemy URL.create with Psycopg 3
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.POSTGRES_USER,
    password=settings.POSTGRES_PASSWORD,
    host=settings.POSTGRES_HOST,
    port=settings.POSTGRES_PORT,
    database=settings.POSTGRES_DB,
)

# Engine configured with connection health check before checkout
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Thread-local database session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session generator and ensure it is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
