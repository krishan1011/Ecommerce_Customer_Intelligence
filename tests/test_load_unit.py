import pandas as pd

from src.load import aggregate_geolocation, dedupe_reviews, normalize_text, null_if_empty


def test_null_if_empty_and_location_normalization():
    assert null_if_empty(None) is None
    assert null_if_empty("") is None
    assert null_if_empty("  \t") is None
    assert null_if_empty(" value ") == "value"
    assert normalize_text("  São José  ") == "sao jose"


def test_geolocation_aggregation_means_modes_and_normalizes():
    source = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": ["00001", "00001", "00002"],
            "geolocation_lat": [1.0, 3.0, 5.0],
            "geolocation_lng": [10.0, 14.0, 20.0],
            "geolocation_city": ["São Paulo", "sao paulo", "Águas Lindas"],
            "geolocation_state": ["SP", "SP", "GO"],
        }
    )

    result = aggregate_geolocation(source).set_index("zip_prefix")

    assert result.loc[1, "lat"] == 2.0
    assert result.loc[1, "lng"] == 12.0
    assert result.loc[1, "city"] == "sao paulo"
    assert result.loc[1, "state"] == "sp"
    assert result.loc[2, "city"] == "aguas lindas"


def test_review_deduplication_keeps_latest_answer_per_order():
    source = pd.DataFrame(
        {
            "review_id": ["r1", "r1", "r1", "r2"],
            "order_id": ["o1", "o1", "o2", "o1"],
            "review_score": ["1", "5", "4", "3"],
            "review_answer_timestamp": [
                "2018-01-01 00:00:00",
                "2018-02-01 00:00:00",
                "2018-01-03 00:00:00",
                "",
            ],
            "review_creation_date": ["2018-01-01", "2018-02-01", "2018-01-03", "2018-01-04"],
            "review_comment_message": ["old", "latest", "other order", "unique"],
        }
    )

    result = dedupe_reviews(source)

    assert len(result) == 3
    assert result.loc[result["order_id"] == "o1", "review_score"].tolist() == ["5", "3"]
    assert "latest" in result["review_comment_message"].tolist()
