"""Belief stack v2 — constrained reverse-DCF decomposition

Drop old belief_stack table. Add belief_stack_nodes, dcf_decomposition,
node_signal_mapping, job_posting_signals, squeeze_probability_signals.
Update signal type enums.

Revision ID: 002
Revises: 001
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old belief_stack table
    op.drop_table("belief_stack")

    # --- belief_stack_nodes ---
    op.create_table(
        "belief_stack_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("node_id", sa.String(16), nullable=False),
        sa.Column("node_name", sa.String(256), nullable=False),
        sa.Column("parent_node", sa.String(16), nullable=True),
        sa.Column("market_implied_value", sa.Text, server_default=""),
        sa.Column("market_implied_label", sa.Text, server_default=""),
        sa.Column("evidence_value", sa.Text, server_default=""),
        sa.Column("evidence_label", sa.Text, server_default=""),
        sa.Column("evidence_direction", sa.String(32), server_default="NEUTRAL"),
        sa.Column("evidence_confidence", sa.String(16), server_default="LOW"),
        sa.Column("gap_magnitude", sa.Numeric(18, 8), nullable=True),
        sa.Column("conviction_score", sa.Numeric(18, 8), nullable=True),
        sa.Column("evidence_sources", postgresql.JSONB, nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- dcf_decomposition ---
    op.create_table(
        "dcf_decomposition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("scan_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("current_ev", sa.Integer, nullable=True),
        sa.Column("current_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("shares", sa.Integer, nullable=True),
        sa.Column("debt", sa.Integer, nullable=True),
        sa.Column("cash", sa.Integer, nullable=True),
        sa.Column("ttm_revenue", sa.Integer, nullable=True),
        sa.Column("ttm_gross_profit", sa.Integer, nullable=True),
        sa.Column("ttm_ebit", sa.Integer, nullable=True),
        sa.Column("implied_year1_growth", sa.Numeric(12, 8), nullable=True),
        sa.Column("implied_terminal_margin", sa.Numeric(12, 8), nullable=True),
        sa.Column("implied_wacc", sa.Numeric(12, 8), nullable=True),
        sa.Column("ev_revenue_multiple", sa.Numeric(12, 6), nullable=True),
        sa.Column("solver_converged", sa.Boolean, server_default="false"),
        sa.Column("solver_error", sa.Numeric(18, 4), nullable=True),
        sa.Column("raw_solver_output", postgresql.JSONB, nullable=True),
    )

    # --- node_signal_mapping ---
    op.create_table(
        "node_signal_mapping",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("node_id", sa.String(16), nullable=False, index=True),
        sa.Column("signal_type", sa.String(64), nullable=False),
        sa.Column("signal_weight", sa.Numeric(8, 4), server_default="1.0"),
        sa.Column("direction_mapping", postgresql.JSONB, nullable=True),
    )

    # --- job_posting_signals ---
    op.create_table(
        "job_posting_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("signal_subtype", sa.String(16), nullable=False),
        sa.Column("week_start_date", sa.Date, nullable=False, index=True),
        sa.Column("weekly_count", sa.Integer, server_default="0"),
        sa.Column("four_week_avg", sa.Numeric(12, 4), nullable=True),
        sa.Column("thirteen_week_avg", sa.Numeric(12, 4), nullable=True),
        sa.Column("yoy_change", sa.Numeric(12, 8), nullable=True),
        sa.Column("wow_change", sa.Numeric(12, 8), nullable=True),
        sa.Column("velocity_score", sa.Numeric(12, 8), nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
    )

    # --- squeeze_probability_signals ---
    op.create_table(
        "squeeze_probability_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("signal_date", sa.Date, nullable=False, index=True),
        sa.Column("days_to_cover", sa.Numeric(12, 4), nullable=True),
        sa.Column("borrow_rate", sa.Numeric(12, 8), nullable=True),
        sa.Column("put_call_ratio", sa.Numeric(12, 8), nullable=True),
        sa.Column("price_proximity_52w_low", sa.Numeric(12, 8), nullable=True),
        sa.Column("squeeze_score", sa.Numeric(12, 8), nullable=True),
        sa.Column("raw_inputs", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("squeeze_probability_signals")
    op.drop_table("job_posting_signals")
    op.drop_table("node_signal_mapping")
    op.drop_table("dcf_decomposition")
    op.drop_table("belief_stack_nodes")

    # Recreate old belief_stack table
    op.create_table(
        "belief_stack",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("layer", sa.String(32), nullable=False),
        sa.Column("assumption_text", sa.Text, server_default=""),
        sa.Column("market_implied_value", sa.Text, server_default=""),
        sa.Column("variant_value", sa.Text, server_default=""),
        sa.Column("confidence_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("confirming_signals", sa.Integer, server_default="0"),
        sa.Column("contradicting_signals", sa.Integer, server_default="0"),
        sa.Column("net_direction", sa.String(64), server_default="NEUTRAL"),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
