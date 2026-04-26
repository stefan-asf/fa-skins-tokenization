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
from app.models.withdrawal import Withdrawal
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
    Минтит 1 токен за один депозит (legacy, используется для одиночных депозитов).
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

        tx_hash = mint_token(deposit.wallet_address, quantity=1)
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


@celery_app.task(name="blockchain.mint_for_deposit_batch", bind=True, max_retries=3)
def mint_for_deposit_batch(self, deposit_ids: list):
    """
    Минтит N токенов за один вызов (один tx) для всего батча депозитов.
    Избегает nonce-конфликтов при параллельных транзакциях.
    """
    db = SessionLocal()
    try:
        deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
        if not deposits:
            logger.error("No deposits found for ids: %s", deposit_ids)
            return

        wallet_address = deposits[0].wallet_address
        quantity = len(deposits)

        tx_hash = mint_token(wallet_address, quantity=quantity)
        logger.info("Batch minted %d token(s) for deposits %s, tx: %s", quantity, deposit_ids, tx_hash)

        for d in deposits:
            d.status = "minted"
            d.tx_hash = tx_hash
        db.commit()

        for d in deposits:
            _log(db, "deposit", d.id, "minted", tx_hash)

    except Exception as exc:
        logger.error("mint_for_deposit_batch error: %s", exc)
        db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).update({"status": "failed"})
        db.commit()
        try:
            for d_id in deposit_ids:
                _log(db, "deposit", d_id, "mint_failed", str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="blockchain.burn_for_withdrawal", bind=True, max_retries=3)
def burn_for_withdrawal(self, withdrawal_ids: list):
    """
    Сжигает N токенов после того, как пользователь принял трейд-оффер.
    Финальный шаг: переводит записи в статус 'delivered'.
    """
    db = SessionLocal()
    try:
        withdrawals = db.query(Withdrawal).filter(Withdrawal.id.in_(withdrawal_ids)).all()
        if not withdrawals:
            logger.error("No withdrawals found for ids: %s", withdrawal_ids)
            return

        wallet_address = withdrawals[0].wallet_address
        quantity = len(withdrawals)

        tx_hash = burn_token(wallet_address, quantity)
        logger.info("Burned %d token(s) from %s, tx: %s", quantity, wallet_address, tx_hash)

        for w in withdrawals:
            w.burn_tx_hash = tx_hash
            w.status = "delivered"
        db.commit()

        for w in withdrawals:
            _log(db, "withdrawal", w.id, "burned_and_delivered", tx_hash)
        logger.info("Withdrawals %s delivered, tokens burned", withdrawal_ids)

    except Exception as exc:
        logger.error("burn_for_withdrawal error: %s", exc)
        try:
            for w_id in withdrawal_ids:
                _log(db, "withdrawal", w_id, "burn_failed", str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
