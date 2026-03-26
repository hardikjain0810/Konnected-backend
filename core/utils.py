import random
import string
from datetime import datetime
from models.database_models import Country
from fastapi import Request

BLOCKED_KR_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", 
    "icloud.com", "proton.me", "naver.com", "daum.net", "kakao.com"
]

def get_lang(request: Request) -> str:
    lang = request.headers.get("Accept-Language", "en")
    return "ko" if "ko" in lang.lower() else "en"

def generate_otp(length: int = 6) -> str:
    return "123456"
    #return ''.join(random.choices(string.digits, k=length))

def validate_email_eligibility(email: str, country: Country) -> bool:
    domain = email.split('@')[-1].lower()
    
    if country == Country.US:
        return domain.endswith('.edu')
    elif country == Country.KR:
        return domain not in BLOCKED_KR_DOMAINS
    return False

def check_age_eligibility(birth_year: int) -> bool:
    current_year = datetime.now().year
    age = current_year - birth_year
    return 14 <= age <= 17

def success_response(message: str, data=None):
    return {
        "response_code": "1",
        "detail": message,
        "data": data
    }

def error_response(message: str):
    return {
        "response_code": "0",
        "detail": message
    }

