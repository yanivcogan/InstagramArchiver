import json
import logging
import os
import threading
from contextlib import contextmanager
from typing import Literal

import mysql
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
USER = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")
DB_HOST = os.getenv("DB_HOST")

logger = logging.getLogger(__name__)

cnx_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="connections", pool_size=20,
    pool_reset_session=True,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=USER,
    password=PASSWORD
)


class DbError(Exception):
    """Raised when a database query fails."""
    pass


# Thread-local storage for transaction batching — each thread gets its own connection.
_local = threading.local()


@contextmanager
def transaction_batch():
    """
    Context manager for batching multiple queries into a single transaction.
    Commits only once at the end instead of after every query.

    Usage:
        with db.transaction_batch():
            db.execute_query(...)  # No commit
            db.execute_query(...)  # No commit
            db.execute_query(...)  # No commit
        # Commits here when exiting the context

    This can provide 5-10x speedup for bulk insert operations.
    Nested calls reuse the same connection (inner batch is a no-op boundary).
    Thread-safe: each thread maintains its own connection via threading.local().
    """
    if getattr(_local, "connection", None) is not None:
        # Already in a batch on this thread — nested call, just yield through.
        yield
        return

    cnx = cnx_pool.get_connection()
    cnx.autocommit = False
    _local.connection = cnx
    try:
        yield
        cnx.commit()
    except Exception:
        cnx.rollback()
        raise
    finally:
        _local.connection = None
        cnx.close()


def execute_query(query, args, return_type: Literal["single_row", "rows", "id", "none", "debug"] = "rows"):
    if getattr(_local, "connection", None) is not None:
        # Reuse the open transaction connection on this thread.
        return _execute_query_on_connection(_local.connection, query, args, return_type, commit=False)

    cnx = cnx_pool.get_connection()
    try:
        return _execute_query_on_connection(cnx, query, args, return_type, commit=True)
    finally:
        cnx.close()


def _execute_query_on_connection(cnx, query, args, return_type, commit=True):
    """Internal function to execute query on a given connection."""
    cursor = cnx.cursor(buffered=True)
    try:
        cursor.execute(query, args)
        if return_type == "single_row":
            return select_result(cursor)
        if return_type == "rows":
            return select_results(cursor)
        if return_type == "debug":
            return cursor.statement
        if return_type == "id":
            last_row_id = cursor.lastrowid
            if not last_row_id:
                return False
            return last_row_id
        if return_type == "none":
            return True
        return None
    except mysql.connector.Error as err:
        logger.error("DB query failed: %s\nQuery: %s\nArgs: %s", err, query, json.dumps(args, default=str))
        raise DbError(str(err)) from err
    finally:
        cursor.close()
        if commit:
            cnx.commit()


def select_results(cursor):
    data = cursor.fetchall()
    columns = [i[0] for i in cursor.description]
    if not data:
        return []
    results = [{columns[i]: row[i] for i in range(len(columns))} for row in data]
    return results


def select_result(cursor):
    data = cursor.fetchone()
    columns = [i[0] for i in cursor.description]
    if not data:
        return None
    results = {columns[i]: data[i] for i in range(len(columns))}
    return results
