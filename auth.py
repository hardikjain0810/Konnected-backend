from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from database_models import User
import jwt
from typing import Optional
from config import settings
from translations import get_text

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

from exceptions import APIException

def get_lang(request: Request) -> str:
    lang = request.headers.get("Accept-Language", "en")
    return "ko" if "ko" in lang.lower() else "en"

def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    lang = get_lang(request)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                response_msg=get_text("auth_failed", lang),
            )
    except jwt.ExpiredSignatureError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_msg=get_text("token_expired", lang),
        )
    except jwt.InvalidTokenError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            response_msg=get_text("auth_failed", lang),
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND, 
            response_msg=get_text("user_not_found", lang)
        )
    return user
