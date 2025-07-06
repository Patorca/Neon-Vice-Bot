import os
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class FiveMMonitor(Base):
    __tablename__ = 'fivem_monitors'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ServerConfig(Base):
    __tablename__ = 'server_configs'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    config_data = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
else:
    engine = None
    SessionLocal = None

def get_db():
    """Get database session"""
    if SessionLocal:
        db = SessionLocal()
        try:
            return db
        except Exception:
            db.close()
            raise
    return None