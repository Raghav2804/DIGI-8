"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CAREERPULSE_DATA_DIR", BASE_DIR / "dataset"))
DATABASE_PATH = Path(os.getenv("CAREERPULSE_DATABASE", BASE_DIR / "database" / "careerpulse.sqlite3"))
SECRET_KEY = os.getenv("CAREERPULSE_SECRET_KEY", "change-this-before-deployment")
MAX_CONTENT_LENGTH = 64 * 1024 * 1024
APP_VERSION = "1.0.0"
