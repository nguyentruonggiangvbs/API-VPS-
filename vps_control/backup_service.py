from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import audit_log
from .config import settings
from .file_service import FileServiceError, file_service
from .jobs import job_store


class BackupServiceError(RuntimeError):
    pass


_EXCLUDED_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".cache",
    ".venv",
    "venv",
}


class BackupService:
    def __init__(self) -> None:
        self.directory = settings.data_dir / "backups"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(
        self,
        *,
        root_alias: str,
        relative_path: str,
        label: str,
        actor: str,
        client_ip: str,
    ) -> dict[str, Any]:
        try:
            _, source = file_service.resolve(
                root_alias,
                relative_path,
                must_exist=True,
            )
        except FileServiceError as exc:
            raise BackupServiceError(str(exc)) from exc

        job = job_store.create(
            kind="backup",
            target=f"{root_alias}:{relative_path}",
            metadata={"label": label},
        )
        thread = threading.Thread(
            target=self._create_worker,
            args=(
                job["id"],
                root_alias,
                relative_path,
                source,
                label,
                actor,
                client_ip,
            ),
            daemon=True,
            name=f"backup-{job['id'][:8]}",
        )
        thread.start()
        return job

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for manifest_path in self.directory.glob("*.json"):
            try:
                item = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            archive = self.directory / item.get("archive", "")
            item["available"] = archive.is_file()
            item["size"] = archive.stat().st_size if archive.is_file() else 0
            rows.append(item)
        rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return rows

    def get_archive(self, backup_id: str) -> tuple[dict[str, Any], Path]:
        manifest = self._manifest(backup_id)
        archive = self.directory / manifest["archive"]
        if not archive.is_file():
            raise BackupServiceError("Không tìm thấy file backup")
        return manifest, archive

    def delete(self, backup_id: str) -> None:
        manifest = self._manifest(backup_id)
        archive = self.directory / manifest["archive"]
        archive.unlink(missing_ok=True)
        (self.directory / f"{backup_id}.json").unlink(missing_ok=True)

    def restore(
        self,
        *,
        backup_id: str,
        target_root: str,
        target_path: str,
        overwrite: bool,
        actor: str,
        client_ip: str,
    ) -> dict[str, Any]:
        manifest, archive = self.get_archive(backup_id)
        try:
            root, target = file_service.resolve(
                target_root,
                target_path,
                must_exist=False,
            )
        except FileServiceError as exc:
            raise BackupServiceError(str(exc)) from exc
        if root.read_only:
            raise BackupServiceError("Thư mục đích chỉ cho phép đọc")
        target.parent.mkdir(parents=True, exist_ok=True)

        target_has_data = False
        if target.exists():
            target_has_data = (
                any(target.iterdir()) if target.is_dir() else True
            )
        if target_has_data and not overwrite:
            raise BackupServiceError(
                "Đích đã có dữ liệu. Bật overwrite để xác nhận ghi đè."
            )

        job = job_store.create(
            kind="restore",
            target=f"{target_root}:{target_path}",
            metadata={
                "backup_id": backup_id,
                "source": manifest.get("source"),
                "overwrite": overwrite,
            },
        )
        thread = threading.Thread(
            target=self._restore_worker,
            args=(
                job["id"],
                backup_id,
                archive,
                target,
                overwrite,
                actor,
                client_ip,
            ),
            daemon=True,
            name=f"restore-{job['id'][:8]}",
        )
        thread.start()
        return job

    def _create_worker(
        self,
        job_id: str,
        root_alias: str,
        relative_path: str,
        source: Path,
        label: str,
        actor: str,
        client_ip: str,
    ) -> None:
        backup_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc)
        safe_label = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in label.strip()
        )[:40] or "manual"
        archive_name = (
            f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-"
            f"{safe_label}-{backup_id[:8]}.tar.gz"
        )
        archive_path = self.directory / archive_name
        temp_path = archive_path.with_suffix(".tar.gz.tmp")

        try:
            job_store.update(
                job_id,
                state="running",
                message="Đang tạo backup",
                started=True,
            )
            job_store.log(job_id, f"Nguồn: {source}")
            with tarfile.open(temp_path, "w:gz") as tar:
                tar.add(
                    source,
                    arcname=source.name,
                    recursive=True,
                    filter=self._tar_filter,
                )
            temp_path.replace(archive_path)
            manifest = {
                "id": backup_id,
                "label": label,
                "created_at": timestamp.isoformat(),
                "source": {
                    "root": root_alias,
                    "path": relative_path,
                    "name": source.name,
                },
                "archive": archive_name,
                "size": archive_path.stat().st_size,
            }
            (self.directory / f"{backup_id}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            job_store.update(
                job_id,
                state="success",
                message="Tạo backup thành công",
                result=manifest,
                finished=True,
            )
            job_store.log(job_id, f"Backup: {archive_name}")
            audit_log.write(
                action="backup.create",
                outcome="success",
                actor=actor,
                client_ip=client_ip,
                details={
                    "backup_id": backup_id,
                    "root": root_alias,
                    "path": relative_path,
                    "size": manifest["size"],
                },
            )
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            job_store.update(
                job_id,
                state="failed",
                message="Tạo backup thất bại",
                result={"error": str(exc)},
                finished=True,
            )
            job_store.log(job_id, f"LỖI: {exc}")
            audit_log.write(
                action="backup.create",
                outcome="failed",
                actor=actor,
                client_ip=client_ip,
                details={"error": str(exc)},
            )

    def _restore_worker(
        self,
        job_id: str,
        backup_id: str,
        archive: Path,
        target: Path,
        overwrite: bool,
        actor: str,
        client_ip: str,
    ) -> None:
        temp_dir = Path(
            tempfile.mkdtemp(prefix=".restore-", dir=target.parent)
        )
        try:
            job_store.update(
                job_id,
                state="running",
                message="Đang khôi phục backup",
                started=True,
            )
            job_store.log(job_id, f"Backup: {archive.name}")
            with tarfile.open(archive, "r:gz") as tar:
                self._validate_archive(tar)
                tar.extractall(temp_dir, filter="data")

            extracted = list(temp_dir.iterdir())
            if len(extracted) != 1:
                raise BackupServiceError(
                    "Cấu trúc backup không hợp lệ"
                )
            source = extracted[0]

            if target.exists():
                if target.is_dir():
                    if overwrite:
                        shutil.rmtree(target)
                    elif any(target.iterdir()):
                        raise BackupServiceError("Thư mục đích không trống")
                    else:
                        target.rmdir()
                else:
                    if overwrite:
                        target.unlink()
                    else:
                        raise BackupServiceError("File đích đã tồn tại")

            source.replace(target)
            job_store.update(
                job_id,
                state="success",
                message="Khôi phục thành công",
                result={
                    "backup_id": backup_id,
                    "target": str(target),
                },
                finished=True,
            )
            job_store.log(job_id, f"Đã khôi phục vào {target}")
            audit_log.write(
                action="backup.restore",
                outcome="success",
                actor=actor,
                client_ip=client_ip,
                details={
                    "backup_id": backup_id,
                    "target": str(target),
                },
            )
        except Exception as exc:
            job_store.update(
                job_id,
                state="failed",
                message="Khôi phục thất bại",
                result={"error": str(exc)},
                finished=True,
            )
            job_store.log(job_id, f"LỖI: {exc}")
            audit_log.write(
                action="backup.restore",
                outcome="failed",
                actor=actor,
                client_ip=client_ip,
                details={
                    "backup_id": backup_id,
                    "error": str(exc),
                },
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        path_parts = Path(info.name).parts
        if any(part in _EXCLUDED_NAMES for part in path_parts):
            return None
        return info

    @staticmethod
    def _validate_archive(tar: tarfile.TarFile) -> None:
        for member in tar.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise BackupServiceError(
                    "Backup chứa đường dẫn không an toàn"
                )
            if member.issym() or member.islnk():
                link = Path(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise BackupServiceError(
                        "Backup chứa symlink không an toàn"
                    )

    def _manifest(self, backup_id: str) -> dict[str, Any]:
        if len(backup_id) != 32 or any(
            char not in "0123456789abcdef" for char in backup_id
        ):
            raise BackupServiceError("Backup id không hợp lệ")
        path = self.directory / f"{backup_id}.json"
        if not path.is_file():
            raise BackupServiceError("Không tìm thấy backup")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupServiceError("Manifest backup bị lỗi") from exc


backup_service = BackupService()
