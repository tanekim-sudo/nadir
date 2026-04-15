import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.company import Company
from app.models.enums import SystemState


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_company(db) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker="TEST",
        name="Test Corp",
        sector="Technology",
        system_state=SystemState.NORMAL.value,
        conditions_met=0,
        current_price=Decimal("50.00"),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture
def watch_company(db) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker="WATCH",
        name="Watch Corp",
        sector="Technology",
        system_state=SystemState.WATCH.value,
        conditions_met=3,
        current_price=Decimal("30.00"),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture
def nadir_company(db) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker="NADIR",
        name="Nadir Corp",
        sector="Technology",
        system_state=SystemState.NADIR_COMPLETE.value,
        conditions_met=5,
        current_price=Decimal("15.00"),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
