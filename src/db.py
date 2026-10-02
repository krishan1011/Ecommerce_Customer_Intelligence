from sqlalchemy import create_engine, text
from .config import DATABASE_URL


def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def check_connection() -> bool:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
