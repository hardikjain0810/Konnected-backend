from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from db.database import get_db
from sqlalchemy.orm import Session
from core.logging_config import get_logger
from schemas.schemas import CancelSlotCreate, CancelSlotResponse
from models.database_models import TutorSlot, SlotStatus, AvailabilityRule


router = APIRouter(prefix="/tutor", tags=["tutor"])
logger = get_logger()

@router.delete("/cancel/{slot_id}", response_model=CancelSlotResponse)
def delete_tutor_slot(
    slot_id: UUID, 
    request: CancelSlotCreate, 
    db: Session = Depends(get_db)
):
    # 1. Fetch the specific 30-minute slot
    # We filter by both IDs to ensure the tutor owns this specific slot
    slot = db.query(TutorSlot).filter(
        TutorSlot.id == slot_id,
        TutorSlot.tutor_id == request.tutor_id
    ).first()

    if not slot:
        raise HTTPException(
            status_code=404, 
            detail="Slot not found or does not belong to this tutor."
        )

    # 2. Safety Check: Is it already booked?
    # If a student already booked it, you might want to prevent deletion 
    # or trigger a refund/notification logic here.
    if slot.status == SlotStatus.booked:
        # Optional: raise error if you don't allow deleting booked sessions
        # raise HTTPException(status_code=400, detail="Cannot delete a booked slot.")
        pass

    try:
        # 3. Delete ONLY the TutorSlot
        # This keeps the 1-4 hour AvailabilityRule intact for other slots
        db.delete(slot)
        db.commit()

        return {
            "response_code": "1",
            "detail": "30-minute slot successfully removed from schedule.",
            "data": [
                {
                    "tutor_id": request.tutor_id,
                    "slot_id": slot_id
                }
            ]
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Deletion Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))