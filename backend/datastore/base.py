"""
Datastore abstraction for sessions, users, studies, study config, and user-study privileges.
Implementations: mock (in-memory) for dev, mariadb for production.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Roles for user-study access. viewer < editor < admin.
# Product labels: Study admin = admin; Study staff = editor (STUDY_ROLE_STAFF_ALIAS).
STUDY_ROLE_VIEWER = "viewer"
STUDY_ROLE_EDITOR = "editor"
STUDY_ROLE_ADMIN = "admin"
STUDY_ROLE_STAFF_ALIAS = "editor"  # API "staff" maps to editor


@dataclass
class User:
    """User record from OAuth (e.g. Google)."""

    id: str
    google_id: str
    email: str
    name: str
    created_at: datetime
    updated_at: datetime
    is_superuser: bool = False
    # When True, HTTP tool API (/v1/tools/invoke) masks sensitive tool output for keys owned by this user.
    tool_api_data_proxy_enabled: bool = True
    # Stored only in DB / mock; never expose in public JSON (use hasPassword in API).
    password_hash: Optional[str] = None


@dataclass
class Session:
    """Session record: id is the session_id (cookie value)."""

    id: str
    user_id: str
    expires_at: datetime
    created_at: datetime


@dataclass
class Study:
    """Internal study entity: one pipeline config unit."""

    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class UserStudy:
    """User privilege for a study: user_id, study_id, role."""

    user_id: str
    study_id: str
    role: str  # viewer | editor | admin
    created_at: datetime


# Built-in default pipeline id when a study has no saved pipelines.
DEFAULT_PIPELINE_ID = "__default__"

# Default pipeline graph (Qualtrics → Process → Grid → Box) for studies with no saved pipelines.
DEFAULT_PIPELINE_NODES = [
    {"id": "qualtrics", "type": "stage", "position": {"x": 0, "y": 0}, "data": {"label": "Qualtrics"}},
    {"id": "process", "type": "stage", "position": {"x": 220, "y": 0}, "data": {"label": "Process"}},
    {"id": "grid", "type": "stage", "position": {"x": 440, "y": 0}, "data": {"label": "Grid"}},
    {"id": "box", "type": "stage", "position": {"x": 660, "y": 0}, "data": {"label": "Box"}},
]
DEFAULT_PIPELINE_EDGES = [
    {"id": "e-qualtrics-process", "source": "qualtrics", "target": "process"},
    {"id": "e-process-grid", "source": "process", "target": "grid"},
    {"id": "e-grid-box", "source": "grid", "target": "box"},
]


@dataclass
class PipelineDefinition:
    """Saved pipeline for a study: graph (nodes, edges) and metadata."""

    id: str
    name: str
    is_default: bool
    nodes: list  # list of {id, type, position: {x,y}, data?: {...}}
    edges: list  # list of {id, source, target}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class McpApiKeyRecord:
    """MCP / tool API key metadata (never includes the secret or hash)."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]  # empty = allow all tools
    allowed_study_ids: list[str]  # empty = all studies (when using study_id in tool args)
    owner_user_id: Optional[str]
    created_at: datetime
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime] = None


@dataclass
class ToolInvocationLogEntry:
    """One row for GET /api/admin/tool-invocations."""

    id: str
    created_at: datetime
    api_key_id: Optional[str]
    key_source: str  # "database" | "env"
    key_prefix: str  # display hint, e.g. "rw_abc..." or "env"
    tool_name: str
    study_id: Optional[str]
    status_code: int
    duration_ms: int
    error_detail: Optional[str]


class Datastore(ABC):
    """Abstract datastore for sessions, users, studies, and privileges."""

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Return session by id or None if not found/expired."""
        ...

    @abstractmethod
    def create_session(self, user_id: str, session_id: str, expires_at: datetime) -> None:
        """Create a new session."""
        ...

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Remove a session (e.g. on logout)."""
        ...

    @abstractmethod
    def expire_old_sessions(self) -> None:
        """Remove expired sessions (optional maintenance)."""
        ...

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Return user by id or None."""
        ...

    @abstractmethod
    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Return user by Google id or None."""
        ...

    @abstractmethod
    def create_or_update_user(self, google_id: str, email: str, name: str) -> User:
        """Create or update user by google_id; return the user."""
        ...

    # --- Studies ---

    @abstractmethod
    def list_studies_for_user(self, user_id: str) -> list[tuple[Study, str]]:
        """Return (study, role) for each study the user has access to. Sorted by study name."""
        ...

    @abstractmethod
    def list_all_studies(self) -> list[Study]:
        """Return every study (for platform superuser dashboard). Sorted by name, then id."""
        ...

    @abstractmethod
    def get_study(self, study_id: str) -> Optional[Study]:
        """Return study by id or None."""
        ...

    @abstractmethod
    def create_study(self, name: str, description: Optional[str] = None) -> Study:
        """Create a new study. Caller should then set_user_study_role to assign an admin."""
        ...

    @abstractmethod
    def update_study(
        self,
        study_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Update study name and/or description. No-op for None values."""
        ...

    @abstractmethod
    def delete_study(self, study_id: str) -> None:
        """Delete study and its config and user_study rows. Caller must ensure no run in progress."""
        ...

    @abstractmethod
    def get_study_config(self, study_id: str) -> dict[str, str]:
        """Return key-value config for the study. Empty dict if study has no config."""
        ...

    @abstractmethod
    def set_study_config(self, study_id: str, config: dict[str, str]) -> None:
        """Replace config for the study with the given key-value dict."""
        ...

    def get_study_box_config(self, study_id: str) -> Optional[str]:
        """Return Box JWT config JSON string for the study, or None if not set."""
        return None

    def set_study_box_config(self, study_id: str, config_json: str) -> None:
        """Store Box JWT config JSON for the study. Overwrites any existing."""
        raise NotImplementedError

    def get_processed_ids(self, study_id: str) -> set[str]:
        """Return set of processed response IDs for the study. Default: empty set."""
        return set()

    def add_processed_ids(self, study_id: str, ids: set[str]) -> None:
        """Add response IDs to the processed set for the study. Default: no-op."""
        pass

    def create_run(self, study_id: str, external_id: str) -> str:
        """Create a run record for the study; return run id (UUID). Default: no-op, returns empty string."""
        return ""

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
        """Update run metadata. Default: no-op."""
        pass

    def append_run_log(self, run_id: str, level: str, message: str, step: str = "") -> None:
        """Append a log line to the run. Default: no-op."""
        pass

    @abstractmethod
    def get_user_study_role(self, user_id: str, study_id: str) -> Optional[str]:
        """Return user's role for the study (viewer/editor/admin) or None if no access."""
        ...

    @abstractmethod
    def set_user_study_role(self, user_id: str, study_id: str, role: str) -> None:
        """Set or update user's role for the study. Creates user_study if needed."""
        ...

    @abstractmethod
    def remove_user_study(self, user_id: str, study_id: str) -> None:
        """Remove user's access to the study."""
        ...

    @abstractmethod
    def list_study_users(self, study_id: str) -> list[tuple[User, str]]:
        """Return (user, role) for each user with access to the study."""
        ...

    def list_users(self) -> list[User]:
        """Return all users. Used for migration (assign default study). Default: empty list."""
        return []

    def has_any_study(self) -> bool:
        """Return True if at least one study exists. Used for migration. Default: False."""
        return False

    def get_any_study(self) -> Optional[Study]:
        """Return any one study (e.g. for bootstrap assigning first user). Default: None."""
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Return user by email or None. Used for add-user-by-email. Default: None."""
        return None

    def create_provisioned_user(self, email: str, name: str, password_hash: Optional[str] = None) -> User:
        """Create a user with pending google_id until OAuth links the account. Default: not supported."""
        raise NotImplementedError

    def update_user_profile(self, user_id: str, *, email: Optional[str] = None, name: Optional[str] = None) -> None:
        """Update email and/or name. Default: not supported."""
        raise NotImplementedError

    def set_user_password_hash(self, user_id: str, password_hash: Optional[str]) -> None:
        """Set or clear bcrypt password hash. Default: not supported."""
        raise NotImplementedError

    def link_oauth_to_pending_user(self, user_id: str, google_id: str, email: str, name: str) -> User:
        """Replace pending google_id with real OAuth subject. Default: not supported."""
        raise NotImplementedError

    def set_user_superuser(self, user_id: str, is_superuser: bool) -> None:
        """Set platform superuser flag. Default: not implemented."""
        raise NotImplementedError

    def set_user_tool_api_data_proxy(self, user_id: str, enabled: bool) -> None:
        """Enable/disable data proxy for HTTP tool API keys owned by this user."""
        raise NotImplementedError

    # --- MCP tool API keys & invocation audit (platform admin) ---

    @abstractmethod
    def create_mcp_api_key(
        self,
        name: str,
        scopes: list[str],
        owner_user_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        allowed_study_ids: Optional[list[str]] = None,
    ) -> tuple[McpApiKeyRecord, str]:
        """Create a key; return (public record, plaintext secret shown once)."""

    @abstractmethod
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
        """Update metadata. Pass clear_expires_at=True to remove expiry. Set owner_user_id to reassign human owner."""

    @abstractmethod
    def rotate_mcp_api_key(self, key_id: str) -> tuple[McpApiKeyRecord, str]:
        """Revoke old key and create a replacement with same name, scopes, owner, expiry; return (record, secret once)."""

    @abstractmethod
    def list_mcp_api_keys(self) -> list[McpApiKeyRecord]:
        """All keys including revoked."""

    @abstractmethod
    def revoke_mcp_api_key(self, key_id: str) -> None:
        """Mark key revoked."""

    @abstractmethod
    def resolve_mcp_api_key_secret(
        self, plaintext: str
    ) -> Optional[tuple[str, list[str], str, list[str], Optional[str]]]:
        """
        If plaintext matches an active stored key, return
        (key_id, scopes, key_prefix, allowed_study_ids, owner_user_id).
        scopes empty list means all tools allowed.
        Product rules: valid keys must have a non-empty allowed_study_ids and owner_user_id (enforced in API/auth).
        """

    @abstractmethod
    def has_active_mcp_api_keys(self) -> bool:
        """True if at least one non-revoked MCP API key exists in the datastore."""

    @abstractmethod
    def touch_mcp_api_key_last_used(self, key_id: str) -> None:
        """Update last_used_at to now."""

    @abstractmethod
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
        """Append audit row for POST /v1/tools/invoke."""

    @abstractmethod
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
        """Return (rows, total matching filters)."""

    @abstractmethod
    def purge_tool_invocation_logs_before(self, before: datetime) -> int:
        """Delete logs with created_at < before; return rows removed."""

    @abstractmethod
    def platform_dashboard_stats(self) -> dict:
        """Counts for superuser dashboard: user_count, mcp_key_active_count, invocations_24h, invocations_7d, failed_24h."""

    # --- Pipeline definitions (per study, stored in DB) ---

    @abstractmethod
    def list_pipelines(self, study_id: str) -> list[PipelineDefinition]:
        """Return all saved pipelines for the study. If none, return one default (DEFAULT_PIPELINE_ID)."""
        ...

    @abstractmethod
    def get_pipeline(self, study_id: str, pipeline_id: str) -> Optional[PipelineDefinition]:
        """Return pipeline by id, or None. For DEFAULT_PIPELINE_ID return built-in default if no pipelines saved."""
        ...

    @abstractmethod
    def set_pipeline(
        self,
        study_id: str,
        pipeline_id: str,
        name: str,
        is_default: bool,
        nodes: list,
        edges: list,
    ) -> None:
        """Create or update a pipeline. If is_default True, clear default on others."""
        ...

    @abstractmethod
    def create_pipeline(
        self,
        study_id: str,
        name: str,
        is_default: bool,
        nodes: list,
        edges: list,
    ) -> str:
        """Create a new pipeline; return pipeline_id (e.g. UUID). If is_default True, clear default on others."""
        ...

    @abstractmethod
    def delete_pipeline(self, study_id: str, pipeline_id: str) -> None:
        """Delete a pipeline. If it was default, caller should set another as default."""
        ...

    @abstractmethod
    def get_default_pipeline_id(self, study_id: str) -> Optional[str]:
        """Return the default pipeline id for the study, or None if no pipelines / use built-in default."""
        ...
