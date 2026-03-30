from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from . import models, oauth2
from db.database import get_db
from sqlalchemy.orm import Session
from core.logging_config import get_logger
from schemas.schemas import CancelSlotCreate, CancelSlotResponse


router = APIRouter(prefix="", tags=["tutor"])
logger = get_logger()

@router.put("/slots/{slot_id}/cancel",response_model=CancelSlotResponse)
def cancel_and_reopen_slot(
    request: CancelSlotCreate,
    db: Session = Depends(get_db)):
    
    try:
        # Fetch the slot
        slot = db.query(models.TutorSlot).filter(
            models.TutorSlot.id == request.slot_id,
            models.TutorSlot.tutor_id == request.tutor_id
        ).first()

        if not slot:
            raise HTTPException(
                status_code=404, 
                detail={"error": "Slot not found or does not belong to this tutor"}
            )

        # 1-Hour Cancellation Rule
        # Calculate the time difference between 'now' and the slot start time
        now = datetime.now()
        time_until_start = slot.start_at - now

        if time_until_start < timedelta(hours=1):
            raise HTTPException(
                status_code=400,
                detail={"error": "Cannot cancel a slot within 1 hour of the start time."}
            )

        # Validation: Only cancel slots that are actually 'booked'
        if slot.status != "booked":
            raise HTTPException(
                status_code=400,
                detail={"error": f"Only 'booked' slots can be cancelled. Current status: {slot.status}"}
            )

        try:
            # Update status back to 'open'
            slot.status = "open"
            db.commit()
            
            return {
                "response_code": "1",
                "detail": "Slot has been successfully cancelled and is now open for new bookings."
            }

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail={"error": str(e)})
        
    except Exception as e:
        db.rollback()
        logger.error({"error":str(e)})
        raise HTTPException(status_code=500, detail={"error":str(e)})