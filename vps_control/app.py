from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .audit import audit_log
from .backup_service import (
    BackupServiceError,
    backup_service,
)
from .config import settings
from .deploy_service import DeployServiceError, deploy_service
from .docker_service import DockerServiceError, docker_service
from .file_service import FileServiceError, file_service
from .jobs import job_store
from .models import (
    BackupCreateRequest,
    BackupDeleteRequest,
    BackupRestoreRequest,
    DirectoryCreateRequest,
    DockerActionRequest,
    FileDeleteRequest,
    FileRenameRequest,
    FileWriteRequest,
)
from .security import require_api_key
from .system_service import metrics_collector


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    await metrics_collector.start()
    audit_log.write(
        action="service.start",
        outcome="success",
        actor="system",
        client_ip="local",
        details={"version": __version__},
    )
    try:
        yield
    finally:
        await metrics_collector.stop()
        audit_log.write(
            action="service.stop",
            outcome="success",
            actor="system",
            client_ip="local",
            details={"version": __version__},
        )


app = FastAPI(
    title="API-VPS Control Center",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(FileServiceError)
async def handle_file_error(_: Request, exc: FileServiceError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(DockerServiceError)
async def handle_docker_error(_: Request, exc: DockerServiceError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DeployServiceError)
async def handle_deploy_error(_: Request, exc: DeployServiceError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(BackupServiceError)
async def handle_backup_error(_: Request, exc: BackupServiceError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


Auth = Annotated[str, Depends(require_api_key)]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _snapshot() -> dict[str, Any]:
    if metrics_collector.history:
        return metrics_collector.history[-1]
    value = metrics_collector.snapshot()
    metrics_collector.history.append(value)
    return value


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "api-vps",
        "version": __version__,
    }


@app.get("/api/auth/verify")
def verify_auth(_: Auth) -> dict[str, Any]:
    return {"authenticated": True, "version": __version__}


@app.get("/api/overview")
def overview(_: Auth) -> dict[str, Any]:
    snapshot = _snapshot()
    try:
        containers = docker_service.list_containers(include_stats=True)
        docker_available = True
    except DockerServiceError:
        containers = []
        docker_available = False

    return {
        "host": metrics_collector.host_info(),
        "metrics": snapshot,
        "alerts": metrics_collector.alerts(snapshot),
        "docker": {
            "available": docker_available,
            "containers": containers,
            "running": sum(
                1 for item in containers if item["status"] == "running"
            ),
            "stopped": sum(
                1 for item in containers if item["status"] != "running"
            ),
        },
        "roots": file_service.roots(),
        "recent_activity": audit_log.read(limit=8),
        "version": __version__,
    }


@app.get("/api/system/metrics")
def system_metrics(_: Auth) -> dict[str, Any]:
    return _snapshot()


@app.get("/api/system/history")
def system_history(
    _: Auth,
    limit: int = Query(default=120, ge=1, le=5_000),
) -> dict[str, Any]:
    return {"points": metrics_collector.recent(limit)}


@app.get("/api/system/processes")
def system_processes(
    _: Auth,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return {"processes": metrics_collector.processes(limit)}


@app.get("/api/system/info")
def system_info(_: Auth) -> dict[str, Any]:
    return {
        "host": metrics_collector.host_info(),
        "metrics": _snapshot(),
    }


@app.get("/api/docker/containers")
def docker_containers(
    _: Auth,
    include_stats: bool = Query(default=True),
) -> dict[str, Any]:
    return {
        "containers": docker_service.list_containers(
            include_stats=include_stats
        )
    }


@app.get("/api/docker/containers/{container_name}")
def docker_container(
    container_name: str,
    _: Auth,
) -> dict[str, Any]:
    return {
        "container": docker_service.inspect(container_name),
        "stats": docker_service.stats(container_name),
    }


@app.post("/api/docker/containers/{container_name}/action")
def docker_action(
    container_name: str,
    body: DockerActionRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    try:
        result = docker_service.action(container_name, body.action)
        audit_log.write(
            action=f"docker.{body.action}",
            outcome="success",
            client_ip=_client_ip(request),
            details={"container": container_name},
        )
        return result
    except DockerServiceError as exc:
        audit_log.write(
            action=f"docker.{body.action}",
            outcome="failed",
            client_ip=_client_ip(request),
            details={
                "container": container_name,
                "error": str(exc),
            },
        )
        raise


@app.get("/api/docker/containers/{container_name}/logs")
def docker_logs(
    container_name: str,
    _: Auth,
    tail: int = Query(default=300, ge=1, le=5_000),
    since_seconds: int | None = Query(
        default=None,
        ge=1,
        le=604_800,
    ),
) -> dict[str, Any]:
    return {
        "container": container_name,
        "logs": docker_service.logs(
            container_name,
            tail=tail,
            since_seconds=since_seconds,
        ),
    }


@app.get("/api/docker/images")
def docker_images(_: Auth) -> dict[str, Any]:
    return {"images": docker_service.images()}


@app.get("/api/files/roots")
def file_roots(_: Auth) -> dict[str, Any]:
    return {"roots": file_service.roots()}


@app.get("/api/files/list")
def file_list(
    _: Auth,
    root: str = Query(...),
    path: str = Query(default=""),
    show_hidden: bool = Query(default=False),
) -> dict[str, Any]:
    return file_service.list_directory(
        root,
        path,
        show_hidden=show_hidden,
    )


@app.get("/api/files/read")
def file_read(
    _: Auth,
    root: str = Query(...),
    path: str = Query(...),
) -> dict[str, Any]:
    return file_service.read_file(root, path)


@app.put("/api/files/write")
def file_write(
    body: FileWriteRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    try:
        result = file_service.write_file(
            body.root,
            body.path,
            body.content,
            expected_mtime_ns=body.expected_mtime_ns,
            create=body.create,
        )
        audit_log.write(
            action="file.write",
            outcome="success",
            client_ip=_client_ip(request),
            details={
                "root": body.root,
                "path": body.path,
                "create": body.create,
                "size": result["size"],
            },
        )
        return result
    except FileServiceError as exc:
        audit_log.write(
            action="file.write",
            outcome="failed",
            client_ip=_client_ip(request),
            details={
                "root": body.root,
                "path": body.path,
                "error": str(exc),
            },
        )
        raise


@app.post("/api/files/directory")
def file_create_directory(
    body: DirectoryCreateRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    result = file_service.create_directory(body.root, body.path)
    audit_log.write(
        action="file.mkdir",
        outcome="success",
        client_ip=_client_ip(request),
        details={"root": body.root, "path": body.path},
    )
    return result


@app.post("/api/files/rename")
def file_rename(
    body: FileRenameRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    result = file_service.rename(
        body.root,
        body.path,
        body.new_name,
    )
    audit_log.write(
        action="file.rename",
        outcome="success",
        client_ip=_client_ip(request),
        details={
            "root": body.root,
            "path": body.path,
            "new_name": body.new_name,
        },
    )
    return result


@app.delete("/api/files")
def file_delete(
    body: FileDeleteRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    result = file_service.delete(
        body.root,
        body.path,
        recursive=body.recursive,
    )
    audit_log.write(
        action="file.delete",
        outcome="success",
        client_ip=_client_ip(request),
        details={
            "root": body.root,
            "path": body.path,
            "recursive": body.recursive,
        },
    )
    return result


@app.post("/api/files/upload")
def file_upload(
    request: Request,
    _: Auth,
    root: Annotated[str, Form()],
    path: Annotated[str, Form()] = "",
    overwrite: Annotated[bool, Form()] = False,
    upload: UploadFile = File(...),
) -> dict[str, Any]:
    filename = upload.filename or "upload.bin"
    result = file_service.upload(
        root,
        path,
        filename,
        upload.file,
        overwrite=overwrite,
    )
    audit_log.write(
        action="file.upload",
        outcome="success",
        client_ip=_client_ip(request),
        details={
            "root": root,
            "path": result["path"],
            "size": result["size"],
        },
    )
    return result


@app.get("/api/files/search")
def file_search(
    _: Auth,
    root: str = Query(...),
    query: str = Query(..., min_length=2),
    path: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    return {
        "results": file_service.search(
            root,
            query,
            relative_path=path,
            limit=limit,
        )
    }


@app.get("/api/files/download")
def file_download(
    _: Auth,
    root: str = Query(...),
    path: str = Query(...),
):
    _, target = file_service.resolve(root, path, must_exist=True)
    if not target.is_file():
        raise FileServiceError("Đường dẫn không phải file")
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/octet-stream",
    )


@app.get("/api/projects")
def projects(_: Auth) -> dict[str, Any]:
    return {"projects": deploy_service.list_projects()}


@app.post("/api/projects/{project_id}/deploy")
def project_deploy(
    project_id: str,
    body: DeployRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    del body
    return deploy_service.deploy(
        project_id,
        actor="api-key",
        client_ip=_client_ip(request),
    )


@app.get("/api/jobs")
def jobs(
    _: Auth,
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return {"jobs": job_store.list(kind=kind, limit=limit)}


@app.get("/api/jobs/{job_id}")
def job(job_id: str, _: Auth) -> dict[str, Any]:
    try:
        return job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ") from exc


@app.get("/api/backups")
def backups(_: Auth) -> dict[str, Any]:
    return {"backups": backup_service.list()}


@app.post("/api/backups")
def backup_create(
    body: BackupCreateRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    return backup_service.create(
        root_alias=body.root,
        relative_path=body.path,
        label=body.label,
        actor="api-key",
        client_ip=_client_ip(request),
    )


@app.get("/api/backups/{backup_id}/download")
def backup_download(backup_id: str, _: Auth):
    manifest, archive = backup_service.get_archive(backup_id)
    return FileResponse(
        archive,
        filename=manifest["archive"],
        media_type="application/gzip",
    )


@app.delete("/api/backups/{backup_id}")
def backup_delete(
    backup_id: str,
    body: BackupDeleteRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    del body
    backup_service.delete(backup_id)
    audit_log.write(
        action="backup.delete",
        outcome="success",
        client_ip=_client_ip(request),
        details={"backup_id": backup_id},
    )
    return {"deleted": True}


@app.post("/api/backups/{backup_id}/restore")
def backup_restore(
    backup_id: str,
    body: BackupRestoreRequest,
    request: Request,
    _: Auth,
) -> dict[str, Any]:
    return backup_service.restore(
        backup_id=backup_id,
        target_root=body.target_root,
        target_path=body.target_path,
        overwrite=body.overwrite,
        actor="api-key",
        client_ip=_client_ip(request),
    )


@app.get("/api/audit")
def audit(
    _: Auth,
    limit: int = Query(default=200, ge=1, le=2_000),
    action: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "events": audit_log.read(
            limit=limit,
            action=action,
            outcome=outcome,
            search=search,
        )
    }


@app.get("/api/settings")
def safe_settings(_: Auth) -> dict[str, Any]:
    return {
        "version": __version__,
        "managed_roots": file_service.roots(),
        "limits": {
            "max_read_bytes": settings.max_read_bytes,
            "max_write_bytes": settings.max_write_bytes,
            "max_upload_bytes": settings.max_upload_bytes,
        },
        "metrics": {
            "interval_seconds": settings.metrics_interval_seconds,
            "history_points": settings.metrics_history_points,
        },
        "security": {
            "api_key_configured": len(settings.api_key) >= 32,
            "api_key_visible": False,
            "self_container_protected": settings.self_container_name,
        },
        "projects_file": str(settings.projects_file),
        "data_dir": str(settings.data_dir),
    }


app.mount(
    "/",
    StaticFiles(directory=settings.dashboard_dir, html=True),
    name="dashboard",
)
