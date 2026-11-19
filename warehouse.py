
import sqlite3
from pathlib import Path


# Project paths
PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_FILE = PROJECT_DIR / "clinical_portal.db"
SCHEMA_FILE = PROJECT_DIR / "sql" / "warehouse_schema.sql"


def get_warehouse_connection():
    """Connect to the existing SQLite database with foreign keys enabled."""
    connection = sqlite3.connect(DATABASE_FILE)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_warehouse():
    """Create warehouse tables without modifying existing user accounts."""

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"Warehouse schema not found: {SCHEMA_FILE}"
        )

    connection = get_warehouse_connection()

    try:
        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        connection.executescript(schema_sql)
        connection.commit()

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        print("Warehouse initialized successfully!")
        print("\nDatabase tables:")

        for table in tables:
            print(f"- {table[0]}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_warehouse()
