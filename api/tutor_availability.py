from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Date, Time, cast, and_
from datetime import datetime, timedelta, date
from core.logging_config import get_logger
from uuid import UUID
from db.database import get_db
from models.database_models import AvailabilityRule, TutorSlot
from schemas.schemas import AvailabilityRuleCreate, AvailabilityResponse, TutorAvailabilitySlotResponse

router = APIRouter(prefix="/tutor", tags=["tutor"])
logger = get_logger()

@router.post("/availability", response_model=AvailabilityResponse)
def set_availability(
    request: AvailabilityRuleCreate,
    db: Session = Depends(get_db),
):
    # Date Range Validation (The 21-Day Rule)
    today = date.today()
    max_future_date = today + timedelta(days=21)

    if request.availability_date < today:
        raise HTTPException(status_code=400, detail="Cannot set availability for a past date")
    
    if request.availability_date > max_future_date:
        raise HTTPException(
            status_code=400, 
            detail=f"You can only set availability up to 21 days in advance (until {max_future_date})"
        )

    # 1. Define start and end
    start_dt = datetime.combine(request.availability_date, request.start_time)
    end_dt = datetime.combine(request.availability_date, request.end_time)

    # 2. Calculate exact duration in seconds
    duration_seconds = int((end_dt - start_dt).total_seconds())

    # 3. STRICT CHECK: Must be exactly 30 minutes (1800 seconds)
    if duration_seconds != 1800:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid duration. You must select exactly 30 minutes. Your selection was {duration_seconds // 60} minutes."
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
        raise HTTPException(status_code=400, detail="An active 30-minute slot already exists here.")

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
            "detail": "Availability and slot synchronized successfully!",
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
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/list-availability/{tutor_id}", response_model=TutorAvailabilitySlotResponse)
def get_tutor_availability(
    tutor_id: UUID,
    db: Session = Depends(get_db)
):
    rules = db.query(AvailabilityRule).filter(
        AvailabilityRule.tutor_id == tutor_id
    ).order_by(
        AvailabilityRule.date.asc(),
        AvailabilityRule.start_time.asc()
    ).all()

    formatted_data = [
        {
            "tutor_id": rule.tutor_id,
            "date": rule.date,
            "start_time": rule.start_time,
            "end_time": rule.end_time,
        }
        for rule in rules
    ]

    return {
        "response_code": "1",
        "detail": "Successfully retrieved availability list",
        "data": formatted_data
    }
