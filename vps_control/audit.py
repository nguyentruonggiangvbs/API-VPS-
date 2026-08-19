from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


_SENSITIVE_WORDS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "private_key",
}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _SENSITIVE_WORDS:
                clean[key] = "[redacted]"
            else:
                clean[key] = _sanitize(item)
        return clean
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, str) and len(value) > 8_000:
        return value[:8_000] + "…"
    return value


class AuditLog:
    def __init__(self, path: Path, max_bytes: int = 10 * 1024 * 1024) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def write(
        self,
        *,
        action: str,
        outcome: str,
        actor: str = "api-key",
        client_ip: str = "unknown",
        details: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "outcome": outcome,
            "actor": actor,
            "client_ip": client_ip,
            "details": _sanitize(details or {}),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )

    def read(
        self,
        *,
        limit: int = 200,
        action: str | None = None,
        outcome: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []

        limit = min(max(limit, 1), 2_000)
        query = (search or "").lower().strip()
        results: list[dict[str, Any]] = []

        with self._lock:
            lines = self.path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()

        for line in reversed(lines):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if action and item.get("action") != action:
                continue
            if outcome and item.get("outcome") != outcome:
                continue
            if query and query not in json.dumps(
                item, ensure_ascii=False
            ).lower():
                continue
            results.append(item)
            if len(results) >= limit:
                break
        return results

    def _rotate_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return
        rotated = self.path.with_suffix(self.path.suffix + ".1")
        rotated.unlink(missing_ok=True)
        self.path.replace(rotated)


audit_log = AuditLog(settings.data_dir / "logs" / "audit.jsonl")
