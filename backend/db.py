"""Thin PostgreSQL layer. Connects straight to Supabase's Postgres with psycopg (connection string in .env)."""
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None


def init_pool(url, max_size=5):
    global _pool
    if _pool is not None:
        _pool.close()
    # prepare_threshold=None -> works with Supabase's pooled (pgbouncer) connections
    # check= validates a connection before handing it out, so a database that went to sleep (Neon free) or a dropped connection
    # costs one reconnect instead of an error page. max_lifetime/max_idle recycle old connections.
    _pool = ConnectionPool(url, min_size=1, max_size=max_size, open=True, timeout=30, check=ConnectionPool.check_connection,
                           max_lifetime=1800, max_idle=240,
                           kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": True})


class _Runner:
    def __init__(self, conn):
        self.c = conn

    def q(self, sql, args=()):
        return self.c.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.c.execute(sql, args).fetchone()

    def run(self, sql, args=()):
        return self.c.execute(sql, args).rowcount


def q(sql, args=()):
    with _pool.connection() as c:
        return _Runner(c).q(sql, args)


def one(sql, args=()):
    with _pool.connection() as c:
        return _Runner(c).one(sql, args)


def run(sql, args=()):
    with _pool.connection() as c:
        return _Runner(c).run(sql, args)


@contextmanager
def tx():
    """with db.tx() as t: t.one(...); t.run(...)  -> all-or-nothing."""
    with _pool.connection() as c:
        with c.transaction():
            yield _Runner(c)


def apply_sql_file(path):
    with open(path, encoding="utf-8") as fh:
        sql = fh.read()
    with _pool.connection() as c:
        c.execute(sql)
