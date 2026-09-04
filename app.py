from vps_control.app import app
from vps_control.design_api import router as design_router

# Chèn API thư viện thiết kế trước StaticFiles mount ở "/" để các route /api/design/* được ưu tiên.
app.router.routes[0:0] = list(design_router.routes)

__all__ = ["app"]
