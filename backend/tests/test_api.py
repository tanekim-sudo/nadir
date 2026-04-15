"""Tests for FastAPI endpoints."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.alert import Alert
from app.models.company import Company
from app.models.enums import AlertPriority, AlertType, PositionStatus, SystemState
from app.models.position import Position


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_list_universe_empty(client):
    resp = client.get("/api/universe")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_universe_with_company(client, sample_company):
    resp = client.get("/api/universe")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "TEST"


def test_get_company(client, sample_company):
    resp = client.get("/api/universe/TEST")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "TEST"


def test_get_company_not_found(client):
    resp = client.get("/api/universe/NONEXIST")
    assert resp.status_code == 404


def test_add_company(client):
    resp = client.post("/api/universe/add", json={"ticker": "NEW", "name": "New Corp"})
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "NEW"


def test_add_company_duplicate(client, sample_company):
    resp = client.post("/api/universe/add", json={"ticker": "TEST"})
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "TEST"


def test_delete_company(client, sample_company):
    resp = client.delete("/api/universe/TEST")
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"


def test_delete_company_not_found(client):
    resp = client.delete("/api/universe/NONEXIST")
    assert resp.status_code == 404


def test_list_alerts_empty(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_alerts(client, db, sample_company):
    alert = Alert(
        company_id=sample_company.id,
        alert_type=AlertType.WATCH_TRIGGERED.value,
        alert_text="Test alert",
        priority=AlertPriority.HIGH.value,
    )
    db.add(alert)
    db.commit()

    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["alert_type"] == "WATCH_TRIGGERED"


def test_review_alert(client, db, sample_company):
    alert = Alert(
        company_id=sample_company.id,
        alert_type=AlertType.WATCH_TRIGGERED.value,
        alert_text="Test alert",
        priority=AlertPriority.MEDIUM.value,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    resp = client.put(f"/api/alerts/{alert.id}/review", json={"action_taken": "Noted"})
    assert resp.status_code == 200
    assert resp.json()["reviewed"] is True


def test_list_positions_empty(client):
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_signals_not_found(client):
    resp = client.get("/api/signals/NONEXIST")
    assert resp.status_code == 404


def test_get_signals_empty(client, sample_company):
    resp = client.get("/api/signals/TEST")
    assert resp.status_code == 200
    assert resp.json() == []


def test_watchlist(client, watch_company):
    resp = client.get("/api/nadir/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "WATCH"


def test_nadir_complete(client, nadir_company):
    resp = client.get("/api/nadir/complete")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "NADIR"


def test_predictions_empty(client):
    resp = client.get("/api/predictions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_prediction(client, sample_company):
    resp = client.post("/api/predictions", json={
        "company_id": str(sample_company.id),
        "claim_text": "Test claim",
        "observable_outcome": "Test outcome",
        "resolution_date": "2026-07-01",
        "confidence_pct": 65.0,
    })
    assert resp.status_code == 200
    assert resp.json()["claim_text"] == "Test claim"


def test_analytics_performance(client):
    resp = client.get("/api/analytics/performance")
    assert resp.status_code == 200


def test_analytics_signals(client):
    resp = client.get("/api/analytics/signals")
    assert resp.status_code == 200


def test_analytics_kelly(client):
    resp = client.get("/api/analytics/kelly")
    assert resp.status_code == 200


def test_filter_by_state(client, sample_company, watch_company):
    resp = client.get("/api/universe?state=WATCH")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "WATCH"


def test_filter_by_min_conditions(client, sample_company, watch_company):
    resp = client.get("/api/universe?min_conditions=3")
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["conditions_met"] >= 3 for c in data)
