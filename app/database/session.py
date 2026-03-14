from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

#create_engine → builds the database engine

#sessionmaker → creates a session factory

#Session → type hint for database sessions

#settings → gives you settings.DATABASE_URL from your config file

engine = create_engine(settings.DATABASE_URL)

#This does not create a session immediately.
#It creates a factory that can later produce sessions like this:
#db = SessionLocal()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db : Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()