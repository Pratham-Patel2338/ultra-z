from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
def status_check() -> dict[str, bool | str]:
    return {"online": True, "message": "ULTRA-Z backend is online"}
