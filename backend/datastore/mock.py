"""
In-memory datastore for development. No persistence across restarts.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

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


class MockDatastore(Datastore):
    """In-memory implementation: sessions, users, studies, study config, user_study."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._users_by_google: dict[str, str] = {}  # google_id -> user id
        self._sessions: dict[str, Session] = {}
        self._studies: dict[str, Study] = {}
        self._study_config: dict[str, dict[str, str]] = {}  # study_id -> {key: value}
        self._study_box_config: dict[str, str] = {}  # study_id -> Box JWT config JSON
        self._processed_ids: dict[str, set[str]] = {}  # study_id -> set of response_id
        self._runs: dict[str, dict] = {}  # run_id -> {study_id, external_id, status, ...}
        self._run_logs: dict[str, list[dict]] = {}  # run_id -> list of {level, message, step, created_at}
        self._user_study: list[UserStudy] = []  # (user_id, study_id) -> role via lookup
        self._study_pipelines: dict[str, list[dict]] = {}  # study_id -> list of {id, name, is_default, nodes, edges, created_at, updated_at}
        self._mcp_api_keys: dict[str, dict] = {}  # id -> key record dict
        self._tool_invocation_logs: list[dict] = []  # chronological append

    def get_session(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if s is None:
            return None
        if s.expires_at.tzinfo is None:
            exp = s.expires_at.replace(tzinfo=timezone.utc)
        else:
            exp = s.expires_at
        if datetime.now(timezone.utc) >= exp:
            del self._sessions[session_id]
            return None
        return s

    def create_session(self, user_id: str, session_id: str, expires_at: datetime) -> None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        self._sessions[session_id] = Session(
            id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def expire_old_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        to_remove = []
        for sid, s in self._sessions.items():
            exp = (
                s.expires_at.replace(tzinfo=timezone.utc)
                if s.expires_at.tzinfo is None
                else s.expires_at
            )
            if now >= exp:
                to_remove.append(sid)
        for sid in to_remove:
            del self._sessions[sid]

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        uid = self._users_by_google.get(google_id)
        return self._users.get(uid) if uid else None

    def create_or_update_user(self, google_id: str, email: str, name: str) -> User:
        now = datetime.now(timezone.utc)
        existing = self.get_user_by_google_id(google_id)
        if existing:
            # Update in place (same id)
            updated = User(
                id=existing.id,
                google_id=google_id,
                email=email,
                name=name,
                created_at=existing.created_at,
                updated_at=now,
                is_superuser=existing.is_superuser,
                password_hash=existing.password_hash,
            )
            self._users[existing.id] = updated
            self._users_by_google[google_id] = existing.id
            return updated
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            google_id=google_id,
            email=email,
            name=name,
            created_at=now,
            updated_at=now,
            is_superuser=False,
            password_hash=None,
        )
        self._users[user_id] = user
        self._users_by_google[google_id] = user_id
        return user

    def list_users(self) -> list[User]:
        return list(self._users.values())

    def set_user_superuser(self, user_id: str, is_superuser: bool) -> None:
        u = self._users.get(user_id)
        if not u:
            return
        self._users[user_id] = User(
            id=u.id,
            google_id=u.google_id,
            email=u.email,
            name=u.name,
            created_at=u.created_at,
            updated_at=u.updated_at,
            is_superuser=is_superuser,
            password_hash=u.password_hash,
        )

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
        user = User(
            id=user_id,
            google_id=pending_gid,
            email=email,
            name=name,
            created_at=now,
            updated_at=now,
            is_superuser=False,
            password_hash=password_hash,
        )
        self._users[user_id] = user
        self._users_by_google[pending_gid] = user_id
        return user

    def update_user_profile(self, user_id: str, *, email: Optional[str] = None, name: Optional[str] = None) -> None:
        u = self._users.get(user_id)
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
        self._users[user_id] = User(
            id=u.id,
            google_id=u.google_id,
            email=new_email,
            name=new_name,
            created_at=u.created_at,
            updated_at=datetime.now(timezone.utc),
            is_superuser=u.is_superuser,
            password_hash=u.password_hash,
        )

    def set_user_password_hash(self, user_id: str, password_hash: Optional[str]) -> None:
        u = self._users.get(user_id)
        if not u:
            return
        self._users[user_id] = User(
            id=u.id,
            google_id=u.google_id,
            email=u.email,
            name=u.name,
            created_at=u.created_at,
            updated_at=datetime.now(timezone.utc),
            is_superuser=u.is_superuser,
            password_hash=password_hash,
        )

    def link_oauth_to_pending_user(self, user_id: str, google_id: str, email: str, name: str) -> User:
        u = self._users.get(user_id)
        if not u:
            raise RuntimeError("User not found.")
        old_gid = u.google_id
        if old_gid in self._users_by_google:
            del self._users_by_google[old_gid]
        now = datetime.now(timezone.utc)
        updated = User(
            id=u.id,
            google_id=google_id,
            email=email,
            name=name,
            created_at=u.created_at,
            updated_at=now,
            is_superuser=u.is_superuser,
            password_hash=u.password_hash,
        )
        self._users[user_id] = updated
        self._users_by_google[google_id] = user_id
        return updated

    def list_studies_for_user(self, user_id: str) -> list[tuple[Study, str]]:
        out = []
        for us in self._user_study:
            if us.user_id != user_id:
                continue
            study = self._studies.get(us.study_id)
            if study:
                out.append((study, us.role))
        out.sort(key=lambda x: (x[0].name.lower(), x[0].id))
        return out

    def list_all_studies(self) -> list[Study]:
        return sorted(self._studies.values(), key=lambda s: (s.name.lower(), s.id))

    def get_study(self, study_id: str) -> Optional[Study]:
        return self._studies.get(study_id)

    def create_study(self, name: str, description: Optional[str] = None) -> Study:
        now = datetime.now(timezone.utc)
        study_id = str(uuid.uuid4())
        study = Study(
            id=study_id,
            name=name,
            description=description or None,
            created_at=now,
            updated_at=now,
        )
        self._studies[study_id] = study
        self._study_config[study_id] = {}
        return study

    def get_study_box_config(self, study_id: str) -> Optional[str]:
        return self._study_box_config.get(study_id)

    def set_study_box_config(self, study_id: str, config_json: str) -> None:
        self._study_box_config[study_id] = config_json

    def get_processed_ids(self, study_id: str) -> set[str]:
        return set(self._processed_ids.get(study_id) or ())

    def add_processed_ids(self, study_id: str, ids: set[str]) -> None:
        s = self._processed_ids.setdefault(study_id, set())
        s.update(ids)

    def create_run(self, study_id: str, external_id: str) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        self._runs[run_id] = {
            "study_id": study_id,
            "external_id": external_id,
            "status": "running",
            "current_step": "",
            "progress_percent": 0,
            "message": "",
            "started_at": now,
            "finished_at": None,
            "created_at": now,
        }
        self._run_logs[run_id] = []
        return run_id

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
        r = self._runs.get(run_id)
        if not r:
            return
        if status is not None:
            r["status"] = status
        if current_step is not None:
            r["current_step"] = current_step
        if progress_percent is not None:
            r["progress_percent"] = progress_percent
        if message is not None:
            r["message"] = message
        if finished_at is not None:
            r["finished_at"] = finished_at

    def append_run_log(self, run_id: str, level: str, message: str, step: str = "") -> None:
        logs = self._run_logs.get(run_id)
        if logs is None:
            return
        logs.append({
            "level": level,
            "message": message,
            "step": step,
            "created_at": datetime.now(timezone.utc),
        })

    def update_study(
        self,
        study_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        study = self._studies.get(study_id)
        if not study or (name is None and description is None):
            return
        new_name = name if name is not None else study.name
        new_description = description if description is not None else study.description
        now = datetime.now(timezone.utc)
        self._studies[study_id] = Study(
            id=study.id,
            name=new_name,
            description=new_description,
            created_at=study.created_at,
            updated_at=now,
        )

    def delete_study(self, study_id: str) -> None:
        self._studies.pop(study_id, None)
        self._study_config.pop(study_id, None)
        self._study_box_config.pop(study_id, None)
        self._processed_ids.pop(study_id, None)
        self._study_pipelines.pop(study_id, None)
        for run_id in [rid for rid, r in self._runs.items() if r.get("study_id") == study_id]:
            self._runs.pop(run_id, None)
            self._run_logs.pop(run_id, None)
        self._user_study = [us for us in self._user_study if us.study_id != study_id]

    def get_study_config(self, study_id: str) -> dict[str, str]:
        return dict(self._study_config.get(study_id) or {})

    def set_study_config(self, study_id: str, config: dict[str, str]) -> None:
        self._study_config[study_id] = dict(config)

    def get_user_study_role(self, user_id: str, study_id: str) -> Optional[str]:
        for us in self._user_study:
            if us.user_id == user_id and us.study_id == study_id:
                return us.role
        return None

    def set_user_study_role(self, user_id: str, study_id: str, role: str) -> None:
        for i, us in enumerate(self._user_study):
            if us.user_id == user_id and us.study_id == study_id:
                self._user_study[i] = UserStudy(
                    user_id=us.user_id,
                    study_id=us.study_id,
                    role=role,
                    created_at=us.created_at,
                )
                return
        self._user_study.append(
            UserStudy(
                user_id=user_id,
                study_id=study_id,
                role=role,
                created_at=datetime.now(timezone.utc),
            )
        )

    def remove_user_study(self, user_id: str, study_id: str) -> None:
        self._user_study = [
            us for us in self._user_study
            if not (us.user_id == user_id and us.study_id == study_id)
        ]

    def list_study_users(self, study_id: str) -> list[tuple[User, str]]:
        out = []
        for us in self._user_study:
            if us.study_id != study_id:
                continue
            user = self._users.get(us.user_id)
            if user:
                out.append((user, us.role))
        out.sort(key=lambda x: (x[0].email.lower(), x[0].id))
        return out

    def has_any_study(self) -> bool:
        return len(self._studies) > 0

    def get_any_study(self) -> Optional[Study]:
        return next(iter(self._studies.values()), None) if self._studies else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        if not email:
            return None
        email_lower = email.strip().lower()
        for u in self._users.values():
            if (u.email or "").strip().lower() == email_lower:
                return u
        return None

    def list_all_studies(self) -> list[Study]:
        return sorted(self._studies.values(), key=lambda s: (s.name.lower(), s.id))

    def list_pipelines(self, study_id: str) -> list[PipelineDefinition]:
        pipelines = self._study_pipelines.get(study_id) or []
        if not pipelines:
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
        return [
            PipelineDefinition(
                id=p["id"],
                name=p["name"],
                is_default=p["is_default"],
                nodes=p["nodes"],
                edges=p["edges"],
                created_at=p.get("created_at"),
                updated_at=p.get("updated_at"),
            )
            for p in pipelines
        ]

    def get_pipeline(self, study_id: str, pipeline_id: str) -> Optional[PipelineDefinition]:
        if pipeline_id == DEFAULT_PIPELINE_ID:
            pipelines = self._study_pipelines.get(study_id) or []
            if not pipelines:
                return PipelineDefinition(
                    id=DEFAULT_PIPELINE_ID,
                    name="Default",
                    is_default=True,
                    nodes=list(DEFAULT_PIPELINE_NODES),
                    edges=list(DEFAULT_PIPELINE_EDGES),
                    created_at=None,
                    updated_at=None,
                )
        pipelines = self._study_pipelines.get(study_id) or []
        for p in pipelines:
            if p["id"] == pipeline_id:
                return PipelineDefinition(
                    id=p["id"],
                    name=p["name"],
                    is_default=p["is_default"],
                    nodes=p["nodes"],
                    edges=p["edges"],
                    created_at=p.get("created_at"),
                    updated_at=p.get("updated_at"),
                )
        return None

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
        if is_default:
            for p in self._study_pipelines.get(study_id) or []:
                p["is_default"] = False
        pipelines = self._study_pipelines.setdefault(study_id, [])
        for p in pipelines:
            if p["id"] == pipeline_id:
                p["name"] = name
                p["is_default"] = is_default
                p["nodes"] = nodes
                p["edges"] = edges
                p["updated_at"] = now
                return
        pipelines.append(
            {
                "id": pipeline_id,
                "name": name,
                "is_default": is_default,
                "nodes": nodes,
                "edges": edges,
                "created_at": now,
                "updated_at": now,
            }
        )

    def create_pipeline(
        self,
        study_id: str,
        name: str,
        is_default: bool,
        nodes: list,
        edges: list,
    ) -> str:
        pipeline_id = str(uuid.uuid4())
        if is_default:
            for p in self._study_pipelines.get(study_id) or []:
                p["is_default"] = False
        now = datetime.now(timezone.utc)
        self._study_pipelines.setdefault(study_id, []).append(
            {
                "id": pipeline_id,
                "name": name,
                "is_default": is_default,
                "nodes": nodes,
                "edges": edges,
                "created_at": now,
                "updated_at": now,
            }
        )
        return pipeline_id

    def delete_pipeline(self, study_id: str, pipeline_id: str) -> None:
        pipelines = self._study_pipelines.get(study_id) or []
        self._study_pipelines[study_id] = [p for p in pipelines if p["id"] != pipeline_id]

    def get_default_pipeline_id(self, study_id: str) -> Optional[str]:
        pipelines = self._study_pipelines.get(study_id) or []
        if not pipelines:
            return DEFAULT_PIPELINE_ID
        for p in pipelines:
            if p.get("is_default"):
                return p["id"]
        return pipelines[0]["id"] if pipelines else DEFAULT_PIPELINE_ID

    def _mcp_key_is_usable(self, rec: dict) -> bool:
        if rec.get("revoked_at"):
            return False
        exp = rec.get("expires_at")
        if exp is None:
            return True
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < exp

    def create_mcp_api_key(
        self,
        name: str,
        scopes: list[str],
        owner_user_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        allowed_study_ids: Optional[list[str]] = None,
    ) -> tuple[McpApiKeyRecord, str]:
        import secrets

        now = datetime.now(timezone.utc)
        key_id = str(uuid.uuid4())
        plain = secrets.token_urlsafe(32)
        key_prefix = (plain[:12] + "…") if len(plain) > 12 else plain + "…"
        scopes_list = list(scopes) if scopes else []
        allowed_ids = normalize_allowed_study_ids(allowed_study_ids)
        exp = expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        rec = {
            "id": key_id,
            "name": (name or "API key").strip() or "API key",
            "key_prefix": key_prefix,
            "key_hash": hash_mcp_api_secret(plain),
            "scopes": scopes_list,
            "allowed_study_ids": allowed_ids,
            "owner_user_id": owner_user_id,
            "created_at": now,
            "revoked_at": None,
            "last_used_at": None,
            "expires_at": exp,
        }
        self._mcp_api_keys[key_id] = rec
        public = self._rec_to_mcp_public(rec)
        return public, plain

    def _rec_to_mcp_public(self, rec: dict) -> McpApiKeyRecord:
        ea = rec.get("expires_at")
        if ea is not None and ea.tzinfo is None:
            ea = ea.replace(tzinfo=timezone.utc)
        return McpApiKeyRecord(
            id=rec["id"],
            name=rec["name"],
            key_prefix=rec["key_prefix"],
            scopes=list(rec.get("scopes") or []),
            allowed_study_ids=list(rec.get("allowed_study_ids") or []),
            owner_user_id=rec.get("owner_user_id"),
            created_at=rec["created_at"],
            revoked_at=rec.get("revoked_at"),
            last_used_at=rec.get("last_used_at"),
            expires_at=ea,
        )

    def update_mcp_api_key(
        self,
        key_id: str,
        *,
        name: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        clear_expires_at: bool = False,
        allowed_study_ids: Optional[list[str]] = None,
        clear_allowed_study_ids: bool = False,
    ) -> None:
        rec = self._mcp_api_keys.get(key_id)
        if not rec:
            return
        if name is not None:
            rec["name"] = (name.strip() or "API key")[:255]
        if clear_expires_at:
            rec["expires_at"] = None
        elif expires_at is not None:
            exp = expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            rec["expires_at"] = exp
        if clear_allowed_study_ids:
            rec["allowed_study_ids"] = []
        elif allowed_study_ids is not None:
            rec["allowed_study_ids"] = normalize_allowed_study_ids(allowed_study_ids)

    def rotate_mcp_api_key(self, key_id: str) -> tuple[McpApiKeyRecord, str]:
        rec = self._mcp_api_keys.get(key_id)
        if not rec or rec.get("revoked_at"):
            raise ValueError("Key not found or already revoked")
        name = rec["name"]
        scopes = list(rec.get("scopes") or [])
        allowed = list(rec.get("allowed_study_ids") or [])
        allowed_norm = normalize_allowed_study_ids([str(x) for x in allowed])
        if not allowed_norm:
            raise ValueError(
                "This key has no study scope; revoke it and create a new key with an owner and studies."
            )
        owner = rec.get("owner_user_id")
        if not owner or not str(owner).strip():
            raise ValueError(
                "This key has no owner; revoke it and create a new key with a required owner."
            )
        exp = rec.get("expires_at")
        if exp is None:
            raise ValueError(
                "This key has no expiry. Edit the key and set an expiry before rotating, or create a new key."
            )
        self.revoke_mcp_api_key(key_id)
        return self.create_mcp_api_key(
            name, scopes, str(owner).strip(), expires_at=exp, allowed_study_ids=allowed_norm
        )

    def list_mcp_api_keys(self) -> list[McpApiKeyRecord]:
        out = []
        for rec in self._mcp_api_keys.values():
            out.append(self._rec_to_mcp_public(rec))
        out.sort(key=lambda x: x.created_at, reverse=True)
        return out

    def revoke_mcp_api_key(self, key_id: str) -> None:
        rec = self._mcp_api_keys.get(key_id)
        if not rec:
            return
        rec["revoked_at"] = datetime.now(timezone.utc)

    def resolve_mcp_api_key_secret(
        self, plaintext: str
    ) -> Optional[tuple[str, list[str], str, list[str], Optional[str]]]:
        if not plaintext:
            return None
        h = hash_mcp_api_secret(plaintext)
        for kid, rec in self._mcp_api_keys.items():
            if rec.get("key_hash") != h:
                continue
            if not self._mcp_key_is_usable(rec):
                continue
            allow = normalize_allowed_study_ids(list(rec.get("allowed_study_ids") or []))
            ou = rec.get("owner_user_id")
            owner_str = str(ou).strip() if ou else None
            return (
                kid,
                list(rec.get("scopes") or []),
                rec.get("key_prefix") or kid[:8] + "…",
                allow,
                owner_str or None,
            )
        return None

    def has_active_mcp_api_keys(self) -> bool:
        return any(self._mcp_key_is_usable(r) for r in self._mcp_api_keys.values())

    def touch_mcp_api_key_last_used(self, key_id: str) -> None:
        rec = self._mcp_api_keys.get(key_id)
        if rec:
            rec["last_used_at"] = datetime.now(timezone.utc)

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
        lid = str(uuid.uuid4())
        err = (error_detail or "")[:512] if error_detail else None
        self._tool_invocation_logs.append(
            {
                "id": lid,
                "created_at": now,
                "api_key_id": api_key_id,
                "key_source": key_source,
                "key_prefix_display": (key_prefix_display or "")[:64],
                "tool_name": tool_name,
                "study_id": study_id,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error_detail": err,
            }
        )

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
        def norm(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        fts = norm(from_ts)
        tts = norm(to_ts)
        rows = list(self._tool_invocation_logs)
        filtered = []
        for r in rows:
            ca = r["created_at"]
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            if fts and ca < fts:
                continue
            if tts and ca > tts:
                continue
            if api_key_id is not None:
                if r.get("api_key_id") != api_key_id:
                    continue
            if tool_name and (r.get("tool_name") or "") != tool_name:
                continue
            if study_id is not None and study_id != "":
                if (r.get("study_id") or "") != study_id:
                    continue
            sc = int(r.get("status_code") or 0)
            if status_min is not None and sc < status_min:
                continue
            if status_max is not None and sc > status_max:
                continue
            filtered.append(r)
        filtered.sort(key=lambda x: x["created_at"], reverse=True)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        out: list[ToolInvocationLogEntry] = []
        for r in page:
            kid = r.get("api_key_id")
            ks = r.get("key_source") or "database"
            prefix = r.get("key_prefix_display") or (
                "env" if ks == "env" else (kid[:8] + "…" if kid else "")
            )
            ca = r["created_at"]
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            out.append(
                ToolInvocationLogEntry(
                    id=r["id"],
                    created_at=ca,
                    api_key_id=kid,
                    key_source=ks,
                    key_prefix=prefix,
                    tool_name=r.get("tool_name") or "",
                    study_id=r.get("study_id"),
                    status_code=int(r.get("status_code") or 0),
                    duration_ms=int(r.get("duration_ms") or 0),
                    error_detail=r.get("error_detail"),
                )
            )
        return out, total

    def purge_tool_invocation_logs_before(self, before: datetime) -> int:
        if before.tzinfo is None:
            before = before.replace(tzinfo=timezone.utc)
        kept = []
        removed = 0
        for r in self._tool_invocation_logs:
            ca = r["created_at"]
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            if ca < before:
                removed += 1
            else:
                kept.append(r)
        self._tool_invocation_logs = kept
        return removed

    def platform_dashboard_stats(self) -> dict:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)
        users_n = len(self._users)
        active_keys = sum(1 for r in self._mcp_api_keys.values() if self._mcp_key_is_usable(r))
        inv_24 = 0
        inv_7 = 0
        fail_24 = 0
        for r in self._tool_invocation_logs:
            ca = r["created_at"]
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            if ca >= day_ago:
                inv_24 += 1
                if int(r.get("status_code") or 0) >= 400:
                    fail_24 += 1
            if ca >= week_ago:
                inv_7 += 1
        return {
            "userCount": users_n,
            "mcpKeyActiveCount": active_keys,
            "invocations24h": inv_24,
            "invocations7d": inv_7,
            "failedInvocations24h": fail_24,
        }
