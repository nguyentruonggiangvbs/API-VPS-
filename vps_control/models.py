from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileWriteRequest(BaseModel):
    root: str
    path: str
    content: str
    expected_mtime_ns: int | None = None
    create: bool = False


class DirectoryCreateRequest(BaseModel):
    root: str
    path: str


class FileRenameRequest(BaseModel):
    root: str
    path: str
    new_name: str = Field(min_length=1, max_length=255)


class FileDeleteRequest(BaseModel):
    root: str
    path: str
    recursive: bool = False
    confirmation: Literal["DELETE"]


class DockerActionRequest(BaseModel):
    action: Literal["start", "stop", "restart", "pause", "unpause"]


class DeployRequest(BaseModel):
    confirmation: Literal["DEPLOY"]


class BackupCreateRequest(BaseModel):
    root: str
    path: str = ""
    label: str = Field(default="manual", min_length=1, max_length=80)


class BackupDeleteRequest(BaseModel):
    confirmation: Literal["DELETE"]


class BackupRestoreRequest(BaseModel):
    target_root: str
    target_path: str
    overwrite: bool = False
    confirmation: Literal["RESTORE"]


class ApiResponse(BaseModel):
    ok: bool = True
    data: Any = None
