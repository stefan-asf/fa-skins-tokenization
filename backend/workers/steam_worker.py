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
    from celery.exceptions import Retry, MaxRetriesExceededError

    db = SessionLocal()
    try:
        state = get_trade_offer_state(trade_offer_id)
        logger.info("Trade offer %s current state: %d", trade_offer_id, state)

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
            # Still active — retry in 10s
            try:
                raise self.retry(countdown=10)
            except MaxRetriesExceededError:
                deposits = db.query(Deposit).filter(Deposit.id.in_(deposit_ids)).all()
                for d in deposits:
                    d.status = "failed"
                    _log(db, "deposit", d.id, "trade_timeout", trade_offer_id)
                db.commit()

    except Retry:
        raise  # let Celery handle normal retry scheduling
    except Exception as exc:
        logger.error("poll_deposit_trade_status unexpected error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=10)
        except MaxRetriesExceededError:
            pass
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
def send_withdrawal_trade(self, withdrawal_ids: list):
    """
    Находит N скинов в инвентаре бота и отправляет один трейд-оффер пользователю.
    Вызывается blockchain_worker'ом после сжигания токенов.
    """
    from app.services.steam_bot import SKIN_MARKET_HASH, GAME
    from celery.exceptions import MaxRetriesExceededError

    db = SessionLocal()
    try:
        withdrawals = db.query(Withdrawal).filter(Withdrawal.id.in_(withdrawal_ids)).all()
        if not withdrawals:
            logger.error("No withdrawals found for ids: %s", withdrawal_ids)
            return

        n = len(withdrawals)
        first = withdrawals[0]
        client = get_client()

        # If a prior attempt already created the trade offer, skip straight to confirmation.
        trade_offer_id = next(
            (w.trade_offer_id for w in withdrawals if w.trade_offer_id),
            None,
        )

        if trade_offer_id:
            logger.info("Trade offer %s already exists (prior attempt), retrying 2FA confirmation", trade_offer_id)
        else:
            # Get bot's steam_id and access token from mafile
            import json as _json
            from app.services.steam_bot import _get_mafile_path, _get_fresh_access_token
            with open(_get_mafile_path()) as f:
                _mf = _json.load(f)
            _mf_session = _mf.get("Session", {})
            bot_steam_id = _mf.get("steamid") or _mf_session.get("SteamID")
            bot_access_token = _get_fresh_access_token(_mf_session, bot_steam_id)

            # Find N target skins via the same inventory service used for users
            from app.services.steam_inventory import fetch_user_inventory
            from steampy.models import Asset
            inv_data = fetch_user_inventory(bot_steam_id, user_token=bot_access_token)
            desc_map = {
                f"{d['classid']}_{d['instanceid']}": d
                for d in inv_data.get("descriptions", [])
            }
            skin_asset_ids = []
            for asset in inv_data.get("assets", []):
                key = f"{asset['classid']}_{asset['instanceid']}"
                desc = desc_map.get(key, {})
                if SKIN_MARKET_HASH in desc.get("market_hash_name", "") and desc.get("tradable"):
                    skin_asset_ids.append(str(asset["assetid"]))
                if len(skin_asset_ids) >= n:
                    break

            if len(skin_asset_ids) < n:
                raise RuntimeError(f"Bot only has {len(skin_asset_ids)} tradable skin(s), need {n}")

            items_to_send = [Asset(asset_id=aid, game=GAME, amount=1) for aid in skin_asset_ids]
            offer = client.make_offer_with_url(
                items_from_me=items_to_send,
                items_from_them=[],
                trade_offer_url=first.trade_url,
                message="FA Skins — your skin withdrawal",
            )
            logger.info("make_offer_with_url response: %s", offer)
            if not offer or "tradeofferid" not in offer:
                error = offer.get("strError") if offer else "null response"
                raise RuntimeError(f"Trade offer creation failed: {error}")

            trade_offer_id = offer["tradeofferid"]

            # Persist trade_offer_id BEFORE confirmation so retries can reuse it
            for i, w in enumerate(withdrawals):
                w.trade_offer_id = trade_offer_id
                w.asset_id = skin_asset_ids[i]
                w.status = "sending"
            db.commit()

            for w in withdrawals:
                _log(db, "withdrawal", w.id, "trade_sent", trade_offer_id)
            logger.info("Withdrawal trade %s sent for withdrawals %s", trade_offer_id, withdrawal_ids)

        # Confirm outgoing trade via mobile 2FA (required when bot sends items)
        try:
            confirmations = client.get_confirmations()
            for conf in confirmations:
                if str(getattr(conf, "trade_offer_id", None)) == str(trade_offer_id):
                    client.allow_confirmation(conf)
                    logger.info("Withdrawal trade %s confirmed via 2FA", trade_offer_id)
                    break
            else:
                logger.warning("No confirmation found for trade %s (may already be confirmed)", trade_offer_id)
        except Exception as e:
            logger.warning("Could not confirm withdrawal trade %s: %s", trade_offer_id, e)

        poll_withdrawal_trade_status.apply_async(
            args=[trade_offer_id, withdrawal_ids],
            countdown=30,
        )

    except Exception as exc:
        logger.error("send_withdrawal_trade error: %s", exc)
        try:
            for w_id in withdrawal_ids:
                _log(db, "withdrawal", w_id, "error", str(exc))
        except Exception:
            pass
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            db.query(Withdrawal).filter(Withdrawal.id.in_(withdrawal_ids)).update({"status": "failed"})
            db.commit()
    finally:
        db.close()


@celery_app.task(name="steam.poll_withdrawal_trade_status", bind=True, max_retries=60)
def poll_withdrawal_trade_status(self, trade_offer_id: str, withdrawal_ids: list):
    """
    Проверяет каждые 30 секунд, принял ли пользователь трейд вывода.
    При принятии — переводит все записи в 'delivered'.
    """
    from celery.exceptions import Retry, MaxRetriesExceededError

    db = SessionLocal()
    try:
        state = get_trade_offer_state(trade_offer_id)
        logger.info("Withdrawal trade %s current state: %d", trade_offer_id, state)

        if state == _STATE_ACCEPTED:
            for w_id in withdrawal_ids:
                _log(db, "withdrawal", w_id, "trade_accepted", trade_offer_id)
            logger.info("Withdrawal trade %s accepted, queuing token burn", trade_offer_id)
            from workers.blockchain_worker import burn_for_withdrawal
            burn_for_withdrawal.delay(withdrawal_ids)

        elif state in _STATE_TERMINAL:
            db.query(Withdrawal).filter(Withdrawal.id.in_(withdrawal_ids)).update({"status": "failed"})
            db.commit()
            for w_id in withdrawal_ids:
                _log(db, "withdrawal", w_id, "trade_failed", f"state={state}")
            logger.warning("Withdrawal trade %s terminal state %d", trade_offer_id, state)

        else:
            try:
                raise self.retry(countdown=30)
            except MaxRetriesExceededError:
                db.query(Withdrawal).filter(Withdrawal.id.in_(withdrawal_ids)).update({"status": "failed"})
                db.commit()

    except Retry:
        raise
    except Exception as exc:
        logger.error("poll_withdrawal_trade_status error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=30)
        except MaxRetriesExceededError:
            pass
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
