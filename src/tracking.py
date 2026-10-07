"""MLflow tracking helpers configured from params.yaml."""

import argparse
import hashlib
import json
import math
import numbers
import subprocess
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from .config import (
    DOCS_DIR,
    MLFLOW_EXPERIMENTS,
    MLFLOW_TRACKING_URI,
    PARAMS,
    ROOT,
)

PROJECT_ROOT = ROOT


def _git_tags(root: Path) -> tuple[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
        return commit or "nogit", str(dirty).lower()
    except (OSError, subprocess.CalledProcessError):
        return "nogit", "false"


def _data_hash(root: Path) -> str:
    lock_path = root / "dvc.lock"
    if not lock_path.is_file():
        return "nodvc"
    return hashlib.md5(lock_path.read_bytes()).hexdigest()[:8]


def _data_version(root: Path) -> str:
    manifest_path = root / "data" / "processed" / "manifest.json"
    if not manifest_path.is_file():
        return "nodata"
    try:
        return str(json.loads(manifest_path.read_text(encoding="utf-8"))["data_version"])
    except (OSError, KeyError, json.JSONDecodeError):
        return "nodata"


def _default_tags(root: Path | None = None) -> dict[str, str]:
    root = root or PROJECT_ROOT
    commit, dirty = _git_tags(root)
    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "data_hash": _data_hash(root),
        "data_version": _data_version(root),
        "seed": str(PARAMS["common"]["random_state"]),
        "snapshots": json.dumps(PARAMS["features"]["snapshots"], separators=(",", ":")),
        "horizon_days": str(PARAMS["features"]["horizon_days"]),
    }


def start_run(experiment: str, run_name: str, extra_tags: dict | None = None):
    """Set the configured experiment, start a run, and attach reproducibility tags."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment)
    tags = _default_tags()
    if extra_tags:
        tags.update({str(key): str(value) for key, value in extra_tags.items()})
    return mlflow.start_run(run_name=run_name, tags=tags)


def _flatten_params(values: dict, prefix: str = "") -> dict[str, str]:
    flattened = {}
    for key, value in values.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_params(value, full_key))
        elif isinstance(value, (list, tuple)):
            flattened[full_key] = json.dumps(value, separators=(",", ":"))
        else:
            flattened[full_key] = str(value)
    return flattened


def log_params_flat(values: dict) -> None:
    """Flatten nested parameters and log values as MLflow-compatible strings."""
    flattened = _flatten_params(values)
    if flattened:
        mlflow.log_params(flattened)


def log_metrics_safe(values: dict) -> None:
    """Log finite numeric metrics and ignore nonnumeric or non-finite values."""
    safe = {
        str(key): float(value)
        for key, value in values.items()
        if isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    }
    if safe:
        mlflow.log_metrics(safe)


def log_artifact_if_exists(path: str | Path) -> bool:
    """Log a file or directory if it exists; return whether anything was logged."""
    artifact = Path(path)
    if not artifact.exists():
        return False
    if artifact.is_dir():
        mlflow.log_artifacts(str(artifact))
    else:
        mlflow.log_artifact(str(artifact))
    return True


def register_model(run_id: str, artifact_path: str, name: str, alias: str = "challenger"):
    """Register a run artifact and set its requested model-registry alias."""
    model_version = mlflow.register_model(f"runs:/{run_id}/{artifact_path}", name)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    client.set_registered_model_alias(name, alias, model_version.version)
    return model_version


def promote_to_champion(name: str, version: str | int) -> None:
    """Move the champion alias to a registered model version."""
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    client.set_registered_model_alias(name, "champion", str(version))


def init_experiments() -> list[str]:
    """Create configured experiments, leaving existing ones unchanged."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    for experiment in MLFLOW_EXPERIMENTS:
        mlflow.set_experiment(experiment)
        print(f"MLflow experiment ready: {experiment}")
    return list(MLFLOW_EXPERIMENTS)


def export_runs(output_path: Path | None = None) -> Path:
    """Export all active experiment runs with params, metrics, and tags to CSV."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    experiments = client.search_experiments()
    rows = []
    for experiment in experiments:
        runs = client.search_runs([experiment.experiment_id], max_results=100_000)
        for run in runs:
            row = {
                "experiment": experiment.name,
                "run_id": run.info.run_id,
                "run_name": run.data.tags.get("mlflow.runName", ""),
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
            }
            row.update({f"param_{key}": value for key, value in run.data.params.items()})
            row.update({f"metric_{key}": value for key, value in run.data.metrics.items()})
            row.update({f"tag_{key}": value for key, value in run.data.tags.items()})
            rows.append(row)
    target = Path(output_path) if output_path else DOCS_DIR / "experiments_summary.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(target, index=False)
    print(f"Exported {len(rows):,} runs to {target}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="MLflow experiment utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="create the configured MLflow experiments")
    subparsers.add_parser("export", help="export experiments and runs to CSV")
    args = parser.parse_args()
    if args.command == "init":
        init_experiments()
    elif args.command == "export":
        export_runs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
