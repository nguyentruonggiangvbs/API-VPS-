# Auto Deploy Architecture

## Luồng chính thức

```text
ChatGPT/Codex
      ↓ cập nhật source
GitHub `main`
      ↓ GitHub Actions
SSH key dành riêng
      ↓
VPS `/opt/api-vps`
      ↓
`scripts/deploy-vps.sh`
      ↓
Git fetch + reset có backup
      ↓
Docker Compose build/up
      ↓
Health check
      ├─ thành công → giữ bản mới
      └─ thất bại → rollback commit trước
```

Không mở webhook agent hoặc cổng deploy riêng ra Internet.

## Kích hoạt tự động một lần

Trên VPS, sau khi GitHub CLI đã đăng nhập đúng tài khoản quản trị repository:

```bash
cd /opt/api-vps
git fetch origin main
git reset --hard origin/main
chmod 0755 scripts/*.sh
sudo ./scripts/activate-auto-deploy.sh
```

Script tự tạo user `api-vps-deploy`, SSH key riêng, `authorized_keys`, `known_hosts`, GitHub Actions Secrets và kích hoạt workflow đầu tiên.

Giá trị mặc định đã được cố định cho VPS hiện tại:

```text
repository: nguyentruonggiangvbs/API-VPS-
host:       187.127.124.155
port:       22
project:    /opt/api-vps
health:     http://127.0.0.1:9000/api/health
```

Có thể ghi đè bằng biến môi trường khi chuyển VPS hoặc thay cổng SSH.

## GitHub Actions secrets

Script kích hoạt tự ghi các secret sau:

| Secret | Giá trị |
|---|---|
| `VPS_HOST` | IP/hostname VPS |
| `VPS_PORT` | Cổng SSH, mặc định `22` |
| `VPS_USER` | User deploy riêng |
| `VPS_SSH_KEY` | Private key dành riêng cho deploy |
| `VPS_KNOWN_HOSTS` | SSH host key thật của VPS |
| `VPS_PROJECT_PATH` | `/opt/api-vps` |
| `VPS_HEALTH_URL` | `http://127.0.0.1:9000/api/health` |
| `VPS_PUBLIC_URL` | URL HTTPS công khai, không bắt buộc |

Nếu thiếu secret, workflow ghi trạng thái chưa kích hoạt và không kết nối VPS.

## Nguyên tắc an toàn

- Strict host-key checking.
- Không dùng mật khẩu SSH trong workflow.
- Không public cổng `9000` hoặc deploy-agent port.
- Giữ `.env`, `data`, `config/projects.json` ngoài Git.
- Mỗi lần deploy tạo patch backup thay đổi local.
- Health check thất bại sẽ reset Git và build lại commit trước.
- Dùng `flock` để ngăn hai deployment chạy đồng thời.
- `camera-pc` không nằm trong Compose của API-VPS và không bị restart bởi workflow này.
