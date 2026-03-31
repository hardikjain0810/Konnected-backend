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
    access_token: str 
    token_type: str
    tutor_id: Optional[UUID] = None
    student_id: Optional[UUID] = None

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
    topics: List[str]
    is_published: bool

class TutorProfileData(BaseModel):
    user_id: str
    name: str
    headline: str
    bio: str
    languages_taught: str
    languages_spoken: str
    topics: List[str]
    is_published: bool

class TutorProfileResponse(BaseResponse):
    data: Optional[TutorProfileData] = None

class AvailabilityRuleCreate(BaseModel):
    tutor_id: str
    availability_date: date
    start_time: time
    end_time: time
    topic: str
    short_description: str

class AvailabilityRuleData(BaseModel):
    tutor_id: str
    availability_date: date
    start_time: time
    end_time: time
    topic: str
    short_description : str

class AvailabilityResponse(BaseResponse):
    response_code: str 
    detail: str
    data: List[AvailabilityRuleData] = None

class TutorRecommendation(BaseModel):
    id: UUID
    display_name: str
    teaches_languages: str  
    topics: List[str]        
    next_slot: Optional[datetime] = None

class TutorDataWrapper(BaseModel):
    tutors: List[TutorRecommendation]
    
class MarketplaceResponse(BaseResponse):
    response_code: str
    detail: str
    data: TutorDataWrapper   

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
    tutor_id: UUID
    slot_date: date
    start_time: time
    topic: str

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

class TutorTopicRequest(BaseModel):
    tutor_id: UUID

class TutorTopicResponse(BaseModel):
    response_code: str = "1"
    detail: str
    topics: List[str]

class BookingsData(BaseModel):
    display_name: str
    starts_at: datetime
    topic: str

class BookingOut(BaseResponse):
    response_code: str = "1"
    detail: str
    data: List[BookingsData]

class GetTutorAvailability(BaseModel):
    tutor_id: UUID
    availability_date: Optional[str] = None 

class GetTutorAvailabilityData(BaseModel):
    tutor_id: str
    date: date
    start_time: time
    end_time: time
    topics: str

class GetTutorAvailabilityResponse(BaseResponse):
    response_code:str
    detail: str 
    data: List[GetTutorAvailabilityData]

class CancelSlotCreate(BaseModel):
    tutor_id: UUID
    slot_id: UUID

class CancelSlotData(BaseResponse):
    tutor_id: UUID
    slot_id: UUID

class CancelSlotResponse(BaseResponse):
    data: List[CancelSlotData]

class StudentBookingCreate(BaseModel):
    student_id: str

class StudentBookingDetail(BaseModel):
    slot_id: UUID
    tutor_name: str
    start_date: str
    start_time: str
    end_time: str
    status: str

class StudentBookingsResponse(BaseResponse):
    response_code: str
    detail: str
    data: List[StudentBookingDetail]

class GetAvailabilityRuleCreate(BaseModel):
    tutor_id: str
    availability_date: Optional[str]

class GetAvailabilityRuleData(BaseModel):
    tutor_id: str
    availability_date: date = Field(alias="date")
    start_time: time
    end_time: time
    topic: str
    short_description : str

class GetAvailabilityResponse(BaseResponse):
    response_code: str 
    detail: str
    data: List[AvailabilityRuleData] = None

