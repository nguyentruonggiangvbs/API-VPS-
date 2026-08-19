from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound

from .config import settings


_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class DockerServiceError(RuntimeError):
    pass


class DockerService:
    def __init__(self) -> None:
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env(timeout=15)
                self._client.ping()
            except Exception as exc:
                self._client = None
                raise DockerServiceError(
                    "Không thể kết nối Docker daemon"
                ) from exc
        return self._client

    def available(self) -> bool:
        try:
            return bool(self.client.ping())
        except DockerServiceError:
            return False

    def list_containers(self, include_stats: bool = False) -> list[dict[str, Any]]:
        try:
            containers = self.client.containers.list(all=True)
        except DockerException as exc:
            raise DockerServiceError(str(exc)) from exc

        rows: list[dict[str, Any]] = []
        for container in containers:
            try:
                container.reload()
                attrs = container.attrs
                state = attrs.get("State", {})
                row = {
                    "id": container.short_id,
                    "name": container.name,
                    "image": _image_name(container),
                    "status": container.status,
                    "health": state.get("Health", {}).get("Status"),
                    "created": attrs.get("Created"),
                    "started_at": state.get("StartedAt"),
                    "ports": _format_ports(attrs),
                    "labels": attrs.get("Config", {}).get("Labels") or {},
                    "protected": container.name == settings.self_container_name,
                }
                if include_stats and container.status == "running":
                    row["stats"] = self.stats(container.name)
                rows.append(row)
            except DockerException:
                continue

        rows.sort(
            key=lambda item: (
                item["status"] != "running",
                item["name"].lower(),
            )
        )
        return rows

    def inspect(self, name: str) -> dict[str, Any]:
        container = self._get(name)
        try:
            container.reload()
        except DockerException as exc:
            raise DockerServiceError(str(exc)) from exc
        attrs = container.attrs
        state = attrs.get("State", {})
        config = attrs.get("Config", {})
        host_config = attrs.get("HostConfig", {})
        return {
            "id": container.id,
            "name": container.name,
            "image": _image_name(container),
            "status": container.status,
            "health": state.get("Health", {}).get("Status"),
            "created": attrs.get("Created"),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "restart_count": attrs.get("RestartCount", 0),
            "ports": _format_ports(attrs),
            "environment": _redact_environment(config.get("Env") or []),
            "mounts": [
                {
                    "type": mount.get("Type"),
                    "source": mount.get("Source"),
                    "destination": mount.get("Destination"),
                    "mode": mount.get("Mode"),
                    "rw": mount.get("RW"),
                }
                for mount in attrs.get("Mounts", [])
            ],
            "restart_policy": host_config.get("RestartPolicy"),
            "command": config.get("Cmd"),
            "protected": container.name == settings.self_container_name,
        }

    def stats(self, name: str) -> dict[str, Any]:
        container = self._get(name)
        try:
            data = container.stats(stream=False, one_shot=True)
        except (DockerException, TypeError) as exc:
            raise DockerServiceError(str(exc)) from exc

        cpu_delta = (
            data.get("cpu_stats", {})
            .get("cpu_usage", {})
            .get("total_usage", 0)
            - data.get("precpu_stats", {})
            .get("cpu_usage", {})
            .get("total_usage", 0)
        )
        system_delta = (
            data.get("cpu_stats", {}).get("system_cpu_usage", 0)
            - data.get("precpu_stats", {}).get("system_cpu_usage", 0)
        )
        online_cpus = data.get("cpu_stats", {}).get("online_cpus") or len(
            data.get("cpu_stats", {})
            .get("cpu_usage", {})
            .get("percpu_usage", [])
        )
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta >= 0 and online_cpus:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100

        memory_stats = data.get("memory_stats", {})
        memory_usage = memory_stats.get("usage", 0)
        memory_limit = memory_stats.get("limit", 0)
        cache = memory_stats.get("stats", {}).get(
            "inactive_file",
            memory_stats.get("stats", {}).get("cache", 0),
        )
        working_set = max(memory_usage - cache, 0)
        memory_percent = (
            (working_set / memory_limit) * 100 if memory_limit else 0.0
        )

        networks = data.get("networks") or {}
        received = sum(item.get("rx_bytes", 0) for item in networks.values())
        sent = sum(item.get("tx_bytes", 0) for item in networks.values())

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage": working_set,
            "memory_limit": memory_limit,
            "memory_percent": round(memory_percent, 2),
            "network_received": received,
            "network_sent": sent,
            "block_read": _sum_blkio(
                data, "Read"
            ),
            "block_write": _sum_blkio(
                data, "Write"
            ),
        }

    def action(self, name: str, action: str) -> dict[str, Any]:
        if name == settings.self_container_name:
            raise DockerServiceError(
                "Container API-VPS được bảo vệ. "
                "Hãy cập nhật bằng scripts/update.sh."
            )

        container = self._get(name)
        allowed = {"start", "stop", "restart", "pause", "unpause"}
        if action not in allowed:
            raise DockerServiceError("Hành động Docker không hợp lệ")

        try:
            if action == "start":
                container.start()
            elif action == "stop":
                container.stop(timeout=20)
            elif action == "restart":
                container.restart(timeout=20)
            elif action == "pause":
                container.pause()
            elif action == "unpause":
                container.unpause()
            container.reload()
        except APIError as exc:
            raise DockerServiceError(exc.explanation or str(exc)) from exc

        return {
            "name": container.name,
            "action": action,
            "status": container.status,
        }

    def logs(
        self,
        name: str,
        *,
        tail: int = 300,
        since_seconds: int | None = None,
    ) -> str:
        container = self._get(name)
        tail = min(max(tail, 1), 5_000)
        since = None
        if since_seconds is not None:
            since_seconds = min(max(since_seconds, 1), 7 * 24 * 3600)
            since = int(datetime.now(timezone.utc).timestamp()) - since_seconds
        try:
            payload = container.logs(
                stdout=True,
                stderr=True,
                timestamps=True,
                tail=tail,
                since=since,
            )
        except DockerException as exc:
            raise DockerServiceError(str(exc)) from exc
        return _strip_ansi(payload.decode("utf-8", errors="replace"))

    def images(self) -> list[dict[str, Any]]:
        try:
            images = self.client.images.list()
        except DockerException as exc:
            raise DockerServiceError(str(exc)) from exc
        rows: list[dict[str, Any]] = []
        for image in images:
            attrs = image.attrs
            rows.append(
                {
                    "id": image.short_id,
                    "tags": image.tags,
                    "size": attrs.get("Size", 0),
                    "created": attrs.get("Created"),
                }
            )
        rows.sort(key=lambda item: item.get("created") or "", reverse=True)
        return rows

    def _get(self, name: str):
        if not _NAME_RE.fullmatch(name):
            raise DockerServiceError("Tên container không hợp lệ")
        try:
            return self.client.containers.get(name)
        except NotFound as exc:
            raise DockerServiceError("Không tìm thấy container") from exc
        except DockerException as exc:
            raise DockerServiceError(str(exc)) from exc


def _image_name(container) -> str:
    tags = getattr(container.image, "tags", None) or []
    return tags[0] if tags else container.image.short_id


def _format_ports(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    ports = attrs.get("NetworkSettings", {}).get("Ports") or {}
    for container_port, bindings in ports.items():
        if not bindings:
            result.append(
                {
                    "container": container_port,
                    "host_ip": None,
                    "host_port": None,
                }
            )
            continue
        for binding in bindings:
            result.append(
                {
                    "container": container_port,
                    "host_ip": binding.get("HostIp"),
                    "host_port": binding.get("HostPort"),
                }
            )
    return result


def _redact_environment(items: list[str]) -> list[str]:
    sensitive = ("PASSWORD", "SECRET", "TOKEN", "KEY", "AUTH", "COOKIE")
    result: list[str] = []
    for item in items:
        name, separator, value = item.partition("=")
        if separator and any(word in name.upper() for word in sensitive):
            result.append(f"{name}=[redacted]")
        else:
            result.append(item)
    return result


def _sum_blkio(data: dict[str, Any], operation: str) -> int:
    entries = (
        data.get("blkio_stats", {})
        .get("io_service_bytes_recursive")
        or []
    )
    return sum(
        int(item.get("value", 0))
        for item in entries
        if str(item.get("op", "")).lower() == operation.lower()
    )


_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value)


docker_service = DockerService()
