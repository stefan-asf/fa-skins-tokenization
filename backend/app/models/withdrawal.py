from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    steam_id: Mapped[str] = mapped_column(String(32), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(32), nullable=False)
    skin_name: Mapped[str] = mapped_column(String(256), nullable=False)
    trade_url: Mapped[str] = mapped_column(String(512), nullable=False)
    trade_offer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    burn_tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    # burning → sending → delivered → failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="burning")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
