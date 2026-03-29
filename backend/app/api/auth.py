from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.services.steam_openid import get_login_redirect_url, verify_and_get_steam_id
from app.services.jwt_utils import create_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_CALLBACK_URL = f"{settings.base_url}/api/auth/callback"


class WalletUpdate(BaseModel):
    wallet_address: str


@router.get("/steam")
def steam_login():
    url = get_login_redirect_url(_CALLBACK_URL, settings.base_url)
    return RedirectResponse(url)


@router.get("/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    steam_id = await verify_and_get_steam_id(params)
    if not steam_id:
        raise HTTPException(status_code=400, detail="Steam auth failed")

    user = db.query(User).filter(User.steam_id == steam_id).first()
    if not user:
        user = User(steam_id=steam_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_token(steam_id)
    response = RedirectResponse(url=f"{settings.base_url}/")
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.jwt_expire_hours * 3600,
    )
    return response


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "steam_id": user.steam_id,
        "wallet_address": user.wallet_address,
        "created_at": user.created_at,
    }


@router.post("/wallet")
def set_wallet(
    body: WalletUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = body.wallet_address.strip().lower()
    if not addr.startswith("0x") or len(addr) != 42:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    user.wallet_address = addr
    db.commit()
    return {"wallet_address": user.wallet_address}


@router.post("/logout")
def logout():
    response = RedirectResponse(url=f"{settings.base_url}/")
    response.delete_cookie("session")
    return response
