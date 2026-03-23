from fastapi import HTTPException

class APIException(HTTPException):
    def __init__(self, status_code: int, response_msg: str):
        super().__init__(status_code=status_code, detail=response_msg)
