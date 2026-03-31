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

@router.put("/slots/{slot_id}/cancel",response_model=CancelSlotResponse)
def cancel_and_reopen_slot(
    request: CancelSlotCreate,
    db: Session = Depends(get_db)):
    
    # Fetch the slot
    slot = db.query(TutorSlot).filter(
        TutorSlot.id == request.slot_id,
        TutorSlot.tutor_id == request.tutor_id
    ).first()

    if not slot:
        raise HTTPException(
            status_code=404, 
            detail={"error": "Slot not found or does not belong to this tutor"}
        )

    # 1-Hour Cancellation Rule
    # Calculate the time difference between 'now' and the slot start time
    #now = datetime.now()
    #time_until_start = slot.start_at - now

    #if time_until_start < timedelta(hours=1):
    #    raise HTTPException(
    #        status_code=400,
    #        detail={"error": "Cannot cancel a slot within 1 hour of the start time."}
    #    )

    # Validation: Only cancel slots that are actually 'booked'
    #if slot.status != SlotStatus.open:
    #    raise HTTPException(
    #        status_code=400,
    #        detail={"error": f"Only 'booked' slots can be cancelled. Current status: {slot.status}"}
    #    )

    try:
        # 2. Find and Delete the corresponding AvailabilityRule
        # We match by tutor_id and the date/time parts of the slot's start_at
        availability_rule = db.query(AvailabilityRule).filter(
            AvailabilityRule.tutor_id == slot.tutor_id,
            AvailabilityRule.date == slot.start_at.date(),
            AvailabilityRule.start_time == slot.start_at.time()
        ).first()

        if availability_rule:
            db.delete(availability_rule)
        else:
            logger.error("Some error")

        # 3. Handle the TutorSlot
        # If your manager wants it GONE from the system, use db.delete(slot)
        # If they just want it 'open' again, use slot.status = "open"
        slot.status = SlotStatus.open

        db.commit()
        
        return {
            "response_code": "1",
            "detail": "Slot successfully.",
            "data": []
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Cancellation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")