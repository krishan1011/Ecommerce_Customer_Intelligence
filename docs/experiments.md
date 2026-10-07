# MLflow experiments

Start the local UI with make mlflow-ui, or run
mlflow ui --backend-store-uri sqlite:///mlflow.db from the project root.

Configured experiments: churn, segments, clv, forecast, delay, recsys, nlp, dl.

Export a CSV summary of runs, parameters, metrics, and tags with
python -m src.tracking export. The file is written to
docs/experiments_summary.csv.
