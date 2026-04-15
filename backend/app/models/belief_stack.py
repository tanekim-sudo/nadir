import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.company import Company


class BeliefStack(Base):
    __tablename__ = "belief_stack"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    assumption_text: Mapped[str] = mapped_column(Text, default="")
    market_implied_value: Mapped[str] = mapped_column(Text, default="")
    variant_value: Mapped[str] = mapped_column(Text, default="")
    confidence_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    confirming_signals: Mapped[int] = mapped_column(Integer, default=0)
    contradicting_signals: Mapped[int] = mapped_column(Integer, default=0)
    net_direction: Mapped[str] = mapped_column(String(64), default="NEUTRAL")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company", back_populates="belief_layers")
