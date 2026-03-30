from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, Profile, TutorProfile, Language, Timezone, Interest, TutorSlot, Booking
from schemas.schemas import ProfileCreate, ProfileResponse, StudentBookingCreate, StudentBookingsResponse
from core.utils import get_lang,success_response
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/data")
async def get_data():
    return success_response(message="Data received successfully",
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

@router.get("/my-sessions", response_model=StudentBookingsResponse)
def get_student_sessions(
    request: StudentBookingCreate,
    db: Session = Depends(get_db)):
    
    if not request.student_id:
        raise HTTPException(
            status_code=400,
            detail="User not authenticated or ID is missing"
        )
    try:
        from uuid import UUID
        student_id = request.student_id
        if isinstance(student_id, str):
            student_id = UUID(student_id)
        results = db.query(
            TutorSlot,
            TutorProfile.name.label("tutor_name")
        ).join(
            Booking, TutorSlot.id == Booking.slot_id
        ).outerjoin(
            TutorProfile, Booking.tutor_id == TutorProfile.user_id
        ).filter(
            Booking.student_id == student_id) \
        .all()

        session_list = []
        for slot, tutor_name in results:
            session_list.append({
                "slot_id": str(slot.id),
                "tutor_name": tutor_name,
                "start_date": slot.start_at.date().isoformat(),
                "start_time": slot.start_at.time().strftime("%H:%M"),
                "end_time": slot.end_at.time().strftime("%H:%M"),
                "status": str(slot.status)
            })

        return {
            "response_code": "1",
            "detail": "Retrieved booked sessions successfully",
            "data": session_list
        }

    except Exception as e:
        logger.error(f"Error in get_student_sessions: {str(e)}")
        raise HTTPException(status_code=500, detail={"error":str(e)}) 