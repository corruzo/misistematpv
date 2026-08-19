from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import DATABASE_URL

# Engine and session for SQL Server via pyodbc.
# Each request must get its own session; reusing a global scoped_session can leave
# the same pyodbc connection busy across concurrent refreshes and trigger the
# "Connection is busy with results for another command" error.
engine = create_engine(
    DATABASE_URL,
    fast_executemany=True,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
