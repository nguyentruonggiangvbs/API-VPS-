from __future__ import annotations

import asyncio
import os
import platform
import socket
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from .config import settings


def _read_key_value_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def _read_text(path: Path, fallback: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
        return value or fallback
    except OSError:
        return fallback


class MetricsCollector:
    def __init__(self) -> None:
        self.history: deque[dict[str, Any]] = deque(
            maxlen=settings.metrics_history_points
        )
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_net: tuple[float, int, int] | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        psutil.cpu_percent(interval=None)
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.history.append(self.snapshot())
            except Exception:
                # Monitoring must never take down the control plane.
                pass
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=settings.metrics_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    def snapshot(self) -> dict[str, Any]:
        now_monotonic = time.monotonic()
        now = datetime.now(timezone.utc)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage(str(settings.disk_probe_path))
        network = psutil.net_io_counters()
        cpu_percent = psutil.cpu_percent(interval=None)
        load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

        recv_rate = 0.0
        sent_rate = 0.0
        if self._last_net:
            last_time, last_recv, last_sent = self._last_net
            elapsed = max(now_monotonic - last_time, 0.001)
            recv_rate = max(network.bytes_recv - last_recv, 0) / elapsed
            sent_rate = max(network.bytes_sent - last_sent, 0) / elapsed
        self._last_net = (
            now_monotonic,
            network.bytes_recv,
            network.bytes_sent,
        )

        uptime_seconds = max(time.time() - psutil.boot_time(), 0)

        return {
            "timestamp": now.isoformat(),
            "cpu": {
                "percent": round(cpu_percent, 2),
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
                "load_1": round(load[0], 2),
                "load_5": round(load[1], 2),
                "load_15": round(load[2], 2),
            },
            "memory": {
                "total": memory.total,
                "used": memory.used,
                "available": memory.available,
                "percent": round(memory.percent, 2),
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "percent": round(swap.percent, 2),
            },
            "disk": {
                "path": str(settings.disk_probe_path),
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": round(disk.percent, 2),
            },
            "network": {
                "bytes_received": network.bytes_recv,
                "bytes_sent": network.bytes_sent,
                "receive_bytes_per_second": round(recv_rate, 2),
                "send_bytes_per_second": round(sent_rate, 2),
                "packets_received": network.packets_recv,
                "packets_sent": network.packets_sent,
                "errors_in": network.errin,
                "errors_out": network.errout,
            },
            "uptime_seconds": int(uptime_seconds),
        }

    def host_info(self) -> dict[str, Any]:
        os_release = _read_key_value_file(settings.host_os_release_file)
        hostname = _read_text(
            settings.host_hostname_file,
            socket.gethostname(),
        )
        return {
            "hostname": hostname,
            "operating_system": os_release.get(
                "PRETTY_NAME", platform.platform()
            ),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "boot_time": datetime.fromtimestamp(
                psutil.boot_time(), tz=timezone.utc
            ).isoformat(),
        }

    def recent(self, limit: int = 120) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), settings.metrics_history_points)
        return list(self.history)[-limit:]

    def processes(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 200)
        rows: list[dict[str, Any]] = []

        for process in psutil.process_iter(
            ["pid", "name", "username", "cpu_percent", "memory_percent", "status"]
        ):
            try:
                info = process.info
                rows.append(
                    {
                        "pid": info.get("pid"),
                        "name": info.get("name") or "unknown",
                        "username": info.get("username") or "unknown",
                        "cpu_percent": round(
                            float(info.get("cpu_percent") or 0), 2
                        ),
                        "memory_percent": round(
                            float(info.get("memory_percent") or 0), 2
                        ),
                        "status": info.get("status") or "unknown",
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        rows.sort(
            key=lambda item: (
                item["cpu_percent"],
                item["memory_percent"],
            ),
            reverse=True,
        )
        return rows[:limit]

    @staticmethod
    def alerts(snapshot: dict[str, Any]) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        thresholds = (
            ("cpu", snapshot["cpu"]["percent"], 90, 75),
            ("memory", snapshot["memory"]["percent"], 90, 80),
            ("disk", snapshot["disk"]["percent"], 90, 80),
        )
        labels = {
            "cpu": "CPU",
            "memory": "RAM",
            "disk": "Ổ đĩa",
        }
        for key, value, critical, warning in thresholds:
            if value >= critical:
                alerts.append(
                    {
                        "level": "critical",
                        "title": f"{labels[key]} đang ở mức nguy hiểm",
                        "message": f"{value:.1f}% đang được sử dụng",
                    }
                )
            elif value >= warning:
                alerts.append(
                    {
                        "level": "warning",
                        "title": f"{labels[key]} đang tải cao",
                        "message": f"{value:.1f}% đang được sử dụng",
                    }
                )
        return alerts


metrics_collector = MetricsCollector()
