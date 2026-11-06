import sys
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


def verify_database_connection() -> bool:
    """Verify connectivity to PostgreSQL by executing a test query."""
    safe_target = engine.url.render_as_string(hide_password=True)
    print(f"Connecting to PostgreSQL database at: {safe_target}")

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("SUCCESS: Database connection verified. SELECT 1 returned 1.")
                return True

            print(
                f"FAILURE: Unexpected query result. Expected 1, received: {result}",
                file=sys.stderr,
            )
            return False
    except SQLAlchemyError as err:
        print(
            f"ERROR: Failed to connect to database ({err.__class__.__name__}): {err}",
            file=sys.stderr,
        )
        return False
    except Exception as err:
        print(
            f"ERROR: Unexpected exception occurred: {err}",
            file=sys.stderr,
        )
        return False


if __name__ == "__main__":
    if not verify_database_connection():
        sys.exit(1)
