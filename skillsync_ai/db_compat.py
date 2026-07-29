"""SQL dialect helpers: SQLite ↔ MySQL for this codebase's query style."""

from __future__ import annotations

import re
from typing import Any


_INSERT_OR_IGNORE = re.compile(r"(?i)\bINSERT\s+OR\s+IGNORE\s+INTO\b")
_ON_CONFLICT = re.compile(r"(?is)\bON CONFLICT\s*\([^)]+\)\s*DO UPDATE SET\b")
_EXCLUDED = re.compile(r"(?i)\bexcluded\.(\w+)\b")
_AUTOINCREMENT = re.compile(r"(?i)\bINTEGER PRIMARY KEY AUTOINCREMENT\b")
_BEGIN_IMMEDIATE = re.compile(r"(?i)\bBEGIN IMMEDIATE\b")


def adapt_sql(sql: str, engine: str) -> str:
    """Translate SQLite-flavoured SQL used in this app into MySQL when needed."""
    if engine != "mysql":
        return sql
    out = _INSERT_OR_IGNORE.sub("INSERT IGNORE INTO", sql)
    out = _ON_CONFLICT.sub("ON DUPLICATE KEY UPDATE", out)
    out = _EXCLUDED.sub(r"VALUES(\1)", out)
    out = _AUTOINCREMENT.sub("INT AUTO_INCREMENT PRIMARY KEY", out)
    out = _BEGIN_IMMEDIATE.sub("START TRANSACTION", out)
    out = qmark_to_percent(out)
    return out


def qmark_to_percent(sql: str) -> str:
    """Replace unbound ? placeholders with %s (MySQL/PyMySQL)."""
    out: list[str] = []
    i = 0
    in_single = False
    in_double = False
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            # handle escaped '' inside single quotes
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue
        if ch == "?" and not in_single and not in_double:
            out.append("%s")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class DictRow(dict):
    """dict that also supports integer index access like sqlite3.Row."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def as_row(mapping: Any) -> DictRow | None:
    if mapping is None:
        return None
    if isinstance(mapping, DictRow):
        return mapping
    return DictRow(mapping)
