from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class ManagedRoot:
    alias: str
    path: Path
    label: str
    read_only: bool = False


@dataclass(frozen=True)
class Settings:
    api_key: str
    allow_insecure_api_key: bool
    data_dir: Path
    dashboard_dir: Path
    projects_file: Path
    managed_roots: dict[str, ManagedRoot]
    max_read_bytes: int
    max_write_bytes: int
    max_upload_bytes: int
    metrics_interval_seconds: int
    metrics_history_points: int
    self_container_name: str
    host_hostname_file: Path
    host_os_release_file: Path
    version: str = "1.0.0"

    @classmethod
    def from_env(cls) -> "Settings":
        package_root = Path(__file__).resolve().parent.parent
        data_dir = Path(os.getenv("DATA_DIR", "/data")).resolve()
        dashboard_dir = Path(
            os.getenv("DASHBOARD_DIR", str(package_root / "dashboard"))
        ).resolve()
        projects_file = Path(
            os.getenv("PROJECTS_FILE", "/app/config/projects.json")
        ).resolve()

        roots = _parse_managed_roots(
            os.getenv("MANAGED_ROOTS", "opt=/opt;www=/var/www")
        )

        return cls(
            api_key=os.getenv("API_KEY", "").strip(),
            allow_insecure_api_key=_env_bool("ALLOW_INSECURE_API_KEY", False),
            data_dir=data_dir,
            dashboard_dir=dashboard_dir,
            projects_file=projects_file,
            managed_roots=roots,
            max_read_bytes=_env_int(
                "MAX_READ_BYTES", 2 * 1024 * 1024, 1024, 20 * 1024 * 1024
            ),
            max_write_bytes=_env_int(
                "MAX_WRITE_BYTES", 4 * 1024 * 1024, 1024, 50 * 1024 * 1024
            ),
            max_upload_bytes=_env_int(
                "MAX_UPLOAD_BYTES",
                100 * 1024 * 1024,
                1024,
                2 * 1024 * 1024 * 1024,
            ),
            metrics_interval_seconds=_env_int(
                "METRICS_INTERVAL_SECONDS", 5, 2, 60
            ),
            metrics_history_points=_env_int(
                "METRICS_HISTORY_POINTS", 720, 60, 20_000
            ),
            self_container_name=os.getenv(
                "SELF_CONTAINER_NAME", "api-vps"
            ).strip(),
            host_hostname_file=Path(
                os.getenv("HOST_HOSTNAME_FILE", "/host/etc/hostname")
            ),
            host_os_release_file=Path(
                os.getenv("HOST_OS_RELEASE_FILE", "/host/etc/os-release")
            ),
        )

    def validate(self) -> None:
        if not self.allow_insecure_api_key:
            if len(self.api_key) < 32:
                raise RuntimeError(
                    "API_KEY must contain at least 32 characters. "
                    "Run scripts/install.sh to generate one."
                )
            weak_values = {
                "change-me",
                "changeme",
                "password",
                "api-key",
                "secret",
                "12345678901234567890123456789012",
            }
            if self.api_key.lower() in weak_values:
                raise RuntimeError("API_KEY is not secure")

        if not self.dashboard_dir.is_dir():
            raise RuntimeError(
                f"Dashboard directory does not exist: {self.dashboard_dir}"
            )

        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "backups").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)

    @property
    def disk_probe_path(self) -> Path:
        for root in self.managed_roots.values():
            if root.path.exists():
                return root.path
        return Path("/")


def _parse_managed_roots(raw: str) -> dict[str, ManagedRoot]:
    roots: dict[str, ManagedRoot] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise RuntimeError(
                "MANAGED_ROOTS entries must use alias=/absolute/path[:ro]"
            )
        alias, path_value = item.split("=", 1)
        alias = alias.strip().lower()
        path_value = path_value.strip()

        if not alias or not alias.replace("-", "").replace("_", "").isalnum():
            raise RuntimeError(f"Invalid managed root alias: {alias!r}")

        read_only = False
        if path_value.endswith(":ro"):
            read_only = True
            path_value = path_value[:-3]

        path = Path(path_value)
        if not path.is_absolute():
            raise RuntimeError(
                f"Managed root {alias!r} must use an absolute path"
            )

        roots[alias] = ManagedRoot(
            alias=alias,
            path=path,
            label=alias.replace("_", " ").replace("-", " ").title(),
            read_only=read_only,
        )

    if not roots:
        raise RuntimeError("At least one managed root is required")
    return roots


settings = Settings.from_env()
