from datetime import datetime, timedelta, timezone
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.logging_config import logger
from core.translations import get_text
from core.utils import get_lang
from db.database import get_db
from db.redis import redis_client
from models.database_models import (
    Booking,
    TutorSlot,
    User,
    Profile,
    TutorProfile,
    Timezone,
    LiveSessionStats,
    LiveSessionParticipant,
)
from schemas.schemas import (
    LiveSessionJoinRequest,
    LiveSessionJoinResponse,
    LiveSessionStatusRequest,
    LiveSessionStatusResponse,
    LiveSessionEndRequest,
    LiveSessionEndResponse,
    LiveSessionAnalyticsRequest,
    LiveSessionAnalyticsResponse,
)

router = APIRouter(prefix="/live-session", tags=["live-session"])


def _parse_uuid(value: str, error_message: str):
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_message)


def _build_room_id(tutor_id: str, slot: TutorSlot) -> str:
    date_str = slot.start_at.date().isoformat()
    start_str = slot.start_at.time().strftime("%H_%M_%S")
    end_str = slot.end_at.time().strftime("%H_%M_%S")
    return f"{tutor_id}_{date_str}_{start_str}_{end_str}"


def _timezone_from_profile(profile_tz: Timezone | None) -> timezone | None:
    if profile_tz is None:
        return None
    raw = profile_tz.value if hasattr(profile_tz, "value") else str(profile_tz)
    tz_map = {
        "UTC-5 (EST)": timezone(timedelta(hours=-5)),
        "UTC+9 (KST)": timezone(timedelta(hours=9)),
        "UTC+5:30 (IST)": timezone(timedelta(hours=5, minutes=30)),
    }
    return tz_map.get(raw)


def _within_join_window(slot: TutorSlot, slot_tz: timezone | None = None) -> bool:
    # Slot timestamps are persisted as DateTime (often naive).
    # If tutor timezone is known, interpret naive slot times in that timezone.
    if slot.start_at.tzinfo is None and slot.end_at.tzinfo is None:
        open_at = slot.start_at - timedelta(minutes=5)
        close_at = slot.end_at + timedelta(minutes=10)

        if slot_tz is not None:
            start_at_utc = slot.start_at.replace(tzinfo=slot_tz).astimezone(timezone.utc)
            end_at_utc = slot.end_at.replace(tzinfo=slot_tz).astimezone(timezone.utc)
            open_at_utc = start_at_utc - timedelta(minutes=5)
            close_at_utc = end_at_utc + timedelta(minutes=10)
            now_utc = datetime.now(timezone.utc)
            in_window = open_at_utc <= now_utc <= close_at_utc
            logger.info(
                "Live join window check (naive+tutor_tz): open_at_utc=%s close_at_utc=%s now_utc=%s in_window=%s",
                open_at_utc.isoformat(),
                close_at_utc.isoformat(),
                now_utc.isoformat(),
                in_window,
            )
            return in_window

        # Fallback: check common app timezones to avoid false negatives
        # when profile timezone data is absent for old users.
        candidate_tzs = [
            timezone.utc,
            timezone(timedelta(hours=-5)),
            timezone(timedelta(hours=9)),
            timezone(timedelta(hours=5, minutes=30)),
        ]
        in_any_window = False
        now_utc = datetime.now(timezone.utc)
        candidates = []
        for tz in candidate_tzs:
            now_in_tz_naive = now_utc.astimezone(tz).replace(tzinfo=None)
            in_window = open_at <= now_in_tz_naive <= close_at
            candidates.append(f"{tz.tzname(None)}:{now_in_tz_naive.isoformat()}={in_window}")
            in_any_window = in_any_window or in_window

        logger.info(
            "Live join window check (naive+fallback): open_at=%s close_at=%s candidates=%s in_any=%s",
            open_at.isoformat(),
            close_at.isoformat(),
            " | ".join(candidates),
            in_any_window,
        )
        return in_any_window

    now_utc = datetime.now(timezone.utc)
    start_at_utc = slot.start_at.astimezone(timezone.utc)
    end_at_utc = slot.end_at.astimezone(timezone.utc)
    open_at_utc = start_at_utc - timedelta(minutes=5)
    close_at_utc = end_at_utc + timedelta(minutes=10)
    in_window = open_at_utc <= now_utc <= close_at_utc
    logger.info(
        "Live join window check (aware): open_at_utc=%s close_at_utc=%s now_utc=%s in_window=%s",
        open_at_utc.isoformat(),
        close_at_utc.isoformat(),
        now_utc.isoformat(),
        in_window,
    )
    return in_window


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
    try:
        # Common path when copying ZEGO token generator source directly.
        from zego_token_pkg.python.src.token04 import generate_token04  # type: ignore
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

    if hasattr(token, "error_code"):
        if int(getattr(token, "error_code", -1)) != 0:
            raise ValueError(getattr(token, "error_message", "Unknown ZEGO token error"))
        token = getattr(token, "token", "")
    elif isinstance(token, tuple):
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


def _touch_session_stats(
    db: Session,
    room_id: str,
    slot_uuid: UUID,
    tutor_uuid: UUID,
) -> LiveSessionStats:
    now = datetime.now(timezone.utc)
    stats = db.query(LiveSessionStats).filter(LiveSessionStats.room_id == room_id).first()
    booked_count = db.query(Booking).filter(Booking.slot_id == slot_uuid, Booking.tutor_id == tutor_uuid).count()

    if not stats:
        stats = LiveSessionStats(
            room_id=room_id,
            slot_id=slot_uuid,
            tutor_id=tutor_uuid,
            booked_count=booked_count,
            joined_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(stats)
        db.flush()
        return stats

    stats.booked_count = booked_count
    stats.updated_at = now
    db.flush()
    return stats


def _mark_participant_joined(
    db: Session,
    room_id: str,
    slot_uuid: UUID,
    tutor_uuid: UUID,
    actor_uuid: UUID,
    actor_type: str,
) -> None:
    now = datetime.now(timezone.utc)
    participant = db.query(LiveSessionParticipant).filter(
        LiveSessionParticipant.room_id == room_id,
        LiveSessionParticipant.actor_id == actor_uuid,
    ).first()

    if not participant:
        participant = LiveSessionParticipant(
            room_id=room_id,
            slot_id=slot_uuid,
            tutor_id=tutor_uuid,
            actor_id=actor_uuid,
            actor_type=actor_type,
            first_joined_at=now,
            last_joined_at=now,
            is_active=True,
            total_seconds=0,
            created_at=now,
            updated_at=now,
        )
        db.add(participant)
        db.flush()
        return

    if not participant.is_active:
        participant.last_joined_at = now
        participant.is_active = True
    participant.updated_at = now
    db.flush()


def _finalize_session_participants(db: Session, room_id: str, ended_at: datetime) -> None:
    participants = db.query(LiveSessionParticipant).filter(
        LiveSessionParticipant.room_id == room_id
    ).all()
    for participant in participants:
        if participant.is_active and participant.last_joined_at:
            delta_seconds = int((ended_at - participant.last_joined_at).total_seconds())
            participant.total_seconds = int(participant.total_seconds or 0) + max(delta_seconds, 0)
            participant.last_left_at = ended_at
            participant.is_active = False
        participant.updated_at = ended_at
    db.flush()


def _effective_total_seconds(participant: LiveSessionParticipant, now_utc: datetime) -> int:
    total = int(participant.total_seconds or 0)
    if participant.is_active and participant.last_joined_at:
        total += max(int((now_utc - participant.last_joined_at).total_seconds()), 0)
    return total


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

    tutor_profile = db.query(Profile).filter(Profile.user_id == tutor_uuid).first()
    tutor_tz = _timezone_from_profile(tutor_profile.timezone if tutor_profile else None)

    # Student joins are time-gated. Tutor can always join their own slot.
    if payload.actor_type == "student" and not _within_join_window(slot, tutor_tz):
        raise HTTPException(status_code=422, detail=get_text("outside_join_window", lang))

    room_id = _build_room_id(payload.tutor_id, slot)
    stats = _touch_session_stats(db, room_id, slot_uuid, tutor_uuid)

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
    except Exception as e:
        logger.error(f"ZEGO token generation failed: {str(e)}")
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
        _mark_participant_joined(db, room_id, slot_uuid, tutor_uuid, actor_uuid, payload.actor_type)
        stats.joined_count = db.query(LiveSessionParticipant).filter(LiveSessionParticipant.room_id == room_id).count()
        stats.updated_at = datetime.now(timezone.utc)

    db.commit()

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
    if session_state == "ended":
        host_joined = False
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

    expected_room_id = _build_room_id(payload.tutor_id, slot)
    if payload.room_id != expected_room_id:
        raise HTTPException(status_code=422, detail=get_text("room_mismatch", lang))

    ended_at = datetime.now(timezone.utc)

    room_meta = redis_client.get_live_session_meta(expected_room_id) or {}
    room_meta.update(
        {
            "session_state": "ended",
            "host_joined": False,
            "ended_at": ended_at.isoformat(),
        }
    )
    redis_client.set_live_session_meta(expected_room_id, room_meta, ttl_seconds=7200)

    stats = _touch_session_stats(db, expected_room_id, slot_uuid, tutor_uuid)
    _finalize_session_participants(db, expected_room_id, ended_at)
    stats.joined_count = db.query(LiveSessionParticipant).filter(
        LiveSessionParticipant.room_id == expected_room_id
    ).count()
    stats.ended_at = ended_at
    stats.updated_at = ended_at

    participants = redis_client.get_room_participants(expected_room_id)
    for participant_id in participants:
        redis_client.clear_user_active_room(participant_id)
    redis_client.clear_room_participants(expected_room_id)
    db.commit()

    return {
        "response_code": "200",
        "detail": get_text("live_session_ended", lang),
        "data": {
            "room_id": expected_room_id,
            "ended_at": ended_at,
            "session_state": "ended",
        },
    }

@router.post("/analytics", response_model=LiveSessionAnalyticsResponse)
def live_session_analytics(
    payload: LiveSessionAnalyticsRequest,
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
    stats = db.query(LiveSessionStats).filter(LiveSessionStats.room_id == room_id).first()
    participants = db.query(LiveSessionParticipant).filter(
        LiveSessionParticipant.room_id == room_id,
        LiveSessionParticipant.actor_type == "student",
    ).all()

    now_utc = datetime.now(timezone.utc)
    booked_count = db.query(Booking).filter(
        Booking.slot_id == slot_uuid,
        Booking.tutor_id == tutor_uuid
    ).count()
    joined_count = db.query(LiveSessionParticipant).filter(
        LiveSessionParticipant.room_id == room_id
    ).count()

    return {
        "response_code": "200",
        "detail": get_text("live_status_fetched", lang),
        "data": {
            "room_id": room_id,
            "booked_count": int(stats.booked_count) if stats else booked_count,
            "joined_count": int(stats.joined_count) if stats else joined_count,
            "session_ended_at": stats.ended_at if stats else None,
            "participants": [
                {
                    "actor_id": str(p.actor_id),
                    "actor_type": p.actor_type,
                    "total_seconds": _effective_total_seconds(p, now_utc),
                    "first_joined_at": p.first_joined_at,
                    "last_left_at": p.last_left_at,
                }
                for p in participants
            ],
        },
    }
