"""User store / auth tests (rack15512.auth)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.auth import UserStore


def _store(tmp_path):
    return UserStore(str(tmp_path / "users"))


def test_add_and_verify_login(tmp_path):
    us = _store(tmp_path)
    us.add_user("Alice", "Alice A.", "correct-horse", role="admin")
    u = us.verify_login("alice", "correct-horse")   # username case/space folded
    assert u is not None and u.username == "alice" and u.is_admin
    assert us.verify_login("alice", "wrong-password") is None
    assert us.verify_login("nobody", "x") is None


def test_password_hash_never_stored_in_plaintext(tmp_path):
    us = _store(tmp_path)
    us.add_user("bob", "Bob", "s3cret")
    raw = open(os.path.join(us.root, "users.json"), encoding="utf-8").read()
    assert "s3cret" not in raw


def test_roles_and_reset_password(tmp_path):
    us = _store(tmp_path)
    us.add_user("carol", "Carol", "pw1", role="user")
    assert us.get("carol").role == "user"
    us.set_role("carol", "admin")
    assert us.get("carol").is_admin
    with pytest.raises(ValueError):
        us.set_role("carol", "superuser")
    us.reset_password("carol", "pw2")
    assert us.verify_login("carol", "pw1") is None
    assert us.verify_login("carol", "pw2") is not None


def test_delete_user(tmp_path):
    us = _store(tmp_path)
    us.add_user("dan", "Dan", "pw")
    assert us.exists("dan")
    us.delete_user("dan")
    assert not us.exists("dan")


def test_admin_count(tmp_path):
    us = _store(tmp_path)
    us.add_user("a1", "A1", "pw", role="admin")
    us.add_user("a2", "A2", "pw", role="admin")
    us.add_user("u1", "U1", "pw", role="user")
    assert us.admin_count() == 2


def test_bootstrap_admin_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "boss")
    monkeypatch.setenv("ADMIN_PASSWORD", "top-secret")
    us = _store(tmp_path)
    us.bootstrap_admin_from_env()
    u = us.verify_login("boss", "top-secret")
    assert u is not None and u.is_admin
    # second call is a no-op once users exist
    us.bootstrap_admin_from_env()
    assert len(us.list_users()) == 1


def test_bootstrap_admin_generated_password(tmp_path, capsys):
    us = _store(tmp_path)
    us.bootstrap_admin_from_env()
    assert us.admin_count() == 1
    out = capsys.readouterr().out
    assert "generated one-time password" in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
