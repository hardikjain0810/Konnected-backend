from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from core.logging_config import get_logger

logger = get_logger()

def init_exception_handlers(app):

    # HTTP errors (like 404, 401, etc.)
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        logger.warning(f"{exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content={"response_code": "0", "detail": exc.detail}
        )

    # All other unexpected errors
    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        logger.error(f"{str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={"response_code": "0", "detail": "Internal server error"}
        )