from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timezone
from pathlib import Path
import uuid

# Absolute path so DB location is always next to this file,
# regardless of where uvicorn is launched from.
_DB_PATH = Path(__file__).parent / "xolo.db"
DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=True)
    totp_secret = Column(String, nullable=True, default=None)
    totp_enabled = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)  # UUID set by beacon
    hostname = Column(String)
    ip_external = Column(String)
    ip_internal = Column(String)
    os_info = Column(String)
    username = Column(String)
    pid = Column(Integer)
    sleep_interval = Column(Integer, default=5)
    last_seen = Column(DateTime)
    active = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    note = Column(String, default="")
    cwd = Column(String, default="")
    tags = Column(String, default="")
    country = Column(String, default="")
    country_code = Column(String, default="")
    city = Column(String, default="")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    beacon_lang = Column(String, default="")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    command = Column(Text, nullable=False)
    output = Column(Text, default="")
    status = Column(String, default="pending")  # pending | running | done | error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor = Column(String, nullable=False)   # username
    action = Column(String, nullable=False)  # LOGIN, TASK_SENT, AGENT_DELETED, etc.
    detail = Column(Text, default="")        # JSON extra context
    ip = Column(String, default="")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BeaconKey(Base):
    __tablename__ = "beacon_keys"

    bid = Column(String, primary_key=True)          # UUID embedded in beacon
    enc_key = Column(String, nullable=False)         # hex encryption key (never in binary)
    fp_hash = Column(String, nullable=True)          # SHA-256(hostname+mac), locked on first use
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrate: add new columns if missing (safe on existing DBs)
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE agents ADD COLUMN cwd TEXT DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN tags TEXT DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN country TEXT DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN country_code TEXT DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN city TEXT DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN latitude REAL",
            "ALTER TABLE agents ADD COLUMN longitude REAL",
            "ALTER TABLE users ADD COLUMN totp_secret TEXT DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN totp_enabled INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN beacon_lang TEXT DEFAULT ''",
            # Grant admin to the first-created user named 'admin' on upgrade
            "UPDATE users SET is_admin = 1 WHERE username = 'admin' AND is_admin = 0",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass
