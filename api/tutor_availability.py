from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, date
from core.logging_config import get_logger
from core.utils import get_lang
from core.auth import get_current_user
from db.database import get_db
from core.translations import get_text
from models.database_models import UserRole, AvailabilityRule, TutorSlot, SlotStatus, RoleType
from schemas.schemas import AvailabilityRuleCreate, AvailabilityResponse

router = APIRouter(prefix="/tutor", tags=["tutor"])
logger = get_logger()

@router.post("/availability", response_model=AvailabilityResponse)
def set_availability(
    request: AvailabilityRuleCreate,
    req: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    lang = get_lang(req)
    
    # 1. Role Validation: Ensure user is a tutor
    role = db.query(UserRole).filter(
        UserRole.user_id == current_user.id,
        UserRole.role == RoleType.tutor
    ).first()

    if not role:
        logger.warning(f"Non-tutor tried to set availability: {current_user.id}")
        raise HTTPException(status_code=403, detail="Only tutors can set availability")

    # 2. Clear existing rules for this tutor (Update behavior)
    db.query(AvailabilityRule).filter(AvailabilityRule.tutor_id == current_user.id).delete()

    # 3. Process Rules and Generate Slots
    for item in request.availability:
        if item.start_time >= item.end_time:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time range for {item.availability_date}"
            )

        # Save the Rule
        new_rule = AvailabilityRule(
            tutor_id=current_user.id,
            date=item.availability_date,
            start_time=item.start_time,
            end_time=item.end_time,
            topic=item.topic
        )
        db.add(new_rule)

        # 4. Generate 30-minute Slots
        # Calculate how many 30-min blocks fit in the range
        current_dt = datetime.combine(item.availability_date, item.start_time)
        end_dt = datetime.combine(item.availability_date, item.end_time)

        while current_dt + timedelta(minutes=30) <= end_dt:
            slot_end = current_dt + timedelta(minutes=30)
            
            # Check if slot already exists to avoid UniqueConstraint errors
            existing_slot = db.query(TutorSlot).filter(
                TutorSlot.tutor_id == current_user.id,
                TutorSlot.start_at == current_dt
            ).first()

            if not existing_slot:
                new_slot = TutorSlot(
                    tutor_id=current_user.id,
                    start_at=current_dt,
                    end_at=slot_end,
                    status=SlotStatus.open # Mark as open for booking [cite: 121, 179]
                )
                db.add(new_slot)
            
            current_dt = slot_end

    try:
        db.commit()
        logger.info(f"Availability and slots generated for tutor: {current_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving availability: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error saving slots")

    return {
        "response_code": "1",
        "detail": get_text("availability_saved", lang),
        "data": {
            "tutor_id": str(current_user.id),
            "availability_date": str(item.availability_date),
            "start_time": str(item.start_time),
            "end_time": str(item.end_time),
            "topic": str(item.topic)
        }
    }