import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import DateTime, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    companies_scanned: Mapped[int] = mapped_column(Integer, default=0)
    nadir_complete_count: Mapped[int] = mapped_column(Integer, default=0)
    watch_count: Mapped[int] = mapped_column(Integer, default=0)
    new_alerts: Mapped[int] = mapped_column(Integer, default=0)
    scan_duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    errors: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
