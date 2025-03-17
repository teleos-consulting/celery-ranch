# Import only what's needed
import random

from flask import jsonify, render_template, request

from . import app
from .models import Client, DataProcessingJob, SessionLocal, init_db
from .tasks import generate_random_jobs, process_client_data


# Initialize database on startup
@app.before_first_request
def setup():
    init_db()
    # Create some example clients if they don't exist
    db = SessionLocal()
    if db.query(Client).count() == 0:
        clients = [
            Client(name="Client A", email="clienta@example.com"),
            Client(name="Client B", email="clientb@example.com"),
            Client(name="Client C", email="clientc@example.com"),
            Client(name="Client D", email="clientd@example.com"),
            Client(name="Client E", email="cliente@example.com"),
        ]
        db.add_all(clients)
        db.commit()
    db.close()


# Get a database session
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


# Home page
@app.route("/")
def index():
    db = get_db()
    clients = db.query(Client).all()
    jobs = (
        db.query(DataProcessingJob)
        .order_by(DataProcessingJob.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("index.html", clients=clients, jobs=jobs)


# API: Client list
@app.route("/api/clients")
def list_clients():
    db = get_db()
    clients = db.query(Client).all()
    return jsonify(
        [
            {"id": client.id, "name": client.name, "email": client.email}
            for client in clients
        ]
    )


# API: Job list
@app.route("/api/jobs")
def list_jobs():
    db = get_db()
    jobs = (
        db.query(DataProcessingJob).order_by(DataProcessingJob.created_at.desc()).all()
    )
    return jsonify(
        [
            {
                "id": job.id,
                "client_id": job.client_id,
                "data_size": job.data_size,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
            }
            for job in jobs
        ]
    )


# API: Create a new job
@app.route("/api/jobs", methods=["POST"])
def create_job():
    data = request.json
    client_id = data.get("client_id")
    data_size = data.get("data_size", random.uniform(1, 10))

    if not client_id:
        return jsonify({"error": "client_id is required"}), 400

    db = get_db()

    # Check if client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404

    # Create a new job
    new_job = DataProcessingJob(
        client_id=client_id, data_size=data_size, status="pending"
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Schedule the task with LRU prioritization
    process_client_data.lru_delay(
        str(client_id), client_id, new_job.id, data_size  # LRU key is the client ID
    )

    return jsonify(
        {
            "id": new_job.id,
            "client_id": client_id,
            "data_size": data_size,
            "status": "pending",
            "created_at": new_job.created_at.isoformat(),
        }
    )


# API: Generate random jobs
@app.route("/api/generate-jobs", methods=["POST"])
def api_generate_jobs():
    data = request.json
    num_jobs = data.get("num_jobs", 5)

    task = generate_random_jobs.delay(num_jobs=num_jobs)

    return jsonify(
        {"task_id": task.id, "status": "Jobs generation started", "num_jobs": num_jobs}
    )
