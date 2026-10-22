from fastapi import APIRouter

from app.api.v1.endpoints import assignments, audit, auth, clients, health, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(assignments.router)
api_router.include_router(clients.router)
api_router.include_router(audit.router)
