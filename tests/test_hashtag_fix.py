import pytest
import json
from app.routes import _row_to_dict

def test_row_to_dict_hashtags_list():
    row = {"id": 1, "batch_id": "B1", "platform": "pinterest", "hashtags": ["#A", "#B"]}
    result = _row_to_dict(row)
    assert result["hashtags"] == ["#A", "#B"]
    assert result["hashtag_count"] == 2

def test_row_to_dict_hashtags_json_string():
    row = {"id": 1, "batch_id": "B1", "platform": "pinterest", "hashtags": '["#A", "#B"]'}
    result = _row_to_dict(row)
    assert result["hashtags"] == ["#A", "#B"]
    assert result["hashtag_count"] == 2

def test_row_to_dict_hashtags_none():
    row = {"id": 1, "batch_id": "B1", "platform": "pinterest", "hashtags": None}
    result = _row_to_dict(row)
    assert result["hashtags"] == []
    assert result["hashtag_count"] == 0

def test_row_to_dict_hashtags_missing():
    row = {"id": 1, "batch_id": "B1", "platform": "pinterest"}
    result = _row_to_dict(row)
    assert result["hashtags"] == []
    assert result["hashtag_count"] == 0
