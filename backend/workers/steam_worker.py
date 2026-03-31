"""
Steam Worker — Celery задачи для работы с трейд-офферами.

Запуск:
    cd backend
    celery -A workers.celery_app worker --loglevel=info -Q steam
"""
import logging
from workers.celery_app import celery_app
from app.services.steam_bot import get_client, accept_trade_offer, send_trade_offer
from app.db import SessionLocal
from app.models.deposit import Deposit
from app.models.withdrawal import Withdrawal
from app.models.trade_log import TradeLog

logger = logging.getLogger(__name__)


def _log(db, operation_type: str, operation_id: int, event: str, details: str = None):
    db.add(TradeLog(
        operation_type=operation_type,
        operation_id=operation_id,
        event=event,
        details=details,
    ))
    db.commit()


@celery_app.task(name="steam.accept_deposit_trade", bind=True, max_retries=3)
def accept_deposit_trade(self, deposit_id: int, trade_offer_id: str):
    """
    Принимает входящий трейд-оффер от пользователя (депозит).
    После принятия обновляет статус депозита → 'accepted'.
    Mint токенов запускается отдельно в blockchain_worker.
    """
    db = SessionLocal()
    try:
        client = get_client()
        success = accept_trade_offer(client, trade_offer_id)

        deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
        if not deposit:
            logger.error("Deposit %d not found", deposit_id)
            return

        if success:
            deposit.status = "accepted"
            db.commit()
            _log(db, "deposit", deposit_id, "trade_accepted", trade_offer_id)
            from workers.blockchain_worker import mint_for_deposit
            mint_for_deposit.delay(deposit_id)
            logger.info("Deposit %d accepted, mint queued", deposit_id)
        else:
            deposit.status = "failed"
            db.commit()
            _log(db, "deposit", deposit_id, "trade_accept_failed", trade_offer_id)

    except Exception as exc:
        logger.error("accept_deposit_trade error: %s", exc)
        _log(db, "deposit", deposit_id, "error", str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="steam.send_withdrawal_trade", bind=True, max_retries=3)
def send_withdrawal_trade(self, withdrawal_id: int):
    """
    Отправляет скин пользователю (вывод).
    Вызывается blockchain_worker'ом после события TokensBurned.
    """
    db = SessionLocal()
    try:
        withdrawal = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
        if not withdrawal:
            logger.error("Withdrawal %d not found", withdrawal_id)
            return

        client = get_client()
        trade_offer_id = send_trade_offer(
            client=client,
            trade_url=withdrawal.trade_url,
            asset_ids=[withdrawal.asset_id],
            message="FA Skins — your skin withdrawal",
        )

        withdrawal.trade_offer_id = trade_offer_id
        withdrawal.status = "sending"
        db.commit()
        _log(db, "withdrawal", withdrawal_id, "trade_sent", trade_offer_id)
        logger.info("Withdrawal %d trade sent: %s", withdrawal_id, trade_offer_id)

    except Exception as exc:
        logger.error("send_withdrawal_trade error: %s", exc)
        db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).update({"status": "failed"})
        db.commit()
        _log(db, "withdrawal", withdrawal_id, "error", str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="steam.poll_incoming_trades")
def poll_incoming_trades():
    """
    Периодическая задача: проверяет входящие трейды и сопоставляет
    с pending депозитами в БД.

    Запускать через celery beat или вручную для тестирования.
    """
    db = SessionLocal()
    try:
        client = get_client()
        incoming = client.get_trade_offers(merge=False)
        offers = incoming.get("response", {}).get("trade_offers_received", [])

        for offer in offers:
            trade_offer_id = offer.get("tradeofferid")
            # offer_state 2 = Active
            if offer.get("trade_offer_state") != 2:
                continue

            # Ищем депозит с этим trade_offer_id
            deposit = (
                db.query(Deposit)
                .filter(
                    Deposit.trade_offer_id == trade_offer_id,
                    Deposit.status == "pending",
                )
                .first()
            )
            if deposit:
                accept_deposit_trade.delay(deposit.id, trade_offer_id)
                logger.info("Queued accept for deposit %d / offer %s", deposit.id, trade_offer_id)

    except Exception as e:
        logger.error("poll_incoming_trades error: %s", e)
    finally:
        db.close()
