# VPS Security Baseline

## Network

- API-VPS bind `127.0.0.1:9000` mặc định.
- Chỉ Nginx được public qua `80/443`.
- Bắt buộc HTTPS trước khi nhập API key.
- Không mở cổng deploy agent hoặc Docker API TCP.
- SSH nên giới hạn theo key, tắt đăng nhập mật khẩu sau khi xác nhận key hoạt động.

## Authentication

- `API_KEY` tối thiểu 32 ký tự; installer tạo 64 ký tự hex.
- Lưu API key trong password manager, không commit hoặc chụp màn hình.
- Đổi API key định kỳ và ngay khi nghi ngờ lộ.
- GitHub Actions dùng SSH key riêng, không dùng key root cá nhân.
- `VPS_KNOWN_HOSTS` phải lấy từ máy quản trị tin cậy.

## Docker

`/var/run/docker.sock` tương đương quyền quản trị VPS.

- Chỉ container `api-vps` được mount socket.
- Container dùng `read_only`, `no-new-privileges` và bind localhost.
- Không public Docker daemon TCP.
- Container `api-vps` được đánh dấu protected khỏi self-stop trong dashboard.

## File Manager

- Chỉ truy cập root trong `MANAGED_ROOTS`.
- Root nhạy cảm nên cấu hình `:ro`.
- Không thêm `/`, `/etc`, `/root` hoặc `/var/lib/docker` làm root ghi.
- Audit log mọi thao tác ghi, đổi tên, xóa, deploy và restore.

## Deployment

- GitHub Actions kết nối SSH với strict host-key checking.
- `scripts/deploy-vps.sh` dùng `flock`, backup local diff, health check và rollback.
- `.env`, `data/`, `config/projects.json` được giữ ngoài Git.
- Không dùng webhook agent có secret mặc định.

## Backup

- Backup cục bộ không thay thế backup ngoài VPS.
- Định kỳ sao chép backup mã hóa sang nơi lưu trữ khác.
- Kiểm tra restore trên môi trường thử nghiệm.

## Checklist production

- [ ] GitHub Actions secrets đã cấu hình.
- [ ] SSH key deploy riêng hoạt động.
- [ ] Nginx + HTTPS hoạt động.
- [ ] Port `9000` không public.
- [ ] UFW chỉ mở cổng cần thiết.
- [ ] API key đã lưu an toàn.
- [ ] `MANAGED_ROOTS` đã rà soát.
- [ ] Backup ngoài VPS đã cấu hình.
- [ ] Audit log được kiểm tra định kỳ.
