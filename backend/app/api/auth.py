from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/steam")
def steam_login():
    return {"status": "stub", "message": "Steam auth — этап 2"}


@router.get("/steam/callback")
def steam_callback():
    return {"status": "stub", "message": "Steam callback — этап 2"}
