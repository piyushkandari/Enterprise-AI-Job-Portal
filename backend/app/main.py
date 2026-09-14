from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings

app = FastAPI(title="AI Job Board API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "jobboard-api"}