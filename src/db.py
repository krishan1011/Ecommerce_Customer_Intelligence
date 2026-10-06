import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, text

from .config import DATABASE_URL, SQL_DIR


def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def check_connection() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1


def run_schema(yes: bool = False) -> None:
    """Reset and recreate the schema after explicit confirmation."""
    print("WARNING: raw, core and analytics schemas will be dropped and recreated.")
    if not yes and os.getenv("ALLOW_SCHEMA_RESET") != "1":
        raise SystemExit("Refusing to reset database. Pass --yes or set ALLOW_SCHEMA_RESET=1.")

    schema_path = SQL_DIR / "01_schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    sql_script = schema_path.read_text(encoding="utf-8")
    engine = get_engine()

    with engine.begin() as conn:
        conn.exec_driver_sql(sql_script)

    inspector = inspect(engine)
    schemas = [s for s in inspector.get_schema_names() if s in ("raw", "core", "analytics")]
    print(f"Schemas created: {schemas}")
    for s in schemas:
        tables = inspector.get_table_names(schema=s)
        print(f"  [{s}] ({len(tables)} tables): {', '.join(tables)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Database utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    schema_parser = subparsers.add_parser("schema", help="Reset and recreate database schemas")
    schema_parser.add_argument(
        "--yes", action="store_true", help="confirm dropping raw, core, and analytics"
    )
    subparsers.add_parser("check", help="check the database connection")
    subparsers.add_parser("load", help="load Olist CSV data into raw and core schemas")
    args = parser.parse_args()

    if args.command == "schema":
        run_schema(yes=args.yes)
        return 0
    if args.command == "load":
        from .load import load_data

        load_data()
        return 0
    connected = check_connection()
    print(f"Database connection: {'OK' if connected else 'FAILED'}")
    return 0 if connected else 1


if __name__ == "__main__":
    sys.exit(main())
