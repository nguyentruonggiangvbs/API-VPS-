# Triển khai API-VPS

## Trạng thái chuẩn

- Repository: `nguyentruonggiangvbs/API-VPS-`
- Nhánh production: `main`
- VPS project path: `/opt/api-vps`
- API nội bộ: `127.0.0.1:9000`
- Health check: `/api/health`
- Dashboard: `/`
- Runtime:
  - `.env`
  - `config/projects.json`
  - `data/`
- Các file runtime không được commit.

## Cài đặt lần đầu trên VPS

```bash
cd /opt/api-vps
git fetch origin main
git reset --hard origin/main
chmod 0755 scripts/*.sh
./scripts/install.sh
```

Kiểm tra:

```bash
curl -fsS http://127.0.0.1:9000/api/health
docker compose ps
```

`install.sh` tạo API key an toàn và chỉ in một lần. Lưu khóa trong trình quản lý mật khẩu.

## Nginx và HTTPS

API mặc định chỉ bind localhost. Trỏ tên miền về VPS rồi chạy:

```bash
sudo ./scripts/install-nginx.sh api-vps.example.com
sudo certbot --nginx -d api-vps.example.com
```

Không nhập API key qua HTTP công khai.

## Deploy thủ công có rollback

```bash
cd /opt/api-vps
./scripts/deploy-vps.sh \
  /opt/api-vps \
  main \
  http://127.0.0.1:9000/api/health
```

Script:

1. khóa deployment bằng `flock`;
2. backup trạng thái Git và local diff;
3. fetch `origin/main`;
4. reset source về commit đã duyệt;
5. giữ nguyên `.env`, `data/`, `config/projects.json`;
6. build và khởi động Docker Compose;
7. health check;
8. rollback commit trước nếu lỗi;
9. ghi trạng thái vào `data/deploy/status.json`.

## Auto deploy GitHub → VPS

Workflow:

```text
.github/workflows/deploy-vps.yml
```

Workflow dùng SSH key dành riêng và gọi `scripts/deploy-vps.sh` từ source đã checkout. Xem danh sách secret trong `docs/AUTO-DEPLOY-ARCHITECTURE.md`.

## Khôi phục khi workflow không chạy được

```bash
cd /opt/api-vps
git fetch origin main
./scripts/deploy-vps.sh
```

Xem log:

```bash
ls -1t data/deploy/logs | head
tail -n 200 data/deploy/logs/<file>.log
docker compose logs --tail=250 api-vps
```

## Không triển khai bằng các cách sau

- Không `curl | bash` từ nguồn không xác minh.
- Không mở port deploy agent.
- Không dùng `git pull` khi working tree có thay đổi mà không backup.
- Không commit API key, PAT, SSH key hoặc `.env`.
- Không bind `9000` ra `0.0.0.0` trên production.
