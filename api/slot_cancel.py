from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from db.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import Date, Time, cast
from core.logging_config import get_logger
from core.utils import get_lang
from core.translations import get_text
from schemas.schemas import CancelSlotCreate, CancelSlotResponse
from models.database_models import TutorSlot, SlotStatus, AvailabilityRule


router = APIRouter(prefix="/tutor", tags=["tutor"])
logger = get_logger()

@router.delete("/cancel/{slot_id}", response_model=CancelSlotResponse)
def delete_tutor_slot(
    slot_id: UUID, 
    request: CancelSlotCreate,
    req: Request,
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    # 1. Fetch the specific slot based on tutor_id and the slot_id from params
    slot = db.query(TutorSlot).filter(
        TutorSlot.id == slot_id,
        TutorSlot.tutor_id == request.tutor_id
    ).first()

    if not slot:
        raise HTTPException(
            status_code=404, 
            detail=get_text("slot_not_found_or_owner", lang)
        )

    # 2. Find the corresponding AvailabilityRule
    # We match by tutor, date, and start_time to find the exact rule that created this 30m slot
    rule = db.query(AvailabilityRule).filter(
        AvailabilityRule.tutor_id == slot.tutor_id,
        AvailabilityRule.date == cast(slot.start_at, Date),
        AvailabilityRule.start_time == cast(slot.start_at, Time)
    ).first()

    try:
        # 3. Action: Delete from AvailabilityRule table
        if rule:
            db.delete(rule)
        
            # 4. Action: Mark TutorSlot as 'disabled' instead of deleting
            # Note: Ensure "disabled" is a valid value in your SlotStatus Enum or String column
            slot.status = "disabled" 
        
        db.commit()
        db.refresh(slot)

        return {
            "response_code": "1",
            "detail": get_text("slot_disabled_success", lang),
            "data": [
                {
                    "tutor_id": str(request.tutor_id),
                    "slot_id": str(slot_id),
                    "new_status": slot.status
                }
            ]
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Cancellation Error: {str(e)}")
        raise HTTPException(status_code=500, detail=get_text("slot_cancel_error", lang))
