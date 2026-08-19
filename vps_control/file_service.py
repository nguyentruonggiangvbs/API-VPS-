from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .config import ManagedRoot, settings


class FileServiceError(RuntimeError):
    pass


_TEXT_EXTENSIONS = {
    ".txt", ".md", ".log", ".json", ".jsonl", ".yaml", ".yml", ".toml",
    ".ini", ".conf", ".cfg", ".env", ".py", ".js", ".mjs", ".cjs", ".ts",
    ".tsx", ".jsx", ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".sh", ".bash", ".zsh", ".ps1", ".sql", ".csv", ".xml", ".svg",
    ".dockerfile", ".gitignore", ".gitattributes", ".properties",
}
_SKIP_SEARCH_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".cache", ".venv", "venv", "vendor",
}


class FileService:
    def roots(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for root in settings.managed_roots.values():
            rows.append(
                {
                    "alias": root.alias,
                    "label": root.label,
                    "path": str(root.path),
                    "available": root.path.exists(),
                    "read_only": root.read_only,
                }
            )
        return rows

    def list_directory(
        self,
        alias: str,
        relative_path: str = "",
        *,
        show_hidden: bool = False,
    ) -> dict[str, Any]:
        root, target = self.resolve(alias, relative_path, must_exist=True)
        if not target.is_dir():
            raise FileServiceError("Đường dẫn không phải thư mục")

        entries: list[dict[str, Any]] = []
        try:
            iterator = os.scandir(target)
        except OSError as exc:
            raise FileServiceError(str(exc)) from exc

        with iterator:
            for entry in iterator:
                if not show_hidden and entry.name.startswith("."):
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                mode = info.st_mode
                if stat.S_ISDIR(mode):
                    kind = "directory"
                elif stat.S_ISLNK(mode):
                    kind = "symlink"
                else:
                    kind = "file"
                entries.append(
                    {
                        "name": entry.name,
                        "path": self.relative_path(root, Path(entry.path)),
                        "kind": kind,
                        "size": info.st_size,
                        "modified_at": datetime.fromtimestamp(
                            info.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "mtime_ns": info.st_mtime_ns,
                        "permissions": stat.filemode(mode),
                        "editable": (
                            kind == "file"
                            and self._looks_text(Path(entry.name), info.st_size)
                        ),
                    }
                )

        entries.sort(
            key=lambda item: (
                item["kind"] != "directory",
                item["name"].lower(),
            )
        )
        return {
            "root": root.alias,
            "path": self.relative_path(root, target),
            "read_only": root.read_only,
            "entries": entries,
        }

    def read_file(self, alias: str, relative_path: str) -> dict[str, Any]:
        root, target = self.resolve(alias, relative_path, must_exist=True)
        if not target.is_file():
            raise FileServiceError("Đường dẫn không phải file")

        info = target.stat()
        if info.st_size > settings.max_read_bytes:
            raise FileServiceError(
                f"File vượt quá giới hạn đọc {settings.max_read_bytes} byte"
            )

        payload = target.read_bytes()
        if self._is_binary(payload):
            raise FileServiceError("File nhị phân không thể mở bằng trình soạn thảo")

        text = payload.decode("utf-8", errors="replace")
        preview: dict[str, Any] | None = None
        suffix = target.suffix.lower()
        if suffix == ".json":
            try:
                preview = {"type": "json", "value": json.loads(text)}
            except json.JSONDecodeError:
                preview = {"type": "text"}
        elif suffix == ".csv":
            preview = {
                "type": "csv",
                "rows": self._csv_preview(text),
            }

        return {
            "root": root.alias,
            "path": self.relative_path(root, target),
            "name": target.name,
            "content": text,
            "size": info.st_size,
            "mtime_ns": info.st_mtime_ns,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "read_only": root.read_only,
            "preview": preview,
        }

    def write_file(
        self,
        alias: str,
        relative_path: str,
        content: str,
        *,
        expected_mtime_ns: int | None = None,
        create: bool = False,
    ) -> dict[str, Any]:
        root, target = self.resolve(
            alias, relative_path, must_exist=not create
        )
        self._ensure_writable(root)

        payload = content.encode("utf-8")
        if len(payload) > settings.max_write_bytes:
            raise FileServiceError(
                f"Nội dung vượt quá giới hạn {settings.max_write_bytes} byte"
            )

        if target.exists():
            if not target.is_file():
                raise FileServiceError("Đường dẫn không phải file")
            current = target.stat()
            if (
                expected_mtime_ns is not None
                and current.st_mtime_ns != expected_mtime_ns
            ):
                raise FileServiceError(
                    "File đã thay đổi trên máy chủ. Hãy tải lại trước khi lưu."
                )
            mode = stat.S_IMODE(current.st_mode)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = 0o640

        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, mode)
            os.replace(temp_name, target)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

        info = target.stat()
        return {
            "root": root.alias,
            "path": self.relative_path(root, target),
            "size": info.st_size,
            "mtime_ns": info.st_mtime_ns,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    def create_directory(
        self, alias: str, relative_path: str
    ) -> dict[str, Any]:
        root, target = self.resolve(alias, relative_path, must_exist=False)
        self._ensure_writable(root)
        if target.exists():
            raise FileServiceError("Thư mục hoặc file đã tồn tại")
        target.mkdir(parents=False, exist_ok=False)
        return {
            "root": root.alias,
            "path": self.relative_path(root, target),
        }

    def rename(
        self,
        alias: str,
        relative_path: str,
        new_name: str,
    ) -> dict[str, Any]:
        root, target = self.resolve(alias, relative_path, must_exist=True)
        self._ensure_writable(root)
        self._validate_name(new_name)
        destination = target.with_name(new_name)
        self._assert_inside(root, destination)
        if destination.exists():
            raise FileServiceError("Tên mới đã tồn tại")
        target.rename(destination)
        return {
            "root": root.alias,
            "path": self.relative_path(root, destination),
        }

    def delete(
        self,
        alias: str,
        relative_path: str,
        *,
        recursive: bool,
    ) -> dict[str, Any]:
        root, target = self.resolve(alias, relative_path, must_exist=True)
        self._ensure_writable(root)
        if target.resolve() == root.path.resolve():
            raise FileServiceError("Không được xóa thư mục gốc")

        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
        else:
            raise FileServiceError("Loại file không được hỗ trợ")
        return {"deleted": True}

    def upload(
        self,
        alias: str,
        directory: str,
        filename: str,
        stream: BinaryIO,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        root, target_dir = self.resolve(alias, directory, must_exist=True)
        self._ensure_writable(root)
        if not target_dir.is_dir():
            raise FileServiceError("Đích upload không phải thư mục")
        self._validate_name(filename)

        target = target_dir / filename
        self._assert_inside(root, target)
        if target.exists() and not overwrite:
            raise FileServiceError("File đã tồn tại")

        descriptor, temp_name = tempfile.mkstemp(
            prefix=".upload.",
            suffix=".tmp",
            dir=target_dir,
        )
        total = 0
        try:
            with os.fdopen(descriptor, "wb") as handle:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > settings.max_upload_bytes:
                        raise FileServiceError(
                            "File upload vượt quá giới hạn cho phép"
                        )
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o640)
            os.replace(temp_name, target)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

        return {
            "root": root.alias,
            "path": self.relative_path(root, target),
            "size": total,
        }

    def search(
        self,
        alias: str,
        query: str,
        *,
        relative_path: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        root, start = self.resolve(alias, relative_path, must_exist=True)
        if not start.is_dir():
            raise FileServiceError("Đường dẫn tìm kiếm không phải thư mục")

        query = query.strip().lower()
        if len(query) < 2:
            raise FileServiceError("Từ khóa phải có ít nhất 2 ký tự")
        limit = min(max(limit, 1), 500)
        results: list[dict[str, Any]] = []

        for current, directories, filenames in os.walk(start):
            directories[:] = [
                name
                for name in directories
                if name not in _SKIP_SEARCH_DIRS
            ]
            for name in [*directories, *filenames]:
                if query not in name.lower():
                    continue
                path = Path(current) / name
                try:
                    info = path.lstat()
                except OSError:
                    continue
                results.append(
                    {
                        "name": name,
                        "path": self.relative_path(root, path),
                        "kind": "directory" if path.is_dir() else "file",
                        "size": info.st_size,
                        "modified_at": datetime.fromtimestamp(
                            info.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
                if len(results) >= limit:
                    return results
        return results

    def resolve(
        self,
        alias: str,
        relative_path: str,
        *,
        must_exist: bool,
    ) -> tuple[ManagedRoot, Path]:
        root = settings.managed_roots.get(alias.lower())
        if root is None:
            raise FileServiceError("Thư mục gốc không hợp lệ")

        relative_path = (relative_path or "").strip().replace("\\", "/")
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise FileServiceError("Đường dẫn không hợp lệ")

        candidate = root.path.joinpath(*pure.parts)
        self._assert_inside(root, candidate)

        if must_exist and not candidate.exists() and not candidate.is_symlink():
            raise FileServiceError("Đường dẫn không tồn tại")
        return root, candidate

    @staticmethod
    def relative_path(root: ManagedRoot, target: Path) -> str:
        # Keep the lexical path for UI display. Security-sensitive operations
        # call _assert_inside(), which resolves symlinks before access.
        try:
            return target.absolute().relative_to(
                root.path.absolute()
            ).as_posix()
        except ValueError as exc:
            raise FileServiceError("Đường dẫn vượt ngoài phạm vi cho phép") from exc

    @staticmethod
    def _assert_inside(root: ManagedRoot, target: Path) -> None:
        root_path = root.path.resolve(strict=False)
        candidate = target.resolve(strict=False)
        try:
            candidate.relative_to(root_path)
        except ValueError as exc:
            raise FileServiceError(
                "Đường dẫn vượt ngoài phạm vi cho phép"
            ) from exc

    @staticmethod
    def _ensure_writable(root: ManagedRoot) -> None:
        if root.read_only:
            raise FileServiceError("Thư mục này chỉ cho phép đọc")

    @staticmethod
    def _validate_name(name: str) -> None:
        if (
            not name
            or name in {".", ".."}
            or "/" in name
            or "\\" in name
            or "\x00" in name
            or len(name.encode("utf-8")) > 255
        ):
            raise FileServiceError("Tên file hoặc thư mục không hợp lệ")

    @staticmethod
    def _is_binary(payload: bytes) -> bool:
        sample = payload[:8_192]
        return b"\x00" in sample

    @staticmethod
    def _looks_text(path: Path, size: int) -> bool:
        if size > settings.max_read_bytes:
            return False
        suffix = path.suffix.lower()
        name = path.name.lower()
        return (
            suffix in _TEXT_EXTENSIONS
            or name in {
                "dockerfile", "makefile", "procfile",
                ".env", ".gitignore", ".gitattributes",
            }
            or not suffix
        )

    @staticmethod
    def _csv_preview(text: str) -> list[list[str]]:
        reader = csv.reader(io.StringIO(text))
        rows: list[list[str]] = []
        for index, row in enumerate(reader):
            rows.append(row[:30])
            if index >= 99:
                break
        return rows


file_service = FileService()
