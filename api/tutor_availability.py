from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import Date, Time, cast
from datetime import datetime, timedelta, date
from core.logging_config import get_logger
from core.utils import get_lang
from typing import Optional, List
from db.database import get_db
from models.database_models import AvailabilityRule, TutorSlot, Booking
from schemas.schemas import AvailabilityRuleCreate, AvailabilityResponse, GetAvailabilityResponse, GetAvailabilityRuleCreate

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

    # Duration Validation and time integrity
    start_dt = datetime.combine(request.availability_date, request.start_time)
    end_dt = datetime.combine(request.availability_date, request.end_time)

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    duration_minutes = (end_dt - start_dt).total_seconds() / 60
    if duration_minutes % 30 != 0:
        raise HTTPException(
            status_code=400, 
            detail="Duration must be a multiple of 30 minutes (e.g., 30, 60, 90 mins)"
        )
    
    # Overlap validation
    overlapping_rule = db.query(AvailabilityRule).filter(
        AvailabilityRule.tutor_id == request.tutor_id,
        AvailabilityRule.date == request.availability_date,
        AvailabilityRule.start_time < request.end_time,  # S1 < E2
        AvailabilityRule.end_time > request.start_time   # E1 > S2
    ).first()

    if overlapping_rule:
        raise HTTPException(status_code=400, detail=f"Conflict: You already have availability set from {overlapping_rule.start_time} to {overlapping_rule.end_time}")

    try:
        # Save the main Availability Rule
        new_rule = AvailabilityRule(
            tutor_id=request.tutor_id,
            date=request.availability_date,
            start_time=request.start_time,
            end_time=request.end_time,
            topic=request.topic,
            short_description=request.short_description
        )
        db.add(new_rule)

        # Generate the 30-minute Slots
        # This "carves" a 60-min window into two 30-min entries
        temp_start = start_dt
        while temp_start + timedelta(minutes=30) <= end_dt:
            temp_end = temp_start + timedelta(minutes=30)
            
            # Check for overlaps to avoid UniqueConstraint errors
            exists = db.query(TutorSlot).filter(
                TutorSlot.tutor_id == request.tutor_id,
                TutorSlot.start_at == temp_start
            ).first()

            if not exists:
                new_slot = TutorSlot(
                    tutor_id=request.tutor_id,
                    start_at=temp_start,
                    end_at=temp_end,
                    status="open"
                )
                db.add(new_slot)
            
            temp_start = temp_end # Move to the next 30-min block

        db.commit()
        
        return {
            "response_code": "1",
            "detail": "Availability and 30-minute slots generated successfully!",
            "data": [new_rule]
        }

    except Exception as e:
        db.rollback()
        logger.error({"error":str(e)})
        raise HTTPException(status_code=500, detail={"error":str(e)})
    
@router.post("/list-availability/{tutor_id}", response_model=GetAvailabilityResponse)
def get_tutor_availability(
    request: GetAvailabilityRuleCreate,
    db: Session = Depends(get_db)
):
    # 1. Get the rules
    query = db.query(AvailabilityRule).filter(AvailabilityRule.tutor_id == request.tutor_id)

    if request.availability_date and request.availability_date.strip() != "":
        try:
            parsed_date = datetime.strptime(request.availability_date, "%Y-%m-%d").date()
            query = query.filter(AvailabilityRule.date == parsed_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format.")

    rules = query.all()
    formatted_data = []

    for rule in rules:
        # 2. Get the full TutorSlot object
        slot = db.query(TutorSlot).filter(
            TutorSlot.tutor_id == rule.tutor_id,
            cast(TutorSlot.start_at, Date) == rule.date,
            cast(TutorSlot.start_at, Time) == rule.start_time
        ).first()

        final_status = "open"
        current_slot_id = None

        if slot:
            current_slot_id = slot.id
            # 3. Check Booking table for status
            booking = db.query(Booking).filter(Booking.slot_id == slot.id).first()
            
            if booking:
                final_status = booking.status.value if hasattr(booking.status, 'value') else booking.status
            else:
                # Fallback to slot status (handle Enum if necessary)
                final_status = slot.status.value if hasattr(slot.status, 'value') else slot.status

        # 4. Construct the dictionary to match GetAvailabilityRuleData
        formatted_data.append({
            "slot_id": current_slot_id, # FIX: Don't use slot[0]
            "tutor_id": rule.tutor_id,
            "date": rule.date,          # Matches Field(alias="date")
            "start_time": rule.start_time,
            "end_time": rule.end_time,
            "topic": rule.topic,
            "short_description": rule.short_description,
            "status": str(final_status)
        })

    return {
        "response_code": "1",
        "detail": "Successfully retrieved availability list",
        "data": formatted_data
    }