from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from .config import Config

# Create SQLAlchemy engine and session
engine = create_engine(Config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define data models
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Client {self.name}>"

class DataProcessingJob(Base):
    __tablename__ = "data_processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, index=True)
    data_size = Column(Float)  # Size in MB
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<DataProcessingJob {self.id} for client {self.client_id}>"

# Create all tables in the database
def init_db():
    Base.metadata.create_all(bind=engine)