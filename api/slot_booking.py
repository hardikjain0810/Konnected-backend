from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from core.logging_config import get_logger
from core.utils import get_lang
from core.auth import get_current_user
from db.database import get_db
from core.translations import get_text
from models.database_models import TutorSlot, SlotStatus, BookingStatus, Booking
from schemas.schemas import SlotBookingCreate, SlotBookingResponse
import uuid
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="", tags=["tutor"])
logger = get_logger()

@router.post("/bookings", status_code=status.HTTP_201_CREATED, response_model=SlotBookingResponse)
def create_booking(request: SlotBookingCreate, 
                   req: Request,
                   db: Session = Depends(get_db), 
                   current_user = Depends(get_current_user)):
    lang = get_lang(req)
    now = datetime.now()
    start_at = datetime.combine(request.slot_date,request.start_time)
    # Validation: Is the requested time in the future?
    if start_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_text("book_slot_in_past",lang)
        )

    # Database Lookup with Row Locking
    # This prevents race conditions where two students book the same slot
    requested_slot = db.query(TutorSlot).filter(
        TutorSlot.tutor_id == request.tutor_id,
        TutorSlot.start_at == start_at,
        TutorSlot.status.in_([SlotStatus.open, SlotStatus.booked])
    ).with_for_update().first()

    # Suggestion Logic (If exact slot is missing or taken)
    if not requested_slot:
        nearest_slot = db.query(TutorSlot).filter(
            TutorSlot.tutor_id == request.tutor_id,
            TutorSlot.status.in_([SlotStatus.open, SlotStatus.booked]),
            TutorSlot.start_at > start_at
        ).order_by(TutorSlot.start_at.asc()).first()

        error_details = {
            "error": get_text("slot_unavailable", lang),
            "suggested_time": nearest_slot.start_at if nearest_slot else None,
            "message": get_text("slot_taken_next", lang, time=nearest_slot.start_at) if nearest_slot else get_text("slot_no_other", lang)
        }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=jsonable_encoder(error_details)
        )

    # Validation: same student cannot book the same tutor slot twice.
    existing_student_booking = db.query(Booking).filter(
        Booking.slot_id == requested_slot.id,
        Booking.student_id == current_user.id,
        Booking.tutor_id == request.tutor_id
    ).first()
    if existing_student_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=get_text("duplicate_student_slot_booking", lang)
        )

    # Atomic Transaction: Create Booking & Update Slot
    try:
        # Create the Booking record with 'scheduled' status
        new_booking = Booking(
            id=uuid.uuid4(),
            tutor_id=request.tutor_id,
            student_id=current_user.id,
            slot_id=requested_slot.id,
            status=BookingStatus.scheduled, # Updated to use your Enum
            goal=request.topic,
            starts_at=requested_slot.start_at,
            ends_at=requested_slot.end_at
        )
        
        # Keep slot in booked state once first booking is created.
        requested_slot.status = SlotStatus.booked
        
        db.add(new_booking)
        db.commit() # Save both changes at once
        db.refresh(new_booking)
        
        return {
            "response_code": "1",
            "detail": get_text("slot_booked_success", lang),
            "data":{
                "booking_id": new_booking.id,
                "tutor_id": new_booking.tutor_id,
                "slot_id": new_booking.slot_id,
                "starts_at": new_booking.starts_at,
                "ends_at": new_booking.ends_at,
                "status": new_booking.status,
            }
        }
        
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Booking conflict for slot {requested_slot.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=get_text("slot_unavailable_retry", lang)
        )
    except Exception as e:
        db.rollback() # Undo changes if anything fails (e.g., DB connection drop)
        logger.error(f"Error during booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("booking_internal_error", lang)
        )
