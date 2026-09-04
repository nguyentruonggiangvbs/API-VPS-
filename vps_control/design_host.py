from __future__ import annotations

from .app import app
from .design_api import router as design_router

# Core app mounts the dashboard at "/" as its final route. Insert the public
# design-library routes immediately before that catch-all mount so existing
# API-VPS behavior and lifespan remain unchanged.
try:
    dashboard_index = next(
        index
        for index, route in enumerate(app.router.routes)
        if getattr(route, "name", None) == "dashboard"
    )
except StopIteration:
    dashboard_index = len(app.router.routes)

app.router.routes[dashboard_index:dashboard_index] = list(design_router.routes)

__all__ = ["app"]
