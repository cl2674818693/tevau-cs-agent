from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def health() -> dict[str, bool]:
    return {"ok": True}
