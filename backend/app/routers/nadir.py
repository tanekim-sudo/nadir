from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.models.enums import SystemState
from app.models.position import Position
from app.schemas.company import CompanyOut
from app.services.belief_stack_builder import build_belief_stack
from app.services.nadir_validator import validate_nadir
from app.services.thesis_generator import generate_thesis

router = APIRouter(prefix="/api/nadir", tags=["nadir"])


@router.get("/watchlist", response_model=List[CompanyOut])
def get_watchlist(db: Session = Depends(get_db)):
    return (
        db.query(Company)
        .filter(Company.conditions_met >= 3)
        .order_by(Company.conditions_met.desc())
        .all()
    )


@router.get("/complete", response_model=List[CompanyOut])
def get_nadir_complete(db: Session = Depends(get_db)):
    return (
        db.query(Company)
        .filter(Company.system_state == SystemState.NADIR_COMPLETE.value)
        .order_by(Company.ticker)
        .all()
    )


@router.get("/{ticker}/validate")
def validate_company(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    result = validate_nadir(db, company)
    if not result:
        raise HTTPException(status_code=500, detail="Validation failed")
    return result


@router.get("/{ticker}/thesis")
def get_thesis(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check if position already has thesis
    position = (
        db.query(Position)
        .filter(Position.company_id == company.id)
        .filter(Position.thesis.isnot(None))
        .order_by(Position.created_at.desc())
        .first()
    )
    if position and position.thesis:
        return position.thesis

    # Generate new thesis
    validation = validate_nadir(db, company)
    if not validation:
        raise HTTPException(status_code=500, detail="Validation required before thesis generation")

    thesis = generate_thesis(db, company, validation)
    if not thesis:
        raise HTTPException(status_code=500, detail="Thesis generation failed")
    return thesis
