from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, TutorProfile, Language, TutorTopic, RoleType, UserRole, TutorSlot, Booking,AvailabilityRule, Profile
from schemas.schemas import TutorProfileCreate, TutorProfileResponse, TutorDetailResponse, MarketplaceResponse
from datetime import timezone, datetime
from core.utils import get_lang
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from core.exceptions import init_exception_handlers
from typing import List
from sqlalchemy import and_, asc
from uuid import uuid4, UUID

router = APIRouter(prefix="/tutor", tags=["tutor"])

@router.get("/options")
async def get_tutor_options():
    """Get available options for languages and topics."""
    return {
        "response_code": "1",
        "detail": "Options fetched successfully",
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
        topics=[t.value for t in request.topics],
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
    tutor_profile.topics = [t.value for t in request.topics]
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
@router.get("/recommended", response_model=MarketplaceResponse)
def get_home_tutors(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # 1. Get student's target language
    student = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if student is None:
        raise HTTPException(status_code=401, detail="User doesn't exist.")
    # 2. Query Tutors (Filtering by is_published and Language)
    tutors = db.query(TutorProfile,TutorProfile.name).filter(
        TutorProfile.is_published == True,
        TutorProfile.languages_taught == student.primary_language.value 
    ).all()
    logger.info(f"Tutors : {tutors}")
    results = []
    for tutor, name in tutors:
        # 3. Find the very next open slot for this tutor
        next_val = db.query(TutorSlot.start_at).filter(
            TutorSlot.tutor_id == tutor.user_id,
            TutorSlot.status == "open",
            TutorSlot.start_at > datetime.now()
        ).order_by(TutorSlot.start_at.asc()).first()

        results.append({
            "display_name": name,
            "teaches_languages": tutor.languages_taught,
            "topics": tutor.topics,
            "next_slot": next_val[0] if next_val else None
        })

    return {"tutors": results}

@router.get("/{tutor_id}", response_model=TutorDetailResponse)
async def get_tutor_details(tutor_id: UUID, db: Session = Depends(get_db)):
    # Fetch only from TutorProfile
    profile = db.query(TutorProfile).filter(TutorProfile.user_id == tutor_id).first()

    if not profile:
        logger.warning(f"Tutor Profile not found for ID: {tutor_id}")
        raise HTTPException(status_code=404, detail="Tutor not found")

    # Fetch the next 3 available slots from the Slots table
    upcoming_slots = db.query(TutorSlot).\
        filter(
            TutorSlot.tutor_id == tutor_id,
            TutorSlot.start_at > datetime.now(timezone.utc),
            TutorSlot.status == "open"
        ).\
        order_by(asc(TutorSlot.start_at)).\
        limit(3).all()

    # Construct Response using data only from 'profile'
    return {
        "tutor_id": profile.user_id,
        "name": profile.name,
        "languages_taught":profile.languages_taught,
        "languages_spoken":profile.languages_spoken,
        "topics": profile.topics,
        "bio": profile.bio,
        "upcoming_slots": upcoming_slots
    }
