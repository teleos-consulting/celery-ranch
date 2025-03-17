import os


class Config:
    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Database
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql://ranch_user:ranch_password@localhost:5432/ranch_db"
    )

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-for-development-only")
