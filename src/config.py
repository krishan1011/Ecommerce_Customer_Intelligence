import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
SQL_DIR = ROOT / "sql"
DOCS_DIR = ROOT / "docs"

PARAMS = yaml.safe_load((ROOT / "params.yaml").read_text())

RANDOM_STATE = PARAMS["common"]["random_state"]
ANALYSIS_START = PARAMS["common"]["analysis_start"]
ANALYSIS_END = PARAMS["common"]["analysis_end"]
VALID_STATUSES = PARAMS["common"]["valid_statuses"]

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://ecom:change_me@localhost:5432/ecommerce"
)
