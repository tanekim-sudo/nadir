import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.company import Company


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    dollar_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    position_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    p_win: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    kelly_fraction: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    thesis: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_result: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    falsification_conditions: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    time_horizon_days: Mapped[int] = mapped_column(Integer, default=180)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False, index=True)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    alpaca_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pending_approval: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company", back_populates="positions")
