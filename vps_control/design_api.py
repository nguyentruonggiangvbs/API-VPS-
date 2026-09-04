from __future__ import annotations

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter()

PROFILES = [
    {
        "id": "profile-01",
        "name": "Minimal Clean · Marketplace",
        "category": "Marketplace",
        "style": "Minimal Clean",
        "description": "Ít chi tiết, nhiều khoảng trắng, hierarchy rõ, phù hợp app mua sắm và marketplace.",
        "palette": ["#FFFFFF", "#F5F7FB", "#111827", "#2F6BFF"],
        "apps": ["Market One", "Market Plus", "Shop Flow", "Deal Hub", "Catalog Go", "Cart Studio", "Urban Mart", "Quick Buy", "Selecta", "Bazaar Pro"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Tìm kiếm", "Danh mục", "Chi tiết sản phẩm", "Giỏ hàng/Thanh toán", "Chat/Hỗ trợ", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-02",
        "name": "Soft Minimal · Beauty",
        "category": "Beauty",
        "style": "Soft Minimal",
        "description": "Tối giản mềm mại, thân thiện, phù hợp beauty, makeup, spa và wellness.",
        "palette": ["#FFF9F5", "#FCE8E7", "#7A3F58", "#EF8494"],
        "apps": ["Glow Muse", "Pink Ritual", "Beauty Lane", "Velvet Skin", "Soft Blush", "Aura Studio", "Bloom Care", "Rose Touch", "Pure Glam", "Serene Spa"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Dịch vụ", "Chuyên viên", "Chi tiết dịch vụ", "Đặt lịch", "Chat/Tư vấn", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-03",
        "name": "Editorial · Travel",
        "category": "Travel",
        "style": "Editorial",
        "description": "Typography nổi bật, ảnh truyền cảm hứng, phù hợp du lịch, khám phá và booking.",
        "palette": ["#FFF9F3", "#E9D5C1", "#10233D", "#E56A47"],
        "apps": ["Wander Note", "Trip Canvas", "Nomad Story", "Horizon Go", "Voyage Tale", "Stay Route", "Here Beyond", "Travel Loom", "Terra Diary", "Scenic Book"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Khám phá", "Điểm đến", "Chi tiết địa điểm", "Đặt vé/Đặt phòng", "Chat/Hỗ trợ", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-04",
        "name": "Swiss Grid · Food Delivery",
        "category": "Food Delivery",
        "style": "Swiss Grid",
        "description": "Lưới mạnh, typography chuẩn, bố cục rõ ràng, phù hợp giao đồ ăn và ordering.",
        "palette": ["#FFFDF8", "#F1EEE9", "#101010", "#E52C26"],
        "apps": ["Quick Bite", "Grid Kitchen", "Meal Route", "Box Lunch", "Urban Dish", "Fast Fork", "Order Lane", "Bento Dash", "Daily Tray", "Swift Meal"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Tìm món", "Nhà hàng", "Chi tiết món", "Giỏ hàng", "Theo dõi đơn", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-05",
        "name": "Bento Modular · Fintech",
        "category": "Fintech",
        "style": "Bento Modular",
        "description": "Các khối module rõ ràng, dễ tổng hợp dữ liệu, phù hợp fintech và quản lý tài chính.",
        "palette": ["#F7F8FF", "#E9ECFF", "#171A2C", "#5B5FEF"],
        "apps": ["Bento Pay", "Cash Blocks", "Wallet Grid", "Nova Money", "Ledger One", "Flux Bank", "Coin Nest", "Pocket Line", "Smart Vault", "Fin Box"],
        "screens": ["Onboarding", "Đăng nhập", "Tổng quan", "Ví/Tài khoản", "Giao dịch", "Chi tiết giao dịch", "Chuyển tiền", "Chat/Hỗ trợ", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-06",
        "name": "Glassmorphism · Banking",
        "category": "Banking",
        "style": "Glassmorphism",
        "description": "Hiệu ứng kính mờ hiện đại, sang trọng, phù hợp app ngân hàng và tài chính premium.",
        "palette": ["#091D49", "#183A79", "#F5F8FF", "#72A7FF"],
        "apps": ["Crystal Bank", "Frost Wallet", "Halo Finance", "Clear Credit", "Pearl Bank", "Glass Vault", "Lumi Card", "Nova Trust", "Prism Pay", "Zenith Bank"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Tài khoản", "Thẻ", "Chi tiết tài khoản", "Chuyển khoản", "Chat/Hỗ trợ", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-07",
        "name": "Neumorphism · Healthcare",
        "category": "Healthcare",
        "style": "Neumorphism",
        "description": "Bo tròn mềm, đổ bóng nhẹ, cảm giác thân thiện, phù hợp y tế và sức khỏe.",
        "palette": ["#F2F8F8", "#DFF2EF", "#3C5368", "#69CDBB"],
        "apps": ["Care Soft", "Health Ease", "Pulse Clinic", "Med Touch", "Doctor Flow", "Vital Care", "Soft Remedy", "Heart Line", "Well Doctor", "Gentle Med"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Bác sĩ", "Đặt lịch khám", "Hồ sơ sức khỏe", "Chi tiết bác sĩ", "Tư vấn/Chat", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-08",
        "name": "Neo Brutalism · Fitness",
        "category": "Fitness",
        "style": "Neo Brutalism",
        "description": "Tương phản mạnh, khối táo bạo, năng lượng cao, phù hợp fitness và workout.",
        "palette": ["#111111", "#2B2B2B", "#FFFFFF", "#FFD300"],
        "apps": ["Brut Fit", "Power Blocks", "Lift Mode", "Active Bold", "Pulse Gym", "Strong Pop", "Sprint Core", "Motion Lab", "Smash Fit", "Energy Set"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Bài tập", "Huấn luyện viên", "Chi tiết bài tập", "Lịch tập", "Chat/Cộng đồng", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-09",
        "name": "Dark Premium · Education",
        "category": "Education",
        "style": "Dark Premium",
        "description": "Giao diện tối sang trọng, tập trung nội dung học tập, phù hợp edtech và khóa học.",
        "palette": ["#07111F", "#0E2035", "#F4F7FB", "#E8B548"],
        "apps": ["Night Learn", "Scholar Dark", "Master Class", "Focus Study", "Wise Track", "Learn Prime", "Course Vault", "Deep Skill", "Tutor Noir", "Academy One"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Khóa học", "Bài học", "Chi tiết khóa học", "Bài tập/Kiểm tra", "Chat/Hỏi đáp", "Thông báo", "Cá nhân"],
    },
    {
        "id": "profile-10",
        "name": "Luxury · Real Estate",
        "category": "Real Estate",
        "style": "Luxury",
        "description": "Cao cấp, sang trọng, ảnh lớn và thông tin chọn lọc, phù hợp bất động sản và property.",
        "palette": ["#0D0D0D", "#25231F", "#F7F3EB", "#D4AF37"],
        "apps": ["Luxe Estate", "Prime House", "Gold Living", "Manor View", "Pearl Realty", "Grand Property", "Villa Line", "Urban Luxe", "Elite Home", "Prestige Land"],
        "screens": ["Onboarding", "Đăng nhập", "Trang chủ", "Tìm kiếm", "Bản đồ/Danh sách", "Chi tiết dự án", "Lịch xem nhà", "Chat/Tư vấn", "Thông báo", "Cá nhân"],
    },
]

PROFILE_MAP = {item["id"]: item for item in PROFILES}


def _cors_headers(cache: str = "public, max-age=300") -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": cache,
    }


def _origin(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    scheme = forwarded_proto or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host")
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def _profile_payload(request: Request, profile: dict) -> dict:
    origin = _origin(request)
    apps = []
    for app_index, app_name in enumerate(profile["apps"], start=1):
        app_id = f"app-{app_index:02d}"
        screens = []
        for screen_index, screen_name in enumerate(profile["screens"], start=1):
            screen_id = f"screen-{screen_index:02d}"
            screens.append(
                {
                    "id": screen_id,
                    "name": screen_name,
                    "image": f"{origin}/api/design/v1/screen/{profile['id']}/{app_id}/{screen_id}.svg",
                    "width": 480,
                    "height": 1040,
                    "mime": "image/svg+xml",
                }
            )
        apps.append(
            {
                "id": app_id,
                "name": app_name,
                "cover": screens[2]["image"],
                "screens": screens,
            }
        )
    return {
        "id": profile["id"],
        "name": profile["name"],
        "category": profile["category"],
        "style": profile["style"],
        "description": profile["description"],
        "palette": profile["palette"],
        "app_count": len(apps),
        "screen_count": sum(len(app["screens"]) for app in apps),
        "cover": apps[0]["cover"],
        "apps": apps,
    }


def _text(x: float, y: float, value: str, size: int, color: str, weight: int = 500, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Inter,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>'
    )


def _rect(x: float, y: float, w: float, h: float, fill: str, radius: float = 18, stroke: str = "none", sw: float = 0) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def _screen_svg(profile: dict, app_index: int, screen_index: int) -> str:
    app_name = profile["apps"][app_index - 1]
    screen_name = profile["screens"][screen_index - 1]
    bg, soft, ink, accent = profile["palette"]
    dark = profile["style"] in {"Glassmorphism", "Neo Brutalism", "Dark Premium", "Luxury"}
    if dark:
        bg, soft, ink = profile["palette"][0], profile["palette"][1], profile["palette"][2]
    border = "#DCE3EC" if not dark else "#FFFFFF33"
    muted = "#6B778C" if not dark else "#D7DEEB"
    white = "#FFFFFF"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="1040" viewBox="0 0 480 1040">',
        _rect(0, 0, 480, 1040, bg, 0),
        _text(32, 38, "9:41", 16, ink, 800),
        _text(448, 38, "●  ◒  ▰", 12, ink, 700, "end"),
        _text(32, 88, app_name, 24, ink, 850),
        _text(448, 87, "♡   ◌", 22, ink, 600, "end"),
    ]

    if screen_index == 1:
        parts += [
            _text(240, 235, profile["style"], 17, accent, 800, "middle"),
            _text(240, 286, app_name, 38, ink, 900, "middle"),
            _text(240, 324, profile["category"], 17, muted, 600, "middle"),
            f'<circle cx="240" cy="465" r="100" fill="{accent}" opacity="0.12"/>',
            f'<circle cx="240" cy="465" r="58" fill="{accent}" opacity="0.92"/>',
            _text(240, 476, str(app_index).zfill(2), 30, white, 900, "middle"),
            _rect(42, 755, 396, 62, accent, 20),
            _text(240, 794, "Bắt đầu", 19, white, 800, "middle"),
            _rect(42, 833, 396, 62, bg, 20, border, 1.2),
            _text(240, 872, "Đăng nhập", 18, accent, 750, "middle"),
        ]
    elif screen_index == 2:
        parts += [
            _text(32, 180, "Chào mừng trở lại", 32, ink, 900),
            _text(32, 218, "Đăng nhập để tiếp tục", 16, muted, 500),
            _rect(32, 300, 416, 64, soft, 18, border, 1),
            _text(60, 339, "Email hoặc số điện thoại", 15, muted, 500),
            _rect(32, 382, 416, 64, soft, 18, border, 1),
            _text(60, 421, "Mật khẩu", 15, muted, 500),
            _text(32, 487, "✓  Ghi nhớ đăng nhập", 14, ink, 600),
            _text(448, 487, "Quên mật khẩu?", 14, accent, 700, "end"),
            _rect(32, 530, 416, 62, accent, 20),
            _text(240, 569, "Đăng nhập", 19, white, 800, "middle"),
            _text(240, 650, "Hoặc đăng nhập bằng", 14, muted, 500, "middle"),
        ]
        for i, label in enumerate(["G", "f", "●", "☎"]):
            x = 42 + i * 104
            parts += [_rect(x, 692, 86, 68, bg, 18, border, 1), _text(x + 43, 735, label, 23, accent if i != 2 else ink, 850, "middle")]
    elif screen_index in {3, 4, 5}:
        title = {3: "Khám phá hôm nay", 4: "Tìm kiếm", 5: profile["category"]}[screen_index]
        parts += [
            _text(32, 146, title, 28, ink, 900),
            _rect(32, 170, 416, 56, soft, 16, border, 1),
            _text(58, 205, "⌕  Tìm sản phẩm, dịch vụ...", 14, muted, 500),
        ]
        for i in range(5):
            x = 32 + i * 82
            parts += [_rect(x, 250, 68, 68, soft, 18, border, 1), f'<circle cx="{x+34}" cy="278" r="13" fill="{accent}" opacity="0.85"/>', _text(x + 34, 307, str(i + 1), 11, ink, 700, "middle")]
        parts += [_text(32, 362, "Nổi bật", 19, ink, 850), _text(448, 362, "Xem tất cả", 13, accent, 700, "end")]
        for row in range(3):
            y = 390 + row * 175
            for col in range(2):
                x = 32 + col * 210
                parts += [
                    _rect(x, y, 194, 154, soft, 18, border, 1),
                    _rect(x + 12, y + 12, 170, 83, accent, 14),
                    _text(x + 16, y + 118, f"{profile['category']} {row*2+col+1}", 14, ink, 750),
                    _text(x + 16, y + 140, f"★ 4.{(app_index+row+col)%9+1}   ·   {(row+1)*199}.000đ", 12, muted, 600),
                ]
    elif screen_index == 6:
        parts += [
            _rect(32, 126, 416, 350, soft, 24, border, 1),
            f'<circle cx="240" cy="300" r="118" fill="{accent}" opacity="0.18"/>',
            f'<circle cx="240" cy="300" r="72" fill="{accent}" opacity="0.86"/>',
            _text(240, 312, "★", 46, white, 800, "middle"),
            _text(32, 530, f"{profile['category']} Premium {app_index}", 25, ink, 900),
            _text(32, 568, "★ 4.9   ·   352 đánh giá", 14, muted, 600),
            _text(448, 615, f"{(app_index+5)*990}.000đ", 24, accent, 900, "end"),
            _text(32, 668, "Màu sắc", 15, ink, 800),
        ]
        for i, color in enumerate(profile["palette"]):
            parts.append(f'<circle cx="{58+i*56}" cy="714" r="18" fill="{color}" stroke="{border}" stroke-width="2"/>')
        parts += [_rect(32, 824, 196, 58, bg, 18, accent, 1.5), _text(130, 860, "Thêm vào", 16, accent, 800, "middle"), _rect(244, 824, 204, 58, accent, 18), _text(346, 860, "Tiếp tục", 16, white, 800, "middle")]
    elif screen_index == 7:
        parts += [_text(32, 146, screen_name, 28, ink, 900)]
        for i in range(3):
            y = 190 + i * 156
            parts += [_rect(32, y, 416, 132, soft, 20, border, 1), _rect(46, y + 14, 102, 102, accent, 16), _text(168, y + 44, f"Mục đã chọn {i+1}", 16, ink, 800), _text(168, y + 72, f"{(i+1)*590}.000đ", 15, ink, 700), _text(412, y + 92, "−   1   +", 16, ink, 700, "end")]
        parts += [_text(32, 716, "Tạm tính", 15, muted, 600), _text(448, 716, "4.570.000đ", 15, ink, 800, "end"), _text(32, 752, "Giảm giá", 15, muted, 600), _text(448, 752, "−150.000đ", 15, accent, 800, "end"), _text(32, 806, "Tổng thanh toán", 18, ink, 900), _text(448, 806, "4.450.000đ", 22, ink, 900, "end"), _rect(32, 856, 416, 62, accent, 20), _text(240, 895, "Thanh toán", 18, white, 800, "middle")]
    elif screen_index == 8:
        parts += [_text(32, 142, screen_name, 26, ink, 900), _text(32, 173, "Đang hoạt động", 13, accent, 700)]
        bubbles = [("left", "Xin chào! Tôi có thể hỗ trợ bạn.", 250), ("right", "Tôi muốn kiểm tra trạng thái đơn hàng.", 355), ("left", "Đơn hàng đang được giao và sẽ đến sớm.", 475), ("right", "Cảm ơn bạn!", 590)]
        for side, text, y in bubbles:
            x = 32 if side == "left" else 148
            fill = soft if side == "left" else accent
            color = ink if side == "left" else white
            parts += [_rect(x, y, 300, 78, fill, 20, border if side == "left" else "none", 1), _text(x + 18, y + 34, text[:34], 13, color, 550), _text(x + 18, y + 58, text[34:], 13, color, 550)]
        parts += [_rect(32, 870, 416, 60, soft, 22, border, 1), _text(58, 907, "Nhập tin nhắn...", 14, muted, 500), f'<circle cx="414" cy="900" r="22" fill="{accent}"/>', _text(414, 906, "➤", 16, white, 800, "middle")]
    elif screen_index == 9:
        parts += [_text(32, 146, screen_name, 28, ink, 900), _text(32, 177, "Cập nhật mới nhất", 14, muted, 500)]
        for i in range(6):
            y = 218 + i * 112
            parts += [_rect(32, y, 416, 92, soft, 18, border, 1), f'<circle cx="68" cy="{y+46}" r="22" fill="{accent}" opacity="0.16"/>', _text(68, y + 52, str(i + 1), 13, accent, 850, "middle"), _text(106, y + 37, f"{profile['category']} update {i+1}", 15, ink, 800), _text(106, y + 63, "Thông tin mới dành cho bạn", 13, muted, 500), _text(426, y + 34, f"{i+1}h", 12, muted, 600, "end")]
    else:
        parts += [_text(32, 146, screen_name, 28, ink, 900), _rect(32, 190, 416, 164, soft, 22, border, 1), f'<circle cx="92" cy="250" r="40" fill="{accent}" opacity="0.82"/>', _text(150, 238, f"Người dùng {app_index}", 18, ink, 850), _text(150, 268, f"member@{quote(app_name.lower().replace(' ',''))}.app", 12, muted, 500), _text(150, 298, "Thành viên Premium", 13, accent, 750)]
        items = ["Đơn hàng / Hoạt động", "Đã lưu", "Phương thức thanh toán", "Địa chỉ", "Trung tâm hỗ trợ", "Cài đặt"]
        for i, item in enumerate(items):
            y = 385 + i * 86
            parts += [_rect(32, y, 416, 66, soft, 16, border, 1), _text(58, y + 40, item, 15, ink, 700), _text(420, y + 40, "›", 22, muted, 700, "end")]

    # shared bottom navigation
    parts += [_rect(0, 968, 480, 72, bg, 0, border, 1)]
    for i, nav in enumerate(["Home", "List", "Action", "Chat", "Me"]):
        x = 48 + i * 96
        color = accent if i == min(4, max(0, (screen_index - 3) // 2)) else muted
        parts += [f'<circle cx="{x}" cy="992" r="8" fill="{color}" opacity="0.92"/>', _text(x, 1020, nav, 10, color, 700, "middle")]
    parts.append("</svg>")
    return "".join(parts)


@router.options("/api/design/v1/{path:path}")
def design_options(path: str):
    del path
    return Response(status_code=204, headers=_cors_headers())


@router.get("/api/design/v1/health")
def design_health():
    return JSONResponse(
        {
            "ok": True,
            "service": "app-design-library",
            "profiles": len(PROFILES),
            "apps": len(PROFILES) * 10,
            "screens": len(PROFILES) * 100,
            "image_mode": "one-screen-one-svg",
        },
        headers=_cors_headers("no-store"),
    )


@router.get("/api/design/v1/profiles")
def design_profiles(
    request: Request,
    limit: int = Query(default=10, ge=1, le=10),
):
    payload = [_profile_payload(request, item) for item in PROFILES[:limit]]
    return JSONResponse(
        {
            "ok": True,
            "version": 1,
            "profile_count": len(payload),
            "app_count": sum(item["app_count"] for item in payload),
            "screen_count": sum(item["screen_count"] for item in payload),
            "profiles": payload,
        },
        headers=_cors_headers(),
    )


@router.get("/api/design/v1/profiles/{profile_id}")
def design_profile(profile_id: str, request: Request):
    profile = PROFILE_MAP.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile không tồn tại")
    return JSONResponse(_profile_payload(request, profile), headers=_cors_headers())


@router.get("/api/design/v1/screen/{profile_id}/{app_id}/{screen_id}.svg")
def design_screen(profile_id: str, app_id: str, screen_id: str):
    profile = PROFILE_MAP.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile không tồn tại")
    try:
        app_index = int(app_id.removeprefix("app-"))
        screen_index = int(screen_id.removeprefix("screen-"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Màn hình không tồn tại") from exc
    if not (1 <= app_index <= 10 and 1 <= screen_index <= 10):
        raise HTTPException(status_code=404, detail="Màn hình không tồn tại")
    return Response(
        _screen_svg(profile, app_index, screen_index),
        media_type="image/svg+xml",
        headers=_cors_headers("public, max-age=86400, immutable"),
    )
