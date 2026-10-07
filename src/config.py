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
CLEANING_PARAMS = PARAMS["cleaning"]
EXTRACTION_PARAMS = PARAMS["extraction"]
MLFLOW_PARAMS = PARAMS["mlflow"]
VALIDATION_PARAMS = PARAMS["validation"]
DVC_PARAMS = PARAMS["dvc"]
LOAD_PARAMS = PARAMS["load"]
MLFLOW_TRACKING_URI = MLFLOW_PARAMS["tracking_uri"]
MLFLOW_EXPERIMENTS = MLFLOW_PARAMS["experiments"]
VALIDATION_SOFT_NULL_RATE_LIMIT = VALIDATION_PARAMS["soft_null_rate_limit"]
VALIDATION_ROW_COUNT_TOLERANCE_PCT = VALIDATION_PARAMS["row_count_tolerance_pct"]
VALIDATION_UNUSUAL_CATEGORY_MIN_COUNT = VALIDATION_PARAMS["unusual_category_min_count"]
DVC_REMOTE_NAME = DVC_PARAMS["remote_name"]

DATABASE_URL = os.getenv("DATABASE_URL")
