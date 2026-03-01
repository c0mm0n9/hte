"""
Lambda: create PostgreSQL database if it does not exist.
Invoke with event: { "db_host", "db_port", "db_user", "db_password", "db_name" }.
Connects to the default 'postgres' DB, then CREATE DATABASE db_name if not present.
"""
import re
import os


def validate_db_name(name: str) -> bool:
    """Allow only safe identifier characters."""
    return bool(name and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name))


def handler(event: dict, context: object) -> dict:
    db_host = (event.get("db_host") or os.environ.get("DB_HOST") or "").strip()
    db_port = int(event.get("db_port") or os.environ.get("DB_PORT") or "5432")
    db_user = (event.get("db_user") or os.environ.get("DB_USER") or "postgres").strip()
    db_password = (event.get("db_password") or os.environ.get("DB_PASSWORD") or "").strip()
    db_name = (event.get("db_name") or os.environ.get("DB_NAME") or "hte").strip()

    if not db_host:
        return {"status": "error", "message": "db_host required"}
    if not validate_db_name(db_name):
        return {"status": "error", "message": f"invalid db_name: {db_name!r}"}

    try:
        import pg8000.native
    except ImportError:
        return {"status": "error", "message": "pg8000 not installed"}

    try:
        conn = pg8000.native.Connection(
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database="postgres",
        )
        conn.autocommit = True
        rows = list(conn.run("SELECT 1 FROM pg_database WHERE datname = :n", n=db_name))
        if rows:
            conn.close()
            return {"status": "ok", "message": f"database {db_name!r} already exists"}
        conn.run(f'CREATE DATABASE "{db_name}"')
        conn.close()
        return {"status": "ok", "message": f"created database {db_name!r}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
