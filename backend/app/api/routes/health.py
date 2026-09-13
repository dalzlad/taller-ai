from fastapi import APIRouter, status

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    """Liveness endpoint; it does not require a database connection."""
    return {"status": "ok"}
