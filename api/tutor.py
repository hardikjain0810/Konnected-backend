from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, TutorProfile, Language, TutorTopic, RoleType, UserRole, TutorSlot, AvailabilityRule, Profile, Booking, SlotStatus
from schemas.schemas import TutorProfileCreate, TutorProfileResponse, TutorDetailResponse, MarketplaceResponse, GetTutorAvailability, GetTutorAvailabilityResponse, TutorSearchRequest, AvailabilityRuleCreate, AvailabilityResponse, GetAvailabilityRuleCreate, GetAvailabilityResponse
from datetime import datetime, timedelta, date, timezone
from core.utils import get_lang
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from core.exceptions import init_exception_handlers
from sqlalchemy import asc, func, Date, Time, cast, and_, or_
from uuid import UUID

router = APIRouter(prefix="/tutor", tags=["tutor"])

@router.get("/options")
async def get_tutor_options(req: Request):
    """Get available options for languages and topics."""
    lang = get_lang(req)
    return {
        "response_code": "1",
        "detail": get_text("options_fetched", lang),
        "data": {
            "languages": [lang.value for lang in Language],
            "topics": [topic.value for topic in TutorTopic]
        }
    }

@router.post("/profile", response_model=TutorProfileResponse)
async def create_tutor_profile(
    request: TutorProfileCreate,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    logger.info(f"Tutor profile creation attempt for user: {current_user.email}")

    # Check if user has tutor role
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id, UserRole.role == RoleType.tutor).first()
    if not role:
        logger.warning(f"User {current_user.email} is not a tutor")
        raise HTTPException(status_code=403, detail=get_text("not_a_tutor", lang))

    existing_profile = db.query(TutorProfile).filter(TutorProfile.user_id == current_user.id).first()
    if existing_profile:
        logger.warning(f"Tutor profile already exists for user: {current_user.email}")
        raise HTTPException(status_code=400, detail=get_text("profile_exists", lang))

    tutor_profile = TutorProfile(
        user_id=current_user.id,
        name=request.name,
        headline=request.headline,
        bio=request.bio,
        languages_taught=request.languages_taught,
        languages_spoken=request.languages_spoken,
        topics=[t.strip() for t in request.topics],
        is_published=request.is_published
    )
    db.add(tutor_profile)

    try:
        db.commit()
        db.refresh(tutor_profile)
        logger.info(f"Tutor profile created successfully for user: {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating tutor profile for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=get_text("profile_error", lang))

    return {
        "response_code": "1",
        "detail": get_text("profile_success", lang),
        "data": {
            "user_id": str(tutor_profile.user_id),
            "name": tutor_profile.name,
            "headline": tutor_profile.headline,
            "bio": tutor_profile.bio,
            "languages_taught": tutor_profile.languages_taught,
            "languages_spoken": tutor_profile.languages_spoken,
            "topics": tutor_profile.topics,
            "is_published": tutor_profile.is_published
        }
    }

@router.put("/profile", response_model=TutorProfileResponse)
async def update_tutor_profile(
    request: TutorProfileCreate,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    logger.info(f"Tutor profile update attempt for user: {current_user.email}")

    # Check if user has tutor role
    role = db.query(UserRole).filter(UserRole.user_id == current_user.id, UserRole.role == RoleType.tutor).first()
    if not role:
        logger.warning(f"User {current_user.email} is not a tutor")
        raise HTTPException(status_code=403, detail=get_text("not_a_tutor", lang))

    tutor_profile = db.query(TutorProfile).filter(TutorProfile.user_id == current_user.id).first()
    if not tutor_profile:
        logger.warning(f"Tutor profile not found for user: {current_user.email}")
        raise HTTPException(status_code=404, detail=get_text("profile_not_found", lang))

    tutor_profile.name = request.name
    tutor_profile.headline = request.headline
    tutor_profile.bio = request.bio
    tutor_profile.languages_taught = request.languages_taught
    tutor_profile.languages_spoken = request.languages_spoken
    tutor_profile.topics = [t.strip() for t in request.topics]
    tutor_profile.is_published = request.is_published

    try:
        db.commit()
        db.refresh(tutor_profile)
        logger.info(f"Tutor profile updated successfully for user: {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating tutor profile for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=get_text("profile_error", lang))

    return {
        "response_code": "1",
        "detail": get_text("profile_update_success", lang),
        "data": {
            "user_id": str(tutor_profile.user_id),
            "name" : tutor_profile.name,
            "headline": tutor_profile.headline,
            "bio": tutor_profile.bio,
            "languages_taught": tutor_profile.languages_taught,
            "languages_spoken": tutor_profile.languages_spoken,
            "topics": tutor_profile.topics,
            "is_published": tutor_profile.is_published
        }
    }

# API to recommend tutors in student profile.
@router.post("/recommended", response_model=MarketplaceResponse)
def get_home_tutors(
    request: TutorSearchRequest,
    req: Request,
    db: Session = Depends(get_db)):
    lang = get_lang(req)
    # Get student's target language
    student = db.query(Profile).filter(Profile.user_id == request.student_id).first()
    if student is None:
        raise HTTPException(status_code=404, detail=get_text("student_not_found", lang))
    # Query Tutors (Filtering by is_published and Language)
    query = db.query(TutorProfile).filter(
        TutorProfile.is_published == True
    )
    logger.info(f"Tutors : {query}")

    # Toggle logic
    if request.match_language:
        query = query.filter(TutorProfile.languages_taught == student.primary_language.value)

    if request.search and request.search.strip() != "":
        search_term = f"%{request.search}%"
        query = query.filter(TutorProfile.name.ilike(search_term))

    tutor_profiles = query.all()

    results = []
    current_time = datetime.now(timezone.utc)
    for profile in tutor_profiles:
        # 3. Find the very next open slot for this tutor
        next_val = db.query(TutorSlot.start_at).filter(
            TutorSlot.tutor_id == profile.user_id,
            TutorSlot.status == "open",
            TutorSlot.start_at > current_time
        ).order_by(TutorSlot.start_at.asc()).first()

        results.append({
            "id" : profile.user_id,
            "display_name": profile.name,
            "teaches_languages": profile.languages_taught,
            "topics": profile.topics,
            "next_slot": next_val[0] if next_val else None
        })

    return {
        "response_code":"1",
        "detail": get_text("recommended_tutors", lang),
        "match_language": request.match_language,
        "data":{"tutors": results}
        }

@router.post("/slots/booked",response_model=GetTutorAvailabilityResponse)
async def get_tutor_bookings(request: GetTutorAvailability,
                             req: Request,
                             db: Session = Depends(get_db)):
    lang = get_lang(req)
    try:
        query = db.query(
            Booking,
            TutorSlot,
            Profile.display_name.label("student_name")
        ).join(
            TutorSlot,
            Booking.slot_id == TutorSlot.id
        ).outerjoin(
            Profile,
            Profile.user_id == Booking.student_id
        ).filter(
            Booking.tutor_id == request.tutor_id
        )

        if request.availability_date and str(request.availability_date).strip() != "":
            query = query.filter(func.date(Booking.starts_at) == request.availability_date)

        results = query.order_by(Booking.starts_at.asc()).all()

        slot_list = []
        for booking, slot, student_name in results:
            slot_list.append({
                "tutor_id": str(booking.tutor_id),
                "student_id": str(booking.student_id),
                "slot_id": str(booking.slot_id),
                "date": booking.starts_at.date().isoformat(),
                "start_time": booking.starts_at.time().strftime("%H:%M"),
                "end_time": booking.ends_at.time().strftime("%H:%M"),
                "student_name": student_name if student_name else "",
                "booking_time_status": booking.booking_time_status.value if booking.booking_time_status else ""
            })
        return {
            "response_code":"1",
            "detail": get_text("booked_slots_listed", lang),
            "data": slot_list
        }
    except Exception as e:
        logger.error({"error":str(e)})
        raise HTTPException(status_code=500, detail=get_text("internal_error", lang))

@router.get("/get-profile/{tutor_id}", response_model=TutorProfileResponse)
async def get_tutor_profile_by_id(tutor_id: UUID, req: Request, db: Session = Depends(get_db)):
    lang = get_lang(req)
    tutor_profile = db.query(TutorProfile).filter(TutorProfile.user_id == tutor_id).first()

    if not tutor_profile:
        raise HTTPException(status_code=404, detail=get_text("tutor_profile_not_found", lang))

    return {
        "response_code": "1",
        "detail": get_text("tutor_profile_fetched", lang),
        "data": {
            "user_id": str(tutor_profile.user_id),
            "name": tutor_profile.name,
            "headline": tutor_profile.headline,
            "bio": tutor_profile.bio,
            "languages_taught": tutor_profile.languages_taught,
            "languages_spoken": tutor_profile.languages_spoken,
            "topics": tutor_profile.topics,
            "is_published": tutor_profile.is_published
        }
    }

@router.get("/{tutor_id}", response_model=TutorDetailResponse)
async def get_tutor_details(tutor_id: UUID, req: Request, db: Session = Depends(get_db)):
    lang = get_lang(req)
    # Fetch only from TutorProfile
    profile = db.query(TutorProfile).filter(TutorProfile.user_id == tutor_id).first()

    if not profile:
        logger.warning(f"Tutor Profile not found for ID: {tutor_id}")
        raise HTTPException(status_code=404, detail=get_text("tutor_not_found", lang))

    # Fetch the next 3 available slots from the Slots table
    raw_slots = db.query(TutorSlot).\
        filter(
            TutorSlot.tutor_id == tutor_id,
            TutorSlot.start_at > datetime.now(timezone.utc),
            TutorSlot.status == "open"
        ).\
        order_by(asc(TutorSlot.start_at)).\
        limit(3).all()
    
    formatted_slots = [
    {
        "slot_date": slot.start_at.date(), 
        "start_time": slot.start_at.time()
    } 
    for slot in raw_slots
]

    tutor_data =  {
        "tutor_id": profile.user_id,
        "name": profile.name,
        "languages_taught":profile.languages_taught,
        "languages_spoken":profile.languages_spoken,
        "topics": profile.topics,
        "bio": profile.bio,
        "formated_slots": formatted_slots
    }

    return {
        "response_code":"1",
        "detail": get_text("tutor_profile_by_id", lang),
        "data":tutor_data
    }

@router.post("/availability", response_model=AvailabilityResponse)
def set_availability(
    request: AvailabilityRuleCreate,
    req: Request,
    db: Session = Depends(get_db),
):
    lang = get_lang(req)
    # Date Range Validation (The 21-Day Rule)
    today = date.today()
    max_future_date = today + timedelta(days=21)

    if request.availability_date < today:
        raise HTTPException(status_code=400, detail=get_text("cannot_set_past_availability", lang))
    
    if request.availability_date > max_future_date:
        raise HTTPException(
            status_code=400, 
            detail=get_text("availability_21_day_limit", lang, max_future_date=max_future_date)
        )

    # 1. Define start and end
    start_dt = datetime.combine(request.availability_date, request.start_time)
    end_dt = datetime.combine(request.availability_date, request.end_time)

    # Hard guard: if this exact slot is already booked, do not allow re-adding availability.
    existing_slot = db.query(TutorSlot).filter(
        TutorSlot.tutor_id == request.tutor_id,
        TutorSlot.start_at == start_dt
    ).first()
    if existing_slot and existing_slot.status == SlotStatus.booked:
        raise HTTPException(
            status_code=409,
            detail=get_text("availability_already_booked", lang)
        )

    # 2. Calculate exact duration in seconds
    duration_seconds = int((end_dt - start_dt).total_seconds())

    # 3. STRICT CHECK: Must be exactly 30 minutes (1800 seconds)
    if duration_seconds != 1800:
        raise HTTPException(
            status_code=400, 
            detail=get_text("availability_invalid_duration", lang, minutes=duration_seconds // 60)
        )
    
    # Overlap validation
    conflict = db.query(AvailabilityRule).join(
        TutorSlot, 
        and_(
            TutorSlot.tutor_id == AvailabilityRule.tutor_id,
            cast(TutorSlot.start_at, Date) == AvailabilityRule.date,
            cast(TutorSlot.start_at, Time) == AvailabilityRule.start_time
        )
    ).filter(
        AvailabilityRule.tutor_id == request.tutor_id,
        AvailabilityRule.date == request.availability_date,
        AvailabilityRule.start_time < request.end_time,
        AvailabilityRule.end_time > request.start_time,
        TutorSlot.status == "open"
    ).first()

    if conflict:
        raise HTTPException(status_code=400, detail=get_text("availability_overlap", lang))

    try:
        # 3. Clean up any "Dead" rules first (to prevent Duplicate Key errors)
        # If a rule exists but the slot was disabled, delete the old rule to make room for the new one.
        old_rule = db.query(AvailabilityRule).filter(
            AvailabilityRule.tutor_id == request.tutor_id,
            AvailabilityRule.date == request.availability_date,
            AvailabilityRule.start_time == request.start_time
        ).first()
        if old_rule:
            db.delete(old_rule)
            db.flush() # Sync the deletion before adding new_rule

        # 4. Create new Rule
        new_rule = AvailabilityRule(
            tutor_id=request.tutor_id,
            date=request.availability_date,
            start_time=request.start_time,
            end_time=request.end_time,
            topic=request.topic,
            short_description=request.short_description
        )
        db.add(new_rule)

        # 5. Handle Slot (Create or Re-enable)
        slot = db.query(TutorSlot).filter(
            TutorSlot.tutor_id == request.tutor_id,
            TutorSlot.start_at == start_dt
        ).first()

        if not slot:
            slot = TutorSlot(
                tutor_id=request.tutor_id,
                start_at=start_dt,
                end_at=end_dt,
                status="open"
            )
            db.add(slot)
        else:
            slot.status = "open" # Re-enable the disabled slot
            slot.end_at = end_dt # Ensure times are updated

        db.commit()
        db.refresh(new_rule)
        
        return {
            "response_code": "1",
            "detail": get_text("availability_sync_success", lang),
            "data": {
                "tutor_id":new_rule.tutor_id,
                "availability_date": new_rule.date,
                "start_time": new_rule.start_time,
                "end_time": new_rule.end_time,
                "topic": new_rule.topic,
                "short_description" : new_rule.short_description
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Critical Failure: {str(e)}")
        raise HTTPException(status_code=500, detail=get_text("availability_internal_error", lang))
    
@router.post("/list-availability/{tutor_id}", response_model=GetAvailabilityResponse)
def get_tutor_availability(
    tutor_id: UUID,
    req: Request,
    request: GetAvailabilityRuleCreate = Depends(),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    if request.tutor_id != tutor_id:
        raise HTTPException(status_code=400, detail=get_text("availability_tutor_id_mismatch", lang))

    query = db.query(AvailabilityRule, TutorSlot).outerjoin(
        TutorSlot,
        and_(
            TutorSlot.tutor_id == AvailabilityRule.tutor_id,
            cast(TutorSlot.start_at, Date) == AvailabilityRule.date,
            cast(TutorSlot.start_at, Time) == AvailabilityRule.start_time
        )
    ).filter(AvailabilityRule.tutor_id == tutor_id)

    # Exclude only disabled slots; keep open/booked and rules without a slot row.
    query = query.filter(
        or_(
            TutorSlot.id.is_(None),
            TutorSlot.status != SlotStatus.disabled
        )
    )

    if request.availability_date is not None and str(request.availability_date).strip() != "":
        try:
            target_date = datetime.strptime(request.availability_date, "%Y-%m-%d").date()
            query = query.filter(AvailabilityRule.date == target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail=get_text("invalid_date_format", lang))

    results = query.order_by(AvailabilityRule.date.asc(), AvailabilityRule.start_time.asc()).all()

    formatted_data = []
    for rule, slot in results:
        status = "open"
        if slot and slot.status is not None:
            status = slot.status.value if hasattr(slot.status, "value") else str(slot.status)

        formatted_data.append({
            "slot_id": slot.id if slot else "",
            "tutor_id": rule.tutor_id,
            "date": rule.date,
            "start_time": rule.start_time,
            "end_time": rule.end_time,
            "topic": rule.topic,
            "short_description": rule.short_description,
            "status": status,
        })

    return {
        "response_code": "1",
        "detail": get_text("availability_list_success", lang),
        "data": formatted_data
    }
