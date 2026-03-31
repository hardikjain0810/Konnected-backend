from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from db.database import get_db
from sqlalchemy.orm import Session
from core.logging_config import get_logger
from schemas.schemas import CancelSlotCreate, CancelSlotResponse
from models.database_models import TutorSlot, SlotStatus, AvailabilityRule


router = APIRouter(prefix="", tags=["tutor"])
logger = get_logger()

@router.delete("/slots/{slot_id}/cancel", status_code=status.HTTP_204_NO_CONTENT,response_model=CancelSlotResponse)
def delete_tutor_slot_and_rule(
    request: CancelSlotCreate, # Pass this as a query param or from request body
    db: Session = Depends(get_db)
):
    # 1. Fetch the TutorSlot first
    # This gives us the 'start_at' timestamp we need to find the Rule
    slot = db.query(TutorSlot).filter(
        TutorSlot.id == request.slot_id,
        TutorSlot.tutor_id == request.tutor_id
    ).first()

    if not slot:
        raise HTTPException(
            status_code=404, 
            detail="Slot not found or doesn't belong to this tutor"
        )

    try:
        # 2. Identify the matching AvailabilityRule
        # We extract .date() and .time() from the DateTime object
        availability_rule = db.query(AvailabilityRule).filter(
            AvailabilityRule.tutor_id == request.tutor_id,
            AvailabilityRule.date == slot.start_at.date(),
            AvailabilityRule.start_time == slot.start_at.time()
        ).first()

        # 3. Perform Deletions
        if availability_rule:
            db.delete(availability_rule)
        
        db.delete(slot)

        # 4. Commit as a single transaction
        db.commit()
        
        return {
            "response_code": "1",
            "detail": "Slot deleted successfully",
            "data": {
                "tutor_id":request.tutor_id,
                "slot_id":request.slot_id
            }
        } # 204 No Content doesn't return a body

    except Exception as e:
        db.rollback()
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")