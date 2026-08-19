# API‑VPS Control Center

Bảng điều khiển web dành cho VPS của **ĐI ƠI**, chạy bằng FastAPI + Docker.

## Chức năng

- Dashboard tổng quan CPU, RAM, ổ đĩa, mạng, uptime và cảnh báo.
- Biểu đồ đo lường realtime và danh sách tiến trình.
- File Manager theo các thư mục allowlist:
  - duyệt thư mục;
  - xem/sửa file văn bản;
  - tạo file/thư mục;
  - upload/download;
  - tìm kiếm, đổi tên và xóa;
  - kiểm soát đường dẫn, chống path traversal và symlink thoát root.
- Docker Manager:
  - danh sách container và tài nguyên;
  - start, stop, restart, pause, unpause;
  - xem log;
  - bảo vệ container `api-vps` khỏi tự dừng trong dashboard.
- Deploy Manager:
  - dự án được khai báo trong `config/projects.json`;
  - chỉ chạy project ID có trong allowlist;
  - `git fetch` + fast-forward;
  - Docker Compose hoặc command array allowlist;
  - health check;
  - rollback Git và redeploy khi lỗi.
- Backup Manager:
  - tạo `.tar.gz`;
  - tải về, xóa;
  - khôi phục có xác nhận và kiểm tra đường dẫn archive.
- Audit Log cho các thao tác ghi, Docker, deploy và backup.
- API key qua `Authorization: Bearer` hoặc `X-API-Key`.
- Rate limit cơ bản, security headers, CSP và ẩn secret khỏi log.

## Kiến trúc an toàn

API‑VPS có quyền quản lý Docker socket và các thư mục host được mount. Vì vậy:

1. Không public cổng `9000` trực tiếp mặc định.
2. `docker-compose.yml` bind vào `127.0.0.1`.
3. Truy cập từ xa qua Nginx và **HTTPS**.
4. Không commit `.env`, API key hoặc Git token.
5. Không có web terminal tùy ý.
6. Lệnh deploy chỉ lấy từ `config/projects.json` và executable allowlist.

> Quyền Docker socket tương đương quyền quản trị VPS. Chỉ cấp API key cho người quản trị.

## Cài đặt trên VPS hiện tại

VPS dự kiến:

- Ubuntu 24.04 LTS
- Docker + Docker Compose v2
- source: `/opt/api-vps`
- container hiện có `camera-pc` ở cổng `3000`
- API‑VPS nội bộ ở `127.0.0.1:9000`

Chạy:

```bash
cd /opt/api-vps
git pull --ff-only origin main
chmod +x scripts/*.sh
./scripts/install.sh
```

Script sẽ:

- tạo API key 64 ký tự hex;
- tạo `.env`;
- tạo `config/projects.json`;
- build và chạy container;
- in API key đúng một lần trên Terminal.

Kiểm tra:

```bash
curl http://127.0.0.1:9000/api/health
docker compose ps
```

## Truy cập bằng tên miền và HTTPS

Trỏ DNS về IP VPS, sau đó:

```bash
sudo ./scripts/install-nginx.sh api-vps.example.com
sudo certbot --nginx -d api-vps.example.com
```

Mở:

```text
https://api-vps.example.com
```

Không nhập API key qua HTTP công khai.

## Cập nhật API‑VPS

Container API‑VPS được bảo vệ khỏi self-restart trong dashboard. Cập nhật bằng:

```bash
cd /opt/api-vps
./scripts/update.sh
```

## Cấu hình `.env`

Tạo từ `.env.example`.

| Biến | Ý nghĩa |
|---|---|
| `API_KEY` | Khóa quản trị, tối thiểu 32 ký tự |
| `BIND_ADDRESS` | Mặc định `127.0.0.1` |
| `PORT` | Mặc định `9000` |
| `MANAGED_ROOTS` | Danh sách `alias=/path` phân cách bằng `;` |
| `GIT_HTTP_TOKEN` | Token đọc repo private, không bắt buộc |
| `MAX_READ_BYTES` | Giới hạn editor |
| `MAX_WRITE_BYTES` | Giới hạn lưu editor |
| `MAX_UPLOAD_BYTES` | Giới hạn upload |
| `METRICS_INTERVAL_SECONDS` | Chu kỳ lấy số liệu |
| `METRICS_HISTORY_POINTS` | Số điểm lưu trong RAM |

Ví dụ root chỉ đọc:

```dotenv
MANAGED_ROOTS=opt=/opt;www=/var/www;logs=/var/log:ro
```

## Cấu hình dự án deploy

Sao chép `config/projects.example.json` thành `config/projects.json`.

### Dự án Docker Compose

```json
{
  "id": "camera-pc",
  "name": "Camera PC",
  "root": "opt",
  "path": "camera-pc",
  "branch": "main",
  "mode": "compose",
  "compose_file": "docker-compose.yml",
  "health_url": "http://host.docker.internal:3000/health",
  "enabled": true,
  "protected": false,
  "allow_dirty": false,
  "timeout_seconds": 1200
}
```

### Dự án dùng command array

Không nhận command từ request API. Command phải tồn tại trước trong file cấu hình.

```json
{
  "id": "static-site",
  "name": "Static site",
  "root": "opt",
  "path": "static-site",
  "branch": "main",
  "mode": "commands",
  "commands": [
    ["npm", "ci"],
    ["npm", "run", "build"],
    ["rsync", "-a", "--delete", "{project_dir}/dist/", "/var/www/static-site/"]
  ],
  "health_url": "https://example.com/health",
  "enabled": true,
  "protected": false
}
```

Executable hiện được cho phép:

```text
docker, docker-compose, npm, npx, pnpm, yarn, rsync, cp, mkdir
```

## Repository GitHub riêng tư

Tạo fine-grained Personal Access Token chỉ có quyền **Contents: Read** cho đúng repository rồi đặt trong `.env`:

```dotenv
GIT_HTTP_USERNAME=x-access-token
GIT_HTTP_TOKEN=github_pat_...
```

Không đưa token vào `projects.json`, dashboard hoặc commit.

## API chính

Tất cả endpoint quản trị cần:

```http
Authorization: Bearer <API_KEY>
```

Các nhóm:

```text
GET    /api/overview
GET    /api/system/metrics
GET    /api/system/history
GET    /api/system/processes

GET    /api/files/roots
GET    /api/files/list
GET    /api/files/read
PUT    /api/files/write
POST   /api/files/upload
POST   /api/files/directory
POST   /api/files/rename
DELETE /api/files

GET    /api/docker/containers
POST   /api/docker/containers/{name}/action
GET    /api/docker/containers/{name}/logs

GET    /api/projects
POST   /api/projects/{id}/deploy
GET    /api/jobs/{id}

GET    /api/backups
POST   /api/backups
POST   /api/backups/{id}/restore
DELETE /api/backups/{id}

GET    /api/audit
```

OpenAPI:

```text
/api/docs
/api/openapi.json
```

## Dữ liệu runtime

Không commit các file sau:

```text
.env
data/
config/projects.json
```

`data/` chứa:

```text
data/
├── backups/
├── jobs/
└── logs/audit.jsonl
```

## Phạm vi quản trị

Bản này không cung cấp:

- shell/terminal tùy ý trên trình duyệt;
- xóa Docker image/container;
- chỉnh firewall;
- quản lý tài khoản Linux;
- hiển thị secret/token;
- truy cập ngoài `MANAGED_ROOTS`.

Các chức năng trên có mức rủi ro cao và cần một agent quyền hạn riêng nếu bổ sung sau.
