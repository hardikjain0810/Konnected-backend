from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.auth import router as auth_router
from api.profile import router as profile_router
from db.database import engine
from models.database_models import Base
from core.logging_config import logger
from core.translations import get_text

from core.utils import get_lang
from core.exceptions import APIException

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Konnected API",
    description="Peer-to-peer language tutoring marketplace for high school students",
    version="1.0.0"
)

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.error(f"API exception: {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"response_code": "0", "response_msg": exc.detail}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(f"HTTP exception: {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"response_code": "0", "response_msg": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    lang = get_lang(request)
    msg = get_text("validation_error", lang)
    logger.error(f"Validation error: {exc.errors()}", exc_info=True)
    return JSONResponse(
        status_code=422,
        content={"response_code": "0", "response_msg": msg}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    lang = get_lang(request)
    msg = get_text("internal_error", lang)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"response_code": "0", "response_msg": msg}
    )

# Include routers
app.include_router(auth_router)
app.include_router(profile_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Konnected API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
