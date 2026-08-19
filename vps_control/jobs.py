from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


class JobStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(
        self,
        *,
        kind: str,
        target: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "kind": kind,
            "target": target,
            "state": "queued",
            "message": "Đang chờ xử lý",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "metadata": metadata or {},
            "result": None,
        }
        self._write(job)
        self.log(job_id, f"Đã tạo tác vụ {kind} cho {target}")
        return job

    def update(
        self,
        job_id: str,
        *,
        state: str | None = None,
        message: str | None = None,
        result: Any = None,
        started: bool = False,
        finished: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            job = self._read_unlocked(job_id)
            now = datetime.now(timezone.utc).isoformat()
            if state is not None:
                job["state"] = state
            if message is not None:
                job["message"] = message
            if result is not None:
                job["result"] = result
            if started and job.get("started_at") is None:
                job["started_at"] = now
            if finished:
                job["finished_at"] = now
            job["updated_at"] = now
            self._write_unlocked(job)
            return job

    def get(self, job_id: str, include_log: bool = True) -> dict[str, Any]:
        with self._lock:
            job = self._read_unlocked(job_id)
        if include_log:
            job["log"] = self.read_log(job_id)
        return job

    def list(
        self,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        jobs: list[dict[str, Any]] = []
        for path in self.directory.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if kind and item.get("kind") != kind:
                continue
            jobs.append(item)
        jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return jobs[:limit]

    def log(self, job_id: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        line = f"{timestamp} {message.rstrip()}\n"
        path = self._log_path(job_id)
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def read_log(self, job_id: str, limit_bytes: int = 512_000) -> str:
        path = self._log_path(job_id)
        if not path.is_file():
            return ""
        with path.open("rb") as handle:
            size = path.stat().st_size
            if size > limit_bytes:
                handle.seek(-limit_bytes, 2)
            payload = handle.read()
        return payload.decode("utf-8", errors="replace")

    def _read_unlocked(self, job_id: str) -> dict[str, Any]:
        self._validate_id(job_id)
        path = self.directory / f"{job_id}.json"
        if not path.is_file():
            raise KeyError(job_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, job: dict[str, Any]) -> None:
        with self._lock:
            self._write_unlocked(job)

    def _write_unlocked(self, job: dict[str, Any]) -> None:
        path = self.directory / f"{job['id']}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(job, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)

    def _log_path(self, job_id: str) -> Path:
        self._validate_id(job_id)
        return self.directory / f"{job_id}.log"

    @staticmethod
    def _validate_id(job_id: str) -> None:
        if len(job_id) != 32 or any(
            character not in "0123456789abcdef" for character in job_id
        ):
            raise KeyError(job_id)


job_store = JobStore(settings.data_dir / "jobs")
