from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import TutorProfile # Ensure this import is correct
from core.utils import get_lang
from core.translations import get_text
from schemas.schemas import TutorTopicRequest, TutorTopicResponse

router = APIRouter()

@router.post("/get-topics", response_model=TutorTopicResponse)
async def get_tutor_topics(
    request: TutorTopicRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    lang = get_lang(req)
    # Look up the profile by tutor_id
    profile = db.query(TutorProfile).filter(
        TutorProfile.user_id == request.tutor_id
    ).first()

    # Handle case where tutor doesn't exist
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_text("tutor_profile_not_found", lang)
        )

    # Return the topics list
    return {
        "response_code": "1",
        "detail": get_text("tutor_topics_retrieved", lang, name=profile.name),
        "topics": profile.topics if profile.topics else []
    }
