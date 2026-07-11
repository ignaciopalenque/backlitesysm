import os
from datetime import timedelta

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///litesysm.db'
    JSON_SORT_KEYS = False
    METRICS_RETENTION_DAYS = 30
    COLLECTION_INTERVAL = 5  # segundos