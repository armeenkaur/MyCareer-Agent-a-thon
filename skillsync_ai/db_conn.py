"""DB connection wrappers for SQLite and MySQL."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence

from .db_compat import DictRow, adapt_sql, as_row

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover
    pymysql = None  # type: ignore[assignment]
    DictCursor = None  # type: ignore[misc, assignment]


class CompatConnection:
    """Minimal connection API matching how backend code uses sqlite3."""

    def __init__(self, engine: str, raw: Any) -> None:
        self.engine = engine
        self._raw = raw
        self._cursor: Any = None
        if engine == "sqlite":
            raw.row_factory = sqlite3.Row

    def _ensure_cursor(self) -> Any:
        if self._cursor is None:
            if self.engine == "mysql":
                self._cursor = self._raw.cursor(DictCursor)
            else:
                self._cursor = self._raw.cursor()
        return self._cursor

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> CompatConnection:
        cur = self._ensure_cursor()
        adapted = adapt_sql(sql, self.engine)
        if params is None:
            cur.execute(adapted)
        else:
            cur.execute(adapted, tuple(params))
        return self

    def executescript(self, script: str) -> CompatConnection:
        if self.engine == "sqlite":
            self._raw.executescript(script)
            self._cursor = None
            return self
        # MySQL: run statements one by one (no multi-PRAGMA scripts).
        parts = [p.strip() for p in script.split(";") if p.strip()]
        for part in parts:
            self.execute(part)
        return self

    def fetchone(self) -> DictRow | None:
        cur = self._ensure_cursor()
        row = cur.fetchone()
        if row is None:
            return None
        if self.engine == "sqlite":
            return as_row(dict(row))
        return as_row(row)

    def fetchall(self) -> list[DictRow]:
        cur = self._ensure_cursor()
        rows = cur.fetchall()
        if self.engine == "sqlite":
            return [as_row(dict(r)) for r in rows]
        return [as_row(r) for r in rows]

    def __iter__(self):
        """sqlite3 parity: `for row in connection.execute(...)`."""
        return iter(self.fetchall())

    @property
    def lastrowid(self) -> int:
        cur = self._ensure_cursor()
        return int(cur.lastrowid or 0)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        try:
            if self._cursor is not None:
                self._cursor.close()
        finally:
            self._cursor = None
            self._raw.close()

    def __enter__(self) -> CompatConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect_sqlite(path: str) -> CompatConnection:
    raw = sqlite3.connect(path, timeout=30)
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA journal_mode = WAL")
    raw.execute("PRAGMA synchronous = NORMAL")
    return CompatConnection("sqlite", raw)


def connect_mysql(cfg: dict[str, Any]) -> CompatConnection:
    if pymysql is None:
        raise RuntimeError("pymysql is required for MySQL. pip install pymysql")
    raw = pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port") or 3306),
        user=cfg["user"],
        password=cfg.get("password") or "",
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=False,
        cursorclass=DictCursor,
    )
    return CompatConnection("mysql", raw)
