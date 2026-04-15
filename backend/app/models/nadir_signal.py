import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SignalType

if TYPE_CHECKING:
    from app.models.company import Company


class NadirSignal(Base):
    __tablename__ = "nadir_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    previous_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    condition_met: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_data: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company", back_populates="signals")

    @property
    def signal_type_enum(self) -> SignalType:
        return SignalType(self.signal_type)
