from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import *
from app.scripts import seed_demo

DEMO_DATABASE_PATH = Path("parishconnect_demo.db")
DEMO_DATABASE_URL = f"sqlite:///{DEMO_DATABASE_PATH.as_posix()}"


def main() -> None:
    engine = create_engine(DEMO_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    demo_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    seed_demo.SessionLocal = demo_session_factory
    result = seed_demo.seed_demo_data()

    print(f"Demo SQLite database ready: {DEMO_DATABASE_PATH.resolve()}")
    print(f"Seed result: {result}")


if __name__ == "__main__":
    main()

