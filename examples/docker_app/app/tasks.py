import time
import datetime
import random
from celery import Celery
from ranch import lru_task
from ranch.utils.persistence import RedisStorage
from ranch.utils.prioritize import configure
import redis
from sqlalchemy.orm import Session
from .models import SessionLocal, DataProcessingJob
from .config import Config

# Create Celery application
app = Celery(
    'tasks',
    broker=Config.CELERY_BROKER_URL,
    result_backend=Config.CELERY_RESULT_BACKEND
)

# Configure Ranch with Redis for LRU prioritization
redis_client = redis.from_url(Config.REDIS_URL)
redis_storage = RedisStorage(redis_client, prefix="ranch_demo:")
configure(app=app, storage=redis_storage)

# Get a database session
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

@lru_task(app)
def process_client_data(client_id, job_id, data_size):
    """
    Process data for a client with LRU prioritization.
    
    This simulates a CPU-intensive task that processes data.
    The client_id is used as the LRU key to ensure fair scheduling.
    """
    db = get_db()
    
    # Update job status to processing
    job = db.query(DataProcessingJob).filter(DataProcessingJob.id == job_id).first()
    if job:
        job.status = "processing"
        db.commit()
    
    # Simulate processing time based on data size
    processing_time = data_size * random.uniform(0.5, 1.5)
    print(f"Processing {data_size}MB of data for client {client_id} (job {job_id})")
    print(f"Estimated processing time: {processing_time:.2f} seconds")
    
    # Simulate work with sleep
    time.sleep(processing_time)
    
    # Update job status to completed
    if job:
        job.status = "completed"
        job.completed_at = datetime.datetime.utcnow()
        db.commit()
    
    return {
        "client_id": client_id,
        "job_id": job_id,
        "data_size": data_size,
        "processing_time": processing_time,
        "status": "completed"
    }

@app.task
def generate_random_jobs(num_jobs=5, clients_range=(1, 5)):
    """
    Generate random jobs for testing.
    """
    db = get_db()
    jobs_created = []
    
    for _ in range(num_jobs):
        # Randomly select a client ID
        client_id = random.randint(clients_range[0], clients_range[1])
        
        # Generate random data size between 1 and 10 MB
        data_size = random.uniform(1, 10)
        
        # Create a new job in the database
        new_job = DataProcessingJob(
            client_id=client_id,
            data_size=data_size,
            status="pending"
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        
        # Schedule the processing task with LRU prioritization
        process_client_data.lru_delay(
            str(client_id),  # LRU key is the client ID
            client_id,
            new_job.id,
            data_size
        )
        
        jobs_created.append({
            "job_id": new_job.id,
            "client_id": client_id,
            "data_size": data_size
        })
    
    return jobs_created