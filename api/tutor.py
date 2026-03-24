from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, TutorProfile, Language, TutorTopic, RoleType, UserRole
from schemas.schemas import TutorProfileCreate, TutorProfileResponse, TutorProfileData
from core.utils import get_lang
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from core.exceptions import init_exception_handlers
from typing import List

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
        headline=request.headline,
        bio=request.bio,
        languages_taught=[l.value for l in request.languages_taught],
        languages_spoken=[l.value for l in request.languages_spoken],
        topics=[t.value for t in request.topics]
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

    tutor_profile.headline = request.headline
    tutor_profile.bio = request.bio
    tutor_profile.languages_taught = [l.value for l in request.languages_taught]
    tutor_profile.languages_spoken = [l.value for l in request.languages_spoken]
    tutor_profile.topics = [t.value for t in request.topics]

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
            "headline": tutor_profile.headline,
            "bio": tutor_profile.bio,
            "languages_taught": tutor_profile.languages_taught,
            "languages_spoken": tutor_profile.languages_spoken,
            "topics": tutor_profile.topics,
            "is_published": tutor_profile.is_published
        }
    }
