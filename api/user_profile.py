from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, cast, Date, Time
from datetime import timedelta
from db.database import get_db
from models.database_models import User, Profile, TutorProfile, Language, Timezone, Interest, TutorSlot, Booking, AvailabilityRule, UserRole, RoleType, BookingTimeStatus, SlotStatus, BookingStatus
from schemas.schemas import ProfileCreate, ProfileResponse, StudentBookingCreate, SlotBookingCreate, BaseResponse, StudentTutorAvailabilityResponse, GetTutorAvailabilityForStudent, StudentSessionListResponse, SlotBookingResponse, SessionCancelRequest
from core.utils import get_lang,success_response
from sqlalchemy.exc import IntegrityError
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from uuid import UUID
import uuid

from datetime import datetime
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/data")
async def get_data(req: Request):
    lang = get_lang(req)
    return success_response(message=get_text("data_received_success", lang),
                            data={"language":[lang.value for lang in Language],"Timezone":[tz.value for tz in Timezone],"Interest":[inter.value for inter in Interest]})

@router.post("", response_model=ProfileResponse)
async def create_profile(
    request: ProfileCreate,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    logger.info(f"Profile creation attempt for user: {current_user.email}")
    
    existing_profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if existing_profile:
        logger.warning(f"Profile already exists for user: {current_user.email}")
        raise HTTPException(status_code=400, detail=get_text("profile_exists", lang))

    profile = Profile(
        user_id=current_user.id,
        display_name=request.display_name,
        timezone=request.timezone,
        primary_language=request.primary_language,
        target_language=request.target_language,
        interests=[interest.value for interest in request.interests],
        bio=request.bio
    )
    db.add(profile)
    
    try:
        db.commit()
        db.refresh(profile)
        logger.info(f"Profile created successfully for user: {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating profile for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=get_text("profile_error", lang, error=str(e)))
    
    return {
        "response_code": "1",
        "detail": get_text("profile_success", lang),
        "data": {
            "user_id": str(profile.user_id),
            "display_name": profile.display_name,
            "timezone": profile.timezone.value,
            "primary_language": profile.primary_language.value,
            "target_language": profile.target_language.value,
            "interests": profile.interests,
            "bio": profile.bio
        }
    }

@router.put("", response_model=ProfileResponse)
async def update_profile(
    request: ProfileCreate,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    logger.info(f"Profile update attempt for user: {current_user.email}")
    
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        logger.warning(f"Profile not found for user: {current_user.email}")
        raise HTTPException(status_code=404, detail=get_text("profile_not_found", lang))

    profile.display_name = request.display_name
    profile.timezone = request.timezone
    profile.primary_language = request.primary_language
    profile.target_language = request.target_language
    profile.interests = [interest.value for interest in request.interests]
    profile.bio = request.bio
    
    try:
        db.commit()
        db.refresh(profile)
        logger.info(f"Profile updated successfully for user: {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating profile for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=get_text("profile_error", lang, error=str(e)))
    
    return {
        "response_code": "1",
        "detail": get_text("profile_update_success", lang),
        "data": {
            "user_id": str(profile.user_id),
            "display_name": profile.display_name,
            "timezone": profile.timezone.value,
            "primary_language": profile.primary_language.value,
            "target_language": profile.target_language.value,
            "interests": profile.interests,
            "bio": profile.bio
        }
    }

@router.get("/get-profile/{user_id}", response_model=ProfileResponse)
async def get_profile_by_user_id(user_id: UUID, req: Request, db: Session = Depends(get_db)):
    lang = get_lang(req)
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    if not profile:
        raise HTTPException(status_code=404, detail=get_text("profile_not_found", lang))

    return {
        "response_code": "1",
        "detail": get_text("profile_fetched_success", lang),
        "data": {
            "user_id": str(profile.user_id),
            "display_name": profile.display_name,
            "timezone": profile.timezone.value,
            "primary_language": profile.primary_language.value,
            "target_language": profile.target_language.value,
            "interests": profile.interests,
            "bio": profile.bio
        }
    }

@router.post("/bookings/list", response_model=StudentSessionListResponse)
def get_student_sessions_list(
    request: StudentBookingCreate,
    req: Request,
    db: Session = Depends(get_db)
):
    lang = get_lang(req)

    if not request.student_id:
        raise HTTPException(
            status_code=400,
            detail=get_text("student_auth_missing", lang)
        )

    try:
        student_id = request.student_id
        if isinstance(student_id, str):
            student_id = UUID(student_id)

        rows = db.query(
            Booking,
            TutorSlot,
            AvailabilityRule.topic,
            TutorProfile.name.label("tutor_name")
        ).join(
            TutorSlot, Booking.slot_id == TutorSlot.id
        ).outerjoin(
            AvailabilityRule,
            and_(
                AvailabilityRule.tutor_id == Booking.tutor_id,
                AvailabilityRule.date == cast(TutorSlot.start_at, Date),
                AvailabilityRule.start_time == cast(TutorSlot.start_at, Time)
            )
        ).outerjoin(
            TutorProfile,
            TutorProfile.user_id == Booking.tutor_id
        ).filter(
            Booking.student_id == student_id
        ).order_by(
            TutorSlot.start_at.asc()
        ).all()

        now = datetime.now()
        data = []
        status_changed = False
        for booking, slot, topic, tutor_name in rows:
            # Respect DB value directly. Auto-fill only if it's missing.
            if booking.booking_time_status is None:
                if slot.start_at <= now <= slot.end_at:
                    booking.booking_time_status = BookingTimeStatus.current
                elif now < slot.start_at:
                    booking.booking_time_status = BookingTimeStatus.upcoming
                else:
                    booking.booking_time_status = BookingTimeStatus.past
                status_changed = True

            booking_state = booking.booking_time_status.value

            data.append({
                "tutor_id": str(booking.tutor_id),
                "tutor_name": tutor_name if tutor_name else "",
                "session_id": str(booking.slot_id),
                "student_id": str(booking.student_id),
                "slot": f"{slot.start_at.strftime('%Y-%m-%d')} / {slot.start_at.strftime('%H.%M.%S')} - {slot.end_at.strftime('%H.%M.%S')}",
                "topic": topic if topic else "",
                "status": booking_state
            })

        if status_changed:
            db.commit()

        return {
            "response_code": "1",
            "detail": get_text("session_list_success", lang),
            "data": data
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=get_text("student_auth_missing", lang))
    except Exception as e:
        logger.error(f"Error in get_student_sessions_list: {str(e)}")
        raise HTTPException(status_code=500, detail=get_text("student_sessions_error", lang))

@router.post("/tutor-availability/{tutor_id}", response_model=StudentTutorAvailabilityResponse)
def get_tutor_availability_for_student(
    tutor_id: UUID,
    request: GetTutorAvailabilityForStudent,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    student_role = db.query(UserRole).filter(
        UserRole.user_id == current_user.id,
        UserRole.role.in_([RoleType.student, RoleType.both])
    ).first()

    if not student_role:
        raise HTTPException(status_code=403, detail=get_text("not_a_student", lang))

    availability = db.query(AvailabilityRule).filter(
        AvailabilityRule.tutor_id == tutor_id
    ).order_by(
        AvailabilityRule.date.asc(),
        AvailabilityRule.start_time.asc()
    ).all()

    return {
        "response_code": "1",
        "detail": get_text("tutor_availability_fetched", lang),
        "data": [
            {
                "tutor_id": slot.tutor_id,
                "date": slot.date,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
            }
            for slot in availability
        ],
    }

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
                "topic": request.topic,
                "date": requested_slot.start_at.date(),
                "starts_at": requested_slot.start_at.time(),
                "ends_at": requested_slot.end_at.time(),
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

@router.delete("/bookings/cancel", response_model=BaseResponse)
def cancel_student_booking(
    request: SessionCancelRequest,
    req: Request,
    db: Session = Depends(get_db)):
    lang = get_lang(req)

    booking = db.query(Booking).filter(
        Booking.slot_id == request.slot_id,
        Booking.student_id == request.student_id
    ).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_text("booking_not_found", lang)
        )

    now = datetime.now()
    if booking.starts_at - now <= timedelta(hours=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_text("cancel_before_one_hour", lang)
        )

    slot = db.query(TutorSlot).filter(TutorSlot.id == booking.slot_id).first()

    try:
        db.delete(booking)
        db.flush()

        remaining_bookings = db.query(Booking).filter(
            Booking.slot_id == booking.slot_id
        ).count()

        if slot and remaining_bookings == 0 and slot.status != SlotStatus.disabled:
            slot.status = SlotStatus.open

        db.commit()

        return {
            "response_code": "1",
            "detail": get_text("session_deleted_success", lang)
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error while cancelling booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_text("booking_internal_error", lang)
        )
