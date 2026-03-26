from datetime import datetime
from typing import Any, List, Optional
from datetime import date, time
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from models.database_models import AvailabilityRule
from models.database_models import (
    BookingStatus,
    Country,
    Interest,
    Language,
    RoleType,
    SlotStatus,
    Timezone,
    TutorTopic,
)

class BaseResponse(BaseModel):
    response_code: str
    detail: str
    data: Optional[Any] = None

class SignupRequest(BaseModel):
    email: EmailStr
    country: Country
    birth_year: int
    user_role: RoleType

class LoginRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)

class TokenData(BaseModel):
    token: str 
    tutor_id: UUID
    student_id: UUID

class TokenResponse(BaseResponse):
    data: Optional[TokenData] = None

class ProfileCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50)
    timezone: Timezone
    primary_language: Language
    target_language: Language
    interests: List[Interest]
    bio: str = Field(..., max_length=400)

class ProfileData(BaseModel):
    user_id: str
    display_name: str
    timezone: Timezone
    primary_language: Language
    target_language: Language
    interests: List[Interest]
    bio: str

class ProfileResponse(BaseResponse):
    data: Optional[ProfileData] = None

class TutorProfileCreate(BaseModel):
    name: str
    headline: str = Field(..., min_length=5, max_length=100)
    bio: str = Field(..., min_length=5, max_length=500)
    languages_taught: str
    languages_spoken: str
    topics: List[TutorTopic]
    is_published: bool

class TutorProfileData(BaseModel):
    user_id: str
    name: str
    headline: str
    bio: str
    languages_taught: str
    languages_spoken: str
    topics: List[TutorTopic]
    is_published: bool

class TutorProfileResponse(BaseResponse):
    data: Optional[TutorProfileData] = None

class AvailabilityRuleCreate(BaseModel):
    availability_date: date
    start_time: time
    end_time: time
    topic: str

class AvailabilityRuleData(BaseModel):
    tutor_id: str
    availability_date: date
    start_time: time
    end_time: time
    topic: str

class AvailabilityResponse(BaseModel):
    response_code: str = "1"
    detail: str
    data: Optional[AvailabilityRuleData] = None

class TutorRecommendation(BaseModel):
    id: UUID
    display_name: str
    teaches_languages: str  
    topics: List[str]        
    next_slot: Optional[datetime] = None
    
class MarketplaceResponse(BaseModel):
    tutors: List[TutorRecommendation]   

class SlotSchema(BaseModel):
    slot_date: date
    start_time: time

class TutorDetailData(BaseModel):
    name: str
    languages_taught: str
    languages_spoken: str    
    topics: List[str]
    bio: str
    formated_slots: List[SlotSchema]


class TutorDetailResponse(BaseModel):
    data: Optional[TutorDetailData] = None

class SlotBookingCreate(BaseModel):
    slot_id: UUID
    goal: str

class SlotBookingData(BaseModel):
    booking_id: UUID
    tutor_id: UUID
    slot_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str

class SlotBookingResponse(BaseModel):
    response_code: str = "1"
    detail: str
    data: Optional[SlotBookingData] = None

