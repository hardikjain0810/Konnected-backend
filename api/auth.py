from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.database import get_db
from models.database_models import User, Country, UserRole, RoleType
from schemas.schemas import SignupRequest, LoginRequest, VerifyOTPRequest, TokenResponse, BaseResponse
from core.utils import validate_email_eligibility, check_age_eligibility, generate_otp, get_lang
from db.redis import redis_client
from core.auth import create_access_token
from datetime import datetime,timezone
from core.logging_config import logger
from core.translations import get_text
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=BaseResponse)
async def signup(request: SignupRequest, response: Response, req: Request, db: Session = Depends(get_db)):
    lang = get_lang(req)
    logger.info(f"Signup attempt for email: {request.email}")

    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        logger.info(f"User already exists for email: {request.email}")
        raise HTTPException(status_code=400, detail=get_text("user_exists", lang))

    if not redis_client.check_send_limit(request.email):
        logger.warning(f"OTP send limit exceeded for email: {request.email}")
        raise HTTPException(status_code=429, detail=get_text("too_many_otp", lang))
    
    if not validate_email_eligibility(request.email, request.country):
        logger.warning(f"Invalid email domain for email: {request.email}")
        raise HTTPException(status_code=400, detail=get_text("invalid_email", lang))
    
    if not check_age_eligibility(request.birth_year):
        logger.warning(f"Age not eligible for email: {request.email}")
        raise HTTPException(status_code=400, detail=get_text("invalid_age", lang))
    
    otp = generate_otp()
    redis_client.set_auth_session(request.email, otp, request.country.value, request.birth_year, request.user_role.value)
    redis_client.increment_send_count(request.email)
    
    response.set_cookie(key="session_email", value=request.email, httponly=True, max_age=600) # 10 minutes

    logger.info(f"OTP generated for email: {request.email}")
    logger.info(f"OTP : {otp}")
    
    return {"response_code": "1", "detail": get_text("otp_sent", lang)}

@router.post("/login", response_model=BaseResponse)
async def login(request: LoginRequest, response: Response, req: Request, db: Session = Depends(get_db)):
    lang = get_lang(req)
    logger.info(f"Login attempt for email: {request.email}")

    # Check if user exists
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        logger.info(f"User does not exist for email: {request.email}")
        raise HTTPException(status_code=400, detail=get_text("user_not_found", lang))

    if not redis_client.check_send_limit(request.email):
        logger.warning(f"OTP send limit exceeded for email: {request.email}")
        raise HTTPException(status_code=429, detail=get_text("too_many_otp", lang))

    otp = generate_otp()
    # For login, we use the existing user's country and birth_year from DB
    redis_client.set_auth_session(request.email, otp, user.country.value, user.birth_year)
    redis_client.increment_send_count(request.email)

    response.set_cookie(key="session_email", value=request.email, httponly=True, max_age=600) # 10 minutes

    logger.info(f"OTP generated for login: {request.email}")
    logger.info(f"OTP : {otp}")

    return {"response_code": "1", "detail": get_text("otp_sent", lang)}

@router.post("/verify", response_model=TokenResponse)
async def verify(request: VerifyOTPRequest, response: Response, req: Request, db: Session = Depends(get_db), session_email: str = Cookie(None)):
    lang = get_lang(req)
    if not session_email:
        raise HTTPException(status_code=400, detail=get_text("session_expired", lang))

    logger.info(f"Verification attempt for email: {session_email}")
    if not redis_client.check_verify_limit(session_email):
        logger.warning(f"Verification limit exceeded for email: {session_email}")
        raise HTTPException(status_code=429, detail=get_text("too_many_verify", lang))
    
    stored_otp, country, birth_year, user_role = redis_client.get_auth_session(session_email)
    if not stored_otp:
        redis_client.increment_verify_count(session_email)
        logger.warning(f"OTP not found or expired for email: {session_email}")
        raise HTTPException(status_code=400, detail=get_text("otp_expired", lang))
    
    if stored_otp != request.otp:
        redis_client.increment_verify_count(session_email)
        logger.warning(f"Invalid OTP for email: {session_email}")
        raise HTTPException(status_code=400, detail=get_text("invalid_otp", lang))
    
    redis_client.delete_otp(session_email)
    response.delete_cookie("session_email")
    
    user = db.query(User).filter(User.email == session_email).first()
    if not user:
        logger.info(f"Creating new user for email: {session_email}")
        user = User(
            email=session_email,
            country=Country(country),
            birth_year=birth_year,
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.flush() # Get user ID without committing yet

        # Add user role if it was a signup (user_role will be present)
        if user_role:
            logger.info(f"Adding role {user_role} for user: {session_email}")
            role = UserRole(user_id=user.id, role=RoleType(user_role))
            db.add(role)
        
        db.commit()
        db.refresh(user)
    
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    logger.info(f"User verified and token generated for email: {session_email}")

    user_role = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    if not user_role:
        raise HTTPException(status_code=404, detail="User role not assigned.")
    
    tutor_id = None
    student_id = None

    if user_role.role == RoleType.tutor: 
        tutor_id = user.id
    else:
        student_id = user.id
    
    return {
        "response_code": "1",
        "detail": get_text("verify_success", lang),
        "data":{
            "tutor_id": tutor_id,
            "student_id": student_id,
            "access_token": token,
            "token_type":"Bearer token"
        }
    }
