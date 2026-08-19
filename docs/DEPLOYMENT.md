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

## Kích hoạt GitHub → VPS tự động một lần

Điều kiện:

- chạy bằng `root` trên VPS;
- GitHub CLI đã đăng nhập đúng tài khoản có quyền quản trị repository;
- Docker, Docker Compose, Git và OpenSSH đã hoạt động.

Kiểm tra GitHub CLI:

```bash
gh auth status -h github.com
```

Sau đó chạy:

```bash
cd /opt/api-vps
git fetch origin main
git reset --hard origin/main
chmod 0755 scripts/*.sh
sudo ./scripts/activate-auto-deploy.sh
```

Script tự động:

1. tạo user giới hạn quyền `api-vps-deploy`;
2. thêm user vào group Docker;
3. tạo SSH key Ed25519 riêng cho GitHub Actions;
4. cài public key vào `authorized_keys`;
5. tạo `known_hosts` từ SSH host key thật của chính VPS;
6. ghi toàn bộ GitHub Actions Secrets qua `gh secret set`;
7. kích hoạt workflow deploy production lần đầu.

Không gửi hoặc commit private key, API key hay GitHub token.

Theo mặc định production bind vào `127.0.0.1:9000`. Sau khi cập nhật, truy cập trực tiếp bằng `http://IP:9000` sẽ không còn hoạt động; đây là hành vi bảo mật đúng.

## Nginx và HTTPS

Trỏ tên miền về VPS rồi chạy:

```bash
sudo ./scripts/install-nginx.sh api-vps.example.com
sudo certbot --nginx -d api-vps.example.com
```

Sau đó mở dashboard bằng HTTPS qua tên miền. Không nhập API key qua HTTP công khai.

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
5. giữ nguyên `.env`, `data`, `config/projects.json`;
6. build và khởi động Docker Compose;
7. health check;
8. rollback commit trước nếu lỗi;
9. ghi trạng thái vào `data/deploy/status.json`.

## Auto deploy GitHub → VPS

Workflow:

```text
.github/workflows/deploy-vps.yml
```

Workflow dùng SSH key dành riêng, strict host-key checking và gọi `scripts/deploy-vps.sh` từ source đã checkout. Xem chi tiết trong `docs/AUTO-DEPLOY-ARCHITECTURE.md`.

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
