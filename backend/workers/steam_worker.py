"""
Steam Worker — Celery задачи для работы с трейд-офферами.

Запуск:
    cd backend
    celery -A workers.celery_app worker --loglevel=info -Q steam
"""
import logging
from workers.celery_app import celery_app
from app.services.steam_bot import (
    get_client,
    accept_trade_offer,
    send_trade_offer,
    request_items_from_user,
    get_trade_offer_state,
)
from app.db import SessionLocal
from app.models.deposit import Deposit
from app.models.withdrawal import Withdrawal
from app.models.trade_log import TradeLog

logger = logging.getLogger(__name__)

# Trade offer states
_STATE_ACCEPTED = 3
_STATE_TERMINAL = {4, 5, 6, 7, 8, 10}


def _log(db, operation_type: str, operation_id: int, event: str, details: str = None):
    db.add(TradeLog(
        operation_type=operation_type,
        operation_id=operation_id,
        event=event,
        details=details,
    ))
    db.commit()


# ── New deposit flow (bot requests skins from user) ───────────────────────────

@celery_app.task(name="steam.send_deposit_trade_request", bind=True, max_retries=3)
def send_deposit_trade_request(self, deposit_ids: list):
    """
    Отправляет трейд-оффер пользователю, запрашивая скины для депозита.
    После успешной отправки переводит все депозиты в статус 'sent'
    и запускает polling статуса.
    """
    db = SessionLocal()
    try:
        deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
        if not deposits:
            logger.error("No deposits found for ids: %s", deposit_ids)
            return

        first = deposits[0]
        user_steam_id = first.steam_id
        trade_url = None

        # Get trade URL from user record
        from app.models.user import User
        user = db.query(User).filter(User.steam_id == user_steam_id).first()
        if user:
            trade_url = user.steam_trade_url

        if not trade_url:
            logger.error("No trade URL for user %s", user_steam_id)
            for d in deposits:
                d.status = "failed"
            db.commit()
            return

        asset_ids = [d.asset_id for d in deposits]
        client = get_client()

        trade_offer_id = request_items_from_user(
            client=client,
            trade_url=trade_url,
            user_steam_id=user_steam_id,
            asset_ids=asset_ids,
            message="FA Skins — please accept to deposit your skins",
        )

        for d in deposits:
            d.trade_offer_id = trade_offer_id
            d.status = "sent"
        db.commit()

        for d in deposits:
            _log(db, "deposit", d.id, "trade_sent", trade_offer_id)

        logger.info("Deposit trade offer %s sent to user %s", trade_offer_id, user_steam_id)

        # Start polling
        poll_deposit_trade_status.apply_async(
            args=[trade_offer_id, deposit_ids],
            countdown=10,
        )

    except Exception as exc:
        logger.error("send_deposit_trade_request error: %s", exc)
        try:
            for d in db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all():
                _log(db, "deposit", d.id, "error", str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="steam.poll_deposit_trade_status", bind=True, max_retries=60)
def poll_deposit_trade_status(self, trade_offer_id: str, deposit_ids: list):
    """
    Проверяет статус трейд-оффера каждые 10 секунд (max 10 минут).
    При принятии — переводит в 'accepted' и запускает минт для каждого депозита.
    При терминальном состоянии — переводит в 'failed'.
    """
    db = SessionLocal()
    try:
        state = get_trade_offer_state(trade_offer_id)

        if state == _STATE_ACCEPTED:
            deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
            for d in deposits:
                d.status = "accepted"
            db.commit()

            for d in deposits:
                _log(db, "deposit", d.id, "trade_accepted", trade_offer_id)

            logger.info("Trade offer %s accepted, queuing mint for %s", trade_offer_id, deposit_ids)
            from workers.blockchain_worker import mint_for_deposit
            for d in deposits:
                mint_for_deposit.delay(d.id)

        elif state in _STATE_TERMINAL:
            deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
            for d in deposits:
                d.status = "failed"
            db.commit()
            for d in deposits:
                _log(db, "deposit", d.id, "trade_failed", f"state={state}")
            logger.warning("Trade offer %s terminal state %d, deposits failed", trade_offer_id, state)

        else:
            # Still active or needs confirmation — retry in 10s
            raise self.retry(countdown=10)

    except self.MaxRetriesExceededError:
        db2 = SessionLocal()
        try:
            for d in db2.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all():
                d.status = "failed"
                _log(db2, "deposit", d.id, "trade_timeout", trade_offer_id)
            db2.commit()
        finally:
            db2.close()
    except Exception as exc:
        logger.error("poll_deposit_trade_status error: %s", exc)
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()


# ── Legacy tasks (kept for withdrawal flow) ───────────────────────────────────

@celery_app.task(name="steam.accept_deposit_trade", bind=True, max_retries=3)
def accept_deposit_trade(self, deposit_id: int, trade_offer_id: str):
    """
    [Legacy] Принимает входящий трейд-оффер от пользователя (депозит).
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
    [Legacy] Периодическая задача: проверяет входящие трейды.
    """
    db = SessionLocal()
    try:
        client = get_client()
        incoming = client.get_trade_offers(merge=False)
        offers = incoming.get("response", {}).get("trade_offers_received", [])

        for offer in offers:
            trade_offer_id = offer.get("tradeofferid")
            if offer.get("trade_offer_state") != 2:
                continue

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
