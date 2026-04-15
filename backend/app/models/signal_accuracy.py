import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SignalAccuracy(Base):
    __tablename__ = "signal_accuracy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_type: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    true_positives: Mapped[int] = mapped_column(Integer, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, default=0)
    true_negatives: Mapped[int] = mapped_column(Integer, default=0)
    false_negatives: Mapped[int] = mapped_column(Integer, default=0)
    precision: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8), nullable=True)
    recall: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8), nullable=True)
    f1_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 8), nullable=True)
    last_calculated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
