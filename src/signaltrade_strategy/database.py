from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from signaltrade_strategy.config import settings

options = ({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
           if settings.database_url.startswith("sqlite") else {})
engine = create_engine(settings.database_url, **options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

