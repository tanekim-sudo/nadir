"""Tests for signal collectors with mocked external APIs."""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.company import Company
from app.models.enums import SignalType
from app.models.nadir_signal import NadirSignal
from app.services.signal_collectors import (
    _get_previous_signal,
    finalize_short_interest_universe,
)


def test_get_previous_signal_none(db, sample_company):
    result = _get_previous_signal(db, sample_company.id, SignalType.SHORT_INTEREST)
    assert result is None


def test_get_previous_signal_exists(db, sample_company):
    signal = NadirSignal(
        company_id=sample_company.id,
        signal_type="SHORT_INTEREST",
        current_value=Decimal("0.25"),
        condition_met=True,
        source="test",
    )
    db.add(signal)
    db.commit()

    result = _get_previous_signal(db, sample_company.id, SignalType.SHORT_INTEREST)
    assert result == Decimal("0.25")


def test_finalize_short_interest_no_signals(db):
    """Should not crash with no signals."""
    finalize_short_interest_universe(db)


def test_finalize_short_interest_marks_top_20(db, sample_company):
    """Create 10 signals, top 2 should be in top 20%."""
    from datetime import datetime, timezone

    for i in range(10):
        company = Company(
            ticker=f"T{i:02d}",
            name=f"Test {i}",
            sector="Technology",
            system_state="NORMAL",
            conditions_met=0,
        )
        db.add(company)
        db.flush()

        signal = NadirSignal(
            company_id=company.id,
            signal_type="SHORT_INTEREST",
            current_value=Decimal(f"0.{25 + i}"),
            condition_met=False,
            raw_data={"short_float": 0.25 + i * 0.01, "borrow_rate": 0.01 * (i + 1)},
            source="test",
        )
        db.add(signal)
    db.commit()

    finalize_short_interest_universe(db)
    db.commit()

    signals = db.query(NadirSignal).filter(NadirSignal.signal_type == "SHORT_INTEREST").all()
    top_20_count = sum(1 for s in signals if s.raw_data and s.raw_data.get("in_top_20_borrow"))
    assert top_20_count == 2


def test_detection_signals_set():
    """Verify the 5 detection signals are correctly defined."""
    from app.models.enums import DETECTION_SIGNALS

    assert len(DETECTION_SIGNALS) == 5
    assert SignalType.SHORT_INTEREST in DETECTION_SIGNALS
    assert SignalType.ANALYST_SENTIMENT in DETECTION_SIGNALS
    assert SignalType.INSIDER_BUYING in DETECTION_SIGNALS
    assert SignalType.JOB_POSTING_VELOCITY in DETECTION_SIGNALS
    assert SignalType.SQUEEZE_PROBABILITY in DETECTION_SIGNALS
    assert SignalType.GRR_MONITORING not in DETECTION_SIGNALS
