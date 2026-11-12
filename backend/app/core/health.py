"""
Health check endpoint.

GET /health — no auth required.
Used by:
  - GitHub Actions CI/CD (curl health check after deploy)
  - Docker HEALTHCHECK instruction
  - AWS ALB / Route 53 health checks (if added later)
"""
from fastapi import APIRouter

from app.core.tally_tunnel import tunnel_manager

router = APIRouter()


@router.get("/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "connected_tally_clients": len(tunnel_manager.connected_clients()),
    }