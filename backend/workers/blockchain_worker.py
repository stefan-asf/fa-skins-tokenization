"""
Blockchain Worker — Celery задачи для минта/бёрна токенов.

Запуск:
    cd backend
    celery -A workers.celery_app worker --loglevel=info -Q blockchain
"""
import logging
from workers.celery_app import celery_app
from app.db import SessionLocal
from app.models.deposit import Deposit
from app.models.trade_log import TradeLog
from app.services.blockchain import mint_token, burn_token

logger = logging.getLogger(__name__)


def _log(db, operation_type: str, operation_id: int, event: str, details: str = None):
    db.add(TradeLog(
        operation_type=operation_type,
        operation_id=operation_id,
        event=event,
        details=details,
    ))
    db.commit()


@celery_app.task(name="blockchain.mint_for_deposit", bind=True, max_retries=3)
def mint_for_deposit(self, deposit_id: int):
    """
    Минтит 1 токен на кошелёк пользователя после принятия трейда.
    Вызывается steam_worker'ом после статуса 'accepted'.
    """
    db = SessionLocal()
    try:
        deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
        if not deposit:
            logger.error("Deposit %d not found", deposit_id)
            return

        if deposit.status != "accepted":
            logger.warning("Deposit %d status is '%s', expected 'accepted'", deposit_id, deposit.status)
            return

        tx_hash = mint_token(deposit.wallet_address)
        deposit.status = "minted"
        deposit.tx_hash = tx_hash
        db.commit()
        _log(db, "deposit", deposit_id, "minted", tx_hash)
        logger.info("Deposit %d minted, tx: %s", deposit_id, tx_hash)

    except Exception as exc:
        logger.error("mint_for_deposit error: %s", exc)
        db.query(Deposit).filter(Deposit.id == deposit_id).update({"status": "failed"})
        db.commit()
        _log(db, "deposit", deposit_id, "mint_failed", str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
