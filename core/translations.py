from typing import Dict

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "user_exists": "User already exist. please login",
        "user_not_found": "User doesnt exist please signup",
        "too_many_otp": "Too many OTP requests.",
        "too_many_verify": "Too many verification attempts.",
        "invalid_email": "Email domain not eligible.",
        "invalid_age": "User must be 14-17 years old.",
        "otp_sent": "OTP sent successfully.",
        "otp_expired": "OTP expired or not found.",
        "invalid_otp": "Invalid OTP.",
        "verify_success": "Verification successful.",
        "session_expired": "Session expired or not found. Please try signing up or logging in again.",
        "profile_success": "Profile completed successfully.",
        "profile_update_success": "Profile updated successfully.",
        "profile_exists": "Profile already exists.",
        "profile_not_found": "Profile not found.",
        "profile_error": "Error saving profile: {error}",
        "internal_error": "Internal server error",
        "validation_error": "Validation error",
        "auth_failed": "Could not validate credentials",
        "token_expired": "Token has expired",
        "not_a_tutor": "Access denied. You are not a tutor.",
        "availability_saved": "Availability saved successfully"
    },
    "ko": {
        "user_exists": "이미 존재하는 사용자입니다. 로그인해 주세요.",
        "user_not_found": "존재하지 않는 사용자입니다. 회원가입해 주세요.",
        "too_many_otp": "OTP 요청이 너무 많습니다.",
        "too_many_verify": "인증 시도가 너무 많습니다.",
        "invalid_email": "사용할 수 없는 이메일 도메인입니다.",
        "invalid_age": "14세에서 17세 사이의 사용자만 가입 가능합니다.",
        "otp_sent": "OTP가 성공적으로 전송되었습니다.",
        "otp_expired": "OTP가 만료되었거나 찾을 수 없습니다.",
        "invalid_otp": "잘못된 OTP입니다.",
        "verify_success": "인증에 성공했습니다.",
        "session_expired": "세션이 만료되었거나 찾을 수 없습니다. 다시 회원가입 또는 로그인을 시도해 주세요.",
        "profile_success": "프로필 설정이 완료되었습니다.",
        "profile_update_success": "프로필이 성공적으로 업데이트되었습니다.",
        "profile_exists": "프로필이 이미 존재합니다.",
        "profile_not_found": "프로필을 찾을 수 없습니다.",
        "profile_error": "프로필 저장 중 오류 발생: {error}",
        "internal_error": "서버 내부 오류",
        "validation_error": "유효성 검사 오류",
        "auth_failed": "인증 정보를 확인할 수 없습니다.",
        "token_expired": "토큰이 만료되었습니다.",
        "not_a_tutor": "접근이 거부되었습니다. 튜터가 아닙니다."
    }
}

def get_text(key: str, lang: str = "en", **kwargs) -> str:
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text
