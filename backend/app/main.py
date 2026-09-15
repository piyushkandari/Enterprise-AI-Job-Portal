from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .routers import auth as auth_router
from .routers import jobs as jobs_router
from .routers import resumes as resumes_router
from .routers import matches as matches_router
from .routers import interests as interests_router

app = FastAPI(title="AI Job Board API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(jobs_router.router)
app.include_router(resumes_router.router)
app.include_router(matches_router.router)
app.include_router(interests_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "jobboard-api"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}