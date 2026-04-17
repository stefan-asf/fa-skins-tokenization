from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_current_user
from app.db import get_db
from app.models.deposit import Deposit
from app.models.user import User

router = APIRouter(prefix="/deposit", tags=["deposit"])


class AssetInput(BaseModel):
    asset_id: str = Field(..., min_length=1, max_length=32)
    skin_name: str = Field(..., min_length=1, max_length=256)


class DepositRequest(BaseModel):
    assets: List[AssetInput] = Field(..., min_length=1, max_length=50)


@router.post("")
def create_deposit(
    body: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet address not set")
    if not current_user.steam_trade_url:
        raise HTTPException(status_code=400, detail="Steam trade URL not set")

    deposits = []
    for asset in body.assets:
        d = Deposit(
            steam_id=current_user.steam_id,
            wallet_address=current_user.wallet_address,
            asset_id=asset.asset_id,
            skin_name=asset.skin_name,
            status="pending",
        )
        db.add(d)
        deposits.append(d)

    db.commit()
    for d in deposits:
        db.refresh(d)

    deposit_ids = [d.id for d in deposits]

    from workers.steam_worker import send_deposit_trade_request
    send_deposit_trade_request.delay(deposit_ids)

    return {"deposit_ids": deposit_ids}


@router.get("/{deposit_id}")
def get_deposit(
    deposit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if deposit.steam_id != current_user.steam_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "id": deposit.id,
        "asset_id": deposit.asset_id,
        "skin_name": deposit.skin_name,
        "status": deposit.status,
        "trade_offer_id": deposit.trade_offer_id,
        "tx_hash": deposit.tx_hash,
        "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
    }
