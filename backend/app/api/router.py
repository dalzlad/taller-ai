from fastapi import APIRouter

from app.api.routes.customers import router as customers_router
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.evidences import diagnostic_router as diagnostic_evidences_router
from app.api.routes.evidences import router as evidences_router
from app.api.routes.health import router as health_router
from app.api.routes.vehicles import router as vehicles_router
from app.api.routes.work_orders import router as work_orders_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(customers_router)
api_router.include_router(vehicles_router)
api_router.include_router(diagnostics_router)
api_router.include_router(diagnostic_evidences_router)
api_router.include_router(evidences_router)
api_router.include_router(work_orders_router)
