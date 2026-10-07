from sqlalchemy.exc import OperationalError

from src import load


class _FakeEngine:
    def __init__(self):
        self.dispose_calls = 0

    def dispose(self):
        self.dispose_calls += 1


def test_load_retries_connection_shutdown_and_disposes_pool(tmp_path, monkeypatch):
    for filename in load.RAW_FILES.values():
        (tmp_path / filename).touch()
    engine = _FakeEngine()
    attempts = []
    sleeps = []

    def transient_then_success(*_args):
        attempts.append(1)
        if len(attempts) == 1:
            raise OperationalError("COPY", {}, Exception("SSL error: unexpected eof while reading"))
        return {"core_rows": {"orders": 1}, "sql": {}, "pandas": {}}

    monkeypatch.setattr(load, "DATA_RAW", tmp_path)
    monkeypatch.setattr(load, "get_engine", lambda: engine)
    monkeypatch.setattr(load, "count_csv_rows", lambda *_args: 1)
    monkeypatch.setattr(load, "_load_attempt", transient_then_success)
    monkeypatch.setattr(load, "sanity_report", lambda: {})
    monkeypatch.setattr(load.time, "sleep", sleeps.append)
    monkeypatch.setattr(load, "LOAD_PARAMS", {"retry_attempts": 3, "retry_backoff_seconds": 1})

    result = load.load_data()

    assert result["core_rows"] == {"orders": 1}
    assert len(attempts) == 2
    assert engine.dispose_calls == 1
    assert sleeps == [1]
