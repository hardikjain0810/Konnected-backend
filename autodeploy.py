from fastapi import FastAPI,APIRouter


app = FastAPI(
    title="Konnected API",
    description="Peer-to-peer language tutoring marketplace for high school students",
    version="1.0.0"
)

router = APIRouter(prefix="/health", tags=["auth"])

@router.get("/health")
def health():
    return {"status": "superrrr"}