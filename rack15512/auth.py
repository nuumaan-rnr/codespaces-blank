"""Username/password auth + role-based access for the internal app.

No external auth dependency: PBKDF2-HMAC password hashing (stdlib hashlib)
plus a filesystem-backed user directory, the same JSON-per-store pattern as
MasterStore (rack15512.master_store) and ProjectStore (rack15512.project).

    users/
      users.json      # {username: {name, password_hash, salt, role, created}}

Two roles:
    admin  - everything: section masters + the User Access page + projects
    user   - projects dashboard only (can still SELECT an existing master
             when building a configuration - only the master LIBRARY
             management page is admin-only)

Session state (st.session_state["user"]) holds the logged-in user for the
lifetime of the browser session; there is no persistent login cookie, so a
manual page refresh requires signing in again. Acceptable for a small
internal tool (max 2-3 users) and keeps this dependency-free; revisit if
that becomes annoying in practice.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

ROLES = ("admin", "user")


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), 200_000)
    return digest.hex(), salt


def _verify_password(password: str, digest_hex: str, salt: str) -> bool:
    check, _ = _hash_password(password, salt)
    return secrets.compare_digest(check, digest_hex)


@dataclass
class User:
    username: str
    name: str
    role: str = "user"
    password_hash: str = ""
    salt: str = ""
    created: str = field(default_factory=_now)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "User":
        known = {"username", "name", "role", "password_hash", "salt", "created"}
        return User(**{k: v for k, v in d.items() if k in known})


class UserStore:
    """Filesystem-backed user directory (same pattern as MasterStore/ProjectStore)."""

    def __init__(self, root: str = "users"):
        self.root = root
        os.makedirs(self.root, exist_ok=True)
        self._file = os.path.join(self.root, "users.json")

    def _load_all(self) -> Dict[str, dict]:
        if not os.path.isfile(self._file):
            return {}
        try:
            with open(self._file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_all(self, data: Dict[str, dict]) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_users(self) -> List[User]:
        return sorted((User.from_dict(d) for d in self._load_all().values()),
                     key=lambda u: u.username)

    def get(self, username: str) -> Optional[User]:
        d = self._load_all().get((username or "").strip().lower())
        return User.from_dict(d) if d else None

    def exists(self, username: str) -> bool:
        return (username or "").strip().lower() in self._load_all()

    def add_user(self, username: str, name: str, password: str,
                role: str = "user") -> User:
        username = (username or "").strip().lower()
        if not username or not password:
            raise ValueError("username and password are required")
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        data = self._load_all()
        digest, salt = _hash_password(password)
        u = User(username=username, name=(name or "").strip() or username,
                 role=role, password_hash=digest, salt=salt)
        data[username] = u.to_dict()
        self._save_all(data)
        return u

    def set_role(self, username: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        data = self._load_all()
        username = (username or "").strip().lower()
        if username not in data:
            raise KeyError(username)
        data[username]["role"] = role
        self._save_all(data)

    def reset_password(self, username: str, new_password: str) -> None:
        if not new_password:
            raise ValueError("new_password is required")
        data = self._load_all()
        username = (username or "").strip().lower()
        if username not in data:
            raise KeyError(username)
        digest, salt = _hash_password(new_password)
        data[username]["password_hash"] = digest
        data[username]["salt"] = salt
        self._save_all(data)

    def delete_user(self, username: str) -> None:
        data = self._load_all()
        data.pop((username or "").strip().lower(), None)
        self._save_all(data)

    def verify_login(self, username: str, password: str) -> Optional[User]:
        u = self.get(username)
        if u is None or not u.password_hash:
            return None
        return u if _verify_password(password, u.password_hash, u.salt) else None

    def admin_count(self) -> int:
        return sum(1 for u in self.list_users() if u.is_admin)

    def bootstrap_admin_from_env(self) -> None:
        """On first run (no users at all), seed one admin from the
        ADMIN_USERNAME/ADMIN_PASSWORD env vars (set these when deploying),
        or a random one-time password printed to the server log if
        ADMIN_PASSWORD isn't set."""
        if self._load_all():
            return
        username = os.environ.get("ADMIN_USERNAME", "admin").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD")
        generated = False
        if not password:
            password = secrets.token_urlsafe(12)
            generated = True
        self.add_user(username, "Administrator", password, role="admin")
        if generated:
            print(f"[auth] No users existed - created initial admin "
                 f"'{username}' with a generated one-time password: "
                 f"{password}\n[auth] Set ADMIN_USERNAME / ADMIN_PASSWORD "
                 f"env vars on future deploys to control this, or sign in "
                 f"now and change it from the User Access page.", flush=True)
