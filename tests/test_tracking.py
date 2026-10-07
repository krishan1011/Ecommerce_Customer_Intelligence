import numpy as np
import pytest

mlflow = pytest.importorskip("mlflow")


def _temporary_uri(tmp_path):
    return f"sqlite:///{(tmp_path / 'tracking.db').as_posix()}"


def test_start_run_attaches_reproducibility_tags_and_fallbacks(tmp_path, monkeypatch):
    from src import tracking

    uri = _temporary_uri(tmp_path)
    monkeypatch.setattr(tracking, "MLFLOW_TRACKING_URI", uri)
    monkeypatch.setattr(tracking, "PROJECT_ROOT", tmp_path)

    with tracking.start_run("tracking-tests", "tag-fallbacks") as run:
        tracking.log_params_flat({"features": {"horizon": 30}, "labels": ["repeat", "single"]})
        tracking.log_metrics_safe({"auc": 0.75, "bad": float("nan"), "note": "ignored"})
        run_id = run.info.run_id

    client = mlflow.tracking.MlflowClient(tracking_uri=uri)
    tags = client.get_run(run_id).data.tags
    assert tags["git_commit"] == "nogit"
    assert tags["git_dirty"] == "false"
    assert tags["data_hash"] == "nodvc"
    assert tags["data_version"] == "nodata"
    assert tags["seed"] == str(tracking.PARAMS["common"]["random_state"])
    assert tags["snapshots"]
    assert tags["horizon_days"] == str(tracking.PARAMS["features"]["horizon_days"])
    assert client.get_run(run_id).data.params["features.horizon"] == "30"
    assert "bad" not in client.get_run(run_id).data.metrics


def test_registered_model_champion_alias_loads_and_predicts(tmp_path, monkeypatch):
    from sklearn.dummy import DummyClassifier

    from src import tracking

    uri = _temporary_uri(tmp_path)
    monkeypatch.setattr(tracking, "MLFLOW_TRACKING_URI", uri)
    monkeypatch.setattr(tracking, "PROJECT_ROOT", tmp_path)
    mlflow.set_tracking_uri(uri)

    model = DummyClassifier(strategy="most_frequent")
    features = np.array([[0.0], [1.0], [2.0], [3.0]])
    labels = np.array([0, 0, 1, 1])
    model.fit(features, labels)
    with tracking.start_run("model-registry-tests", "dummy-classifier") as run:
        mlflow.sklearn.log_model(model, artifact_path="tiny_model")
        run_id = run.info.run_id

    tracking.register_model(run_id, "tiny_model", "smoke_model", alias="champion")
    loaded = mlflow.sklearn.load_model("models:/smoke_model@champion")
    prediction = loaded.predict(np.array([[0.5], [2.5]]))
    assert prediction.shape == (2,)
