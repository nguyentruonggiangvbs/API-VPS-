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

## GitHub Actions secrets

Cấu hình tại **Settings → Secrets and variables → Actions**:

| Secret | Giá trị |
|---|---|
| `VPS_HOST` | IP/hostname VPS |
| `VPS_PORT` | Cổng SSH, mặc định `22` |
| `VPS_USER` | Tài khoản deploy |
| `VPS_SSH_KEY` | Private key dành riêng cho deploy |
| `VPS_KNOWN_HOSTS` | Kết quả `ssh-keyscan -H -p PORT HOST` lấy từ máy tin cậy |
| `VPS_PROJECT_PATH` | `/opt/api-vps` |
| `VPS_HEALTH_URL` | `http://127.0.0.1:9000/api/health` |
| `VPS_PUBLIC_URL` | URL HTTPS công khai, không bắt buộc |

Nếu thiếu secret, workflow ghi trạng thái chưa kích hoạt và không kết nối VPS.

## Nguyên tắc an toàn

- Strict host-key checking.
- Không dùng mật khẩu SSH trong workflow.
- Không public cổng `9000` hoặc một deploy-agent port.
- Giữ `.env`, `data/`, `config/projects.json` ngoài Git.
- Mỗi lần deploy tạo patch backup các thay đổi local.
- Health check thất bại sẽ reset Git và build lại commit trước.
- Dùng `flock` để ngăn hai deployment chạy đồng thời.
