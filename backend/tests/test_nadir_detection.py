"""Tests for NADIR condition detection and state transitions."""
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.company import Company
from app.models.enums import SignalType, SystemState
from app.models.nadir_signal import NadirSignal


def _add_signal(db, company_id, signal_type, value, threshold, condition_met):
    signal = NadirSignal(
        company_id=company_id,
        signal_type=signal_type,
        current_value=Decimal(str(value)),
        threshold=Decimal(str(threshold)),
        condition_met=condition_met,
        source="test",
    )
    db.add(signal)
    return signal


def test_normal_state_no_conditions(db, sample_company):
    """Company with 0 conditions met stays NORMAL."""
    from app.services.nadir_agent import _update_company_states

    _update_company_states(db)
    db.refresh(sample_company)
    assert sample_company.system_state == SystemState.NORMAL.value
    assert sample_company.conditions_met == 0


def test_watch_state_three_conditions(db, sample_company):
    """Company with 3 conditions transitions to WATCH."""
    from app.services.nadir_agent import _update_company_states

    _add_signal(db, sample_company.id, SignalType.SHORT_INTEREST.value, 0.25, 0.20, True)
    _add_signal(db, sample_company.id, SignalType.ANALYST_SENTIMENT.value, 0.75, 0.70, True)
    _add_signal(db, sample_company.id, SignalType.INSIDER_BUYING.value, 10.0, 8.0, True)
    db.commit()

    _update_company_states(db)
    db.refresh(sample_company)
    assert sample_company.conditions_met == 3
    assert sample_company.system_state == SystemState.WATCH.value


def test_nadir_complete_all_conditions(db, sample_company):
    """Company with all 5 conditions transitions to NADIR_COMPLETE."""
    from app.services.nadir_agent import _update_company_states

    for sig_type in SignalType:
        _add_signal(db, sample_company.id, sig_type.value, 1.0, 0.5, True)
    db.commit()

    _update_company_states(db)
    db.refresh(sample_company)
    assert sample_company.conditions_met == 5
    assert sample_company.system_state == SystemState.NADIR_COMPLETE.value


def test_condition_not_met_keeps_normal(db, sample_company):
    """Conditions that are not met don't count."""
    from app.services.nadir_agent import _update_company_states

    _add_signal(db, sample_company.id, SignalType.SHORT_INTEREST.value, 0.10, 0.20, False)
    _add_signal(db, sample_company.id, SignalType.ANALYST_SENTIMENT.value, 0.30, 0.70, False)
    db.commit()

    _update_company_states(db)
    db.refresh(sample_company)
    assert sample_company.conditions_met == 0
    assert sample_company.system_state == SystemState.NORMAL.value


def test_state_transition_creates_alert(db, sample_company):
    """WATCH transition should create an alert."""
    from app.models.alert import Alert
    from app.services.nadir_agent import _update_company_states

    _add_signal(db, sample_company.id, SignalType.SHORT_INTEREST.value, 0.25, 0.20, True)
    _add_signal(db, sample_company.id, SignalType.ANALYST_SENTIMENT.value, 0.75, 0.70, True)
    _add_signal(db, sample_company.id, SignalType.INSIDER_BUYING.value, 10.0, 8.0, True)
    db.commit()

    _update_company_states(db)

    alerts = db.query(Alert).filter(Alert.company_id == sample_company.id).all()
    assert any(a.alert_type == "WATCH_TRIGGERED" for a in alerts)


def test_nadir_complete_creates_critical_alert(db, sample_company):
    """NADIR_COMPLETE transition should create a CRITICAL alert."""
    from app.models.alert import Alert
    from app.services.nadir_agent import _update_company_states

    for sig_type in SignalType:
        _add_signal(db, sample_company.id, sig_type.value, 1.0, 0.5, True)
    db.commit()

    _update_company_states(db)

    alerts = db.query(Alert).filter(Alert.company_id == sample_company.id).all()
    nadir_alert = next((a for a in alerts if a.alert_type == "NADIR_COMPLETE"), None)
    assert nadir_alert is not None
    assert nadir_alert.priority == "CRITICAL"
