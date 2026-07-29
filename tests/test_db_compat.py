from __future__ import annotations

import unittest

from skillsync_ai.db_compat import adapt_sql, qmark_to_percent
from skillsync_ai.database import mysql_config_from_env


class DbCompatTest(unittest.TestCase):
    def test_qmark_skips_string_literals(self) -> None:
        sql = "SELECT '?' AS q WHERE code=?"
        self.assertEqual(qmark_to_percent(sql), "SELECT '?' AS q WHERE code=%s")

    def test_adapt_insert_or_ignore_and_conflict(self) -> None:
        sql = (
            "INSERT OR IGNORE INTO phases(phase, status) VALUES (?, 'closed');"
            "INSERT INTO employees(employee_code,name) VALUES(?,?) "
            "ON CONFLICT(employee_code) DO UPDATE SET name=excluded.name"
        )
        out = adapt_sql(sql, "mysql")
        self.assertIn("INSERT IGNORE INTO", out)
        self.assertIn("ON DUPLICATE KEY UPDATE", out)
        self.assertIn("VALUES(name)", out)
        self.assertIn("%s", out)
        self.assertNotIn("?", out)

    def test_sqlite_passthrough(self) -> None:
        sql = "INSERT OR IGNORE INTO phases(phase) VALUES (?)"
        self.assertEqual(adapt_sql(sql, "sqlite"), sql)

    def test_mysql_config_from_env(self) -> None:
        import os

        prev = {k: os.environ.get(k) for k in (
            "MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "DATABASE_URL"
        )}
        try:
            for k in prev:
                os.environ.pop(k, None)
            self.assertIsNone(mysql_config_from_env())
            os.environ["MYSQL_HOST"] = "db"
            os.environ["MYSQL_USER"] = "u"
            os.environ["MYSQL_DATABASE"] = "mycareer"
            os.environ["MYSQL_PASSWORD"] = "p"
            cfg = mysql_config_from_env()
            assert cfg is not None
            self.assertEqual(cfg["host"], "db")
            self.assertEqual(cfg["database"], "mycareer")
            self.assertEqual(cfg["user"], "u")
            self.assertEqual(cfg["password"], "p")
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
