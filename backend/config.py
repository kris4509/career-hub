import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if database_url:
    database_url = database_url.strip().strip('"').strip("'")
    # Force the psycopg2 driver whatever prefix the provider gave
    for prefix in ("postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            database_url = "postgresql+psycopg2://" + database_url[len(prefix):]
            break


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Checks that a connection is alive before using it (helps with Supabase pooler)
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}