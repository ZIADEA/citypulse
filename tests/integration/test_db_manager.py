"""Intégration SQLite — init, migrations, auth (tmp_path, pas de réseau)."""
import pytest

from app.database import db_manager
from app.database.db_manager import get_connection, hash_password, verify_password, has_permission


def test_hash_password_verify_roundtrip():
    # Arrange
    h, salt = hash_password("secret123")
    # Act / Assert
    assert verify_password("secret123", h, salt)
    assert not verify_password("wrong", h, salt)


def test_db_memory_migrations_applied(db_memory):
    conn = get_connection()
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    conn.close()
    assert row["v"] is not None and row["v"] >= 1


def test_has_permission_admin(db_populated, monkeypatch):
    monkeypatch.setattr(db_manager, "DB_PATH", db_populated)
    conn = get_connection()
    uid = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
    conn.close()
    assert has_permission(uid, "clients", "write") is True
