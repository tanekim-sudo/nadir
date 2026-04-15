"""initial NADIR schema

Revision ID: 001
Revises:
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("sector", sa.String(length=256), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("current_ev", sa.BigInteger(), nullable=True),
        sa.Column("market_implied_nrr", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("market_implied_growth", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("system_state", sa.String(length=32), nullable=False),
        sa.Column("conditions_met", sa.Integer(), nullable=False),
        sa.Column("last_scanned", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)

    op.create_table(
        "scan_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("companies_scanned", sa.Integer(), nullable=False),
        sa.Column("nadir_complete_count", sa.Integer(), nullable=False),
        sa.Column("watch_count", sa.Integer(), nullable=False),
        sa.Column("new_alerts", sa.Integer(), nullable=False),
        sa.Column("scan_duration_seconds", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "signal_accuracy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("true_positives", sa.Integer(), nullable=False),
        sa.Column("false_positives", sa.Integer(), nullable=False),
        sa.Column("true_negatives", sa.Integer(), nullable=False),
        sa.Column("false_negatives", sa.Integer(), nullable=False),
        sa.Column("precision", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("recall", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("f1_score", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("last_calculated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_signal_accuracy_signal_type"), "signal_accuracy", ["signal_type"], unique=True)

    op.create_table(
        "nadir_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("previous_value", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("threshold", sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column("condition_met", sa.Boolean(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=256), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_nadir_signals_company_id"), "nadir_signals", ["company_id"], unique=False)
    op.create_index(op.f("ix_nadir_signals_signal_type"), "nadir_signals", ["signal_type"], unique=False)

    op.create_table(
        "belief_stack",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("assumption_text", sa.Text(), nullable=False),
        sa.Column("market_implied_value", sa.Text(), nullable=False),
        sa.Column("variant_value", sa.Text(), nullable=False),
        sa.Column("confidence_pct", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("confirming_signals", sa.Integer(), nullable=False),
        sa.Column("contradicting_signals", sa.Integer(), nullable=False),
        sa.Column("net_direction", sa.String(length=64), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_belief_stack_company_id"), "belief_stack", ["company_id"], unique=False)

    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("belief_stack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("observable_outcome", sa.Text(), nullable=False),
        sa.Column("resolution_date", sa.Date(), nullable=False),
        sa.Column("confidence_pct", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("actual_outcome", sa.Text(), nullable=True),
        sa.Column("outcome_direction", sa.String(length=32), nullable=True),
        sa.Column("signal_accuracy_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["belief_stack_id"], ["belief_stack.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_predictions_company_id"), "predictions", ["company_id"], unique=False)
    op.create_index(op.f("ix_predictions_resolution_date"), "predictions", ["resolution_date"], unique=False)

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("dollar_amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("position_pct", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("p_win", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("kelly_fraction", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("thesis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("falsification_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("time_horizon_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("return_pct", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("exit_reason", sa.String(length=256), nullable=True),
        sa.Column("alpaca_order_id", sa.String(length=128), nullable=True),
        sa.Column("pending_approval", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_positions_company_id"), "positions", ["company_id"], unique=False)
    op.create_index(op.f("ix_positions_status"), "positions", ["status"], unique=False)
    op.create_index(op.f("ix_positions_ticker"), "positions", ["ticker"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("alert_text", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("action_taken", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alerts_alert_type"), "alerts", ["alert_type"], unique=False)
    op.create_index(op.f("ix_alerts_company_id"), "alerts", ["company_id"], unique=False)
    op.create_index(op.f("ix_alerts_priority"), "alerts", ["priority"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alerts_priority"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_company_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_alert_type"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_positions_ticker"), table_name="positions")
    op.drop_index(op.f("ix_positions_status"), table_name="positions")
    op.drop_index(op.f("ix_positions_company_id"), table_name="positions")
    op.drop_table("positions")
    op.drop_index(op.f("ix_predictions_resolution_date"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_company_id"), table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(op.f("ix_belief_stack_company_id"), table_name="belief_stack")
    op.drop_table("belief_stack")
    op.drop_index(op.f("ix_nadir_signals_signal_type"), table_name="nadir_signals")
    op.drop_index(op.f("ix_nadir_signals_company_id"), table_name="nadir_signals")
    op.drop_table("nadir_signals")
    op.drop_index(op.f("ix_signal_accuracy_signal_type"), table_name="signal_accuracy")
    op.drop_table("signal_accuracy")
    op.drop_table("scan_history")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.drop_table("companies")
