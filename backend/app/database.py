"""
database.py
Sets up the SQLAlchemy engine, session factory, and declarative base.
Everything else (models.py, routers) imports from here.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite file lives inside backend/ so it's easy to find and delete/reset during dev
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'recovery_iq.db')}"

# check_same_thread=False is required for SQLite when used with FastAPI's
# multiple worker threads. Safe for a single-file dev/demo database.
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()