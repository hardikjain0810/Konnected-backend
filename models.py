from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

class User(BaseModel):
    id: uuid.UUID
    email: str
    country: str
    birth_year: int
    ui_language: str
    status: str

class Profile(BaseModel):
    user_id: uuid.UUID
    display_name: Optional[str]
    timezone: Optional[str]
    primary_language: Optional[str]
    target_language: Optional[str]
    interests: Optional[List[str]]

class TutorSlot(BaseModel):
    id: uuid.UUID
    tutor_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    status: str

class Booking(BaseModel):
    id: uuid.UUID
    tutor_id: uuid.UUID
    student_id: uuid.UUID
    slot_id: uuid.UUID
    status: str
    goal: str
    note: Optional[str]