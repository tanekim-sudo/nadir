import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SystemState

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.belief_stack import (
        BeliefStackNode,
        DCFDecomposition,
        JobPostingSignal,
        SqueezeProbabilitySignal,
    )
    from app.models.nadir_signal import NadirSignal
    from app.models.position import Position
    from app.models.prediction import Prediction


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), default="")
    sector: Mapped[str] = mapped_column(String(256), default="")
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    current_ev: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_implied_nrr: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    market_implied_growth: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    system_state: Mapped[SystemState] = mapped_column(
        String(32), default=SystemState.NORMAL.value, nullable=False
    )
    conditions_met: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_scanned: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    signals: Mapped[List["NadirSignal"]] = relationship(
        "NadirSignal", back_populates="company", cascade="all, delete-orphan"
    )
    belief_nodes: Mapped[List["BeliefStackNode"]] = relationship(
        "BeliefStackNode", back_populates="company", cascade="all, delete-orphan"
    )
    dcf_decompositions: Mapped[List["DCFDecomposition"]] = relationship(
        "DCFDecomposition", back_populates="company", cascade="all, delete-orphan"
    )
    job_posting_signals: Mapped[List["JobPostingSignal"]] = relationship(
        "JobPostingSignal", back_populates="company", cascade="all, delete-orphan"
    )
    squeeze_signals: Mapped[List["SqueezeProbabilitySignal"]] = relationship(
        "SqueezeProbabilitySignal", back_populates="company", cascade="all, delete-orphan"
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="company", cascade="all, delete-orphan"
    )
    positions: Mapped[List["Position"]] = relationship(
        "Position", back_populates="company", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="company", cascade="all, delete-orphan"
    )
