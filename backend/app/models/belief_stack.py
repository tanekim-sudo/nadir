"""New belief stack models: DCF decomposition + node-level evidence scoring."""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.company import Company


class BeliefStackNode(Base):
    """Individual assumption node in the DCF decomposition tree."""
    __tablename__ = "belief_stack_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. 'A1', 'B2', 'C3'
    node_name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_node: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 'A', 'B', 'C' or None for roots
    market_implied_value: Mapped[str] = mapped_column(Text, default="")
    market_implied_label: Mapped[str] = mapped_column(Text, default="")
    evidence_value: Mapped[str] = mapped_column(Text, default="")
    evidence_label: Mapped[str] = mapped_column(Text, default="")
    evidence_direction: Mapped[str] = mapped_column(String(32), default="NEUTRAL")
    evidence_confidence: Mapped[str] = mapped_column(String(16), default="LOW")
    gap_magnitude: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    conviction_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    evidence_sources: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company", back_populates="belief_nodes")


class DCFDecomposition(Base):
    """Stores a single reverse-DCF solve for a company at a point in time."""
    __tablename__ = "dcf_decomposition"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    current_ev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    debt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cash: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttm_revenue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttm_gross_profit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttm_ebit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    implied_year1_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    implied_terminal_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    implied_wacc: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    ev_revenue_multiple: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    solver_converged: Mapped[bool] = mapped_column(Boolean, default=False)
    solver_error: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    raw_solver_output: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="dcf_decompositions")


class NodeSignalMapping(Base):
    """Maps which signals affect which belief stack nodes and how."""
    __tablename__ = "node_signal_mapping"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0"))
    direction_mapping: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class JobPostingSignal(Base):
    """Weekly job posting velocity data (demand + supply)."""
    __tablename__ = "job_posting_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_subtype: Mapped[str] = mapped_column(String(16), nullable=False)  # DEMAND or SUPPLY
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weekly_count: Mapped[int] = mapped_column(Integer, default=0)
    four_week_avg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    thirteen_week_avg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    yoy_change: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    wow_change: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    velocity_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    raw_data: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="job_posting_signals")


class SqueezeProbabilitySignal(Base):
    """Daily short squeeze probability data."""
    __tablename__ = "squeeze_probability_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_to_cover: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    borrow_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    put_call_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    price_proximity_52w_low: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    squeeze_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    raw_inputs: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="squeeze_signals")
