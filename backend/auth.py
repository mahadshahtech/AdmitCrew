import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from database import get_connection


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


ROLES = {"admin", "counselor"}
TOKEN_ISSUER = "admitcrew"
_LOCAL_JWT_SECRET = "admitcrew-local-development-secret-do-not-use-in-production"
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_HASHER = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
_BEARER_SCHEME = HTTPBearer(auto_error=False)


def _configured_jwt_secret() -> str:
    configured_secret = os.getenv("ADMITCREW_JWT_SECRET")
    environment = os.getenv("ADMITCREW_ENV", "production").strip().casefold()
    if configured_secret:
        if len(configured_secret.encode("utf-8")) < 32:
            raise RuntimeError("ADMITCREW_JWT_SECRET must contain at least 32 bytes.")
        return configured_secret
    if environment in {"development", "dev", "test"}:
        return _LOCAL_JWT_SECRET
    raise RuntimeError("ADMITCREW_JWT_SECRET must be configured outside local development/test.")


JWT_SECRET = _configured_jwt_secret()


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def safe_staff_profile(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _log(conn, action: str, details: str):
    conn.execute(
        "INSERT INTO agent_logs (agent, action, details) VALUES ('auth', ?, ?)",
        (action, details),
    )


def _valid_password(password: str) -> bool:
    encoded = password.encode("utf-8")
    return len(encoded) >= 12 and len(encoded) <= 1024


def hash_password(password: str) -> str:
    if not _valid_password(password):
        raise ValueError("Password must be 12-1024 UTF-8 bytes long.")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password, password_hash)
    except Exception:
        return False


def authenticate_staff(email: str, password: str) -> dict | None:
    normalized_email = normalize_email(email)
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM staff_users WHERE email = ?",
        (normalized_email,),
    ).fetchone()
    conn.close()

    if row is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    password_matches = verify_password(password, row["password_hash"])
    if not password_matches or not row["is_active"]:
        return None

    conn = get_connection()
    _log(conn, "staff_login_succeeded", f"Staff ID: {row['id']}; role: {row['role']}")
    conn.commit()
    conn.close()
    return safe_staff_profile(row)


def create_access_token(staff: dict, expires_minutes: int | None = None) -> tuple[str, int]:
    lifetime = expires_minutes or int(os.getenv("ADMITCREW_ACCESS_TOKEN_MINUTES", "30"))
    if lifetime < 1 or lifetime > 1440:
        raise RuntimeError("ADMITCREW_ACCESS_TOKEN_MINUTES must be between 1 and 1440.")
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=lifetime)
    token = jwt.encode(
        {
            "sub": str(staff["id"]),
            "role": staff["role"],
            "iss": TOKEN_ISSUER,
            "iat": issued_at,
            "exp": expires_at,
            "type": "access",
            "jti": secrets.token_urlsafe(12),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return token, lifetime * 60


def _unauthorized(detail: str = "Authentication required."):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(_BEARER_SCHEME),
) -> dict:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "role", "iss", "iat", "exp", "type"]},
        )
        if claims.get("type") != "access":
            raise jwt.InvalidTokenError("Wrong token type")
        staff_id = int(claims["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError, KeyError):
        raise _unauthorized("Invalid or expired access token.")

    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, email, role, is_active, created_at, updated_at FROM staff_users WHERE id = ?",
        (staff_id,),
    ).fetchone()
    conn.close()
    if row is None or not row["is_active"] or row["role"] != claims["role"]:
        raise _unauthorized("Invalid or expired access token.")
    return safe_staff_profile(row)


def require_roles(*allowed_roles: str):
    def check_role(staff: dict = Depends(get_current_staff)) -> dict:
        if staff["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return staff

    return check_role


require_staff = require_roles("admin", "counselor")
require_admin = require_roles("admin")


def list_staff_users() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, email, role, is_active, created_at, updated_at FROM staff_users ORDER BY id"
    ).fetchall()
    conn.close()
    return [safe_staff_profile(row) for row in rows]


def create_staff_user(
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    actor_id: int | None,
) -> dict:
    clean_name = name.strip()
    normalized_email = normalize_email(email)
    if not clean_name:
        return {"error": "name_required"}
    if len(normalized_email) > 254 or not _EMAIL_PATTERN.fullmatch(normalized_email):
        return {"error": "invalid_email"}
    if role not in ROLES:
        return {"error": "invalid_role"}
    try:
        password_hash = hash_password(password)
    except ValueError:
        return {"error": "invalid_password"}

    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """
            INSERT INTO staff_users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (clean_name, normalized_email, password_hash, role),
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return {"error": "email_already_exists"}

    staff_id = cursor.lastrowid
    _log(conn, "staff_account_created", f"Actor ID: {actor_id}; Staff ID: {staff_id}; role: {role}")
    row = conn.execute(
        "SELECT id, name, email, role, is_active, created_at, updated_at FROM staff_users WHERE id = ?",
        (staff_id,),
    ).fetchone()
    conn.commit()
    conn.close()
    return {"staff": safe_staff_profile(row)}


def update_staff_user(staff_id: int, updates: dict, actor_id: int) -> dict:
    allowed_fields = {"name", "role", "is_active", "password"}
    if not updates or not set(updates).issubset(allowed_fields):
        return {"error": "no_valid_changes"}

    clean_name = updates.get("name")
    if "name" in updates and (clean_name is None or not clean_name.strip()):
        return {"error": "name_required"}
    if clean_name is not None:
        clean_name = clean_name.strip()

    role = updates.get("role")
    if role is not None and role not in ROLES:
        return {"error": "invalid_role"}

    active = updates.get("is_active")
    if active is not None and not isinstance(active, bool):
        return {"error": "invalid_active_state"}

    password_hash = None
    if "password" in updates:
        try:
            password_hash = hash_password(updates["password"] or "")
        except ValueError:
            return {"error": "invalid_password"}

    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    current = conn.execute(
        "SELECT id, name, role, is_active FROM staff_users WHERE id = ?",
        (staff_id,),
    ).fetchone()
    if current is None:
        conn.close()
        return {"error": "staff_not_found"}

    new_role = role if role is not None else current["role"]
    new_active = bool(active) if active is not None else bool(current["is_active"])
    removing_admin = (
        current["role"] == "admin"
        and current["is_active"]
        and (new_role != "admin" or not new_active)
    )
    if removing_admin:
        other_active_admins = conn.execute(
            "SELECT COUNT(*) FROM staff_users WHERE role = 'admin' AND is_active = 1 AND id <> ?",
            (staff_id,),
        ).fetchone()[0]
        if other_active_admins == 0:
            conn.close()
            return {"error": "last_active_admin"}

    conn.execute(
        """
        UPDATE staff_users
        SET name = ?, role = ?, is_active = ?,
            password_hash = COALESCE(?, password_hash),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            clean_name if clean_name is not None else current["name"],
            new_role,
            int(new_active),
            password_hash,
            staff_id,
        ),
    )

    if new_role != current["role"]:
        _log(conn, "staff_role_changed", f"Actor ID: {actor_id}; Staff ID: {staff_id}; role: {new_role}")
    if new_active != bool(current["is_active"]):
        action = "staff_account_activated" if new_active else "staff_account_deactivated"
        _log(conn, action, f"Actor ID: {actor_id}; Staff ID: {staff_id}")
    if password_hash is not None:
        _log(conn, "staff_password_reset", f"Actor ID: {actor_id}; Staff ID: {staff_id}")

    row = conn.execute(
        "SELECT id, name, email, role, is_active, created_at, updated_at FROM staff_users WHERE id = ?",
        (staff_id,),
    ).fetchone()
    conn.commit()
    conn.close()
    return {"staff": safe_staff_profile(row)}


def bootstrap_admin(name: str, email: str, password: str) -> dict:
    clean_name = name.strip()
    normalized_email = normalize_email(email)
    if not clean_name:
        return {"error": "name_required"}
    if len(normalized_email) > 254 or not _EMAIL_PATTERN.fullmatch(normalized_email):
        return {"error": "invalid_email"}
    try:
        password_hash = hash_password(password)
    except ValueError:
        return {"error": "invalid_password"}

    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute(
        "SELECT id, role, is_active FROM staff_users WHERE email = ?",
        (normalized_email,),
    ).fetchone()
    if existing is not None:
        conn.close()
        if existing["role"] != "admin":
            return {"error": "email_belongs_to_non_admin"}
        return {
            "created": False,
            "staff_id": existing["id"],
            "is_active": bool(existing["is_active"]),
        }

    active_admin_count = conn.execute(
        "SELECT COUNT(*) FROM staff_users WHERE role = 'admin' AND is_active = 1"
    ).fetchone()[0]
    if active_admin_count:
        conn.close()
        return {"error": "active_admin_already_exists"}

    cursor = conn.execute(
        "INSERT INTO staff_users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        (clean_name, normalized_email, password_hash),
    )
    staff_id = cursor.lastrowid
    _log(conn, "staff_admin_bootstrapped", f"Staff ID: {staff_id}")
    conn.commit()
    conn.close()
    return {"created": True, "staff_id": staff_id, "is_active": True}
