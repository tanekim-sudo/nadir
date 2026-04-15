import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut, AlertReview

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
def list_alerts(
    reviewed: bool = False,
    priority: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(Alert).filter(Alert.reviewed == reviewed)
    if priority:
        q = q.filter(Alert.priority == priority)
    # Order by priority weight then recency
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    alerts = q.order_by(Alert.created_at.desc()).limit(limit).all()
    alerts.sort(key=lambda a: (priority_order.get(a.priority, 4), a.created_at), reverse=False)
    return alerts


@router.put("/{alert_id}/review", response_model=AlertOut)
def review_alert(alert_id: str, body: AlertReview, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.reviewed = True
    alert.action_taken = body.action_taken
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/stream")
async def alert_stream(db: Session = Depends(get_db)):
    """Server-sent events endpoint for real-time alert streaming."""

    async def event_generator():
        last_id = None
        while True:
            latest = (
                db.query(Alert)
                .filter(Alert.reviewed == False)
                .order_by(Alert.created_at.desc())
                .first()
            )
            if latest and str(latest.id) != last_id:
                last_id = str(latest.id)
                data = {
                    "id": str(latest.id),
                    "company_id": str(latest.company_id),
                    "alert_type": latest.alert_type,
                    "alert_text": latest.alert_text,
                    "priority": latest.priority,
                    "created_at": latest.created_at.isoformat(),
                }
                yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
