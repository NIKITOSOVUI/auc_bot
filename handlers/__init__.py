from .common import router as common_router
from .admin import router as admin_router
from .auction import router as auction_router

routers = [common_router, admin_router, auction_router]