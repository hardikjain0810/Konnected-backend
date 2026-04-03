from datetime import datetime, timedelta, timezone
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.translations import get_text
from core.utils import get_lang
from db.database import get_db
from db.redis import redis_client
from models.database_models import Booking, TutorSlot, User, Profile, TutorProfile
from schemas.schemas import (
    LiveSessionJoinRequest,
    LiveSessionJoinResponse,
    LiveSessionStatusRequest,
    LiveSessionStatusResponse,
    LiveSessionEndRequest,
    LiveSessionEndResponse,
)

router = APIRouter(prefix="/live-session", tags=["live-session"])


def _parse_uuid(value: str, error_message: str):
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_message)


def _build_room_id(tutor_id: str, slot: TutorSlot) -> str:
    date_str = slot.start_at.date().isoformat()
    start_str = slot.start_at.time().strftime("%H:%M:%S")
    end_str = slot.end_at.time().strftime("%H:%M:%S")
    return f"{tutor_id}_{date_str}_{start_str}_{end_str}"


def _within_join_window(slot: TutorSlot) -> bool:
    now = datetime.now()
    open_at = slot.start_at - timedelta(minutes=5)
    close_at = slot.end_at + timedelta(minutes=10)
    return open_at <= now <= close_at


def _load_zego_generator():
    # Support common import layouts for ZEGO python assistant package.
    try:
        from zego_server_assistant import generate_token04  # type: ignore
        return generate_token04
    except Exception:
        pass
    try:
        from zego_server_assistant.token04 import generate_token04  # type: ignore
        return generate_token04
    except Exception:
        pass
    try:
        from token04 import generate_token04  # type: ignore
        return generate_token04
    except Exception:
        pass
    return None


def _generate_live_token(user_id: str, room_id: str, role: str) -> tuple[str, datetime]:
    if not settings.ZEGO_SERVER_SECRET:
        raise ValueError("ZEGO_SERVER_SECRET is missing")

    app_id = int(settings.ZEGO_APP_ID)
    if app_id <= 0:
        raise ValueError("ZEGO_APP_ID is invalid")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.ZEGO_TOKEN_EXPIRE_SECONDS)
    effective_seconds = int(settings.ZEGO_TOKEN_EXPIRE_SECONDS)

    # Restrict token to this room; allow login + publish.
    token_payload = json.dumps(
        {
            "room_id": room_id,
            "privilege": {
                "1": 1,
                "2": 1,
            },
            "stream_id_list": [],
            "role": role,
        },
        separators=(",", ":"),
    )

    generator = _load_zego_generator()
    if generator is None:
        raise ValueError("ZEGO token04 generator package not installed")

    try:
        token = generator(app_id, user_id, settings.ZEGO_SERVER_SECRET, effective_seconds, token_payload)
    except TypeError:
        # Some helper versions don't take payload in signature.
        token = generator(app_id, user_id, settings.ZEGO_SERVER_SECRET, effective_seconds)

    if isinstance(token, tuple):
        # Defensive support if SDK returns (token, error)
        token = token[0]
    if not token:
        raise ValueError("Token generation returned empty token")

    return str(token), expires_at


def _get_user_name(db: Session, actor_type: str, actor_uuid: UUID) -> str:
    if actor_type == "student":
        profile = db.query(Profile).filter(Profile.user_id == actor_uuid).first()
        if profile and profile.display_name:
            return profile.display_name
    else:
        tutor_profile = db.query(TutorProfile).filter(TutorProfile.user_id == actor_uuid).first()
        if tutor_profile and tutor_profile.name:
            return tutor_profile.name

    user = db.query(User).filter(User.id == actor_uuid).first()
    return user.email if user else str(actor_uuid)


@router.post("/join", response_model=LiveSessionJoinResponse)
def join_live_session(
    payload: LiveSessionJoinRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    lang = get_lang(req)

    if str(current_user.id) != payload.actor_id:
        raise HTTPException(status_code=401, detail=get_text("identity_mismatch", lang))

    actor_uuid = _parse_uuid(payload.actor_id, get_text("validation_error", lang))
    tutor_uuid = _parse_uuid(payload.tutor_id, get_text("validation_error", lang))
    slot_uuid = _parse_uuid(payload.slot_id, get_text("validation_error", lang))

    slot = db.query(TutorSlot).filter(TutorSlot.id == slot_uuid, TutorSlot.tutor_id == tutor_uuid).first()
    if not slot:
        raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    if payload.date != slot.start_at.date() or payload.start_time != slot.start_at.time() or payload.end_time != slot.end_at.time():
        raise HTTPException(status_code=422, detail=get_text("validation_error", lang))

    # Access validation
    if payload.actor_type == "student":
        booking = db.query(Booking).filter(
            Booking.slot_id == slot_uuid,
            Booking.tutor_id == tutor_uuid,
            Booking.student_id == actor_uuid
        ).first()
        if not booking:
            raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))
    else:
        if actor_uuid != tutor_uuid:
            raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    if not _within_join_window(slot):
        raise HTTPException(status_code=422, detail=get_text("outside_join_window", lang))

    room_id = _build_room_id(payload.tutor_id, slot)

    # Overlap rule for student
    if payload.actor_type == "student":
        active_room = redis_client.get_user_active_room(payload.actor_id)
        if active_room and active_room != room_id:
            raise HTTPException(status_code=409, detail=get_text("student_overlap_conflict", lang))

    room_meta = redis_client.get_live_session_meta(room_id) or {}
    host_joined = bool(room_meta.get("host_joined", False))
    session_state = room_meta.get("session_state", "waiting")

    if payload.actor_type == "tutor":
        host_joined = True
        session_state = "live"

    can_enter = host_joined or payload.actor_type == "tutor" or (not payload.wait_for_host)
    waiting_message = None if can_enter else get_text("live_waiting_message", lang)

    try:
        token, expires_at = _generate_live_token(payload.actor_id, room_id, payload.actor_type)
    except Exception:
        raise HTTPException(status_code=500, detail=get_text("token_generation_failed", lang))

    redis_client.set_live_session_meta(
        room_id,
        {
            "room_id": room_id,
            "slot_id": payload.slot_id,
            "tutor_id": payload.tutor_id,
            "host_joined": host_joined,
            "session_state": session_state if session_state == "ended" else ("live" if host_joined else "waiting"),
            "start_at": slot.start_at.isoformat(),
            "end_at": slot.end_at.isoformat(),
        },
        ttl_seconds=max(settings.ZEGO_TOKEN_EXPIRE_SECONDS, 7200),
    )

    if can_enter:
        redis_client.set_user_active_room(payload.actor_id, room_id, ttl_seconds=max(settings.ZEGO_TOKEN_EXPIRE_SECONDS, 7200))
        redis_client.add_room_participant(room_id, payload.actor_id, ttl_seconds=max(settings.ZEGO_TOKEN_EXPIRE_SECONDS, 7200))

    return {
        "response_code": "200",
        "detail": get_text("join_payload_generated", lang),
        "data": {
            "room_id": room_id,
            "token": token,
            "user_id": payload.actor_id,
            "user_name": _get_user_name(db, payload.actor_type, actor_uuid),
            "role": payload.actor_type,
            "can_enter_room": can_enter,
            "host_joined": host_joined,
            "waiting_message": waiting_message,
            "expires_at": expires_at,
        },
    }


@router.post("/status", response_model=LiveSessionStatusResponse)
def live_session_status(
    payload: LiveSessionStatusRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lang = get_lang(req)

    if str(current_user.id) != payload.actor_id:
        raise HTTPException(status_code=401, detail=get_text("identity_mismatch", lang))

    actor_uuid = _parse_uuid(payload.actor_id, get_text("validation_error", lang))
    tutor_uuid = _parse_uuid(payload.tutor_id, get_text("validation_error", lang))
    slot_uuid = _parse_uuid(payload.slot_id, get_text("validation_error", lang))

    slot = db.query(TutorSlot).filter(TutorSlot.id == slot_uuid, TutorSlot.tutor_id == tutor_uuid).first()
    if not slot:
        raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    is_tutor = actor_uuid == tutor_uuid
    if not is_tutor:
        booking = db.query(Booking).filter(
            Booking.slot_id == slot_uuid,
            Booking.tutor_id == tutor_uuid,
            Booking.student_id == actor_uuid
        ).first()
        if not booking:
            raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    room_id = _build_room_id(payload.tutor_id, slot)
    room_meta = redis_client.get_live_session_meta(room_id) or {}

    host_joined = bool(room_meta.get("host_joined", False))
    session_state = room_meta.get("session_state", "waiting")
    can_enter = host_joined and session_state != "ended"

    return {
        "response_code": "200",
        "detail": get_text("live_status_fetched", lang),
        "data": {
            "room_id": room_id,
            "session_state": session_state,
            "host_joined": host_joined,
            "can_enter_room": can_enter,
            "server_time": datetime.now(timezone.utc),
        },
    }


@router.post("/end", response_model=LiveSessionEndResponse)
def end_live_session(
    payload: LiveSessionEndRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lang = get_lang(req)

    tutor_uuid = _parse_uuid(payload.tutor_id, get_text("validation_error", lang))
    slot_uuid = _parse_uuid(payload.slot_id, get_text("validation_error", lang))

    if current_user.id != tutor_uuid:
        raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    slot = db.query(TutorSlot).filter(TutorSlot.id == slot_uuid, TutorSlot.tutor_id == tutor_uuid).first()
    if not slot:
        raise HTTPException(status_code=403, detail=get_text("slot_not_authorized", lang))

    expected_room_id = _build_room_id(payload.tutor_id, slot)
    if payload.room_id != expected_room_id:
        raise HTTPException(status_code=422, detail=get_text("room_mismatch", lang))

    ended_at = datetime.now(timezone.utc)

    room_meta = redis_client.get_live_session_meta(expected_room_id) or {}
    room_meta.update(
        {
            "session_state": "ended",
            "host_joined": True,
            "ended_at": ended_at.isoformat(),
        }
    )
    redis_client.set_live_session_meta(expected_room_id, room_meta, ttl_seconds=7200)

    participants = redis_client.get_room_participants(expected_room_id)
    for participant_id in participants:
        redis_client.clear_user_active_room(participant_id)
    redis_client.clear_room_participants(expected_room_id)

    return {
        "response_code": "200",
        "detail": get_text("live_session_ended", lang),
        "data": {
            "room_id": expected_room_id,
            "ended_at": ended_at,
            "session_state": "ended",
        },
    }
