from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, TutorProfile, Language, TutorTopic, RoleType, UserRole, TutorSlot, AvailabilityRule, Profile, Booking
from schemas.schemas import TutorProfileCreate, TutorProfileResponse, TutorDetailResponse, MarketplaceResponse, GetTutorAvailability, GetTutorAvailabilityResponse, TutorSearchRequest
from datetime import timezone, datetime
from core.utils import get_lang
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from core.exceptions import init_exception_handlers
from sqlalchemy import asc, func
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

