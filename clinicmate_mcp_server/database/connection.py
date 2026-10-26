# connection.py
# Gives database connections: a shared pool for the server, a single one for scripts.
import atexit
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config.settings import DATABASE_URL

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Create the pool on first use and reuse it after that."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def get_connection():
    """For repositories. Usage: with get_connection() as conn: conn.execute(...)"""
    return get_pool().connection()


def connect_once() -> psycopg.Connection:
    """For one-time scripts (migrations, seed). Closed after the with-block."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def get_pool() -> ConnectionPool:
    """Create the pool on first use and reuse it after that."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        atexit.register(_pool.close)  # close cleanly when the program exits
    return _pool