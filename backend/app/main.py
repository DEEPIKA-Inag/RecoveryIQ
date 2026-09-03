"""
main.py
FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000
(from inside the backend/ folder, with the venv activated)
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401  (import so tables are registered on Base)
from .routers import transactions, analyze, decisions, dashboard, simulate, allocate, model_quality
app = FastAPI(
    title="Recovery IQ",
    description="Economic decision engine for payment recovery",
    version="0.1.0",
)

# Allow the React dev server (Vite default port 5173) to call this API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://recovery-iq-xi.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    


@app.on_event("startup")
def on_startup():
    # Creates all tables defined in models.py if they don't exist yet.
    # Safe to call every time -- it's a no-op for tables that already exist.
    Base.metadata.create_all(bind=engine)


app.include_router(transactions.router)
app.include_router(analyze.router)
app.include_router(decisions.router)
app.include_router(dashboard.router)
app.include_router(simulate.router)
app.include_router(allocate.router)
app.include_router(model_quality.router)
@app.get("/")
def root():
    return {"status": "ok", "service": "Recovery IQ backend"}


@app.get("/health")
def health():
    return {"status": "healthy"}