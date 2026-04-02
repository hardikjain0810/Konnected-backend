from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.auth import router as auth_router
from api.user_profile import router as profile_router
from api.tutor import router as tutor_router
from api.slot_booking import router as slot_booking
from api.get_tutor_topics import router as get_tutor_topics
from api.slot_cancel import router as cancel_and_reopen_slot
from db.database import engine
from models.database_models import Base
from core.logging_config import logger
from core.translations import get_text
import os
from core.utils import get_lang
from core.exceptions import init_exception_handlers

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Konnected API",
    description="Peer-to-peer language tutoring marketplace for high school students",
    version="1.0.0"
)

init_exception_handlers(app)

# Include routers
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(tutor_router)
app.include_router(slot_booking)
app.include_router(get_tutor_topics)
app.include_router(cancel_and_reopen_slot)

@app.get("/")
async def root():
    return {"message": "Welcome to Konnected API"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
