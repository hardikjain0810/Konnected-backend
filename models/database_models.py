import uuid
import enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Enum, CheckConstraint, UniqueConstraint, Time
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ENUMS
class Country(enum.Enum):
    US = "US"
    KR = "KR"

class UILanguage(enum.Enum):
    en = "en"
    ko = "ko"

class UserStatus(enum.Enum):
    active = "active"
    suspended = "suspended"

class RoleType(enum.Enum):
    student = "student"
    tutor = "tutor"

class SlotStatus(enum.Enum):
    open = "open"
    booked = "booked"
    disabled = "disabled"

class BookingStatus(enum.Enum):
    scheduled = "scheduled"
    canceled = "canceled"
    completed = "completed"
    no_show = "no_show"

class BookingGoal(enum.Enum):
    conversation = "conversation"
    pronunciation = "pronunciation"
    homework = "homework"
    culture = "culture"

class Language(enum.Enum):
    English = "English"
    Hindi = "Hindi"
    Spanish = "Spanish"
    Korean = "Korean"

class Timezone(enum.Enum):
    UTC_minus_5 = "UTC-5 (EST)"
    UTC_plus_9 = "UTC+9 (KST)"
    UTC_plus_5_30 = "UTC+5:30 (IST)"

class Interest(enum.Enum):
    Sports = "Sports"
    Music = "Music"
    Examprep = "Examprep"
    Culture = "Culture"
    Reading = "Reading"
    Travel = "Travel"

class ReportReason(enum.Enum):
    inappropriate_behavior = "inappropriate_behavior"
    harassment = "harassment"
    spam = "spam"
    underage_concern = "underage_concern"
    other = "other"


# TABLES 

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    country = Column(Enum(Country))
    birth_year = Column(Integer)
    ui_language = Column(Enum(UILanguage))
    status = Column(Enum(UserStatus), default=UserStatus.active)
    created_at = Column(DateTime)


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    display_name = Column(String)
    timezone = Column(Enum(Timezone))
    primary_language = Column(Enum(Language))
    target_language = Column(Enum(Language))
    interests = Column(ARRAY(String))
    bio = Column(String(400))  # Short bio within 400 characters


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(Enum(RoleType), primary_key=True)


class TutorProfile(Base):
    __tablename__ = "tutor_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    headline = Column(String)
    bio = Column(String)
    languages = Column(String)
    topics = Column(String)
    is_published = Column(Boolean, default=False)


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    weekday = Column(Integer)
    start_time = Column(Time)
    end_time = Column(Time)


class TutorSlot(Base):
    __tablename__ = "tutor_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    start_at = Column(DateTime, index=True)
    end_at = Column(DateTime)
    status = Column(Enum(SlotStatus), default=SlotStatus.open)

    __table_args__ = (
        UniqueConstraint("tutor_id", "start_at"),
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tutor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    slot_id = Column(UUID(as_uuid=True), ForeignKey("tutor_slots.id"), unique=True)

    status = Column(Enum(BookingStatus))
    goal = Column(Enum(BookingGoal))
    note = Column(String)

    starts_at = Column(DateTime)
    ends_at = Column(DateTime)

    __table_args__ = (
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint("tutor_id <> student_id"),
    )


class Block(Base):
    __tablename__ = "blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blocker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    blocked_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id"),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reported_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"))

    reason = Column(Enum(ReportReason))
    details = Column(String)