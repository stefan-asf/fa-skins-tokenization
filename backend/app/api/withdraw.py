from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.withdrawal import Withdrawal
from app.models.user import User
from app.services.blockchain import get_balance, get_deployer_eth_balance

router = APIRouter(prefix="/withdraw", tags=["withdraw"])

_MIN_DEPLOYER_ETH = int(0.005 * 10**18)  # 0.005 ETH minimum for gas
_SKIN_NAME = "P250 | Sand Dune (Minimal Wear)"


class WithdrawalRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=50)


@router.post("")
def create_withdrawal(
    body: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet address not set")
    if not current_user.steam_trade_url:
        raise HTTPException(status_code=400, detail="Steam trade URL not set")

    token_balance = get_balance(current_user.wallet_address) // 10**18
    if token_balance < body.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient token balance: have {token_balance}, need {body.quantity}",
        )

    eth_balance = get_deployer_eth_balance()
    if eth_balance < _MIN_DEPLOYER_ETH:
        raise HTTPException(
            status_code=503,
            detail="Insufficient deployer ETH balance for gas fees",
        )

    from app.models.deposit import Deposit
    minted = db.query(Deposit).filter(Deposit.status == "minted").count()
    delivered = db.query(Withdrawal).filter(Withdrawal.status == "delivered").count()
    bot_skins = minted - delivered
    if bot_skins < body.quantity:
        raise HTTPException(
            status_code=503,
            detail=f"Bot only has {bot_skins} skin(s) available, need {body.quantity}",
        )

    withdrawals = []
    for _ in range(body.quantity):
        w = Withdrawal(
            steam_id=current_user.steam_id,
            wallet_address=current_user.wallet_address,
            asset_id="tbd",
            skin_name=_SKIN_NAME,
            trade_url=current_user.steam_trade_url,
            status="burning",
        )
        db.add(w)
        withdrawals.append(w)

    db.commit()
    for w in withdrawals:
        db.refresh(w)

    withdrawal_ids = [w.id for w in withdrawals]

    from workers.blockchain_worker import burn_for_withdrawal
    burn_for_withdrawal.delay(withdrawal_ids)

    return {"id": withdrawal_ids[0], "ids": withdrawal_ids}


@router.get("/deployer-balance")
def deployer_balance(current_user: User = Depends(get_current_user)):
    wei = get_deployer_eth_balance()
    return {"eth_balance": wei / 10**18, "wei": wei, "sufficient": wei >= _MIN_DEPLOYER_ETH}


@router.get("/{withdrawal_id}")
def get_withdrawal(
    withdrawal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    withdrawal = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if withdrawal.steam_id != current_user.steam_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "id": withdrawal.id,
        "status": withdrawal.status,
        "skin_name": withdrawal.skin_name,
        "burn_tx_hash": withdrawal.burn_tx_hash,
        "trade_offer_id": withdrawal.trade_offer_id,
        "created_at": withdrawal.created_at.isoformat() if withdrawal.created_at else None,
    }
