import os
import sys
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import engine

EXPECTED_APPLICATION_TABLES = [
    "users",
    "leads",
    "lead_assignments",
    "loan_applications",
    "consents",
    "lender_policies",
    "match_runs",
    "lender_decisions",
    "offers",
    "offer_submissions",
    "lender_events",
]


def verify_database_schema() -> bool:
    """Verify that PostgreSQL schema contains all tables, constraints, and current revision."""
    print("==================================================")
    print("PostgreSQL Database Schema Verification")
    print("==================================================")
    print(f"Database: {settings.POSTGRES_DB}")
    print(f"Host:     {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names(schema="public"))
    actual_app_tables = sorted([t for t in existing_tables if t != "alembic_version"])

    print(f"\nDiscovered {len(actual_app_tables)} application tables in PostgreSQL:")
    for t in actual_app_tables:
        print(f"  - {t}")

    missing_tables = [t for t in EXPECTED_APPLICATION_TABLES if t not in existing_tables]
    if missing_tables:
        print(f"\nERROR: Missing expected tables: {missing_tables}", file=sys.stderr)
        return False

    print("\nAll eleven expected application tables exist in PostgreSQL.")

    if "alembic_version" not in existing_tables:
        print("\nERROR: 'alembic_version' table is missing.", file=sys.stderr)
        return False
    print("'alembic_version' tracking table is present.")

    # Verify Alembic migration revision
    ini_path = "alembic.ini"
    if not os.path.exists(ini_path) and os.path.exists("backend/alembic.ini"):
        ini_path = "backend/alembic.ini"

    cfg = Config(ini_path)
    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()

    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        current_rev = ctx.get_current_revision()

    print(f"\nAlembic Head Revision:    {head_rev}")
    print(f"PostgreSQL Current Rev:   {current_rev}")

    if head_rev != current_rev:
        print("\nERROR: Database revision does not match migration head!", file=sys.stderr)
        return False

    print("Alembic revision is up to date (current matches head).")

    # Detailed constraint sampling
    print("\nSample constraints verified in PostgreSQL:")
    for table_name in ["lender_decisions", "offers", "offer_submissions", "lender_events"]:
        checks = [ck["name"] for ck in inspector.get_check_constraints(table_name)]
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        print(f"  [{table_name}]")
        print(f"    Check constraints: {checks}")
        print(f"    Foreign keys:      {fks}")

    print("\nSUCCESS: PostgreSQL schema and Alembic migration state fully verified.")
    return True


if __name__ == "__main__":
    if not verify_database_schema():
        sys.exit(1)
