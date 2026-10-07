# DVC data setup

The project tracks the Olist source CSVs and generated parquet artifacts with
DVC. Data contents stay out of Git. This workstation uses the local default
remote named storage at ../dvc-storage; that directory is outside the repository.

## Restore on a clean machine

1. Clone the Git repository and install the project dependencies.
2. Provision a shared DVC remote, or copy the existing dvc-storage directory
   beside the cloned repository. The configured local remote is not available
   automatically on another machine.
3. If using a different remote, update its URL locally with
   dvc remote modify storage url <remote-url>.
4. Run dvc pull to restore data/raw and the tracked processed artifacts.
5. Configure DATABASE_URL locally only if database-backed extraction is
   needed. Never commit credentials.

## Pipeline

- dvc repro extract manually refreshes parquet data from the configured Neon
  analytics views. It requires a working database connection; it is not
  automatically forced when its inputs and outputs are unchanged.
- dvc repro clean rebuilds the clean parquet tables.
- dvc repro validate writes metrics/validation.json and
  docs/validation_report.md.
- dvc status reports changed inputs and outputs; dvc dag displays stage
  dependencies.

Use dvc push after adding or refreshing tracked data so another machine can
restore the DVC cache from the configured remote.
