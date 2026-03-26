from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, date
from core.logging_config import get_logger
from core.utils import get_lang
from core.auth import get_current_user
from db.database import get_db
from core.translations import get_text
from models.database_models import TutorSlot, SlotStatus, RoleType
from schemas.schemas import SlotBookingCreate, SlotBookingResponse

router = APIRouter(prefix="", tags=["tutor"])
logger = get_logger()

@router.post("/book", response_model=SlotBookingResponse)
async def book_slot(
    request: SlotBookingCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    # Fetch the slot and check if it's available
    slot = db.query(TutorSlot).filter(
        TutorSlot.id == request.slot_id,
        TutorSlot.status == "open" # Ensure it is still open
    ).first()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Slot is either already booked or does not exist."
        )

    # Prevent users from booking their own slots
    if slot.tutor_id == current_user.id:
        raise HTTPException(
            status_code=400, 
            detail="You cannot book your own tutoring slot."
        )

    try:
        # Create the Booking Record
        new_booking = Booking(
            id=uuid.uuid4(),
            tutor_id=slot.tutor_id,
            student_id=current_user.id,
            slot_id=slot.id,
            status=BookingStatus.confirmed, # Or pending, depending on your flow
            goal=request.goal,
            note=request.note,
            starts_at=slot.start_at,
            ends_at=slot.end_at
        )
        
        # Update the Slot Status to 'booked'
        slot.status = "booked"
        
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)

        return {
            "response_code": "1",
            "detail": "Slot booked successfully!",
            "data": {
                "booking_id": new_booking.id,
                "tutor_id": new_booking.tutor_id,
                "slot_id": new_booking.slot_id,
                "starts_at": new_booking.starts_at,
                "ends_at": new_booking.ends_at,
                "status": "confirmed"
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Booking failed: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while processing your booking.")