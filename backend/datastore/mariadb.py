"""
MariaDB datastore implementation for production.
Requires DATABASE_URL (e.g. mysql://user:pass@host:3306/dbname).
Uses PyMySQL for sync connections.
"""

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import pymysql
from pymysql.cursors import DictCursor

from backend.datastore.base import (
    DEFAULT_PIPELINE_EDGES,
    DEFAULT_PIPELINE_ID,
    DEFAULT_PIPELINE_NODES,
    Datastore,
    McpApiKeyRecord,
    PipelineDefinition,
    Session,
    Study,
    ToolInvocationLogEntry,
    User,
    UserStudy,
)
from backend.mcp_key_hash import hash_mcp_api_secret, normalize_allowed_study_ids
from backend.passwords import PENDING_GOOGLE_PREFIX


def _parse_database_url(url: str) -> dict:
    """Parse DATABASE_URL into pymysql connection kwargs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("mysql", "mysql+pymysql"):
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    path = (parsed.path or "/").lstrip("/")
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "database": path or None,
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }


def _ensure_tables(conn: pymysql.Connection) -> None:
    """Create users and sessions tables if they do not exist."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                google_id VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                updated_at DATETIME(6) NOT NULL
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                expires_at DATETIME(6) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS studies (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at DATETIME(6) NOT NULL,
                updated_at DATETIME(6) NOT NULL
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS study_config (
                study_id VARCHAR(36) NOT NULL,
                config_key VARCHAR(255) NOT NULL,
                config_value TEXT NOT NULL,
                PRIMARY KEY (study_id, config_key),
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_study (
                user_id VARCHAR(36) NOT NULL,
                study_id VARCHAR(36) NOT NULL,
                role VARCHAR(32) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                PRIMARY KEY (user_id, study_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS study_box_config (
                study_id VARCHAR(36) PRIMARY KEY,
                config_json MEDIUMTEXT NOT NULL,
                updated_at DATETIME(6) NOT NULL,
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_response_ids (
                study_id VARCHAR(36) NOT NULL,
                response_id VARCHAR(255) NOT NULL,
                PRIMARY KEY (study_id, response_id),
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id VARCHAR(36) PRIMARY KEY,
                study_id VARCHAR(36) NOT NULL,
                external_id VARCHAR(32) NOT NULL,
                status VARCHAR(32) NOT NULL,
                current_step VARCHAR(255) NOT NULL DEFAULT '',
                progress_percent INT NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                started_at DATETIME(6) NOT NULL,
                finished_at DATETIME(6) NULL,
                created_at DATETIME(6) NOT NULL,
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS run_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id VARCHAR(36) NOT NULL,
                level VARCHAR(32) NOT NULL,
                message TEXT NOT NULL,
                step VARCHAR(255) NOT NULL DEFAULT '',
                created_at DATETIME(6) NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS study_pipelines (
                study_id VARCHAR(36) NOT NULL,
                pipeline_id VARCHAR(36) NOT NULL,
                name VARCHAR(255) NOT NULL,
                is_default TINYINT(1) NOT NULL DEFAULT 0,
                definition_json MEDIUMTEXT NOT NULL,
                created_at DATETIME(6) NOT NULL,
                updated_at DATETIME(6) NOT NULL,
                PRIMARY KEY (study_id, pipeline_id),
                FOREIGN KEY (study_id) REFERENCES studies(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mcp_api_keys (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                key_prefix VARCHAR(64) NOT NULL,
                key_hash VARCHAR(64) NOT NULL,
                scopes_json TEXT NOT NULL,
                allowed_study_ids_json TEXT NOT NULL DEFAULT '[]',
                owner_user_id VARCHAR(36) NULL,
                created_at DATETIME(6) NOT NULL,
                revoked_at DATETIME(6) NULL,
                last_used_at DATETIME(6) NULL,
                expires_at DATETIME(6) NULL,
                UNIQUE KEY uk_mcp_key_hash (key_hash),
                FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_invocation_logs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                created_at DATETIME(6) NOT NULL,
                api_key_id VARCHAR(36) NULL,
                key_source VARCHAR(16) NOT NULL DEFAULT 'database',
                key_prefix_display VARCHAR(64) NOT NULL DEFAULT '',
                tool_name VARCHAR(128) NOT NULL,
                study_id VARCHAR(36) NULL,
                status_code INT NOT NULL,
                duration_ms INT NOT NULL,
                error_detail VARCHAR(512) NULL,
                INDEX idx_til_created (created_at),
                INDEX idx_til_key (api_key_id),
                INDEX idx_til_tool (tool_name)
            )
        """
        )
        _migrate_schema(conn)
        conn.commit()


def _migrate_schema(conn: pymysql.Connection) -> None:
    """Add is_superuser column if missing; upgrade legacy viewer study roles to editor (staff)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'is_superuser'
            """
        )
        row = cur.fetchone()
        if row and row.get("c", 0) == 0:
            cur.execute(
                "ALTER TABLE users ADD COLUMN is_superuser TINYINT(1) NOT NULL DEFAULT 0"
            )
        cur.execute("UPDATE user_study SET role = %s WHERE role = %s", ("editor", "viewer"))
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mcp_api_keys' AND COLUMN_NAME = 'expires_at'
            """
        )
        row_mcp = cur.fetchone()
        if row_mcp and row_mcp.get("c", 0) == 0:
            cur.execute(
                "ALTER TABLE mcp_api_keys ADD COLUMN expires_at DATETIME(6) NULL AFTER last_used_at"
            )
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mcp_api_keys' AND COLUMN_NAME = 'allowed_study_ids_json'
            """
        )
        row_as = cur.fetchone()
        if row_as and row_as.get("c", 0) == 0:
            cur.execute(
                "ALTER TABLE mcp_api_keys ADD COLUMN allowed_study_ids_json TEXT NOT NULL DEFAULT '[]' AFTER scopes_json"
            )
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'password_hash'
            """
        )
        row_ph = cur.fetchone()
        if row_ph and row_ph.get("c", 0) == 0:
            cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL")
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'tool_api_data_proxy_enabled'
            """
        )
        row_tdp = cur.fetchone()
        if row_tdp and row_tdp.get("c", 0) == 0:
            cur.execute(
                "ALTER TABLE users ADD COLUMN tool_api_data_proxy_enabled TINYINT(1) NOT NULL DEFAULT 1"
            )
    conn.commit()


def _naive_to_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC tzinfo."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_user(row: dict) -> User:
    """Convert DB row to User. Assume datetime is naive UTC."""
    su = row.get("is_superuser")
    if su is None:
        is_superuser = False
    else:
        is_superuser = bool(su)
    ph = row.get("password_hash")
    tdp = row.get("tool_api_data_proxy_enabled")
    tool_api_proxy = True if tdp is None else bool(tdp)
    return User(
        id=row["id"],
        google_id=row["google_id"],
        email=row["email"] or "",
        name=row["name"] or "",
        created_at=_naive_to_utc(row["created_at"]),
        updated_at=_naive_to_utc(row["updated_at"]),
        is_superuser=is_superuser,
        tool_api_data_proxy_enabled=tool_api_proxy,
        password_hash=ph if ph else None,
    )


def _row_to_session(row: dict) -> Session:
    """Convert DB row to Session."""
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        expires_at=_naive_to_utc(row["expires_at"]),
        created_at=_naive_to_utc(row["created_at"]),
    )


def _row_to_study(row: dict) -> Study:
    return Study(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        created_at=_naive_to_utc(row["created_at"]),
        updated_at=_naive_to_utc(row["updated_at"]),
    )


class MariaDBDatastore(Datastore):
    """MariaDB implementation: sessions and users in DB tables."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn_params = _parse_database_url(database_url)
        conn = pymysql.connect(**self._conn_params)
        try:
            _ensure_tables(conn)
        finally:
            conn.close()

    def _connection(self) -> pymysql.Connection:
        """Return a new connection (caller should close)."""
        return pymysql.connect(**self._conn_params)

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, expires_at, created_at FROM sessions WHERE id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
            if not row:
                return None
            exp = row["expires_at"]
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= _naive_to_utc(row["expires_at"]):
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                    conn.commit()
                return None
            return _row_to_session(row)
        finally:
            conn.close()

    def create_session(self, user_id: str, session_id: str, expires_at: datetime) -> None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                    (session_id, user_id, expires_at, datetime.now(timezone.utc)),
                )
                conn.commit()
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                conn.commit()
        finally:
            conn.close()

    def expire_old_sessions(self) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE expires_at < %s", (datetime.now(timezone.utc),)
                )
                conn.commit()
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, google_id, email, name, created_at, updated_at, is_superuser, password_hash, tool_api_data_proxy_enabled FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, google_id, email, name, created_at, updated_at, is_superuser, password_hash, tool_api_data_proxy_enabled FROM users WHERE google_id = %s",
                    (google_id,),
                )
                row = cur.fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()

    def create_or_update_user(self, google_id: str, email: str, name: str) -> User:
        now = datetime.now(timezone.utc)
        existing = self.get_user_by_google_id(google_id)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                if existing:
                    cur.execute(
                        "UPDATE users SET email = %s, name = %s, updated_at = %s WHERE id = %s",
                        (email, name, now, existing.id),
                    )
                    conn.commit()
                    return User(
                        id=existing.id,
                        google_id=google_id,
                        email=email,
                        name=name,
                        created_at=existing.created_at,
                        updated_at=now,
                        is_superuser=existing.is_superuser,
                        tool_api_data_proxy_enabled=existing.tool_api_data_proxy_enabled,
                        password_hash=existing.password_hash,
                    )
                user_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO users (id, google_id, email, name, created_at, updated_at, is_superuser, password_hash) VALUES (%s, %s, %s, %s, %s, %s, 0, NULL)",
                    (user_id, google_id, email, name, now, now),
                )
                conn.commit()
                return User(
                    id=user_id,
                    google_id=google_id,
                    email=email,
                    name=name,
                    created_at=now,
                    updated_at=now,
                    is_superuser=False,
                    tool_api_data_proxy_enabled=True,
                    password_hash=None,
                )
        finally:
            conn.close()

    def list_users(self) -> list[User]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, google_id, email, name, created_at, updated_at, is_superuser, password_hash, tool_api_data_proxy_enabled FROM users"
                )
                rows = cur.fetchall()
            return [_row_to_user(r) for r in rows]
        finally:
            conn.close()

    def list_studies_for_user(self, user_id: str) -> list[tuple[Study, str]]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT s.id, s.name, s.description, s.created_at, s.updated_at, us.role
                       FROM studies s
                       INNER JOIN user_study us ON us.study_id = s.id
                       WHERE us.user_id = %s
                       ORDER BY s.name, s.id""",
                    (user_id,),
                )
                rows = cur.fetchall()
            return [
                (_row_to_study({"id": r["id"], "name": r["name"], "description": r.get("description"), "created_at": r["created_at"], "updated_at": r["updated_at"]}), r["role"])
                for r in rows
            ]
        finally:
            conn.close()

    def list_all_studies(self) -> list[Study]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, created_at, updated_at FROM studies ORDER BY name, id"
                )
                rows = cur.fetchall()
            return [_row_to_study(r) for r in rows]
        finally:
            conn.close()

    def get_study(self, study_id: str) -> Optional[Study]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, created_at, updated_at FROM studies WHERE id = %s",
                    (study_id,),
                )
                row = cur.fetchone()
            return _row_to_study(row) if row else None
        finally:
            conn.close()

    def create_study(self, name: str, description: Optional[str] = None) -> Study:
        now = datetime.now(timezone.utc)
        study_id = str(uuid.uuid4())
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO studies (id, name, description, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                    (study_id, name, description, now, now),
                )
                conn.commit()
            return Study(id=study_id, name=name, description=description, created_at=now, updated_at=now)
        finally:
            conn.close()

    def update_study(
        self,
        study_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if name is None and description is None:
            return
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                if name is not None and description is not None:
                    cur.execute(
                        "UPDATE studies SET name = %s, description = %s, updated_at = %s WHERE id = %s",
                        (name, description, datetime.now(timezone.utc), study_id),
                    )
                elif name is not None:
                    cur.execute(
                        "UPDATE studies SET name = %s, updated_at = %s WHERE id = %s",
                        (name, datetime.now(timezone.utc), study_id),
                    )
                else:
                    cur.execute(
                        "UPDATE studies SET description = %s, updated_at = %s WHERE id = %s",
                        (description, datetime.now(timezone.utc), study_id),
                    )
                conn.commit()
        finally:
            conn.close()

    def delete_study(self, study_id: str) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_study WHERE study_id = %s", (study_id,))
                cur.execute("DELETE FROM study_config WHERE study_id = %s", (study_id,))
                cur.execute("DELETE FROM study_box_config WHERE study_id = %s", (study_id,))
                cur.execute("DELETE FROM study_pipelines WHERE study_id = %s", (study_id,))
                cur.execute("DELETE FROM processed_response_ids WHERE study_id = %s", (study_id,))
                cur.execute("DELETE FROM studies WHERE id = %s", (study_id,))
                conn.commit()
        finally:
            conn.close()

    def get_study_config(self, study_id: str) -> dict[str, str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT config_key, config_value FROM study_config WHERE study_id = %s",
                    (study_id,),
                )
                rows = cur.fetchall()
            return {r["config_key"]: (r["config_value"] or "") for r in rows}
        finally:
            conn.close()

    def set_study_config(self, study_id: str, config: dict[str, str]) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM study_config WHERE study_id = %s", (study_id,))
                for k, v in config.items():
                    cur.execute(
                        "INSERT INTO study_config (study_id, config_key, config_value) VALUES (%s, %s, %s)",
                        (study_id, k, str(v) if v is not None else ""),
                    )
                conn.commit()
        finally:
            conn.close()

    def get_study_box_config(self, study_id: str) -> Optional[str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT config_json FROM study_box_config WHERE study_id = %s",
                    (study_id,),
                )
                row = cur.fetchone()
            return row["config_json"] if row else None
        finally:
            conn.close()

    def set_study_box_config(self, study_id: str, config_json: str) -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO study_box_config (study_id, config_json, updated_at)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE config_json = %s, updated_at = %s""",
                    (study_id, config_json, now, config_json, now),
                )
                conn.commit()
        finally:
            conn.close()

    def get_processed_ids(self, study_id: str) -> set[str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT response_id FROM processed_response_ids WHERE study_id = %s",
                    (study_id,),
                )
                rows = cur.fetchall()
            return {r["response_id"] for r in rows}
        finally:
            conn.close()

    def add_processed_ids(self, study_id: str, ids: set[str]) -> None:
        if not ids:
            return
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                for rid in ids:
                    cur.execute(
                        """INSERT IGNORE INTO processed_response_ids (study_id, response_id) VALUES (%s, %s)""",
                        (study_id, rid),
                    )
                conn.commit()
        finally:
            conn.close()

    def create_run(self, study_id: str, external_id: str) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO runs (id, study_id, external_id, status, current_step, progress_percent, message, started_at, finished_at, created_at)
                       VALUES (%s, %s, %s, 'running', '', 0, '', %s, NULL, %s)""",
                    (run_id, study_id, external_id, now, now),
                )
                conn.commit()
            return run_id
        finally:
            conn.close()

    def update_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        current_step: Optional[str] = None,
        progress_percent: Optional[int] = None,
        message: Optional[str] = None,
        finished_at: Optional[datetime] = None,
    ) -> None:
        updates = []
        params = []
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if current_step is not None:
            updates.append("current_step = %s")
            params.append(current_step)
        if progress_percent is not None:
            updates.append("progress_percent = %s")
            params.append(progress_percent)
        if message is not None:
            updates.append("message = %s")
            params.append(message)
        if finished_at is not None:
            updates.append("finished_at = %s")
            params.append(finished_at)
        if not updates:
            return
        params.append(run_id)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE runs SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
                conn.commit()
        finally:
            conn.close()

    def append_run_log(self, run_id: str, level: str, message: str, step: str = "") -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO run_logs (run_id, level, message, step, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (run_id, level, message or "", (step or "")[:255], now),
                )
                conn.commit()
        finally:
            conn.close()

    def get_user_study_role(self, user_id: str, study_id: str) -> Optional[str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role FROM user_study WHERE user_id = %s AND study_id = %s",
                    (user_id, study_id),
                )
                row = cur.fetchone()
            return row["role"] if row else None
        finally:
            conn.close()

    def set_user_study_role(self, user_id: str, study_id: str, role: str) -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO user_study (user_id, study_id, role, created_at)
                       VALUES (%s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE role = %s""",
                    (user_id, study_id, role, now, role),
                )
                conn.commit()
        finally:
            conn.close()

    def remove_user_study(self, user_id: str, study_id: str) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_study WHERE user_id = %s AND study_id = %s",
                    (user_id, study_id),
                )
                conn.commit()
        finally:
            conn.close()

    def list_study_users(self, study_id: str) -> list[tuple[User, str]]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT u.id, u.google_id, u.email, u.name, u.created_at, u.updated_at, u.is_superuser, u.password_hash, u.tool_api_data_proxy_enabled, us.role
                       FROM users u
                       INNER JOIN user_study us ON us.user_id = u.id
                       WHERE us.study_id = %s
                       ORDER BY u.email, u.id""",
                    (study_id,),
                )
                rows = cur.fetchall()
            return [(_row_to_user(r), r["role"]) for r in rows]
        finally:
            conn.close()

    def has_any_study(self) -> bool:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM studies LIMIT 1")
                return cur.fetchone() is not None
        finally:
            conn.close()

    def get_any_study(self) -> Optional[Study]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, created_at, updated_at FROM studies ORDER BY created_at LIMIT 1"
                )
                row = cur.fetchone()
            return _row_to_study(row) if row else None
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[User]:
        if not email or not email.strip():
            return None
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, google_id, email, name, created_at, updated_at, is_superuser, password_hash, tool_api_data_proxy_enabled FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s))",
                    (email,),
                )
                row = cur.fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()

    def set_user_superuser(self, user_id: str, is_superuser: bool) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_superuser = %s, updated_at = %s WHERE id = %s",
                    (1 if is_superuser else 0, datetime.now(timezone.utc), user_id),
                )
                conn.commit()
        finally:
            conn.close()

    def set_user_tool_api_data_proxy(self, user_id: str, enabled: bool) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET tool_api_data_proxy_enabled = %s, updated_at = %s WHERE id = %s",
                    (1 if enabled else 0, datetime.now(timezone.utc), user_id),
                )
                conn.commit()
        finally:
            conn.close()

    def create_provisioned_user(self, email: str, name: str, password_hash: Optional[str] = None) -> User:
        email = (email or "").strip()
        name = (name or "").strip() or "User"
        if not email:
            raise ValueError("email is required")
        if self.get_user_by_email(email):
            raise ValueError("A user with this email already exists.")
        now = datetime.now(timezone.utc)
        user_id = str(uuid.uuid4())
        pending_gid = f"{PENDING_GOOGLE_PREFIX}{uuid.uuid4()}"
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (id, google_id, email, name, created_at, updated_at, is_superuser, password_hash) VALUES (%s, %s, %s, %s, %s, %s, 0, %s)",
                    (user_id, pending_gid, email, name, now, now, password_hash),
                )
                conn.commit()
            return User(
                id=user_id,
                google_id=pending_gid,
                email=email,
                name=name,
                created_at=now,
                updated_at=now,
                is_superuser=False,
                tool_api_data_proxy_enabled=True,
                password_hash=password_hash,
            )
        finally:
            conn.close()

    def update_user_profile(self, user_id: str, *, email: Optional[str] = None, name: Optional[str] = None) -> None:
        u = self.get_user_by_id(user_id)
        if not u:
            raise ValueError("User not found.")
        new_email = (email.strip() if email is not None else u.email) or ""
        new_name = (name.strip() if name is not None else u.name) or ""
        if not new_email:
            raise ValueError("email is required")
        if email is not None:
            other = self.get_user_by_email(new_email)
            if other and other.id != user_id:
                raise ValueError("Another user already has this email.")
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET email = %s, name = %s, updated_at = %s WHERE id = %s",
                    (new_email, new_name, now, user_id),
                )
                conn.commit()
        finally:
            conn.close()

    def set_user_password_hash(self, user_id: str, password_hash: Optional[str]) -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                    (password_hash, now, user_id),
                )
                conn.commit()
        finally:
            conn.close()

    def link_oauth_to_pending_user(self, user_id: str, google_id: str, email: str, name: str) -> User:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET google_id = %s, email = %s, name = %s, updated_at = %s WHERE id = %s",
                    (google_id, email, name, now, user_id),
                )
                conn.commit()
        finally:
            conn.close()
        u = self.get_user_by_id(user_id)
        if not u:
            raise RuntimeError("User missing after OAuth link.")
        return u

    def list_all_studies(self) -> list[Study]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, created_at, updated_at FROM studies ORDER BY name, id"
                )
                rows = cur.fetchall()
            return [_row_to_study(r) for r in rows]
        finally:
            conn.close()

    def list_pipelines(self, study_id: str) -> list[PipelineDefinition]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pipeline_id, name, is_default, definition_json, created_at, updated_at FROM study_pipelines WHERE study_id = %s ORDER BY is_default DESC, name, pipeline_id",
                    (study_id,),
                )
                rows = cur.fetchall()
            if not rows:
                return [
                    PipelineDefinition(
                        id=DEFAULT_PIPELINE_ID,
                        name="Default",
                        is_default=True,
                        nodes=list(DEFAULT_PIPELINE_NODES),
                        edges=list(DEFAULT_PIPELINE_EDGES),
                        created_at=None,
                        updated_at=None,
                    )
                ]
            out = []
            for r in rows:
                defn = json.loads(r["definition_json"] or "{}")
                out.append(
                    PipelineDefinition(
                        id=r["pipeline_id"],
                        name=r["name"] or "Unnamed",
                        is_default=bool(r["is_default"]),
                        nodes=defn.get("nodes", []),
                        edges=defn.get("edges", []),
                        created_at=_naive_to_utc(r["created_at"]) if r.get("created_at") else None,
                        updated_at=_naive_to_utc(r["updated_at"]) if r.get("updated_at") else None,
                    )
                )
            return out
        finally:
            conn.close()

    def get_pipeline(self, study_id: str, pipeline_id: str) -> Optional[PipelineDefinition]:
        if pipeline_id == DEFAULT_PIPELINE_ID:
            pipelines = self.list_pipelines(study_id)
            if pipelines and pipelines[0].id == DEFAULT_PIPELINE_ID:
                return pipelines[0]
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pipeline_id, name, is_default, definition_json, created_at, updated_at FROM study_pipelines WHERE study_id = %s AND pipeline_id = %s",
                    (study_id, pipeline_id),
                )
                row = cur.fetchone()
            if not row:
                return None
            defn = json.loads(row["definition_json"] or "{}")
            return PipelineDefinition(
                id=row["pipeline_id"],
                name=row["name"] or "Unnamed",
                is_default=bool(row["is_default"]),
                nodes=defn.get("nodes", []),
                edges=defn.get("edges", []),
                created_at=_naive_to_utc(row["created_at"]) if row.get("created_at") else None,
                updated_at=_naive_to_utc(row["updated_at"]) if row.get("updated_at") else None,
            )
        finally:
            conn.close()

    def set_pipeline(
        self,
        study_id: str,
        pipeline_id: str,
        name: str,
        is_default: bool,
        nodes: list,
        edges: list,
    ) -> None:
        now = datetime.now(timezone.utc)
        definition_json = json.dumps({"nodes": nodes, "edges": edges})
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                if is_default:
                    cur.execute(
                        "UPDATE study_pipelines SET is_default = 0 WHERE study_id = %s",
                        (study_id,),
                    )
                cur.execute(
                    """INSERT INTO study_pipelines (study_id, pipeline_id, name, is_default, definition_json, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE name = %s, is_default = %s, definition_json = %s, updated_at = %s""",
                    (
                        study_id,
                        pipeline_id,
                        name,
                        1 if is_default else 0,
                        definition_json,
                        now,
                        now,
                        name,
                        1 if is_default else 0,
                        definition_json,
                        now,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

    def create_pipeline(
        self,
        study_id: str,
        name: str,
        is_default: bool,
        nodes: list,
        edges: list,
    ) -> str:
        pipeline_id = str(uuid.uuid4())
        self.set_pipeline(study_id, pipeline_id, name, is_default, nodes, edges)
        return pipeline_id

    def delete_pipeline(self, study_id: str, pipeline_id: str) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM study_pipelines WHERE study_id = %s AND pipeline_id = %s",
                    (study_id, pipeline_id),
                )
                conn.commit()
        finally:
            conn.close()

    def get_default_pipeline_id(self, study_id: str) -> Optional[str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pipeline_id FROM study_pipelines WHERE study_id = %s AND is_default = 1 LIMIT 1",
                    (study_id,),
                )
                row = cur.fetchone()
                if row:
                    return row["pipeline_id"]
                cur.execute("SELECT 1 FROM study_pipelines WHERE study_id = %s LIMIT 1", (study_id,))
                if cur.fetchone():
                    cur.execute(
                        "SELECT pipeline_id FROM study_pipelines WHERE study_id = %s ORDER BY updated_at DESC LIMIT 1",
                        (study_id,),
                    )
                    row = cur.fetchone()
                    return row["pipeline_id"] if row else None
                return DEFAULT_PIPELINE_ID
        finally:
            conn.close()

    def create_mcp_api_key(
        self,
        name: str,
        scopes: list[str],
        owner_user_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        allowed_study_ids: Optional[list[str]] = None,
    ) -> tuple[McpApiKeyRecord, str]:
        now = datetime.now(timezone.utc)
        key_id = str(uuid.uuid4())
        # Plaintext is returned to the caller once; only key_hash is persisted (see hash_mcp_api_secret).
        plain = secrets.token_urlsafe(32)
        key_prefix = (plain[:12] + "…") if len(plain) > 12 else plain + "…"
        scopes_json = json.dumps(list(scopes) if scopes else [])
        allowed_ids = normalize_allowed_study_ids(allowed_study_ids)
        allowed_json = json.dumps(allowed_ids)
        h = hash_mcp_api_secret(plain)
        exp = expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO mcp_api_keys
                       (id, name, key_prefix, key_hash, scopes_json, allowed_study_ids_json, owner_user_id, created_at, revoked_at, last_used_at, expires_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s)""",
                    (
                        key_id,
                        (name or "API key").strip() or "API key",
                        key_prefix,
                        h,
                        scopes_json,
                        allowed_json,
                        owner_user_id,
                        now,
                        exp,
                    ),
                )
                conn.commit()
        finally:
            conn.close()
        public = McpApiKeyRecord(
            id=key_id,
            name=(name or "API key").strip() or "API key",
            key_prefix=key_prefix,
            scopes=list(scopes) if scopes else [],
            allowed_study_ids=allowed_ids,
            owner_user_id=owner_user_id,
            created_at=now,
            revoked_at=None,
            last_used_at=None,
            expires_at=exp,
        )
        return public, plain

    def update_mcp_api_key(
        self,
        key_id: str,
        *,
        name: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        clear_expires_at: bool = False,
        allowed_study_ids: Optional[list[str]] = None,
        clear_allowed_study_ids: bool = False,
        owner_user_id: Optional[str] = None,
    ) -> None:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                if name is not None:
                    cur.execute(
                        "UPDATE mcp_api_keys SET name = %s WHERE id = %s",
                        ((name.strip() or "API key")[:255], key_id),
                    )
                if clear_expires_at:
                    cur.execute(
                        "UPDATE mcp_api_keys SET expires_at = NULL WHERE id = %s",
                        (key_id,),
                    )
                elif expires_at is not None:
                    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
                    cur.execute(
                        "UPDATE mcp_api_keys SET expires_at = %s WHERE id = %s",
                        (exp, key_id),
                    )
                if clear_allowed_study_ids:
                    cur.execute(
                        "UPDATE mcp_api_keys SET allowed_study_ids_json = %s WHERE id = %s",
                        ("[]", key_id),
                    )
                elif allowed_study_ids is not None:
                    aj = json.dumps(normalize_allowed_study_ids(allowed_study_ids))
                    cur.execute(
                        "UPDATE mcp_api_keys SET allowed_study_ids_json = %s WHERE id = %s",
                        (aj, key_id),
                    )
                if owner_user_id is not None:
                    ou = str(owner_user_id).strip() or None
                    cur.execute(
                        "UPDATE mcp_api_keys SET owner_user_id = %s WHERE id = %s",
                        (ou, key_id),
                    )
                conn.commit()
        finally:
            conn.close()

    def rotate_mcp_api_key(self, key_id: str) -> tuple[McpApiKeyRecord, str]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name, scopes_json, allowed_study_ids_json, owner_user_id, expires_at, revoked_at FROM mcp_api_keys WHERE id = %s",
                    (key_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if not row or row.get("revoked_at"):
            raise ValueError("Key not found or already revoked")
        scopes = json.loads(row["scopes_json"] or "[]")
        if not isinstance(scopes, list):
            scopes = []
        raw_allowed = json.loads(row.get("allowed_study_ids_json") or "[]")
        if not isinstance(raw_allowed, list):
            raw_allowed = []
        allowed_ids = normalize_allowed_study_ids([str(x) for x in raw_allowed])
        if not allowed_ids:
            raise ValueError(
                "This key has no study scope; revoke it and create a new key with an owner and studies."
            )
        exp = row.get("expires_at")
        exp_dt = _naive_to_utc(exp) if exp else None
        if exp_dt is None:
            raise ValueError(
                "This key has no expiry. Edit the key and set an expiry before rotating, or create a new key."
            )
        self.revoke_mcp_api_key(key_id)
        owner_uid = row.get("owner_user_id")
        if not owner_uid or not str(owner_uid).strip():
            raise ValueError(
                "This key has no owner; revoke it and create a new key with a required owner."
            )
        return self.create_mcp_api_key(
            row["name"] or "API key",
            [str(x) for x in scopes],
            str(owner_uid).strip(),
            expires_at=exp_dt,
            allowed_study_ids=allowed_ids,
        )

    def list_mcp_api_keys(self) -> list[McpApiKeyRecord]:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, name, key_prefix, scopes_json, allowed_study_ids_json, owner_user_id, created_at, revoked_at, last_used_at, expires_at
                       FROM mcp_api_keys ORDER BY created_at DESC"""
                )
                rows = cur.fetchall()
            out = []
            for r in rows:
                scopes = json.loads(r["scopes_json"] or "[]")
                if not isinstance(scopes, list):
                    scopes = []
                raw_allowed = json.loads(r.get("allowed_study_ids_json") or "[]")
                if not isinstance(raw_allowed, list):
                    raw_allowed = []
                allowed_ids = normalize_allowed_study_ids([str(x) for x in raw_allowed])
                rv = r.get("revoked_at")
                lu = r.get("last_used_at")
                ex = r.get("expires_at")
                out.append(
                    McpApiKeyRecord(
                        id=r["id"],
                        name=r["name"] or "",
                        key_prefix=r["key_prefix"] or "",
                        scopes=[str(x) for x in scopes],
                        allowed_study_ids=allowed_ids,
                        owner_user_id=r.get("owner_user_id"),
                        created_at=_naive_to_utc(r["created_at"]),
                        revoked_at=_naive_to_utc(rv) if rv else None,
                        last_used_at=_naive_to_utc(lu) if lu else None,
                        expires_at=_naive_to_utc(ex) if ex else None,
                    )
                )
            return out
        finally:
            conn.close()

    def revoke_mcp_api_key(self, key_id: str) -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mcp_api_keys SET revoked_at = %s WHERE id = %s",
                    (now, key_id),
                )
                conn.commit()
        finally:
            conn.close()

    def resolve_mcp_api_key_secret(self, plaintext: str) -> Optional[tuple[str, list[str], str, list[str], Optional[str]]]:
        if not plaintext:
            return None
        h = hash_mcp_api_secret(plaintext)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, scopes_json, key_prefix, allowed_study_ids_json, owner_user_id FROM mcp_api_keys
                       WHERE key_hash = %s AND revoked_at IS NULL
                       AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP(6))""",
                    (h,),
                )
                row = cur.fetchone()
            if not row:
                return None
            scopes = json.loads(row["scopes_json"] or "[]")
            if not isinstance(scopes, list):
                scopes = []
            raw_allowed = json.loads(row.get("allowed_study_ids_json") or "[]")
            if not isinstance(raw_allowed, list):
                raw_allowed = []
            allowed_ids = normalize_allowed_study_ids([str(x) for x in raw_allowed])
            prefix = row.get("key_prefix") or ""
            owner_uid = row.get("owner_user_id")
            owner_str = str(owner_uid).strip() if owner_uid else None
            return (row["id"], [str(x) for x in scopes], prefix, allowed_ids, owner_str or None)
        finally:
            conn.close()

    def has_active_mcp_api_keys(self) -> bool:
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM mcp_api_keys WHERE revoked_at IS NULL
                       AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP(6)) LIMIT 1"""
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def touch_mcp_api_key_last_used(self, key_id: str) -> None:
        now = datetime.now(timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mcp_api_keys SET last_used_at = %s WHERE id = %s",
                    (now, key_id),
                )
                conn.commit()
        finally:
            conn.close()

    def append_tool_invocation_log(
        self,
        *,
        api_key_id: Optional[str],
        key_source: str,
        key_prefix_display: str,
        tool_name: str,
        study_id: Optional[str],
        status_code: int,
        duration_ms: int,
        error_detail: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        err = (error_detail or "")[:512] if error_detail else None
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO tool_invocation_logs
                       (created_at, api_key_id, key_source, key_prefix_display, tool_name, study_id, status_code, duration_ms, error_detail)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        now,
                        api_key_id,
                        (key_source or "database")[:16],
                        (key_prefix_display or "")[:64],
                        (tool_name or "")[:128],
                        study_id,
                        int(status_code),
                        int(duration_ms),
                        err,
                    ),
                )
                conn.commit()
        finally:
            conn.close()

    def list_tool_invocation_logs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        api_key_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        study_id: Optional[str] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
    ) -> tuple[list[ToolInvocationLogEntry], int]:
        conditions: list[str] = []
        params: list = []
        if from_ts is not None:
            conditions.append("created_at >= %s")
            params.append(from_ts if from_ts.tzinfo else from_ts.replace(tzinfo=timezone.utc))
        if to_ts is not None:
            conditions.append("created_at <= %s")
            params.append(to_ts if to_ts.tzinfo else to_ts.replace(tzinfo=timezone.utc))
        if api_key_id is not None:
            conditions.append("api_key_id = %s")
            params.append(api_key_id)
        if tool_name:
            conditions.append("tool_name = %s")
            params.append(tool_name)
        if study_id:
            conditions.append("study_id = %s")
            params.append(study_id)
        if status_min is not None:
            conditions.append("status_code >= %s")
            params.append(int(status_min))
        if status_max is not None:
            conditions.append("status_code <= %s")
            params.append(int(status_max))
        where = " AND ".join(conditions) if conditions else "1=1"
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS c FROM tool_invocation_logs WHERE {where}",
                    params,
                )
                total = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    f"""SELECT id, created_at, api_key_id, key_source, key_prefix_display, tool_name, study_id, status_code, duration_ms, error_detail
                        FROM tool_invocation_logs WHERE {where}
                        ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    params + [limit, offset],
                )
                rows = cur.fetchall()
            out = []
            for r in rows:
                ca = r["created_at"]
                if ca and ca.tzinfo is None:
                    ca = ca.replace(tzinfo=timezone.utc)
                out.append(
                    ToolInvocationLogEntry(
                        id=str(r["id"]),
                        created_at=_naive_to_utc(ca) if ca else datetime.now(timezone.utc),
                        api_key_id=r.get("api_key_id"),
                        key_source=r.get("key_source") or "database",
                        key_prefix=(r.get("key_prefix_display") or "")[:64],
                        tool_name=r.get("tool_name") or "",
                        study_id=r.get("study_id"),
                        status_code=int(r.get("status_code") or 0),
                        duration_ms=int(r.get("duration_ms") or 0),
                        error_detail=r.get("error_detail"),
                    )
                )
            return out, total
        finally:
            conn.close()

    def purge_tool_invocation_logs_before(self, before: datetime) -> int:
        b = before if before.tzinfo else before.replace(tzinfo=timezone.utc)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tool_invocation_logs WHERE created_at < %s",
                    (b,),
                )
                removed = cur.rowcount
                conn.commit()
            return int(removed or 0)
        finally:
            conn.close()

    def platform_dashboard_stats(self) -> dict:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM users")
                user_count = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    """SELECT COUNT(*) AS c FROM mcp_api_keys WHERE revoked_at IS NULL
                       AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP(6))"""
                )
                key_count = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    "SELECT COUNT(*) AS c FROM tool_invocation_logs WHERE created_at >= %s",
                    (day_ago,),
                )
                inv_24 = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    "SELECT COUNT(*) AS c FROM tool_invocation_logs WHERE created_at >= %s",
                    (week_ago,),
                )
                inv_7 = int((cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    """SELECT COUNT(*) AS c FROM tool_invocation_logs
                       WHERE created_at >= %s AND status_code >= 400""",
                    (day_ago,),
                )
                fail_24 = int((cur.fetchone() or {}).get("c") or 0)
            return {
                "userCount": user_count,
                "mcpKeyActiveCount": key_count,
                "invocations24h": inv_24,
                "invocations7d": inv_7,
                "failedInvocations24h": fail_24,
            }
        finally:
            conn.close()
