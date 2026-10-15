import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend directory if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

import re

db_path = (BASE_DIR / "resq_os.db").as_posix()
raw_db_url = os.getenv("DATABASE_URL", "").strip()
if not raw_db_url or raw_db_url == "sqlite:///./resq_os.db":
    DATABASE_URL = f"sqlite:///{db_path}"
else:
    DATABASE_URL = raw_db_url
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "RESQ_OS").strip()
MONGODB_INCIDENTS_COLLECTION = "incidents"


def sanitize_uri(uri: str) -> str:
    """Mask credentials in connection URI to prevent secrets leaking in logs or API responses."""
    if not uri:
        return ""
    # Mask password in mongodb://<user>:<pass>@<host> or mongodb+srv://<user>:<pass>@<host>
    return re.sub(r'(mongodb(?:\+srv)?://[^:]+:)([^@]+)(@)', r'\1*****\3', uri)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
