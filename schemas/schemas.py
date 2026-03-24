from pydantic import BaseModel, EmailStr, Field
from models.database_models import Country, Language, Timezone, Interest, RoleType, TutorTopic
from typing import Optional, Any, List

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
    token_type: str = "bearer"

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
    headline: str = Field(..., min_length=10, max_length=100)
    bio: str = Field(..., min_length=50, max_length=500)
    languages_taught: List[Language]
    languages_spoken: List[Language]
    topics: List[TutorTopic]

class TutorProfileData(BaseModel):
    user_id: str
    headline: str
    bio: str
    languages_taught: List[Language]
    languages_spoken: List[Language]
    topics: List[TutorTopic]
    is_published: bool

class TutorProfileResponse(BaseResponse):
    data: Optional[TutorProfileData] = None
