from pydantic import BaseModel, EmailStr, Field
from database_models import Country, Language, Timezone, Interest
from typing import Optional, Any, List

class BaseResponse(BaseModel):
    response_code: str
    response_msg: str
    data: Optional[Any] = None

class SignupRequest(BaseModel):
    email: EmailStr
    country: Country
    birth_year: int

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
