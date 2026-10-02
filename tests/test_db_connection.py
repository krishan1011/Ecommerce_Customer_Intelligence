import pytest

from src.db import check_connection


@pytest.mark.db
def test_postgres_connection():
    assert check_connection()
