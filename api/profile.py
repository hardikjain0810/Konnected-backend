from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, Profile, Language, Timezone, Interest
from schemas.schemas import ProfileCreate, ProfileResponse, ProfileData
from core.utils import get_lang
from core.auth import get_current_user
from core.logging_config import logger
from core.translations import get_text
from core.exceptions import APIException

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/languages")
async def get_languages():
    return [lang.value for lang in Language]

@router.get("/timezones")
async def get_timezones():
    return [tz.value for tz in Timezone]

@router.get("/interests")
async def get_interests():
    return [interest.value for interest in Interest]

@router.post("/complete",response_model=ProfileResponse)
async def complete_profile(
    request: ProfileCreate,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    logger.info(f"Profile completion/update attempt for user: {current_user.email}")
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    
    if profile:
        logger.info(f"Updating existing profile for user: {current_user.email}")
        profile.display_name = request.display_name
        profile.timezone = request.timezone
        profile.primary_language = request.primary_language
        profile.target_language = request.target_language
        profile.interests = [interest.value for interest in request.interests]
        profile.bio = request.bio
    else:
        logger.info(f"Creating new profile for user: {current_user.email}")
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
        logger.info(f"Profile saved successfully for user: {current_user.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving profile for user {current_user.email}: {e}", exc_info=True)
        raise APIException(status_code=500, response_msg=get_text("profile_error", lang, error=str(e)))
    
    return {
        "response_code": "1",
        "response_msg": get_text("profile_success", lang),
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
