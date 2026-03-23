from fastapi import FastAPI


app = FastAPI(
    title="Konnected API",
    description="Peer-to-peer language tutoring marketplace for high school students",
    version="1.0.0"
)

@app.get("/health")
def health():
    return {"status": "ok"}