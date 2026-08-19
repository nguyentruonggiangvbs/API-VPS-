# Changelog

## 1.0.0 — 2026-08-19

### Added

- Production-ready FastAPI VPS Control Center.
- Responsive dashboard with overview, monitoring, file, Docker, deploy, backup, audit and settings views.
- Allowlisted File Manager with traversal and symlink escape protection.
- Docker lifecycle, stats and log management.
- Project deployment jobs with health checks and rollback.
- Backup creation, download, delete and restore.
- API key authentication, rate limiting, CSP, security headers and audit logging.
- Nginx/HTTPS templates and installation scripts.
- CI checks for Python, JavaScript, shell, repository security, Docker Compose and container smoke tests.
- SSH-based auto deployment with strict host verification, deployment lock, local-diff backup, health verification and rollback.
- One-time activation script that creates a dedicated deploy user/key, writes GitHub Actions Secrets and triggers the initial deployment.

### Removed

- Unauthenticated legacy `/control` router.
- Duplicate unsafe file/Docker helper modules.
- Shell-based web terminal prototype.
- Public deploy-agent/webhook port architecture.

### Security

- API binds `127.0.0.1` by default.
- Runtime secrets and data remain outside Git.
- Deployment uses a dedicated SSH key and strict `known_hosts`.
