# run_migrations.py
# Runs every .sql file in database/migrations in order and skips files already applied.

from pathlib import Path

from database.connection import connect_once

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations() -> None:
    with connect_once() as conn:
        # Table that remembers which files already ran
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                file_name   TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        rows = conn.execute("SELECT file_name FROM schema_migrations").fetchall()
        applied = {row["file_name"] for row in rows}
        conn.commit()

        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in applied:
                print(f"skip  {sql_file.name}")
                continue

            # Whole file + its record in one transaction: all or nothing
            with conn.transaction():
                conn.execute(sql_file.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (file_name) VALUES (%s)",
                    (sql_file.name,),
                )
            print(f"done  {sql_file.name}")


if __name__ == "__main__":
    run_migrations()