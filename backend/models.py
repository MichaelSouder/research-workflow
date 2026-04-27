"""Pydantic request/response models for API routes."""

from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    config: dict[str, str]
    persist: bool = False


class StartBody(BaseModel):
    config_overrides: dict[str, str] | None = None
    pipeline_id: str | None = None


class PipelineDefinitionBody(BaseModel):
    name: str
    is_default: bool = False
    nodes: list
    edges: list


class PipelineCreateBody(BaseModel):
    name: str
    is_default: bool = False
    nodes: list | None = None
    edges: list | None = None


class StudyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class StudyCreate(BaseModel):
    name: str
    description: str | None = None


class AddStudyUserBody(BaseModel):
    email: str
    role: str = "staff"  # admin | staff (maps to editor)
